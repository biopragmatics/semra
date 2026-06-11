"""Tests for the core SeMRA API."""

from __future__ import annotations

import unittest
from collections.abc import Iterable
from itertools import islice
from typing import cast

import curies
import pandas as pd
from curies import vocabulary as v
from curies.vocabulary import unspecified_matching_process
from more_itertools import triplewise
from pydantic import BaseModel
from sssom_pydantic import SemanticMapping

from semra import api
from semra.api import (
    Index,
    Mutation,
    count_component_sizes,
    count_coverage_sizes,
    filter_mappings,
    filter_self_matches,
    flip,
    get_index,
    get_many_to_many,
    keep_prefixes,
    prioritize,
    prioritize_df,
    project,
)
from semra.inference import infer_chains, infer_mutations, infer_reversible
from semra.io.graph import from_digraph, to_digraph
from semra.struct import Mapping, ReasonedEvidence, Reference, SimpleEvidence
from semra.vocabulary import (
    BROAD_MATCH,
    DB_XREF,
    EXACT_MATCH,
    KNOWLEDGE_MAPPING,
    NARROW_MATCH,
)
from tests.constants import TEST_MAPPING_SET

PREFIX_A = "go"
PREFIX_B = "mondo"
PREFIX_C = "ido"
PREFIX_D = "obi"
PREFIXES = [PREFIX_A, PREFIX_B, PREFIX_C, PREFIX_D]


def _get_references(
    n: int, *, prefix: str = PREFIX_A, different_prefixes: bool = False
) -> list[Reference]:
    if different_prefixes:
        if n > len(PREFIXES):
            raise ValueError("need to add more default prefixes")
        prefixes = PREFIXES[:n]
    else:
        prefixes = [prefix for _ in range(n)]
    identifiers = [str(i + 1).zfill(7) for i in range(n)]
    return [
        Reference(prefix=prefix, identifier=identifier)
        for prefix, identifier in zip(prefixes, identifiers, strict=False)
    ]


def line(*references: curies.NamableReference) -> list[Mapping]:
    """Create a list of mappings from a simple mappings path."""
    if not (3 <= len(references) and len(references) % 2):
        raise ValueError
    return [
        Mapping.from_sssom_pydantic(
            mapping=SemanticMapping(
                subject=Reference.from_reference(subject),
                predicate=Reference.from_reference(predicate),
                object=Reference.from_reference(obj),
                justification=v.unspecified_matching_process,
            ),
            mapping_set=TEST_MAPPING_SET,
        )
        for subject, predicate, obj in islice(triplewise(references), None, None, 2)
    ]


def _exact(subject: curies.NamableReference, object: curies.NamableReference) -> Mapping:
    mapping = SemanticMapping.exact(subject, object)
    return Mapping.from_sssom_pydantic(mapping, TEST_MAPPING_SET)


def _broad(subject: curies.NamableReference, object: curies.NamableReference) -> Mapping:
    mapping = SemanticMapping.broad(subject, object)
    return Mapping.from_sssom_pydantic(mapping, TEST_MAPPING_SET)


def _narrow(subject: curies.NamableReference, object: curies.NamableReference) -> Mapping:
    mapping = SemanticMapping.narrow(subject, object)
    return Mapping.from_sssom_pydantic(mapping, TEST_MAPPING_SET)


def _dbxref(subject: curies.NamableReference, object: curies.NamableReference) -> Mapping:
    mapping = SemanticMapping(
        subject=subject,
        predicate=DB_XREF,
        object=object,
        justification=v.unspecified_matching_process,
    )
    return Mapping.from_sssom_pydantic(mapping, TEST_MAPPING_SET)


