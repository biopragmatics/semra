"""Constants and rules for inference."""

from semra.struct import Reference

EXACT_MATCH = Reference(prefix="skos", identifier="exactMatch")
BROAD_MATCH = Reference(prefix="skos", identifier="broadMatch")
NARROW_MATCH = Reference(prefix="skos", identifier="narrowMatch")
CLOSE_MATCH = Reference(prefix="skos", identifier="closeMatch")
DB_XREF = Reference(prefix="oboinowl", identifier="dbxref")
EQUIVALENT_TO = Reference(prefix="owl", identifier="equivalentTo")

FLIP = {
    BROAD_MATCH: NARROW_MATCH,
    NARROW_MATCH: BROAD_MATCH,
    EXACT_MATCH: EXACT_MATCH,
    CLOSE_MATCH: CLOSE_MATCH,
    DB_XREF: DB_XREF,
    EQUIVALENT_TO: EQUIVALENT_TO,
}
#: Which predicates are transitive?
TRANSITIVE = {BROAD_MATCH, NARROW_MATCH, EXACT_MATCH}
#: Which predicates are directionless
DIRECTIONLESS = {EXACT_MATCH, CLOSE_MATCH}

#: Two step chain inference rules
TWO_STEP: dict[tuple[Reference, Reference], Reference] = {
    (BROAD_MATCH, EXACT_MATCH): BROAD_MATCH,
    (EXACT_MATCH, BROAD_MATCH): BROAD_MATCH,
    (NARROW_MATCH, EXACT_MATCH): NARROW_MATCH,
    (EXACT_MATCH, NARROW_MATCH): NARROW_MATCH,
}

MANUAL_MAPPING = Reference.from_curie("semapv:ManualMappingCuration")
LEXICAL_MAPPING = Reference.from_curie("semapv:LexicalMatching")
CHARLIE_ORCID = Reference.from_curie("orcid:0000-0003-4423-4370")
BEN_ORCID = Reference.from_curie("orcid:0000-0001-9439-5346")
