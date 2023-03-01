"""Test graph cleaning and normalization functions."""

from unittest import TestCase

from universalizer.norm import clean_and_normalize_graph


class TestNorm(TestCase):
    """Test graph cleaning and normalization functions."""

    def setUp(self) -> None:
        """Set up."""
        self.test_graph_path = "tests/resources/graph_simple_test/"
        self.id_graph_path = "tests/resources/graph_for_ids/"
        self.cat_graph_path = "tests/resources/graph_for_cats/"
        self.chebi_graph_path = "tests/resources/graph_chebi/"
        self.chebi_graph_edges = "tests/resources/graph_chebi/chebi_edges.tsv"
        self.map_paths = [
            "tests/resources/mappings/ogg-gene-test-0.1.sssom.tsv",
            "tests/resources/mappings/skos-biolink_cats-all-1.0.sssom.tsv",
        ]

    def test_clean_and_normalize_graph(self):
        """Test clean_and_normalize_graph."""
        self.assertTrue(
            clean_and_normalize_graph(
                self.test_graph_path,
                compressed=False,
                maps=[],
                update_categories=False,
                contexts=["obo", "bioregistry.upper"],
                namespace_cat_map="",
                oak_lookup=False,
            )
        )

    def test_sssom_node_remap(self):
        """Test remapping nodes with SSSOM maps."""
        self.assertTrue(
            clean_and_normalize_graph(
                self.id_graph_path,
                compressed=False,
                maps=self.map_paths,
                update_categories=False,
                contexts=["obo", "bioregistry.upper"],
                namespace_cat_map="",
                oak_lookup=False,
            )
        )

    def test_sssom_cat_remap(self):
        """Test remapping categories with SSSOM maps."""
        self.assertTrue(
            clean_and_normalize_graph(
                self.cat_graph_path,
                compressed=False,
                maps=self.map_paths,
                update_categories=False,
                contexts=["obo", "bioregistry.upper"],
                namespace_cat_map="",
                oak_lookup=False,
            )
        )

    def test_normalize_and_remove_extra_edges(self):
        """
        Test normalizing and removing extra edges.

        Test clean_and_normalize_graph, in a case where
        a node ID and its category are updated AND category
        edges must be removed. This happens with PHENIO.
        """
        with open(self.chebi_graph_edges, "r") as infile:
            beforelen = len(infile.readlines())
        self.assertTrue(
            clean_and_normalize_graph(
                self.chebi_graph_path,
                compressed=False,
                maps=[],
                update_categories=True,
                contexts=["obo", "bioregistry.upper"],
                namespace_cat_map="",
                oak_lookup=False,
            )
        )
        with open(self.chebi_graph_edges, "r") as infile:
            afterlen = len(infile.readlines())
        self.assertLess(afterlen, beforelen, "Edges not removed?")
