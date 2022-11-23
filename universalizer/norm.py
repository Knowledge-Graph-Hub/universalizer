"""Node cleaning and normalization functions."""

import os
import tarfile
from typing import Dict, List, Tuple

from curies import Converter  # type: ignore
from prefixmaps.io.parser import load_multi_context  # type: ignore
from sssom.parsers import parse_sssom_table  # type: ignore
from sssom.util import MappingSetDataFrame  # type: ignore

from universalizer.categories import STY_TO_BIOLINK
from universalizer.oak_utils import get_cats_from_oak


def clean_and_normalize_graph(
    filepath,
    compressed,
    maps,
    update_categories,
    contexts,
    namespace_cat_map,
    oak_lookup,
) -> bool:
    """
    Replace or remove node IDs or nodes as needed.

    :param filepath: str, name or path of KGX graph files
    :param compressed: bool, True if filepath is tar.gz compressed
    :param maps: list of str filepaths to SSSOM maps
    :param update_categories: bool, if True, update and verify
    Biolink categories for all nodes
    :param contexts: list, contexts to use for prefixes
    :param namespace_cat_map: str, path to a single tsv file
    containing namespaces (e.g., CHEBI) and category names,
    (e.g., biolink:ChemicalSubstance) such that the entirety
    of the namespace should share that category.
    :param oak_lookup: bool, if True, look up additional
    Biolink categories from OAK
    :return: bool, True if successful
    """
    success = True
    mapping = True
    use_oak = False

    if oak_lookup:
        use_oak = True

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
            if filename.endswith("nodes.tsv") or filename.endswith("edges.tsv"):
                graph_file_paths.append(os.path.join(filepath, filename))

    if len(graph_file_paths) > 2:
        raise RuntimeError("Found more than two graph files: " f"{graph_file_paths}")
    elif len(graph_file_paths) == 0:
        raise RuntimeError("Found no graph files!")
    elif len(graph_file_paths) == 2:
        print(f"Found these graph files:{graph_file_paths}")

    # Load SSSOM maps if provided.
    # Merge them together.
    using_sssom = False

    if maps != []:
        using_sssom = True
        print(f"Found these map files:{maps}")
        remaps, recats = load_sssom_maps(maps)

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

    remap_these_nodes = make_id_maps(nodepath, os.path.dirname(nodepath), contexts)

    remove_these_edges: List[str] = []

    ns_map = {}
    if namespace_cat_map != "":
        with open(namespace_cat_map) as ns_map_file:
            for line in ns_map_file:
                splitline = (line.rstrip()).split("\t")
                ns_map[splitline[0]] = splitline[1]

    if update_categories:
        remap_these_categories, remove_these_edges = make_cat_maps(
            nodepath, edgepath, os.path.dirname(nodepath), ns_map, use_oak
        )

    print("Updating graph files...")
    # Continue with mapping if everything's OK so far
    # Sometimes prefixes get capitalized, so we check for that too
    try:
        mapcount = 0
        rem_edge_count = 0
        with open(nodepath, "r") as innodefile, open(edgepath, "r") as inedgefile:
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
                        # Do categories, then IDs
                        if update_categories:
                            if line_split[0] in remap_these_categories:
                                new_node_cat = remap_these_categories[line_split[0]]
                                line_split[1] = new_node_cat
                                changed_this_line = True
                            if using_sssom:
                                if line_split[0] in recats:
                                    line_split[1] = recats[line_split[0]]
                                    changed_this_line = True
                        if line_split[0] in remap_these_nodes:
                            new_node_id = remap_these_nodes[line_split[0]]
                            line_split[0] = new_node_id
                            changed_this_line = True
                        if using_sssom:
                            if line_split[0] in recats:
                                line_split[1] = recats[line_split[0]]
                                changed_this_line = True
                    if changed_this_line:
                        mapcount = mapcount + 1
                    line = "\t".join(line_split) + "\n"
                    outnodefile.write(line)
                for line in inedgefile:
                    line_split = (line.rstrip()).split("\t")
                    if line_split[0] in remove_these_edges:
                        rem_edge_count = rem_edge_count + 1
                        continue
                    if mapping:
                        # Check for edges containing nodes to be remapped
                        for col in [1, 3]:
                            if line_split[col] in remap_these_nodes:
                                new_node_id = remap_these_nodes[line_split[col]]
                                line_split[col] = new_node_id
                            if using_sssom:
                                if line_split[col] in remaps:
                                    new_node_id = remaps[line_split[col]]
                                    line_split[col] = new_node_id
                    line = "\t".join(line_split) + "\n"
                    outedgefile.write(line)

        os.replace(outnodepath, nodepath)
        os.replace(outedgepath, edgepath)

        if mapcount > 0:
            print(f"Updated {mapcount} nodes.")
        elif mapcount == 0:
            print("Could not remap any node IDs.")

        if rem_edge_count > 0:
            print(f"Removed {rem_edge_count} redundant edges.")

        success = True

    except (IOError, KeyError) as e:
        print(f"Failed to remap node IDs: {e}")
        success = False

    return success


