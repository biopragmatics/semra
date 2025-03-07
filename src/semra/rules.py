"""Constants and rules for inference."""

from __future__ import annotations

from curies import Reference
from curies import vocabulary as v

EXACT_MATCH = v.exact_match
BROAD_MATCH = v.broad_match
NARROW_MATCH = v.narrow_match
CLOSE_MATCH = v.close_match
DB_XREF = v.has_dbxref
EQUIVALENT_TO = Reference(prefix="owl", identifier="equivalentTo")
REPLACED_BY = v.term_replaced_by

RELATIONS = [
    EXACT_MATCH,
    DB_XREF,
    BROAD_MATCH,
    NARROW_MATCH,
    CLOSE_MATCH,
    EQUIVALENT_TO,
    REPLACED_BY,
]

IMPRECISE = {DB_XREF, CLOSE_MATCH}
FLIP = {
    BROAD_MATCH: NARROW_MATCH,
    NARROW_MATCH: BROAD_MATCH,
    EXACT_MATCH: EXACT_MATCH,
    CLOSE_MATCH: CLOSE_MATCH,
    DB_XREF: DB_XREF,
    EQUIVALENT_TO: EQUIVALENT_TO,
}
#: Which predicates are transitive? This excludes the imprecise onces
TRANSITIVE = {BROAD_MATCH, NARROW_MATCH, EXACT_MATCH, EQUIVALENT_TO}
#: Which predicates are directionless
DIRECTIONLESS = {EXACT_MATCH, CLOSE_MATCH, DB_XREF, EQUIVALENT_TO}

#: Two step chain inference rules
TWO_STEP: dict[tuple[Reference, Reference], Reference] = {
    (BROAD_MATCH, EXACT_MATCH): BROAD_MATCH,
    (EXACT_MATCH, BROAD_MATCH): BROAD_MATCH,
    (NARROW_MATCH, EXACT_MATCH): NARROW_MATCH,
    (EXACT_MATCH, NARROW_MATCH): NARROW_MATCH,
}

MANUAL_MAPPING = Reference.from_curie("semapv:ManualMappingCuration")
LEXICAL_MAPPING = Reference.from_curie("semapv:LexicalMatching")
UNSPECIFIED_MAPPING = Reference.from_curie("semapv:UnspecifiedMatching")
INVERSION_MAPPING = Reference.from_curie("semapv:MappingInversion")
CHAIN_MAPPING = Reference.from_curie("semapv:MappingChaining")
KNOWLEDGE_MAPPING = Reference.from_curie("semapv:BackgroundKnowledgeBasedMatching")

BEN_ORCID = Reference.from_curie("orcid:0000-0001-9439-5346")
