"""Tests for I/O functions."""

import getpass
import itertools as itt
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

import bioregistry
import curies
import sssom_pydantic
from biomappings.utils import METADATA as BIOMAPPINGS_MAPPING_SET
from pydantic import AnyUrl
from pystow.utils import safe_open
from sssom_pydantic import SemanticMapping
from sssom_pydantic.testing import assert_semantic_mapping_equal

from semra.api import assemble_evidences
from semra.constants import (
    SEMRA_EVIDENCE_PREFIX,
    SEMRA_EVIDENCE_URI_PREFIX,
    SEMRA_MAPPING_PREFIX,
    SEMRA_MAPPING_URI_PREFIX,
)
from semra.io import (
    from_digraph,
    from_jsonl,
    from_multidigraph,
    from_pickle,
    from_pyobo,
    from_sssom,
    to_digraph,
    to_multidigraph,
    write_jsonl,
    write_pickle,
    write_sssom,
)
from semra.io.io import _to_sssom_pydantic
from semra.sources.biopragmatics import get_biomappings_negative_mappings
from semra.struct import (
    CONVERTER,
    Mapping,
    MappingSet,
    ReasonedEvidence,
    Reference,
    SimpleEvidence,
    Triple,
)
from semra.utils import get_semra_uri
from semra.vocabulary import (
    BEN_REFERENCE,
    CHAIN_MAPPING,
    CHARLIE,
    EXACT_MATCH,
    LEXICAL_MAPPING,
    MANUAL_MAPPING,
    UNSPECIFIED_MAPPING,
)
from tests.constants import (
    TEST_MAPPING_1,
    TEST_MAPPING_6,
    TEST_MAPPING_SET,
    TEST_SSSOM_MAPPING_1,
    TEST_SSSOM_MAPPING_6,
    assert_mappings_equal,
)

LOCAL = getpass.getuser() == "cthoyt"

mapping_set_title = "test"
mapping_set_confidence = 0.6


