from semra.rules import EXACT_MATCH, LEXICAL_MAPPING, MANUAL_MAPPING, UNSPECIFIED_MAPPING
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
    # Mapping justifications
    "LEXICAL_MAPPING",
    "MANUAL_MAPPING",
    "UNSPECIFIED_MAPPING",
]