class TestOperations(unittest.TestCase):
    """Test mapping operations."""

    def assert_models_equal(
        self,
        models: Iterable[BaseModel],
        actual: Iterable[BaseModel],
        *,
        exclude_none: bool = True,
        msg: str | None = None,
    ) -> None:
        """Check two model sequences are equal after dumping as JSON."""
        self.assertEqual(
            [m.model_dump(exclude_none=exclude_none, mode="json") for m in models],
            [m.model_dump(exclude_none=exclude_none, mode="json") for m in actual],
            msg=msg,
        )

    def test_path(self) -> None:
        """Test quickly creating mapping lists."""
        r1, r2, r3 = _get_references(3)
        m1 = _exact(r1, r2)
        m2 = _broad(r2, r3)
        self.assert_models_equal([m1], line(r1, v.exact_match, r2))
        self.assert_models_equal([m1, m2], line(r1, v.exact_match, r2, v.broad_match, r3))

    def test_flip_symmetric(self) -> None:
        """Test flipping a symmetric relation (e.g., exact match)."""
        chebi_reference = Reference(prefix="chebi", identifier="10001")
        mesh_reference = Reference(prefix="mesh", identifier="C067604")
        mapping = _exact(chebi_reference, mesh_reference)
        new_mapping = flip(mapping)
        self.assertIsNotNone(new_mapping)
        self.assertEqual(mesh_reference, new_mapping.subject)
        self.assertEqual(EXACT_MATCH, new_mapping.predicate)
        self.assertEqual(chebi_reference, new_mapping.object)
        self.assertEqual(1, len(new_mapping.evidence))
        self.assertIsInstance(new_mapping.evidence[0], ReasonedEvidence)
        evidence: ReasonedEvidence = cast(ReasonedEvidence, new_mapping.evidence[0])
        self.assertIsInstance(evidence.mappings[0].evidence[0], SimpleEvidence)
        self.assertEqual(mapping.evidence[0], evidence.mappings[0].evidence[0])

    def test_flip_asymmetric(self) -> None:
        """Test flipping asymmetric relations (e.g., narrow and broad match)."""
        docetaxel_mesh = Reference(prefix="mesh", identifier="D000077143")
        docetaxel_anhydrous_chebi = Reference(prefix="chebi", identifier="4672")
        narrow_mapping = _narrow(docetaxel_mesh, docetaxel_anhydrous_chebi)
        broad_mapping = _broad(docetaxel_mesh, docetaxel_anhydrous_chebi)

        narrow_mapping_flipped: Mapping = flip(narrow_mapping)
        self.assertIsNotNone(narrow_mapping_flipped)
        self.assertEqual(narrow_mapping.object, narrow_mapping_flipped.subject)
        self.assertEqual(BROAD_MATCH, narrow_mapping_flipped.predicate)
        self.assertEqual(narrow_mapping.subject, narrow_mapping_flipped.object)

        broad_mapping_flipped: Mapping = flip(broad_mapping)
        self.assertIsNotNone(broad_mapping_flipped)
        self.assertEqual(broad_mapping.object, broad_mapping_flipped.subject)
        self.assertEqual(NARROW_MATCH, broad_mapping_flipped.predicate)
        self.assertEqual(broad_mapping.subject, broad_mapping_flipped.object)

    def test_index(self) -> None:
        """Test indexing semantic mappings."""
        r1, r2 = _get_references(2)
        e1 = SimpleEvidence(
            mapping=SemanticMapping.exact(r1, r2, justification=v.lexical_matching_process),
            mapping_set=TEST_MAPPING_SET,
        )
        e2 = SimpleEvidence(
            mapping=SemanticMapping.exact(r1, r2, justification=v.manual_mapping_curation),
            mapping_set=TEST_MAPPING_SET,
        )
        m1 = Mapping(subject=r1, predicate=EXACT_MATCH, object=r2, evidence=[e1])
        m2 = Mapping(subject=r1, predicate=EXACT_MATCH, object=r2, evidence=[e2])
        index = get_index([m1, m2], progress=False)
        self.assertIn(m1.triple, index)
        self.assertEqual(1, len(index))
        self.assertEqual(2, len(index[m1.triple]))
        self.assertEqual(
            {v.lexical_matching_process.identifier, v.manual_mapping_curation.identifier},
            {
                e.justification.identifier
                if e.justification
                else unspecified_matching_process.curie
                for e in index[m1.triple]
            },
        )

    def assert_same_triples(
        self,
        expected_mappings: Index | list[Mapping],
        actual_mappings: Index | list[Mapping],
        msg: str | None = None,
    ) -> None:
        """Assert that two sets of mappings are the same."""
        if not isinstance(expected_mappings, dict):
            expected_mappings = get_index(expected_mappings, progress=False)
        if not isinstance(actual_mappings, dict):
            actual_mappings = get_index(actual_mappings, progress=False)

        self.assertEqual(
            self._clean_index(expected_mappings),
            self._clean_index(actual_mappings),
            msg=msg,
        )

    @staticmethod
    def _clean_index(index: Index) -> list[str]:
        triples = sorted(set(index))
        return [
            f"<{triple.subject.curie}, {triple.predicate.curie}, {triple.object.curie}>"
            for triple in triples
        ]

    def test_infer_exact_match(self) -> None:
        """Test inference through the transitivity of SKOS exact matches."""
        r1, r2, r3, r4 = _get_references(4, different_prefixes=True)
        m1, m2, m3 = line(r1, EXACT_MATCH, r2, EXACT_MATCH, r3, EXACT_MATCH, r4)
        m4 = _exact(r1, r3)
        m5 = _exact(r1, r4)
        m6 = _exact(r2, r4)
        m4_inv, m5_inv, m6_inv = (flip(m, strict=True) for m in (m4, m5, m6))

        backwards_msg = "backwards inference is not supposed to be done here"

        index = get_index(infer_chains([m1, m2], backwards=False, progress=False), progress=False)
        self.assertNotIn(m4_inv.triple, index, msg=backwards_msg)

        index = get_index(
            infer_chains([m1, m2, m3], backwards=False, progress=False), progress=False
        )
        self.assert_same_triples([m1, m2, m3, m4, m4, m5, m6], index)
        self.assertNotIn(m4_inv.triple, index, msg=backwards_msg)
        self.assertNotIn(m5_inv.triple, index, msg=backwards_msg)
        self.assertNotIn(m6_inv.triple, index, msg=backwards_msg)

        # m4's evidence should comprise a single complex evidence
        self.assertEqual(1, len(index[m4.triple]))
        m4_evidence = index[m4.triple][0]
        self.assertIsInstance(m4_evidence, ReasonedEvidence)
        m4_evidence_narrowed = cast(ReasonedEvidence, m4_evidence)
        self.assertEqual(2, len(m4_evidence_narrowed.mappings))
        self.assertEqual([m1, m2], m4_evidence_narrowed.mappings)

    def test_no_infer(self) -> None:
        """Test no inference happens over mixed chains of broad/narrow."""
        r1, r2, r3 = _get_references(3)

        m1, m2 = line(r1, NARROW_MATCH, r2, BROAD_MATCH, r3)
        self.assert_same_triples(
            [m1, m2],
            infer_chains([m1, m2], progress=False),
            msg="No inference between broad and narrow",
        )

        # ------ Same but in reverse ---------
        m1, m2 = line(r1, BROAD_MATCH, r2, NARROW_MATCH, r3)
        self.assert_same_triples(
            [m1, m2],
            infer_chains([m1, m2], progress=False),
            msg="No inference between broad and narrow",
        )

    def test_infer_broad_match_1(self) -> None:
        """Test inferring broad matches."""
        r1, r2, r3, r4 = _get_references(4, different_prefixes=True)
        m1, m2, m3 = line(r1, v.exact_match, r2, v.broad_match, r3, v.exact_match, r4)
        m4 = _broad(r1, r3)
        m5 = _broad(r1, r4)
        m6 = _broad(r2, r4)
        m4_i = _narrow(r3, r1)
        m5_i = _narrow(r4, r1)
        m6_i = _narrow(r4, r2)

        # Check inference over two steps
        self.assert_same_triples(
            [m1, m2, m4],
            infer_chains([m1, m2], backwards=False, progress=False),
            msg="inference over two steps is broken",
        )
        self.assert_same_triples(
            [m1, m2, m4, m4_i],
            infer_chains([m1, m2], backwards=True, progress=False),
            msg="inference over two steps is broken",
        )

        self.assert_same_triples(
            [m1, m2, m3, m4, m5, m6],
            infer_chains([m1, m2, m3], backwards=False, progress=False),
            msg="inference over multiple steps is broken",
        )
        self.assert_same_triples(
            [m1, m2, m3, m4, m5, m4_i, m6, m5_i, m6_i],
            infer_chains([m1, m2, m3], backwards=True, progress=False),
            msg="inference over multiple steps is broken",
        )

    def test_infer_broad_match_2(self) -> None:
        """Test inferring broad matches."""
        r1, r2, r3, r4 = _get_references(4, different_prefixes=True)
        m1, m2, m3 = line(r1, BROAD_MATCH, r2, EXACT_MATCH, r3, BROAD_MATCH, r4)
        m4 = Mapping(subject=r1, predicate=BROAD_MATCH, object=r3)
        m5 = Mapping(subject=r1, predicate=BROAD_MATCH, object=r4)
        m6 = Mapping(subject=r2, predicate=BROAD_MATCH, object=r4)
        m4_i = Mapping(object=r1, predicate=NARROW_MATCH, subject=r3)
        m5_i = Mapping(object=r1, predicate=NARROW_MATCH, subject=r4)
        m6_i = Mapping(object=r2, predicate=NARROW_MATCH, subject=r4)

        # Check inference over two steps
        self.assert_same_triples(
            [m1, m2, m4], infer_chains([m1, m2], backwards=False, progress=False)
        )
        self.assert_same_triples(
            [m1, m2, m4, m4_i], infer_chains([m1, m2], backwards=True, progress=False)
        )

        # Check inference over multiple steps
        self.assert_same_triples(
            [m1, m2, m3, m4, m5, m6], infer_chains([m1, m2, m3], backwards=False, progress=False)
        )
        self.assert_same_triples(
            [m1, m2, m3, m4, m5, m6, m4_i, m5_i, m6_i],
            infer_chains([m1, m2, m3], backwards=True, progress=False),
        )

    def test_infer_narrow_match(self) -> None:
        """Test inferring narrow matches."""
        r1, r2, r3 = _get_references(3, different_prefixes=True)
        m1, m2 = line(r1, EXACT_MATCH, r2, NARROW_MATCH, r3)
        m3 = Mapping(subject=r1, predicate=NARROW_MATCH, object=r3)
        m3_i = Mapping(object=r1, predicate=BROAD_MATCH, subject=r3)
        self.assert_same_triples(
            [m1, m2, m3], infer_chains([m1, m2], backwards=False, progress=False)
        )
        self.assert_same_triples(
            [m1, m2, m3, m3_i], infer_chains([m1, m2], backwards=True, progress=False)
        )

    def test_mixed_inference_1(self) -> None:
        """Test inferring over a mix of narrow, broad, and exact matches."""
        r1, r2, r3 = _get_references(3, different_prefixes=True)
        m1 = Mapping(subject=r1, predicate=EXACT_MATCH, object=r2)
        m2 = Mapping(subject=r2, predicate=NARROW_MATCH, object=r3)
        m3 = Mapping(subject=r1, predicate=NARROW_MATCH, object=r3)

        m4 = Mapping(subject=r2, predicate=EXACT_MATCH, object=r1)
        m5 = Mapping(subject=r3, predicate=BROAD_MATCH, object=r2)
        m6 = Mapping(subject=r3, predicate=BROAD_MATCH, object=r1)

        mappings = [m1, m2]
        mappings = infer_reversible(mappings, progress=False)
        self.assert_same_triples([m1, m2, m4, m5], mappings)

        mappings = infer_chains(mappings, progress=False)
        self.assert_same_triples([m1, m2, m3, m4, m5, m6], mappings)

    def test_filter_prefixes(self) -> None:
        """Test filtering out unwanted prefixes."""
        r11, r12 = _get_references(2, prefix=PREFIX_A)
        r21, r22 = _get_references(2, prefix=PREFIX_B)
        (r31,) = _get_references(1, prefix=PREFIX_C)
        m1 = Mapping(subject=r11, predicate=EXACT_MATCH, object=r21)
        m2 = Mapping(subject=r12, predicate=EXACT_MATCH, object=r22)
        m3 = Mapping(subject=r11, predicate=EXACT_MATCH, object=r31)
        mappings = [m1, m2, m3]
        self.assert_same_triples(
            [m1, m2], keep_prefixes(mappings, {PREFIX_A, PREFIX_B}, progress=False)
        )

    def test_filter_self(self) -> None:
        """Test filtering out mappings within a given prefix."""
        r11, r12, r13 = _get_references(3, prefix=PREFIX_A)
        r21, r22 = _get_references(2, prefix=PREFIX_B)
        m1 = Mapping(subject=r11, predicate=EXACT_MATCH, object=r21)
        m2 = Mapping(subject=r12, predicate=EXACT_MATCH, object=r22)
        m3 = Mapping(subject=r11, predicate=EXACT_MATCH, object=r13)
        mappings = [m1, m2, m3]
        self.assert_same_triples([m1, m2], filter_self_matches(mappings, progress=False))

    def test_filter_negative(self) -> None:
        """Test filtering out mappings within a given prefix."""
        r11, r12 = _get_references(2, prefix=PREFIX_A)
        r21, r22 = _get_references(2, prefix=PREFIX_B)
        m1 = Mapping(subject=r11, predicate=EXACT_MATCH, object=r21)
        m2 = Mapping(subject=r12, predicate=EXACT_MATCH, object=r22)
        mappings = [m1, m2]
        negative = [m2]
        self.assert_same_triples([m1], filter_mappings(mappings, negative, progress=False))

    def test_project(self) -> None:
        """Test projecting into a given source/target pair."""
        r11, r12 = _get_references(2, prefix=PREFIX_A)
        r21, r22 = _get_references(2, prefix=PREFIX_B)
        (r31,) = _get_references(1, prefix=PREFIX_C)
        m1 = Mapping(subject=r11, predicate=EXACT_MATCH, object=r21)
        m2 = Mapping(subject=r12, predicate=EXACT_MATCH, object=r22)
        m2_i = Mapping(object=r12, predicate=EXACT_MATCH, subject=r22)
        m3 = Mapping(subject=r11, predicate=EXACT_MATCH, object=r31)
        mappings = [m1, m2, m2_i, m3]
        self.assert_same_triples(
            [m1, m2], project(mappings, PREFIX_A, PREFIX_B, progress=False, return_sus=False)
        )

    def test_get_many_to_many(self) -> None:
        """Test getting many-to-many mappings."""
        a1, a2, a3 = _get_references(3, prefix=PREFIX_A)
        b1, b2, b3 = _get_references(3, prefix=PREFIX_B)

        # Subject duplicate
        m1 = Mapping(subject=a1, predicate=EXACT_MATCH, object=b1)
        m2 = Mapping(subject=a1, predicate=EXACT_MATCH, object=b3)
        m3 = Mapping(subject=a2, predicate=EXACT_MATCH, object=b2)
        self.assert_same_triples([m1, m2], get_many_to_many([m1, m2, m3]))

        m4 = Mapping(subject=a3, predicate=EXACT_MATCH, object=b2)
        self.assert_same_triples([m3, m4], get_many_to_many([m2, m3, m4]))

    def test_filter_confidence(self) -> None:
        """Test filtering by confidence."""
        (a1, _a2) = _get_references(2, prefix=PREFIX_A)
        (b1, _b2) = _get_references(2, prefix=PREFIX_B)

        s1 = SemanticMapping(
            subject=a1,
            predicate=DB_XREF,
            object=b1,
            confidence=0.95,
            justification=v.unspecified_matching_process,
        )
        m1 = Mapping.from_sssom_pydantic(s1, TEST_MAPPING_SET)
        s2 = SemanticMapping(
            subject=a1,
            predicate=DB_XREF,
            object=b1,
            confidence=0.65,
            justification=v.unspecified_matching_process,
        )
        m2 = Mapping.from_sssom_pydantic(s2, TEST_MAPPING_SET)
        mmm = list(api.filter_minimum_confidence([m1, m2], cutoff=0.7))
        self.assertEqual([m1], mmm)

    def test_filter_subsets(self) -> None:
        """Test filtering by subsets."""
        a1, a2 = _get_references(2, prefix=PREFIX_A)
        b1, b2 = _get_references(2, prefix=PREFIX_B)
        c1, _c2 = _get_references(2, prefix=PREFIX_C)
        m1 = _exact(a1, b1)
        m2 = _exact(b1, a1)
        m3 = _exact(a2, b2)
        m4 = _exact(b2, a2)
        m5 = _exact(b1, c1)
        m6 = _exact(c1, b1)

        terms = {
            PREFIX_A: [a1, a2],
            PREFIX_B: [b1],
        }
        mmm = list(api.filter_subsets([m1, m2, m3, m4, m5, m6], terms))
        self.assertEqual(
            [m1, m2, m5, m6],
            mmm,
            msg="Mappings 3 and 4 should not pass since b2 is not in the term filter",
        )

        terms = {
            PREFIX_A: [a1, a2],
            PREFIX_B: [b1],
            PREFIX_C: [],
        }
        # the fact that c has an empty dictionary will get ignored
        mmm = list(api.filter_subsets([m1, m2, m3, m4, m5, m6], terms))
        self.assertEqual(
            [m1, m2, m5, m6],
            mmm,
            msg="Mappings 3 and 4 should not pass since b2 is not in the term filter",
        )

    def test_count_component_sizes(self) -> None:
        """Test counting component sizes."""
        priority = [PREFIX_A, PREFIX_B, PREFIX_C]
        a1, a2 = _get_references(2, prefix=PREFIX_A)
        b1, b2 = _get_references(2, prefix=PREFIX_B)
        c1, _ = _get_references(2, prefix=PREFIX_C)

        m1 = _exact(a1, b1)
        m2 = _exact(b1, c1)
        m3 = _exact(a2, b2)

        sm4 = SemanticMapping(
            subject=a2, predicate=DB_XREF, object=b2, justification=v.unspecified_matching_process
        )
        m4 = Mapping.from_sssom_pydantic(sm4, TEST_MAPPING_SET)  # this shouldn't hae an effect

        mappings = [m1, m2, m3, m4]
        self.assertEqual(
            {frozenset([PREFIX_A, PREFIX_B]): 1, frozenset([PREFIX_A, PREFIX_B, PREFIX_C]): 1},
            dict(count_component_sizes(mappings, priority)),
        )
        self.assertEqual({1: 0, 2: 1, 3: 1}, dict(count_coverage_sizes(mappings, priority)))

    def test_digraph_roundtrip(self) -> None:
        """Test I/O roundtrip through a directed graph."""
        a1, a2 = _get_references(2, prefix=PREFIX_A)
        b1, b2 = _get_references(2, prefix=PREFIX_B)
        c1, _ = _get_references(2, prefix=PREFIX_C)

        m1 = _exact(a1, b1)
        m2 = _exact(b1, c1)
        m3 = _exact(a2, b2)
        m4 = _dbxref(a2, b2)  # this shouldn't hae an effect
        mappings = [m1, m2, m3, m4]
        self.assertEqual(mappings, from_digraph(to_digraph(mappings)))

    def test_prioritize_df(self) -> None:
        """Test prioritizing entities in a column in a dataframe."""
        a1, a2 = _get_references(2, prefix=PREFIX_A)
        b1, b2 = _get_references(2, prefix=PREFIX_B)
        m1 = _exact(a1, b1)
        m2 = _exact(a2, b2)

        rows = [("r1", a1.curie), ("r2", a2.curie)]
        df = pd.DataFrame(rows, columns=["label", "curie"])

        prioritize_df([m1, m2], df, column="curie")

        self.assertEqual(
            [b1.curie, b2.curie],
            list(df["curie_prioritized"]),
        )

    def test_prioritize(self) -> None:
        """Test prioritize."""
        a1 = Reference(prefix=PREFIX_A, identifier="0000001")
        b1 = Reference(prefix=PREFIX_B, identifier="0000002")
        c1 = Reference(prefix=PREFIX_C, identifier="0000003")
        a1_exact_b1 = _exact(a1, b1)
        b1_exact_a1 = _exact(b1, a1)
        b1_exact_c1 = _exact(b1, c1)
        c1_exact_b1 = _exact(c1, b1)
        a1_exact_c1 = _exact(a1, c1)
        c1_exact_a1 = _exact(c1, a1)

        # can't address priority
        self.assert_same_triples(
            [],
            prioritize(
                [a1_exact_b1, b1_exact_a1, b1_exact_c1, c1_exact_b1, a1_exact_c1, c1_exact_a1],
                [PREFIX_D],
                progress=False,
            ),
        )

        # has unusable priority first, but then defaults
        self.assert_same_triples(
            [b1_exact_a1, c1_exact_a1],
            prioritize(
                [a1_exact_b1, b1_exact_a1, b1_exact_c1, c1_exact_b1, a1_exact_c1, c1_exact_a1],
                [PREFIX_D, PREFIX_A],
                progress=False,
            ),
        )

        self.assert_same_triples(
            [b1_exact_a1, c1_exact_a1],
            prioritize(
                [a1_exact_b1, b1_exact_a1, b1_exact_c1, c1_exact_b1, a1_exact_c1, c1_exact_a1],
                [PREFIX_A],
                progress=False,
            ),
        )
        self.assert_same_triples(
            [a1_exact_b1, c1_exact_b1],
            prioritize(
                [a1_exact_b1, b1_exact_a1, b1_exact_c1, c1_exact_b1, a1_exact_c1, c1_exact_a1],
                [PREFIX_B],
                progress=False,
            ),
        )
        self.assert_same_triples(
            [b1_exact_c1, a1_exact_c1],
            prioritize(
                [a1_exact_b1, b1_exact_a1, b1_exact_c1, c1_exact_b1, a1_exact_c1, c1_exact_a1],
                [PREFIX_C],
                progress=False,
            ),
        )

        # test on component with only 1
        self.assert_same_triples(
            [b1_exact_a1],
            prioritize([a1_exact_b1, b1_exact_a1], [PREFIX_A], progress=False),
        )
        self.assert_same_triples(
            [a1_exact_b1],
            prioritize([a1_exact_b1, b1_exact_a1], [PREFIX_B], progress=False),
        )
        self.assert_same_triples(
            [],
            prioritize([a1_exact_b1, b1_exact_a1], [PREFIX_C], progress=False),
        )

        # the following three tests reflect that the prioritize() function
        # is not implemented in cases when inference hasn't been fully done
        # self.assert_same_triples([m1_rev], prioritize([m1, m2], [PREFIX_A], progress=False))
        # self.assert_same_triples([m2], prioritize([m1, m2], [PREFIX_C], progress=False))

        # this one is able to complete, by chance, but it's not part of
        # the contract, so just left here for later
        # self.assertEqual([m1, m2_rev], prioritize([m1, m2], [PREFIX_B], progress=False))


