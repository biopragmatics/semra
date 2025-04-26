"""Test Neo4j output."""

import tempfile
import unittest
from pathlib import Path

import semra
from semra import (
    EXACT_MATCH,
    LEXICAL_MAPPING,
    MANUAL_MAPPING,
    Mapping,
    MappingSet,
    Reference,
    SimpleEvidence,
)
from semra.io import write_neo4j
from semra.rules import BEN_ORCID, charlie
from tests import resources


class TestNeo4jOutput(unittest.TestCase):
    """Test Neo4j output."""

    def test_neo4j_output(self) -> None:
        """Test Neo4j output."""
        biomappings = MappingSet(
            name="biomappings",
            confidence=0.90,
            license="CC0",
        )
        m1 = Mapping(
            s=Reference.from_curie("chebi:101854", name="talarozole"),
            p=EXACT_MATCH,
            o=Reference.from_curie("mesh:C406527", name="R 115866"),
            evidence=[
                SimpleEvidence(
                    mapping_set=biomappings,
                    justification=MANUAL_MAPPING,
                    author=charlie,
                    confidence=0.99,
                ),
                SimpleEvidence(
                    mapping_set=biomappings,
                    justification=MANUAL_MAPPING,
                    author=BEN_ORCID,
                    confidence=0.94,
                ),
                SimpleEvidence(
                    mapping_set=MappingSet(
                        name="lexical",
                        confidence=0.90,
                    ),
                    justification=LEXICAL_MAPPING,
                    confidence=0.8,
                ),
            ],
        )
        mappings: list[semra.Mapping] = [m1]

        with tempfile.TemporaryDirectory() as _directory:
            directory = Path(_directory)

            # write_neo4j(mappings, "/Users/cthoyt/Desktop/test-neo4j", use_tqdm=False)
            write_neo4j(mappings, directory, use_tqdm=False)

            # this test is important since it makes sure we get deterministic hashes each time
            for path in [
                resources.CONCEPT_NODES_TSV_PATH,
                resources.EVIDENCE_NODES_TSV_PATH,
                resources.MAPPING_NODES_TSV_PATH,
                resources.MAPPING_SET_NODES_TSV_PATH,
                resources.EDGES_TSV_PATH,
                resources.MAPPING_EDGES_TSV_PATH,
            ]:
                self.assertEqual(path.read_text(), directory.joinpath(path.name).read_text())