def make_id_maps(input_nodes: str, output_dir: str, contexts: list) -> dict:
    """
    Retrieve all entity identifiers for a single graph.

    Report all identifiers of expected and unexpected format,
    and find more appropriate prefixes if possible.
    Does not rewrite IRIs.
    :param input_nodes: str, path to input nodefile
    :param output_dir: string of directory, location of unexpected id
    and update map file to be created
    :param contexts: list, contexts to use for prefixes
    :return: dict, map of original node IDs to new node IDs
    """
    id_list = []
    mal_id_list = []
    update_ids: Dict[str, str] = {}

    # TODO: provide more configuration re: curie contexts
    # TODO: expand reverse contexts beyond bijective maps
    # TODO: add more capitalization variants

    curie_contexts = load_multi_context(contexts)
    all_contexts = curie_contexts.as_dict()
    all_contexts = {key: val for key, val in all_contexts.items()}
    curie_converter = Converter.from_prefix_map(all_contexts)

    all_reverse_contexts = {val: key for key, val in all_contexts.items()}
    all_reverse_contexts_lc = {val.lower(): key for key, val in all_contexts.items()}
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
            # Fixes for the OBO space.
            if (identifier.split(":"))[0].upper() == "OBO":
                update_ids[identifier] = obo_handle(identifier)
                mal_id_list.append(identifier)
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

    update_id_len = len(update_ids)
    if update_id_len > 0:
        print(f"Will normalize {update_id_len} identifiers.")
        with open(update_mapfile_name, "w") as mapfile:
            mapfile.write("Old ID\tNew ID\n")
            for identifier in update_ids:
                mapfile.write(f"{identifier}\t{update_ids[identifier]}\n")
            print(f"Wrote IRI maps to {update_mapfile_name}.")

    return update_ids


