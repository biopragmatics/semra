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
    ReasonedEvidence,
    Reference,
    SimpleEvidence,
)
from semra.io import write_neo4j
from semra.rules import BEN_ORCID, CHAIN_MAPPING, UNSPECIFIED_MAPPING, charlie
from semra.struct import Triple
from tests import resources

# TODO test when concept name has problematic characters like tabs or newlines


class TestNeo4jOutput(unittest.TestCase):
    """Test Neo4j output."""

    def test_neo4j_output(self) -> None:
        """Test Neo4j output."""
        r1 = Reference.from_curie("mesh:C406527", name="R 115866")
        r2 = Reference.from_curie("chebi:101854", name="talarozole")
        r3 = Reference.from_curie("chembl.compound:CHEMBL459505", name="TALAROZOLE")

        t1 = Triple(subject=r1, predicate=EXACT_MATCH, object=r2)
        t2 = Triple(subject=r2, predicate=EXACT_MATCH, object=r3)
        t3 = Triple(subject=r1, predicate=EXACT_MATCH, object=r3)

        biomappings = MappingSet(
            purl="https://w3id.org/biopragmatics/biomappings/sssom/biomappings.sssom.tsv",
            name="biomappings",
            confidence=0.90,
            license="CC0",
        )
        self.assertEqual("a678c40e1494d775c3bf4c491fea512c", biomappings.hexdigest())

        chembl = MappingSet(
            name="chembl",
            confidence=0.90,
            license="CC-BY-SA-3.0",
        )

        m1_e1 = SimpleEvidence(
            mapping_set=biomappings,
            justification=MANUAL_MAPPING,
            author=charlie,
            confidence=0.99,
        )
        self.assertEqual("285acf742315635fbb8e239ae3e62b52", m1_e1.hexdigest(t1))

        # check that making an identical evidence gives the same hex digest
        m1_e1_copy = SimpleEvidence(
            mapping_set=biomappings,
            justification=MANUAL_MAPPING,
            author=charlie,
            confidence=0.99,
        )
        self.assertEqual(m1_e1.hexdigest(t1), m1_e1_copy.hexdigest(t1))

        m1_e2 = SimpleEvidence(
            mapping_set=biomappings,
            justification=MANUAL_MAPPING,
            author=BEN_ORCID,
            confidence=0.94,
        )
        m1_e3 = SimpleEvidence(
            mapping_set=MappingSet(
                name="lexical",
                confidence=0.90,
            ),
            justification=LEXICAL_MAPPING,
            confidence=0.8,
        )

        m1 = Mapping.from_triple(
            t1,
            evidence=[m1_e1, m1_e2, m1_e3],
        )

        # this curie is generated as a md5 digest of the pickle dump
        # of the 3-tuple of CURIE strings for the subject, predicate, object
        m1_hexdigest = "c3f216811ba4bd7d1e5a02ec927252b7"
        self.assertEqual(m1_hexdigest, m1.hexdigest())

        # Test that the evidences don't affect the hash
        for x in [
            Mapping.from_triple(t1),
            Mapping.from_triple(t1, evidence=[m1_e1]),
            Mapping.from_triple(t1, evidence=[m1_e2]),
            Mapping.from_triple(t1, evidence=[m1_e3]),
            Mapping.from_triple(t1, evidence=[m1_e2, m1_e1]),
            Mapping.from_triple(t1, evidence=[m1_e2, m1_e1, m1_e3]),
        ]:
            self.assertEqual(m1_hexdigest, x.hexdigest())

        m2_e1 = SimpleEvidence(
            mapping_set=chembl,
            justification=UNSPECIFIED_MAPPING,
            confidence=0.90,
        )
        m2 = Mapping.from_triple(t2, evidence=[m2_e1])

        m3_e1 = ReasonedEvidence(justification=CHAIN_MAPPING, mappings=[m1, m2])
        m3_e1_rev = ReasonedEvidence(justification=CHAIN_MAPPING, mappings=[m2, m1])
        m3 = Mapping.from_triple(t3, evidence=[m3_e1])
        m3_hexdigest = "c3f216811ba4bd7d1e5a02ec927252b7"
        self.assertEqual(m3_hexdigest, m3.hexdigest())

        # check that order of mappings in evidence doesn't change the hash
        self.assertEqual(
            m3_hexdigest,
            Mapping.from_triple(t3, evidence=[m3_e1_rev]).hexdigest(),
        )

        mappings: list[semra.Mapping] = [m1, m2, m3]

        with tempfile.TemporaryDirectory() as _directory:
            directory = Path(_directory)

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
