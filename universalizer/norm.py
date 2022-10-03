"""Node cleaning and normalization functions."""

import os
import tarfile
from typing import Dict

from curies import Converter  # type: ignore
from prefixmaps.io.parser import load_multi_context  # type: ignore
from sssom.parsers import parse_sssom_table  # type: ignore
from sssom.util import MappingSetDataFrame  # type: ignore


def clean_and_normalize_graph(filepath, compressed, maps) -> bool:
    """
    Replace or remove node IDs or nodes as needed.

    Also replaces biolink:OntologyClass node types
    with biolink:NamedThing.
    :param filepath: str, name or path of KGX graph files
    :param compressed: bool, True if filepath is tar.gz compressed
    :param maps: list of str filepaths to SSSOM maps
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
                graph_file_paths.append(
                    os.path.join(os.path.dirname(filepath), graph_file)
                )
        os.remove(filepath)
    else:
        for filename in os.listdir(filepath):
            if filename.endswith(".tsv"):
                graph_file_paths.append(os.path.join(filepath, filename))

    if len(graph_file_paths) > 2:
        raise RuntimeError("Found more than two graph files.")
    elif len(graph_file_paths) == 0:
        raise RuntimeError("Found no graph files!")
    elif len(graph_file_paths) == 2:
        print(f"Found these graph files:{graph_file_paths}")

    # Load SSSOM maps if provided.
    # Merge them together.
    using_sssom = False

    if len(maps) > 0:
        using_sssom = True
        print(f"Found these map files:{maps}")
        remaps, recats = load_sssom_maps(maps)
        print(recats)

    # Remap node IDs
    # First, identify node and edge lists

    for filepath in graph_file_paths:
        if filepath.endswith("nodes.tsv"):
            nodepath = filepath
            outnodepath = nodepath + ".tmp"
        if filepath.endswith("edges.tsv"):
            edgepath = filepath
            outedgepath = edgepath + ".tmp"

    # Now create the set of mappings to perform

    remap_these_nodes = make_id_maps(nodepath, os.path.dirname(nodepath))

    # Continue with mapping if everything's OK so far
    # Sometimes prefixes get capitalized, so we check for that too
    try:
        mapcount = 0
        with open(nodepath, "r") as innodefile, \
                open(edgepath, "r") as inedgefile:
            with open(outnodepath, "w") as outnodefile, open(
                outedgepath, "w"
            ) as outedgefile:
                outnodefile.write(innodefile.readline())
                outedgefile.write(inedgefile.readline())
                for line in innodefile:
                    changed_this_line = False
                    line_split = (line.rstrip()).split("\t")
                    if mapping:
                        # Check for nodes to be remapped
                        if line_split[0] in remap_these_nodes:
                            new_node_id = remap_these_nodes[line_split[0]]
                            line_split[0] = new_node_id
                            changed_this_line = True
                            line = "\t".join(line_split) + "\n"
                        if using_sssom:
                            if line_split[0] in recats:
                                line_split[1] = recats[line_split[0]]
                                changed_this_line = True
                            if line_split[0] in remaps:
                                line_split[0] = remaps[line_split[0]]
                                changed_this_line = True
                            line = "\t".join(line_split) + "\n"
                    if line_split[1] == "biolink:OntologyClass":
                        line_split[1] = "biolink:NamedThing"
                        line = "\t".join(line_split) + "\n"
                    if changed_this_line:
                        mapcount = mapcount + 1
                    outnodefile.write(line)
                for line in inedgefile:
                    line_split = (line.rstrip()).split("\t")
                    if mapping:
                        # Check for edges containing nodes to be remapped
                        for col in [1, 3]:
                            if line_split[col] in remap_these_nodes:
                                new_node_id = \
                                    remap_these_nodes[line_split[col]]
                                line_split[col] = new_node_id
                                line = "\t".join(line_split) + "\n"
                            if using_sssom:
                                if line_split[col] in remaps:
                                    new_node_id = \
                                        remaps[line_split[col]]
                                    line_split[col] = new_node_id
                                    line = "\t".join(line_split) + "\n"
                    outedgefile.write(line)

        os.replace(outnodepath, nodepath)
        os.replace(outedgepath, edgepath)

        if mapcount > 0:
            print(f"Remapped {mapcount} node IDs.")
        elif mapcount == 0:
            print("Could not remap any node IDs.")

        success = True

    except (IOError, KeyError) as e:
        print(f"Failed to remap node IDs: {e}")
        success = False

    return success


def make_id_maps(input_nodes: str, output_dir: str) -> dict:
    """
    Retrieve all entity identifiers for a single graph.

    Report all identifiers of expected and unexpected format,
    and find more appropriate prefixes if possible.
    Does not rewrite IRIs.
    :param input_nodes: Path to input nodefile
    :param output_dir: string of directory, location of unexpected id
    and update map file to be created
    :return: dict, map of original node IDs to new node IDs
    """
    id_list = []
    mal_id_list = []
    update_ids: Dict[str, str] = {}

    # TODO: provide more configuration re: curie contexts
    # TODO: expand reverse contexts beyond bijective maps
    # TODO: add more capitalization variants

    curie_contexts = load_multi_context(["obo", "bioregistry.upper"])
    all_contexts = curie_contexts.as_dict()
    all_contexts = {key: val for key, val in all_contexts.items()}
    curie_converter = Converter.from_prefix_map(all_contexts)

    all_reverse_contexts = {val: key for key, val in all_contexts.items()}
    all_reverse_contexts_lc = {val.lower(): key for key, val
                               in all_contexts.items()}
    all_reverse_contexts.update(all_reverse_contexts_lc)
    iri_converter = Converter.from_reverse_prefix_map(all_reverse_contexts)

    print(f"Retrieving entity names in {input_nodes}...")

    mal_id_file_name = os.path.join(output_dir, "unexpected_ids.tsv")
    update_mapfile_name = os.path.join(output_dir, "update_id_maps.tsv")

    with open(input_nodes, "r") as nodefile:
        nodefile.readline()
        for line in nodefile:
            id_list.append((line.rstrip().split("\t"))[0])

    # For each id, assume it is a CURIE and try to convert to IRI.
    # If that doesn't work, it might be an IRI - try to
    # convert it to a CURIE. If that works, we need to update it.
    # Also checks if IDs with OBO prefixes should be something else.
    try:
        for identifier in id_list:
            # See if there's an OBO prefix
            if (identifier.split(":"))[0].upper() == "OBO":
                mal_id_list.append(identifier)
                new_id = ((identifier[4:]).replace("_", ":")).upper()
                # and check to see if this is referencing an owl file
                # if so, try to remove
                if ".OWL" in new_id:
                    split_new_id = new_id.split(".OWL")
                    new_id = split_new_id[1]
                # May still have a char left over. Remove.
                if new_id[0] in ["/", "#"]:
                    new_id = new_id[1:]
                update_ids[identifier] = new_id
                continue
            try:
                assert curie_converter.expand(identifier)
            except AssertionError:
                mal_id_list.append(identifier)
                new_id = iri_converter.compress(identifier)  # type: ignore
                if new_id:
                    if new_id[0].islower():  # Need to capitalize
                        split_id = new_id.split(":")
                        new_id = f"{split_id[0].upper()}:{split_id[1]}"
                    update_ids[identifier] = new_id
    except IndexError:
        mal_id_list.append(identifier)

    mal_id_list_len = len(mal_id_list)
    if mal_id_list_len > 0:
        print(f"Found {mal_id_list_len} unexpected identifiers.")
        with open(mal_id_file_name, "w") as idfile:
            idfile.write("ID\n")
            for identifier in mal_id_list:
                idfile.write(f"{identifier}\n")
    else:
        print(f"All identifiers in {input_nodes} are as expected.")

    update_id_len = len(update_ids)
    if update_id_len > 0:
        print(f"Will normalize {update_id_len} identifiers.")
        with open(update_mapfile_name, "w") as mapfile:
            mapfile.write("Old ID\tNew ID\n")
            for identifier in update_ids:
                mapfile.write(f"{identifier}\t{update_ids[identifier]}\n")
            print(f"Wrote IRI maps to {update_mapfile_name}.")
    else:
        print(f"No identifiers in {input_nodes} will be normalized.")

    return update_ids


def load_sssom_maps(maps) -> tuple:
    """
    Load all provided SSSOM maps.

    :param maps: a list of paths to SSSOM maps
    :return: tuple of dicts,
    first is all subject_id:object_id,
    second is all subject_id:object_category
    """
    all_maps = MappingSetDataFrame()
    for filepath in maps:
        msdf = parse_sssom_table(filepath)
        all_maps = all_maps.merge(msdf)
    all_maps.clean_prefix_map()

    # Convert the SSSOM maps to two dicts
    id_map = {}
    cat_map = {}
    for _, row in all_maps.df.iterrows():
        subj = None
        obj = None
        obj_cat = None
        for k, v in row.items():
            if k == 'subject_id':
                subj = v
            if k == 'object_id':
                obj = v
            if k == 'object_category':
                obj_cat = v
            if subj and obj and subj != obj:
                id_map[subj] = obj
            if subj and obj_cat:
                cat_map[subj] = obj_cat
    print(f"Loaded {len(id_map)} id mappings.")
    print(f"Loaded {len(cat_map)} category mappings.")

    return (id_map, cat_map)
