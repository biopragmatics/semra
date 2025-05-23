"""Tests for I/O functions."""

import getpass
import itertools as itt
import tempfile
import unittest
from pathlib import Path

import bioregistry
import pandas as pd
import sssom.io
import sssom.validators

from semra import Mapping, MappingSet, ReasonedEvidence, Reference, SimpleEvidence
from semra.api import assemble_evidences
from semra.io import (
    from_digraph,
    from_jsonl,
    from_multidigraph,
    from_pickle,
    from_pyobo,
    from_sssom,
    from_sssom_df,
    to_digraph,
    to_multidigraph,
    write_jsonl,
    write_pickle,
    write_sssom,
)
from semra.rules import (
    BEN_ORCID,
    CHAIN_MAPPING,
    EXACT_MATCH,
    LEXICAL_MAPPING,
    MANUAL_MAPPING,
    UNSPECIFIED_MAPPING,
    charlie,
)
from semra.struct import Triple
from tests.constants import a1, a1_curie, a2, a2_curie, b1, b1_curie, b2, b2_curie

LOCAL = getpass.getuser() == "cthoyt"

mapping_set_title = "test"
mapping_set_confidence = 0.6


@unittest.skipUnless(LOCAL, reason="Don't test remotely since PyOBO content isn't available")
class TestIOLocal(unittest.TestCase):
    """Test I/O functions that only run if pyobo is available."""

    def test_from_pyobo(self) -> None:
        """Test loading content from PyOBO."""
        mappings = from_pyobo("doid")
        for mapping in mappings:
            self.assertEqual("doid", mapping.subject.prefix)

        mappings_2 = from_pyobo("doid", "mesh")
        for mapping in mappings_2:
            self.assertEqual("doid", mapping.subject.prefix)
            self.assertEqual("mesh", mapping.object.prefix)


class TestSSSOM(unittest.TestCase):
    """Tests for I/O functions."""

    def test_from_sssom_df(self) -> None:
        """Test importing mappings from a SSSOM dataframe."""
        expected_evidence = SimpleEvidence(
            mapping_set=MappingSet(
                name=mapping_set_title,
                confidence=mapping_set_confidence,
            ),
            justification=UNSPECIFIED_MAPPING,
        )
        expected_mappings = [
            Mapping(subject=a1, predicate=EXACT_MATCH, object=b1, evidence=[expected_evidence]),
            Mapping(subject=a2, predicate=EXACT_MATCH, object=b2, evidence=[expected_evidence]),
        ]

        # Test 1 - from kwargs
        rows = [
            (a1_curie, "skos:exactMatch", "exact match", b1_curie),
            (a2_curie, "skos:exactMatch", "exact match", b2_curie),
        ]
        columns = [
            "subject_id",
            "predicate_id",
            "predicate_label",
            "object_id",
        ]
        df = pd.DataFrame(rows, columns=columns)
        actual_mappings = from_sssom_df(
            df,
            mapping_set_title=mapping_set_title,
            mapping_set_confidence=mapping_set_confidence,
        )
        self.assertEqual(expected_mappings, actual_mappings)

        # Test 2 - from columns (partial)
        rows_test_2 = [
            (a1_curie, "skos:exactMatch", "exact match", b1_curie, mapping_set_title),
            (a2_curie, "skos:exactMatch", "exact match", b2_curie, mapping_set_title),
        ]
        columns = [
            "subject_id",
            "predicate_id",
            "predicate_label",
            "object_id",
            "mapping_set_name",
        ]
        df = pd.DataFrame(rows_test_2, columns=columns)
        actual_mappings = from_sssom_df(
            df,
            mapping_set_confidence=mapping_set_confidence,
        )
        self.assertEqual(expected_mappings, actual_mappings)

        # Test 3 - from columns (full)
        rows_test_3 = [
            (
                a1_curie,
                "skos:exactMatch",
                "exact match",
                b1_curie,
                mapping_set_title,
                mapping_set_confidence,
            ),
            (
                a2_curie,
                "skos:exactMatch",
                "exact match",
                b2_curie,
                mapping_set_title,
                mapping_set_confidence,
            ),
        ]
        columns = [
            "subject_id",
            "predicate_id",
            "predicate_label",
            "object_id",
            "mapping_set_name",
            "mapping_set_confidence",
        ]
        df = pd.DataFrame(rows_test_3, columns=columns)
        actual_mappings = from_sssom_df(df)
        self.assertEqual(expected_mappings, actual_mappings)

    def test_from_sssom_df_with_license(self) -> None:
        """Test loading a SSSOM dataframe that has a license."""
        test_license = "CC0"
        test_version = "1.0"
        expected_evidence = SimpleEvidence(
            mapping_set=MappingSet(
                name=mapping_set_title,
                confidence=mapping_set_confidence,
                license=test_license,
                version=test_version,
            ),
            justification=UNSPECIFIED_MAPPING,
        )
        expected_mappings = [
            Mapping(subject=a1, predicate=EXACT_MATCH, object=b1, evidence=[expected_evidence]),
            Mapping(subject=a2, predicate=EXACT_MATCH, object=b2, evidence=[expected_evidence]),
        ]

        rows = [
            (a1_curie, "skos:exactMatch", "exact match", b1_curie),
            (a2_curie, "skos:exactMatch", "exact match", b2_curie),
        ]
        columns = [
            "subject_id",
            "predicate_id",
            "predicate_label",
            "object_id",
        ]
        df = pd.DataFrame(rows, columns=columns)
        actual_mappings = from_sssom_df(
            df,
            mapping_set_title=mapping_set_title,
            mapping_set_confidence=mapping_set_confidence,
            license=test_license,
            version=test_version,
        )
        self.assertEqual(expected_mappings, actual_mappings)


