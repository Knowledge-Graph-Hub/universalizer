"""CLI for universalizer."""

import sys
from os import listdir
from os.path import isdir, isfile, join

import click

from universalizer.norm import clean_and_normalize_graph


@click.group()
def cli():
    """Click CLI for universalizer."""
    pass


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--compressed", "-c", required=False, default=False, is_flag=True)
@click.option("--map_path", "-m", required=False, default="")
@click.option("--update_categories", "-u", required=False, default=False, is_flag=True)
@click.option("--contexts", "-x",
              callback=lambda _, __, x: x.split(" ") if x else [],
              default=["obo", "bioregistry.upper"],
              help="""Contexts to use for prefixes.
              Space-delimited. Defaults to obo and bioregistry.upper.""",
              )
@click.option("--oak_lookup", "-l", required=False, default=False, is_flag=True)
def run(
    input_path: str,
    compressed: bool,
    map_path: str,
    update_categories: bool,
    contexts: list,
    oak_lookup: bool,
) -> None:
    """Process a graph, normalizing all nodes.

    :param input_path: Path to a directory containing
    KGX format graph node and edge files, or a single
    file if the compressed flag is used.
    :param compressed: bool, True if input_path is a single .tar.gz
    :param map_path: str, path to a single SSSOM ID map or
    a directory of SSSOM maps. Not recursive.
    :param update_categories: bool, if True, update and verify
    Biolink categories for all nodes
    :contexts: list, contexts to use for prefixes
    :param oak_lookup: bool, if True, look up additional
    Biolink categories from OAK
    :return: None
    """
    print(f"Input path: {input_path}")

    if map_path == "":
        maps = []
    elif isdir(map_path):
        print(f"Will use ID maps in {map_path}.")
        maps = [
            join(map_path, fn) for fn in listdir(map_path) if isfile(join(map_path, fn))
        ]
    else:
        maps = [map_path]

    if update_categories:
        print("Will update categories.")

    if oak_lookup and not update_categories:
        sys.exit(
            "Cannot look up categories if not updating them. "
            "Please check the specified options."
        )

    if clean_and_normalize_graph(
        input_path, compressed, maps, update_categories, contexts, oak_lookup
    ):
        print("Complete.")

    return None