def make_cat_maps(
    input_nodes: str, input_edges: str, output_dir: str, ns_map: dict, use_oak: bool
) -> Tuple[dict, list]:
    """
    Retrieve all categories for nodes in a single graph.

    Report all node to category relationships requiring update.
    Also report all edges to remove because they define categories.
    Does not rewrite categories.
    :param input_nodes: str, path to input nodefile
    :param input_edges: str, path to input edgefile
    :param output_dir: string of directory, location of unexpected id
    and update map file to be created
    :param ns_map: dict, namespace to category maps
    :param use_oak: bool, if True, look up categories from OAK
    :return: tuple containing 1. dict of original node IDs to
    new node categories, and 2. list of lists of original subject,
    predicate, object relations to remove from edgelist
    """
    id_and_cat_map: Dict[str, str] = {}
    mal_cat_list = []
    update_cats: Dict[str, str] = {}
    remove_edges: List[str] = []

    print(f"Retrieving categories in {input_nodes}...")

    mal_cat_file_name = os.path.join(output_dir, "unexpected_categories.tsv")
    update_cat_mapfile_name = os.path.join(output_dir, "update_category_maps.tsv")

    # Examine nodes, obtain categories
    with open(input_nodes, "r") as nodefile:
        nodefile.readline()
        for line in nodefile:
            splitline = line.rstrip().split("\t")
            node_id = splitline[0]
            category = splitline[1]
            if node_id not in id_and_cat_map:
                id_and_cat_map[node_id] = category
            else:
                if id_and_cat_map[node_id] == category:
                    continue
                else:
                    mal_cat_list.append(node_id)

    # if cat is OntologyClass or missing, set to NamedThing
    # If using a namespace to category map,
    # set here too, but not if it already have a
    # more specific category
    for identifier in id_and_cat_map:
        if id_and_cat_map[identifier] in ["", "biolink:OntologyClass"]:
            update_cats[identifier] = "biolink:NamedThing"
        if ns_map:
            ns = identifier.split(":")[0]
            if ns in ns_map and id_and_cat_map[identifier] in [
                "",
                "biolink:OntologyClass",
                "biolink:NamedThing",
            ]:
                update_cats[identifier] = ns_map[ns]

    # Examine edges, obtain biolink:category relations
    # and those from UMLS semantic types (STY)
    # These take precedence over nodelist category assignments
    with open(input_edges, "r") as edgefile:
        edgefile.readline()
        for line in edgefile:
            splitline = line.rstrip().split("\t")
            edge_id = splitline[0]
            subj_node_id = splitline[1]
            pred = splitline[2]
            obj_node_id = splitline[3]
            if pred.lower() == "biolink:category":
                if obj_node_id not in ["biolink:NamedThing", "biolink:OntologyClass"]:
                    remove_edges.append(edge_id)
                    update_cats[subj_node_id] = obj_node_id
            if pred.lower() == "biolink:related_to":
                this_is_sty = False
                if obj_node_id.startswith("STY"):
                    this_is_sty = True
                try:
                    if (obj_node_id.split("/"))[-2] == "STY":
                        this_is_sty = True
                except IndexError:
                    pass

                if this_is_sty:
                    remove_edges.append(edge_id)
                    sty_curie = "STY:" + (obj_node_id.split("/"))[-1]
                    update_cats[subj_node_id] = STY_TO_BIOLINK[sty_curie]

    # For each id, check its category in the nodelist first
    # then look it up in OAK if requested
    # If what OAK says doesn't match the nodelist, use OAK's output
    # If OAK doesn't provide a category then use whatever we have
    if use_oak:
        oak_cat_maps = get_cats_from_oak(list(id_and_cat_map.keys()))
        for identifier in oak_cat_maps:
            if oak_cat_maps[identifier] != "" and id_and_cat_map[identifier] in [
                "",
                "biolink:OntologyClass",
                "biolink:NamedThing",
            ]:
                update_cats[identifier] = oak_cat_maps[identifier]
            elif oak_cat_maps[identifier] != "":
                mal_cat_list.append(identifier)

    mal_id_list_len = len(mal_cat_list)
    if mal_id_list_len > 0:
        print(f"Found {mal_id_list_len} unexpected categories.")
        with open(mal_cat_file_name, "w") as idfile:
            idfile.write("ID\n")
            for identifier in mal_cat_list:
                idfile.write(f"{identifier}\n")
    else:
        print(f"All categories in {input_nodes} are as expected.")

    update_id_len = len(update_cats)
    if update_id_len > 0:
        print(f"Will normalize {update_id_len} categories.")
        with open(update_cat_mapfile_name, "w") as mapfile:
            mapfile.write("Old ID\tNew Category\n")
            for identifier in update_cats:
                mapfile.write(f"{identifier}\t{update_cats[identifier]}\n")
            print(f"Wrote category maps to {update_cat_mapfile_name}.")
    else:
        print(f"No identifiers in {input_nodes} will be normalized.")

    return (update_cats, remove_edges)


def load_sssom_maps(maps: list) -> tuple:
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
            if k == "subject_id":
                subj = v
            if k == "object_id":
                obj = v
            if k == "object_category":
                obj_cat = v
            if subj and obj and subj != obj:
                id_map[subj] = obj
            if subj and obj_cat:
                cat_map[subj] = obj_cat
    print(f"Loaded {len(id_map)} id mappings.")
    print(f"Loaded {len(cat_map)} category mappings.")

    return (id_map, cat_map)


def obo_handle(old_id: str) -> str:
    """
    Process an OBO CURIE.

    For CURIEs referencing the 'native'
    namespace or another (e.g., OBO:ABC_1234)
    they are converted (e.g., ABC:1234).
    For OBO space (e.g., OBO:ABC1234)
    they are left unchanged, including when
    referring to an OWL (e.g., OBO:ABC.owl#1234).
    :param old_id: str, old CURIE
    :return: str, new CURIE
    """
    # Check if this is an ID we should leave alone
    # How do we know?
    # It needs to lack anything we could use to
    # render it as a CURIE
    clues = ["_", ":"]
    convertible = False
    if "#" in old_id[4:]:
        main_id = (old_id.split("#", 1)[0])[4:]
    else:
        main_id = old_id[4:]
    for clue in clues:
        if main_id.count(clue) == 1:
            convertible = True
            break

    if convertible:
        # Remove OBO prefix
        new_id = old_id[4:]

        # Replace the first underscore with colon
        new_id = new_id.replace("_", ":", 1)

        # Capitalize the prefix, but not the rest
        # of the ID
        split_id = new_id.split(":", 1)
        new_id = f"{split_id[0].upper()}:{split_id[1]}"
    else:
        new_id = old_id

    return new_id