class TestIO(unittest.TestCase):
    """Test I/O funcitons."""

    def setUp(self) -> None:
        """Set up the test case."""
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
        chembl = MappingSet(
            purl="https://example.org/test-1",
            name="chembl",
            confidence=0.90,
            license="CC-BY-SA-3.0",
        )
        lexical_ms = MappingSet(purl="https://example.org/test-2", name="lexical", confidence=0.90)

        m1_e1 = SimpleEvidence(
            mapping_set=biomappings, justification=MANUAL_MAPPING, author=charlie, confidence=0.99
        )

        # check that making an identical evidence gives the same hex digest
        m1_e1_copy = SimpleEvidence(
            mapping_set=biomappings, justification=MANUAL_MAPPING, author=charlie, confidence=0.99
        )
        self.assertEqual(m1_e1.hexdigest(t1), m1_e1_copy.hexdigest(t1))

        m1_e2 = SimpleEvidence(
            mapping_set=biomappings, justification=MANUAL_MAPPING, author=BEN_ORCID, confidence=0.94
        )
        m1_e3 = SimpleEvidence(
            mapping_set=lexical_ms, justification=LEXICAL_MAPPING, confidence=0.8
        )

        m1 = Mapping.from_triple(t1, evidence=[m1_e1, m1_e2, m1_e3])

        m2_e1 = SimpleEvidence(
            mapping_set=chembl, justification=UNSPECIFIED_MAPPING, confidence=0.90
        )
        m2 = Mapping.from_triple(t2, evidence=[m2_e1])

        m3_e1 = ReasonedEvidence(justification=CHAIN_MAPPING, mappings=[m1, m2])
        m3 = Mapping.from_triple(t3, evidence=[m3_e1])

        self.mappings = [m1, m2, m3]

    def test_jsonl(self) -> None:
        """Test JSONL I/O."""
        with tempfile.TemporaryDirectory() as directory_:
            for path in [
                Path(directory_).joinpath("test.jsonl"),
                Path(directory_).joinpath("test.jsonl.gz"),
            ]:
                write_jsonl(self.mappings, path)
                new_mappings = from_jsonl(path, show_progress=False)
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
        with tempfile.TemporaryDirectory() as directory_:
            for path in [
                Path(directory_).joinpath("test.pkl"),
                Path(directory_).joinpath("test.pkl.gz"),
            ]:
                write_pickle(self.mappings, path)
                new_mappings = from_pickle(path)
                self.assertEqual(self.mappings, new_mappings)

    def test_sssom(self) -> None:
        """Test I/O with SSSOM."""
        prefix_map = {
            "mesh": bioregistry.get_uri_prefix("mesh"),
            "orcid": bioregistry.get_uri_prefix("orcid"),
            "chembl.compound": bioregistry.get_uri_prefix("chembl.compound"),
            "chebi": bioregistry.get_uri_prefix("chebi"),
        }
        with tempfile.TemporaryDirectory() as directory_:
            for path, prune in itt.product(
                [
                    Path(directory_).joinpath("test.sssom.tsv"),
                    Path(directory_).joinpath("test.sssom.tsv.gz"),
                ],
                [True, False],
            ):
                write_sssom(self.mappings, path, prune=prune)
                new_mappings = assemble_evidences(from_sssom(path), progress=False)

                if not path.suffix.endswith(".gz"):
                    # check gz after addressing https://github.com/mapping-commons/sssom-py/issues/581
                    msdf = sssom.io.parse_sssom_table(path, prefix_map=prefix_map)

                    reports = sssom.validators.validate(msdf, fail_on_error=False)
                    self.assertNotEqual(0, len(reports), msg="no reports generated")
                    for validator, report in reports.items():
                        with self.subTest(msg=f"SSSOM Validation: {validator.name}"):
                            self.assertEqual([], report.results)

                with self.subTest(msg="reconstitution"):
                    # TODO update to also work for reasoned?
                    self.assertEqual(_filter_simple(self.mappings), _filter_simple(new_mappings))


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
