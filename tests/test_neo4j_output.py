"""Test Neo4j output."""

import tempfile
import unittest
from pathlib import Path

import semra
from semra.io import write_neo4j


class TestNeo4jOutput(unittest.TestCase):
    """Test Neo4j output."""

    def test_neo4j_output(self) -> None:
        """Test Neo4j output."""
        mappings: list[semra.Mapping] = []

        with tempfile.TemporaryDirectory() as _directory:
            directory = Path(_directory)

            write_neo4j(mappings, directory)

            self.fail("tests not implemented")
