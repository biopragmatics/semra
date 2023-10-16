from semra.rules import DB_XREF, EXACT_MATCH, LEXICAL_MAPPING, MANUAL_MAPPING, UNSPECIFIED_MAPPING, REPLACED_BY
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
    # Mapping justifications
    "LEXICAL_MAPPING",
    "MANUAL_MAPPING",
    "UNSPECIFIED_MAPPING",
]
