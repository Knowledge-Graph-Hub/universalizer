"""CLI for universalizer."""

from os import listdir
from os.path import isdir, isfile, join

import click

from universalizer.norm import clean_and_normalize_graph


@click.group()
def cli():
    """Click CLI for universalizer."""
    pass


@cli.command()
@click.argument("input_path",
                type=click.Path(exists=True))
@click.option("--compressed",
              "-c",
              required=False,
              default=False,
              is_flag=True)
@click.option("--map_path",
              "-m",
              required=False,
              default="null")
def run(input_path: str, compressed: bool, map_path: str) -> None:
    """Process a graph, normalizing all nodes.

    :param input_path: Path to a directory containing
    KGX format graph node and edge files, or a single
    file if the compressed flag is used.
    :param compressed: bool, True if input_path is a single .tar.gz
    :param map_path: str, path to a single SSSOM ID map or
    a directory of SSSOM maps. Not recursive.
    :return: None
    """
    print(f"Input path: {input_path}")

    if isdir(map_path):
        print(f"Will use ID maps in {map_path}.")
        maps = [join(map_path, fn) for fn in listdir(map_path) if
                isfile(join(map_path, fn))]
    else:
        maps = [map_path]

    if clean_and_normalize_graph(input_path, compressed, maps):
        print("Complete.")

    return None
