"""CLI for universalizer."""

import click

from universalizer.norm import clean_and_normalize_graph

@click.group()
def cli():
    """Click CLI for universalizer."""
    pass


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--compressed", "-c", required=False, default=False, is_flag=True)
def run(input_path: str, compressed: bool) -> None:
    """Process a graph, normalizing all nodes
    :param input_path: Path to a directory containing
    KGX format graph node and edge files, or a single
    file if the compressed flag is used.
    :param compressed: bool, True if input_path is a single .tar.gz
    :return: None
    """
    print(f"Input path: {input_path}")

    if clean_and_normalize_graph(input_path, compressed):
        print("Complete.")

    return None
