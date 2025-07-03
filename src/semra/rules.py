"""Constants and rules for inference."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeAlias

from pyobo import Reference

from semra.vocabulary import (
    BROAD_MATCH,
    CHAIN_MAPPING,
    CLOSE_MATCH,
    DB_XREF,
    EQUIVALENT_TO,
    EXACT_MATCH,
    INVERSION_MAPPING,
    KNOWLEDGE_MAPPING,
    LEXICAL_MAPPING,
    MANUAL_MAPPING,
    NARROW_MATCH,
    REPLACED_BY,
    SUBCLASS,
    UNSPECIFIED_MAPPING,
)

__all__ = [
    "CURIE_TO_JUSTIFICATION",
    "CURIE_TO_RELATION",
    "DIRECTIONLESS",
    "FLIP",
    "GENERALIZATIONS",
    "IMPRECISE",
    "JUSTIFICATIONS",
    "RELATIONS",
    "TRANSITIVE",
    "TWO_STEP",
]

#: A list of mapping predicates suggested by SSSOM.
RELATIONS: list[Reference] = [
    EXACT_MATCH,
    DB_XREF,
    BROAD_MATCH,
    NARROW_MATCH,
    CLOSE_MATCH,
    EQUIVALENT_TO,
    REPLACED_BY,
    SUBCLASS,
]
#: A mapping from CURIEs to reference objects for mapping predicates
CURIE_TO_RELATION = {r.curie: r for r in RELATIONS}

#: A set of mappings that are not considered as precise
IMPRECISE: set[Reference] = {DB_XREF, CLOSE_MATCH}

#: A mapping of inverse relationships that can be applied when inversting mappings
FLIP = {
    BROAD_MATCH: NARROW_MATCH,
    NARROW_MATCH: BROAD_MATCH,
    EXACT_MATCH: EXACT_MATCH,
    CLOSE_MATCH: CLOSE_MATCH,
    DB_XREF: DB_XREF,
    EQUIVALENT_TO: EQUIVALENT_TO,
}
#: Which predicates are transitive? This excludes the imprecise onces
TRANSITIVE: set[Reference] = {BROAD_MATCH, NARROW_MATCH, EXACT_MATCH, EQUIVALENT_TO}
#: Which predicates are directionless
DIRECTIONLESS: set[Reference] = {EXACT_MATCH, CLOSE_MATCH, DB_XREF, EQUIVALENT_TO}

#: Two step chain inference rules
TWO_STEP: dict[tuple[Reference, Reference], Reference] = {
    (BROAD_MATCH, EXACT_MATCH): BROAD_MATCH,
    (EXACT_MATCH, BROAD_MATCH): BROAD_MATCH,
    (NARROW_MATCH, EXACT_MATCH): NARROW_MATCH,
    (EXACT_MATCH, NARROW_MATCH): NARROW_MATCH,
}

#: Rules for relaxing a more strict predicate to a more loose one,
#: see https://mapping-commons.github.io/sssom/chaining-rules/#generalisation-rules
GENERALIZATIONS = {
    EQUIVALENT_TO: EXACT_MATCH,
    SUBCLASS: BROAD_MATCH,
}

#: A list of references that can be used as mapping justifications in SSSOM
JUSTIFICATIONS = [
    MANUAL_MAPPING,
    LEXICAL_MAPPING,
    UNSPECIFIED_MAPPING,
    INVERSION_MAPPING,
    CHAIN_MAPPING,
    KNOWLEDGE_MAPPING,
]
#: A mapping from CURIEs to mapping justifications
CURIE_TO_JUSTIFICATION = {j.curie: j for j in JUSTIFICATIONS}

#: A type represing a subset configuration
SubsetConfiguration: TypeAlias = Mapping[str, list[Reference]]
