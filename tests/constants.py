"""Reusable assets for testing."""

import unittest
from typing import Any

import curies
import sssom_pydantic
from curies import vocabulary as cv
from pydantic import AnyUrl
from sssom_curator.constants import CC0_URL
from sssom_pydantic import MappingSet
from sssom_pydantic import examples as ex

from semra import MANUAL_MAPPING, Evidence, Mapping, ReasonedEvidence, Reference, SimpleEvidence
from semra.constants import SEMRA_EVIDENCE_PREFIX, SEMRA_EVIDENCE_URI_PREFIX, SEMRA_SOURCE

R2_curie = ex.R2.curie
R2 = Reference.from_reference(ex.R2)

R4_curie = ex.R4.curie
R4 = Reference.from_reference(ex.R4)

R1_curie = ex.R1.curie
R1 = Reference.from_reference(ex.R1)

R3_curie = ex.R3.curie
R3 = Reference.from_reference(ex.R3)

P1 = Reference.from_reference(ex.P1)

TEST_CURIES = {R2, R4, R1, R3}

TEST_MAPPING_SET = sssom_pydantic.MappingSet(
    id=AnyUrl("https://example.com/test.sssom.tsv"),
    title="Test Mapping Set",
    confidence=1.0,
)

TEST_SSSOM_MAPPING_1 = sssom_pydantic.SemanticMapping(
    subject=R2,
    predicate=P1,
    object=R1,
    justification=MANUAL_MAPPING,
    authors=[cv.charlie],
)
TEST_MAPPING_1 = Mapping.from_sssom_pydantic(TEST_SSSOM_MAPPING_1, TEST_MAPPING_SET)

TEST_SSSOM_MAPPING_2 = sssom_pydantic.SemanticMapping(
    subject=R3, predicate=P1, object=R4, justification=MANUAL_MAPPING
)
TEST_MAPPING_2 = Mapping.from_sssom_pydantic(TEST_SSSOM_MAPPING_2, TEST_MAPPING_SET)

TEST_MAPPING_4 = Mapping(subject=ex.R5, predicate=P1, object=ex.R6)
TEST_MAPPING_5 = Mapping(subject=ex.R6, predicate=P1, object=ex.R10)
TEST_MAPPING_6 = Mapping(
    subject=ex.R5,
    predicate=P1,
    object=ex.R10,
    evidence=[
        ReasonedEvidence(
            justification=cv.mapping_chaining, mappings=[TEST_MAPPING_4, TEST_MAPPING_5]
        )
    ],
)
TEST_SSSOM_MAPPING_6 = sssom_pydantic.SemanticMapping(
    subject=ex.R5,
    predicate=P1,
    object=ex.R10,
    justification=cv.mapping_chaining,
    derived_from=[TEST_MAPPING_4.get_reference(), TEST_MAPPING_5.get_reference()],
    # automatically added in by semra
    source=SEMRA_SOURCE,
    license=CC0_URL,
    comment="mesh:C027957 chebi:133530 cas:30223-92-8",
)


TEST_PREFIX_MAP = {
    SEMRA_EVIDENCE_PREFIX: SEMRA_EVIDENCE_URI_PREFIX,
    **ex.TEST_PREFIX_MAP,
}
TEST_CONVERTER = curies.Converter.from_prefix_map(TEST_PREFIX_MAP)


def assert_mappings_equal(
    self: unittest.TestCase,
    expected: list[Mapping],
    actual: list[Mapping] | None,
    *,
    msg: str | None = None,
) -> None:
    """Assert mappings are equal."""
    if actual is None:
        raise self.fail()
    self.assertEqual(
        [_simplify_mapping(m).model_dump(exclude_none=True) for m in sorted(expected)],
        [_simplify_mapping(m).model_dump(exclude_none=True) for m in sorted(actual)],
        msg=msg,
    )


def _simplify_mapping(mapping: Mapping) -> Mapping:
    return mapping.model_copy(
        update={"evidence": [_simplify_evidence(evidence) for evidence in mapping.evidence]}
    )


def _simplify_evidence(evidence: Evidence) -> Evidence:
    if isinstance(evidence, SimpleEvidence):
        update: dict[str, Any] = {
            "mapping_set": MappingSet(id=AnyUrl("https://example.com/test.sssom.tsv")),
        }
        return evidence.model_copy(update=update)
    else:
        return evidence