class TestUpgrades(unittest.TestCase):
    """Test inferring mutations."""

    def test_infer_mutations(self) -> None:
        """Test inferring mutations."""
        (a1,) = _get_references(1, prefix=PREFIX_A)
        (b1,) = _get_references(1, prefix=PREFIX_B)
        original_confidence = 0.95
        mutation_confidence = 0.80
        e = SemanticMapping(
            subject=a1,
            predicate=DB_XREF,
            object=b1,
            justification=v.unspecified_matching_process,
            confidence=original_confidence,
        )

        m1 = Mapping.from_sssom_pydantic(e, TEST_MAPPING_SET)
        new_mappings = infer_mutations(
            [m1],
            {(PREFIX_A, PREFIX_B): mutation_confidence},
            old_predicate=DB_XREF,
            new_predicate=EXACT_MATCH,
            progress=False,
        )
        self.assertEqual(2, len(new_mappings))
        new_m1, new_m2 = new_mappings
        self.assertEqual(m1, new_m1)
        self.assertEqual(a1, new_m2.subject)
        self.assertEqual(EXACT_MATCH, new_m2.predicate)
        self.assertEqual(b1, new_m2.object)
        self.assertEqual(1, len(new_m2.evidence))
        new_evidence = new_m2.evidence[0]
        self.assertIsInstance(new_evidence, ReasonedEvidence)
        new_confidence = new_evidence.get_confidence()
        self.assertIsNotNone(new_confidence)
        self.assertEqual(1 - (1 - original_confidence) * (1 - mutation_confidence), new_confidence)
        self.assertEqual(KNOWLEDGE_MAPPING, new_evidence.justification)

    def test_apply_mutations(self) -> None:
        """Test applying mutations."""
        (a1,) = _get_references(1, prefix=PREFIX_A)
        (b1,) = _get_references(1, prefix=PREFIX_B)
        (c1,) = _get_references(1, prefix=PREFIX_C)
        (d1,) = _get_references(1, prefix=PREFIX_D)

        m1 = Mutation(source=PREFIX_A, target=PREFIX_B)
        self.assertTrue(m1.should_apply_to(Mapping(subject=a1, predicate=DB_XREF, object=b1)))

        self.assertFalse(m1.should_apply_to(Mapping(subject=b1, predicate=DB_XREF, object=a1)))
        self.assertFalse(m1.should_apply_to(Mapping(subject=b1, predicate=EXACT_MATCH, object=a1)))
        self.assertFalse(m1.should_apply_to(Mapping(subject=a1, predicate=EXACT_MATCH, object=b1)))
        self.assertFalse(m1.should_apply_to(Mapping(subject=a1, predicate=DB_XREF, object=c1)))
        self.assertFalse(m1.should_apply_to(Mapping(subject=a1, predicate=DB_XREF, object=d1)))

        m2 = Mutation(source=PREFIX_A, target=[PREFIX_B, PREFIX_C])
        self.assertTrue(m2.should_apply_to(Mapping(subject=a1, predicate=DB_XREF, object=b1)))
        self.assertTrue(m2.should_apply_to(Mapping(subject=a1, predicate=DB_XREF, object=c1)))

        self.assertFalse(m2.should_apply_to(Mapping(subject=b1, predicate=DB_XREF, object=a1)))
        self.assertFalse(m2.should_apply_to(Mapping(subject=b1, predicate=EXACT_MATCH, object=a1)))
        self.assertFalse(m2.should_apply_to(Mapping(subject=c1, predicate=EXACT_MATCH, object=a1)))
        self.assertFalse(m2.should_apply_to(Mapping(subject=b1, predicate=EXACT_MATCH, object=c1)))
        self.assertFalse(m2.should_apply_to(Mapping(subject=b1, predicate=DB_XREF, object=c1)))
        self.assertFalse(m2.should_apply_to(Mapping(subject=a1, predicate=DB_XREF, object=d1)))
        self.assertFalse(m2.should_apply_to(Mapping(subject=a1, predicate=EXACT_MATCH, object=b1)))
        self.assertFalse(m2.should_apply_to(Mapping(subject=a1, predicate=EXACT_MATCH, object=c1)))

        m3 = Mutation(source=PREFIX_A)
        self.assertTrue(m3.should_apply_to(Mapping(subject=a1, predicate=DB_XREF, object=b1)))
        self.assertTrue(m3.should_apply_to(Mapping(subject=a1, predicate=DB_XREF, object=c1)))

        self.assertFalse(m3.should_apply_to(Mapping(subject=a1, predicate=EXACT_MATCH, object=c1)))
        self.assertFalse(m3.should_apply_to(Mapping(subject=b1, predicate=EXACT_MATCH, object=c1)))