class TestIO(unittest.TestCase):
    """Test I/O functions."""

    def tearDown(self) -> None:
        """Tear down the test case."""
        self.temporary_directory.cleanup()

    def setUp(self) -> None:
        """Set up the test case."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)

        r1 = Reference.from_curie("mesh:C406527", name="R 115866")
        r2 = Reference.from_curie("chebi:101854", name="talarozole")
        r3 = Reference.from_curie("chembl.compound:CHEMBL459505", name="TALAROZOLE")

        t1 = Triple(subject=r1, predicate=EXACT_MATCH, object=r2)
        t2 = Triple(subject=r2, predicate=EXACT_MATCH, object=r3)
        t3 = Triple(subject=r1, predicate=EXACT_MATCH, object=r3)

        chembl = MappingSet(
            id=AnyUrl(get_semra_uri("chembl")),
            title="ChEMBL",
            license=AnyUrl("https://creativecommons.org/licenses/by/3.0/"),
        )
        lexical_ms = MappingSet(id=AnyUrl(get_semra_uri("lexical-test")), title="lexical")

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
            mapping_set=lexical_ms,
            mapping=SemanticMapping(
                subject=t1.subject,
                predicate=t1.predicate,
                object=t1.object,
                justification=LEXICAL_MAPPING,
                confidence=0.8,
            ),
        )

        m1 = Mapping.from_triple(t1, evidence=[m1_e1, m1_e2, m1_e3])

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
        m3 = Mapping.from_triple(t3, evidence=[m3_e1])

        self.mappings = [m1, m2, m3]

    def test_from_pyobo(self) -> None:
        """Test loading content from PyOBO."""
        mappings = from_pyobo("taxrank")
        for mapping in mappings:
            self.assertEqual("taxrank", mapping.subject.prefix)
            for evidence in mapping.evidence:
                if not isinstance(evidence, SimpleEvidence):
                    raise self.fail()
                self.assertEqual(evidence.justification, UNSPECIFIED_MAPPING)
                self.assertIsNone(evidence.get_confidence())
                self.assertIsNone(evidence.author)
                if evidence.mapping_set is None:
                    raise self.fail()
                self.assertEqual(
                    "http://purl.obolibrary.org/obo/taxrank.obo", str(evidence.mapping_set.id)
                )

        path = self.directory.joinpath("taxrank.sssom.tsv")
        # this is just dummy metadata
        metadata = MappingSet(id=AnyUrl("https://example.com/test.sssom.tsv"))
        write_sssom(mappings, path, metadata=metadata)

        smappings, _, _, errors = sssom_pydantic.read(path, return_errors=True)
        error_lines = "\n- ".join(map(str, errors))
        self.assertEqual(0, len(errors), msg=f"errors:\n\n{error_lines}")
        self.assertLess(
            0,
            len(smappings),
            msg=f"no mappings were written\n\nErrors:\n{error_lines}\n\n{path.read_text()}",
        )
        self.assertIsNotNone(smappings[0].source, msg=f"source is none\n\n{path.read_text()}")
        self.assertEqual(Reference(prefix="obo", identifier="taxrank.obo"), smappings[0].source)

        mappings_2 = from_pyobo("taxrank", "ncbitaxon")
        for mapping in mappings_2:
            self.assertEqual("taxrank", mapping.subject.prefix)
            self.assertEqual("ncbitaxon", mapping.object.prefix)

    def test_jsonl(self) -> None:
        """Test JSONL I/O."""
        for n in ["test.jsonl", "test.jsonl.gz"]:
            path = self.directory.joinpath(n)
            with self.subTest(path=path):
                write_jsonl(self.mappings, path)
                new_mappings = from_jsonl(path, show_progress=False, failure_action="raise")
                self.assertIsInstance(new_mappings, list)
                self.assertEqual(self.mappings, new_mappings)

    def test_digraph(self) -> None:
        """Test I/O to a directed graph."""
        self.assertEqual(sorted(self.mappings), sorted(from_digraph(to_digraph(self.mappings))))

    def test_multidigraph(self) -> None:
        """Test I/O with multi-directed graph."""
        self.assertEqual(
            sorted(self.mappings), sorted(from_multidigraph(to_multidigraph(self.mappings)))
        )

    def test_pickle(self) -> None:
        """Test I/O with pickle."""
        for path in [
            self.directory.joinpath("test.pkl"),
            self.directory.joinpath("test.pkl.gz"),
        ]:
            write_pickle(self.mappings, path)
            new_mappings = from_pickle(path)
            self.assertEqual(self.mappings, new_mappings)

    def test_sssom(self) -> None:
        """Test I/O with SSSOM."""
        prefix_map = {
            "mesh": bioregistry.get_uri_prefix("mesh", strict=True),
            "orcid": bioregistry.get_uri_prefix("orcid", strict=True),
            "chembl.compound": bioregistry.get_uri_prefix("chembl.compound", strict=True),
            "chebi": bioregistry.get_uri_prefix("chebi", strict=True),
            SEMRA_EVIDENCE_PREFIX: SEMRA_EVIDENCE_URI_PREFIX,
            SEMRA_MAPPING_PREFIX: SEMRA_MAPPING_URI_PREFIX,
            "skos": "http://www.w3.org/2004/02/skos/core#",
            "wikidata": "http://www.wikidata.org/entity/",
        }
        converter = curies.Converter.from_prefix_map(prefix_map)
        for n, prune in itt.product(
            ["test.sssom.tsv", "test.sssom.tsv.gz"],
            [True, False],
        ):
            with self.subTest(name=n, prune=prune):
                path = self.directory.joinpath(n)
                write_sssom(
                    self.mappings,
                    path,
                    prune=prune,
                    metadata=TEST_MAPPING_SET,
                    converter=converter,
                )
                # TODO switch with contents = safe_read_text(path)
                with safe_open(path) as file:
                    contents = file.read()

                # check that SSSOM is valid
                smappings, _, _, errors = sssom_pydantic.read(
                    path, converter=converter, return_errors=True
                )
                self.assertEqual([], errors, msg=f"{errors}")
                self.assertNotEqual(0, len(smappings), msg=f"{errors}")

                unassembled_mappings = from_sssom(path, strict=True)
                self.assertNotEqual(
                    0, len(unassembled_mappings), msg=f"error reading\n\n{contents}"
                )

                new_mappings = assemble_evidences(unassembled_mappings, progress=False)
                self.assertNotEqual(0, len(new_mappings), msg="error reading")

                assert_mappings_equal(
                    self,
                    _filter_simple(self.mappings),
                    _filter_simple(new_mappings),
                    msg=f"mapping mismatch\n\n{contents}",
                )

    def test_from_biomappings(self) -> None:
        """Test loading from Biomappings."""
        res = get_biomappings_negative_mappings()
        self.assertNotEqual(0, len(res))


class TestSSSOM(unittest.TestCase):
    """Test SSSOM."""

    def test_to_sssom_pydantic(self) -> None:
        """Test outputting to a SSSOM-style mapping."""
        semantic_mapping = _to_sssom_pydantic(
            TEST_MAPPING_1,
            TEST_MAPPING_1.evidence[0],
            subject=TEST_MAPPING_1.subject,
            object=TEST_MAPPING_1.object,
        )
        assert_semantic_mapping_equal(self, TEST_SSSOM_MAPPING_1, semantic_mapping)

    def test_to_sssom_pydantic_reasoned(self) -> None:
        """Test converting a reasoned evidence to Pydantic."""
        self.assertIsNotNone(TEST_MAPPING_6.subject.name)
        self.assertIsNotNone(TEST_MAPPING_6.object.name)
        self.assertIsNotNone(TEST_SSSOM_MAPPING_6.subject.name)
        self.assertIsNotNone(TEST_SSSOM_MAPPING_6.object.name)

        semantic_mapping = _to_sssom_pydantic(
            TEST_MAPPING_6,
            TEST_MAPPING_6.evidence[0],
            subject=TEST_MAPPING_6.subject,
            object=TEST_MAPPING_6.object,
        )
        assert_semantic_mapping_equal(self, TEST_SSSOM_MAPPING_6, semantic_mapping)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir).joinpath("test.sssom.tsv")
            write_sssom(
                [TEST_MAPPING_6],
                path,
                converter=CONVERTER,
                metadata=MappingSet(id="https://example.org/test.sssom.tsv"),
            )

            x = sssom_pydantic.read(path, return_errors=True)
            self.assertEqual([], x[3], msg="errors were returned!")

            self.assertEqual(
                dedent("""\
                    #curie_map:
                    #  cas: https://commonchemistry.cas.org/detail?cas_rn=
                    #  mapping: https://w3id.org/mapping/
                    #  mesh: https://meshb.nlm.nih.gov/record/ui?ui=
                    #  semapv: https://w3id.org/semapv/vocab/
                    #  skos: http://www.w3.org/2004/02/skos/core#
                    #  wikidata: http://www.wikidata.org/entity/
                    #mapping_set_id: https://example.org/test.sssom.tsv
                    subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification	license	mapping_source	derived_from	comment
                    mesh:C027957	tyramine O-sulfate	skos:exactMatch	cas:30223-92-8	Tyramine sulfate	semapv:MappingChaining	https://creativecommons.org/publicdomain/zero/1.0/	wikidata:Q127259663	mapping:ba04ff1967c311ddb2e8d1ee5eecff61d5e993f4128270464242abca4bb188b4|mapping:a0022401f47964288ecc1ab706d79b4d4abc10edf33d0a71953834a0b0b3c24c	mesh:C027957 chebi:133530 cas:30223-92-8
                """),
                path.read_text(),
            )


def _filter_simple(mappings: list[Mapping]) -> list[Mapping]:
    rv = []
    for mapping in mappings:
        if all(
            isinstance(e, ReasonedEvidence) or e.justification == CHAIN_MAPPING
            for e in mapping.evidence
        ):
            continue
        rv.append(mapping)
    return sorted(rv)
