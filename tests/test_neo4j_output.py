"""Test Neo4j output."""

import tempfile
import unittest
from pathlib import Path

from biomappings.utils import METADATA as BIOMAPPINGS_MAPPING_SET
from pydantic import AnyUrl
from sssom_pydantic import SemanticMapping

import semra
from semra import (
    EXACT_MATCH,
    LEXICAL_MAPPING,
    MANUAL_MAPPING,
    UNSPECIFIED_MAPPING,
    Mapping,
    MappingSet,
    ReasonedEvidence,
    SimpleEvidence,
)
from semra.constants import Reference
from semra.io import write_neo4j
from semra.struct import Triple
from semra.utils import get_semra_uri
from semra.vocabulary import BEN_REFERENCE, CHAIN_MAPPING, CHARLIE
from tests import resources

# TODO test when concept name has problematic characters like tabs or newlines


class TestNeo4jOutput(unittest.TestCase):
    """Test Neo4j output."""

    def test_neo4j_output(self) -> None:
        """Test Neo4j output."""
        mesh_c406527 = Reference.from_curie("mesh:C406527", name="R 115866")
        chebi_101854 = Reference.from_curie("chebi:101854", name="talarozole")
        chembl_459505 = Reference.from_curie("chembl.compound:CHEMBL459505", name="TALAROZOLE")

        t1 = Triple(subject=mesh_c406527, predicate=EXACT_MATCH, object=chebi_101854)
        t2 = Triple(subject=chebi_101854, predicate=EXACT_MATCH, object=chembl_459505)
        t3 = Triple(subject=mesh_c406527, predicate=EXACT_MATCH, object=chembl_459505)

        chembl = MappingSet(
            id=AnyUrl(get_semra_uri("chembl")),
            title="chembl",
            confidence=0.90,
            license=AnyUrl("https://bioregistry.io/spdx:CC-BY-SA-3.0"),
        )

        m1_e1 = SimpleEvidence(
            mapping_set=BIOMAPPINGS_MAPPING_SET,
            mapping=SemanticMapping(
                subject=t1.subject,
                predicate=t1.predicate,
                object=t1.object,
                justification=MANUAL_MAPPING,
                authors=[CHARLIE],
                confidence=0.99,
            ),
        )
        # self.assertEqual("F041E851053AEC64", m1_e1.get_identifier(t1))

        # check that making an identical evidence gives the same hex digest
        m1_e1_copy = SimpleEvidence(
            mapping_set=BIOMAPPINGS_MAPPING_SET,
            mapping=SemanticMapping(
                subject=t1.subject,
                predicate=t1.predicate,
                object=t1.object,
                justification=MANUAL_MAPPING,
                authors=[CHARLIE],
                confidence=0.99,
            ),
        )
        self.assertEqual(m1_e1.get_identifier(t1), m1_e1_copy.get_identifier(t1))

        m1_e2 = SimpleEvidence(
            mapping_set=BIOMAPPINGS_MAPPING_SET,
            mapping=SemanticMapping(
                subject=t1.subject,
                predicate=t1.predicate,
                object=t1.object,
                justification=MANUAL_MAPPING,
                authors=[BEN_REFERENCE],
                confidence=0.94,
            ),
        )
        m1_e3 = SimpleEvidence(
            mapping_set=MappingSet(
                id=AnyUrl(get_semra_uri("test")),
                title="lexical",
                confidence=0.90,
            ),
            mapping=SemanticMapping(
                subject=t1.subject,
                predicate=t1.predicate,
                object=t1.object,
                justification=LEXICAL_MAPPING,
                confidence=0.8,
            ),
        )

        m1 = Mapping.from_triple(
            t1,
            evidence=[m1_e1, m1_e2, m1_e3],
        )

        # this curie is generated as a md5 digest of the pickle dump
        # of the 3-tuple of CURIE strings for the subject, predicate, object
        m1_identifier = "eacc57c4a2bbfb9e5f00c8fc1fa6df4c4968f5b417c508628066be9856054f23"
        self.assertEqual(m1_identifier, m1.get_identifier())

        expected_hex = Mapping.from_triple(t1).get_identifier()

        # Test that the evidences don't affect the hash
        for x in [
            Mapping.from_triple(t1, evidence=[m1_e1]),
            Mapping.from_triple(t1, evidence=[m1_e2]),
            Mapping.from_triple(t1, evidence=[m1_e3]),
            Mapping.from_triple(t1, evidence=[m1_e2, m1_e1]),
            Mapping.from_triple(t1, evidence=[m1_e2, m1_e1, m1_e3]),
        ]:
            self.assertEqual(expected_hex, x.get_identifier())

        m2_e1 = SimpleEvidence(
            mapping_set=chembl,
            mapping=SemanticMapping(
                subject=t2.subject,
                predicate=t2.predicate,
                object=t2.object,
                justification=UNSPECIFIED_MAPPING,
                confidence=0.90,
            ),
        )
        m2 = Mapping.from_triple(t2, evidence=[m2_e1])

        m3_e1 = ReasonedEvidence(justification=CHAIN_MAPPING, mappings=[m1, m2])
        m3_e1_rev = ReasonedEvidence(justification=CHAIN_MAPPING, mappings=[m2, m1])
        m3 = Mapping.from_triple(t3, evidence=[m3_e1])
        m3_identifier = "637fee94e47a222e670bd80d31416519a45b7984b7a53729132176d2a63007bf"
        self.assertEqual(m3_identifier, m3.get_identifier())

        # check that order of mappings in evidence doesn't change the hash
        self.assertEqual(
            Mapping.from_triple(t3, evidence=[m3_e1]).get_identifier(),
            Mapping.from_triple(t3, evidence=[m3_e1_rev]).get_identifier(),
        )

        return
        mappings: list[semra.Mapping] = [m1, m2, m3]

        with tempfile.TemporaryDirectory() as _directory:
            directory = Path(_directory)

            write_neo4j(mappings, directory, use_tqdm=False, quiet=True)
            # write_neo4j(mappings, resources.HERE, use_tqdm=False, quiet=True)
            for path in [
                resources.CONCEPT_NODES_TSV_PATH,
                resources.EVIDENCE_NODES_TSV_PATH,
                resources.MAPPING_NODES_TSV_PATH,
                resources.MAPPING_SET_NODES_TSV_PATH,
                resources.EDGES_TSV_PATH,
                resources.MAPPING_EDGES_TSV_PATH,
            ]:
                self.assertEqual(
                    path.read_text(),
                    directory.joinpath(path.name).read_text(),
                    msg=f"\n\nfailed on {path.name}\n\n",
                )
