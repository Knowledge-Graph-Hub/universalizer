"""Node cleaning and normalization functions."""

import os
import tarfile

def clean_and_normalize_graph(filepath, compressed) -> bool:
    """
    Replace or remove node IDs or nodes as needed.
    Also replaces biolink:OntologyClass node types
    with biolink:NamedThing.
    :param filepath: str, name or path of KGX graph files
    :param compressed: bool, True if filepath is tar.gz compressed
    :return: bool, True if successful
    """

    success = True
    mapping = True

    graph_file_paths = []

    if compressed:
        # Decompress graph
        with tarfile.open(filepath) as intar:
            graph_files = intar.getnames()
            for graph_file in graph_files:
                intar.extract(graph_file, path=os.path.dirname(filepath))
                graph_file_paths.append(os.path.join(os.path.dirname(filepath), graph_file))
        os.remove(filepath)
    else:
        for filename in os.listdir(filepath):
            if filename.endswith(".tsv"):
                graph_file_paths.append(os.path.join(filepath,filename))
    
    if len(graph_file_paths) > 2:
        raise RuntimeError("Found more than the expected number of graph files.")
    elif len(graph_file_paths) == 0:
        raise RuntimeError("Found no graph files!")
    elif len(graph_file_paths) == 2:
        print(f"Found these graph files:{graph_file_paths}")

    # Remap node IDs
    # First, identify node and edge lists

    for filepath in graph_file_paths:
        if filepath.endswith("nodes.tsv"):
            nodepath = filepath
            outnodepath = nodepath + ".tmp"
        if filepath.endswith("edges.tsv"):
            edgepath = filepath
            outedgepath = edgepath + ".tmp"

    # Now load the update_id_map file
    id_map_path = os.path.join(os.path.dirname(filename), "update_id_maps.tsv")
    if not os.path.exists(id_map_path):
        print("Can't find ID remapping file. This may not be a problem.")
        mapping = False
    else:
        remap_these_nodes = {}
        with open(id_map_path) as map_file:
            map_file.readline()
            for line in map_file:
                splitline = line.rstrip().split("\t")
                cap_prefix = (
                    ((splitline[0].split(":"))[0].upper())
                    + ":"
                    + (splitline[0].split(":"))[1]
                )
                remap_these_nodes[splitline[0]] = splitline[1]
                remap_these_nodes[cap_prefix] = splitline[1]

    # Continue with mapping if everything's OK so far
    # Sometimes prefixes get capitalized, so we check for that too
    try:
        mapcount = 0
        with open(nodepath, "r") as innodefile, open(edgepath, "r") as inedgefile:
            with open(outnodepath, "w") as outnodefile, open(
                outedgepath, "w"
            ) as outedgefile:
                outnodefile.write(innodefile.readline())
                outedgefile.write(inedgefile.readline())
                for line in innodefile:
                    line_split = (line.rstrip()).split("\t")
                    if mapping:
                        # Check for nodes to be remapped
                        if line_split[0] in remap_these_nodes:
                            new_node_id = remap_these_nodes[line_split[0]]
                            line_split[0] = new_node_id
                            mapcount = mapcount + 1
                            line = "\t".join(line_split) + "\n"
                    if line_split[1] == "biolink:OntologyClass":
                        line_split[1] = "biolink:NamedThing"
                        line = "\t".join(line_split) + "\n"
                    outnodefile.write(line)
                for line in inedgefile:
                    line_split = (line.rstrip()).split("\t")
                    if mapping:
                        # Check for edges containing nodes to be remapped
                        for col in [1, 3]:
                            if line_split[col] in remap_these_nodes:
                                new_node_id = remap_these_nodes[line_split[col]]
                                line_split[col] = new_node_id
                                mapcount = mapcount + 1
                                line = "\t".join(line_split) + "\n"
                    outedgefile.write(line)

        os.replace(outnodepath, nodepath)
        os.replace(outedgepath, edgepath)

        if mapping and mapcount > 0:
            print(f"Remapped {mapcount} node IDs.")
        elif mapping and mapcount == 0:
            print("Failed to remap node IDs - could not find corresponding nodes.")
        
        success = True

    except (IOError, KeyError) as e:
        print(f"Failed to remap node IDs for {nodepath} and/or {edgepath}: {e}")
        success = False

    return success