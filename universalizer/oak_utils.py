"""Utilities for the Ontology Access Kit (OAK)."""

# For now, this requires an SQL implementation,
# and the SQL version may or may not have
# any better categories than the input.
# So this is mostly a stub.

from typing import Dict, List
from urllib.error import HTTPError

from oaklib.constants import OAKLIB_MODULE
from oaklib.implementations.sqldb.sql_implementation import SqlImplementation
from oaklib.resource import OntologyResource


def get_cats_from_oak(terms: List[str]) -> Dict[str, str]:
    """
    Use OAK term-categories to get Biolink categories.

    :param terms: list of terms to retrieve categories for.
    This assumes terms are CURIEs.
    :return: dict of CURIEs with corresponding categories.
    Those without categories are assigned empty strings.
    """
    db_subsets: Dict[str, list] = {}
    cat_maps: Dict[str, str] = {}

    # Determine which resources we are working with
    # Split up IDs based on their corresponding db.
    for term in terms:
        prefix = (term.split(":"))[0].lower()
        if prefix not in db_subsets:
            db_subsets[prefix] = [term]
        else:
            db_subsets[prefix].append(term)

    # Retrieve the respective sql dbs.
    # They may already be available locally.
    # Set up OAK implementation.
    # SQL is the only one currently supported for this
    # function.
    db_count = len(db_subsets)
    print(f"Seeking {db_count} databases...")

    for db in db_subsets:
        try:
            print(f"Examining {db}...")
            url = f"https://s3.amazonaws.com/bbop-sqlite/{db}.db"
            db_path = OAKLIB_MODULE.ensure(url=url)
            resource = OntologyResource(slug=f"sqlite:///{str(db_path)}")
            oi = SqlImplementation(resource)
            print(db_subsets[db])
            results = oi.terms_categories(db_subsets[db])
            for result in results:
                cat_maps[result[0]] = result[1]
        except HTTPError:
            print(f"Can't find database for {db}.")

    return cat_maps
