"""Semantic Mapping Reasoner and Assembler."""

from semra.pipeline import Configuration, Input, Mutation
from semra.rules import (
    BROAD_MATCH,
    DB_XREF,
    EXACT_MATCH,
    LEXICAL_MAPPING,
    MANUAL_MAPPING,
    NARROW_MATCH,
    REPLACED_BY,
    UNSPECIFIED_MAPPING,
)
from semra.struct import Evidence, Mapping, MappingSet, ReasonedEvidence, Reference, SimpleEvidence

__all__ = [
    "Mapping",
    "Evidence",
    "SimpleEvidence",
    "ReasonedEvidence",
    "Reference",
    "MappingSet",
    # Mapping predicates
    "EXACT_MATCH",
    "DB_XREF",
    "REPLACED_BY",
    "NARROW_MATCH",
    "BROAD_MATCH",
    # Mapping justifications
    "LEXICAL_MAPPING",
    "MANUAL_MAPPING",
    "UNSPECIFIED_MAPPING",
    # Pipeline
    "Configuration",
    "Input",
    "Mutation",
]
