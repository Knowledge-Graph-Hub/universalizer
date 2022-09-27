"""Test graph cleaning and normalization functions."""

from unittest import TestCase

from universalizer.norm import clean_and_normalize_graph


class TestNorm(TestCase):
    """Test graph cleaning and normalization functions."""

    def setUp(self) -> None:
        """Set up."""
        self.test_graph_path = "tests/resources/"
        self.test_graph_path_nodes = "tests/resources/test_nodes.tsv"
        self.test_graph_path_edges = "tests/resources/test_edges.tsv"

    def test_clean_and_normalize_graph(self):
        """Test clean_and_normalize_graph."""
        self.assertTrue(
            clean_and_normalize_graph(self.test_graph_path, compressed=False)
        )
