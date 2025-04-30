"""Constants and rules for inference."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeAlias

import bioregistry
import curies
from curies import vocabulary as v
from pyobo import Reference


def _f(r: curies.NamedReference) -> Reference:
    return Reference(prefix=r.prefix, identifier=r.identifier, name=r.name)


EXACT_MATCH = _f(v.exact_match)
BROAD_MATCH = _f(v.broad_match)
NARROW_MATCH = _f(v.narrow_match)
CLOSE_MATCH = _f(v.close_match)
SUBCLASS = _f(v.is_a)
DB_XREF = _f(v.has_dbxref)
EQUIVALENT_TO = Reference(prefix="owl", identifier="equivalentTo")
REPLACED_BY = _f(v.term_replaced_by)

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
CURIE_TO_RELATION = {r.curie: r for r in RELATIONS}

IMPRECISE: set[Reference] = {DB_XREF, CLOSE_MATCH}
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

MANUAL_MAPPING = _f(v.manual_mapping_curation)
LEXICAL_MAPPING = _f(v.lexical_matching_process)
UNSPECIFIED_MAPPING = _f(v.unspecified_matching_process)
INVERSION_MAPPING = _f(v.mapping_inversion)
CHAIN_MAPPING = _f(v.mapping_chaining)
KNOWLEDGE_MAPPING = _f(v.background_knowledge_based_matching_process)

JUSTIFICATIONS = [
    MANUAL_MAPPING,
    LEXICAL_MAPPING,
    UNSPECIFIED_MAPPING,
    INVERSION_MAPPING,
    CHAIN_MAPPING,
    KNOWLEDGE_MAPPING,
]
CURIE_TO_JUSTIFICATION = {j.curie: j for j in JUSTIFICATIONS}

charlie = _f(v.charlie)
BEN_ORCID = Reference.from_curie("orcid:0000-0001-9439-5346", name="Benjamin M. Gyori")

SubsetConfiguration: TypeAlias = Mapping[str, list[Reference]]

SEMRA_NEO4J_MAPPING_LABEL = "mapping"
SEMRA_NEO4J_CONCEPT_LABEL = "concept"
SEMRA_NEO4J_EVIDENCE_LABEL = "evidence"
SEMRA_NEO4J_MAPPING_SET_LABEL = "mappingset"

SEMRA_MAPPING_PREFIX = "semra.mapping"
SEMRA_MAPPING = bioregistry.Resource(prefix=SEMRA_MAPPING_PREFIX, name="SeMRA Mapping")

SEMRA_EVIDENCE_PREFIX = "semra.evidence"
SEMRA_EVIDENCE = bioregistry.Resource(prefix=SEMRA_EVIDENCE_PREFIX, name="SeMRA Evidence")

SEMRA_MAPPING_SET_PREFIX = "semra.mappingset"
SEMRA_MAPPING_SET = bioregistry.Resource(prefix=SEMRA_MAPPING_SET_PREFIX, name="SeMRA Mapping Set")

for resource in [SEMRA_MAPPING, SEMRA_EVIDENCE, SEMRA_MAPPING_SET]:
    bioregistry.manager.synonyms[resource.prefix] = resource.prefix
    bioregistry.manager.registry[resource.prefix] = resource
