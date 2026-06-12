"""Constants and rules for inference."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeAlias

from curies import vocabulary as v
from pyobo import Reference

from semra.vocabulary import (
    BROAD_MATCH,
    CLOSE_MATCH,
    DB_XREF,
    EQUIVALENT_PROPERTY,
    EQUIVALENT_TO,
    EXACT_MATCH,
    SAME_AS,
    SUBCLASS,
    SUBPROPERTY,
)

__all__ = [
    "FLIP",
    "GENERALIZATIONS",
    "IMPRECISE",
    "RELATIONS",
]

#: A list of mapping predicates suggested by SSSOM.
RELATIONS: list[Reference] = [Reference.from_reference(r) for r in v.extended_match_typedefs]

#: A set of mappings that are not considered as precise
IMPRECISE: set[Reference] = {DB_XREF, CLOSE_MATCH}

#: A mapping of inverse relationships that can be applied when inversting mappings
FLIP: dict[Reference, Reference] = {
    Reference.from_reference(predicate): Reference.from_reference(inverse_predicate)
    for predicate, inverse_predicate in v.inversions.items()
}

#: Rules for relaxing a more strict predicate to a more loose one,
#: see https://mapping-commons.github.io/sssom/chaining-rules/#generalisation-rules
GENERALIZATIONS = {
    EQUIVALENT_TO: EXACT_MATCH,
    EQUIVALENT_PROPERTY: EXACT_MATCH,
    SAME_AS: EXACT_MATCH,
    SUBCLASS: BROAD_MATCH,
    SUBPROPERTY: BROAD_MATCH,
}

#: A type represing a subset configuration
SubsetConfiguration: TypeAlias = Mapping[str, list[Reference]]
