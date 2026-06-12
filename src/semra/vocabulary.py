"""Vocabulary used in SeMRA."""

from __future__ import annotations

import curies
from curies import vocabulary as v
from pyobo import Reference

__all__ = [
    "BEN_REFERENCE",
    "BROAD_MATCH",
    "CHAIN_MAPPING",
    "CHARLIE",
    "CLOSE_MATCH",
    "DB_XREF",
    "EQUIVALENT_TO",
    "EXACT_MATCH",
    "INVERSION_MAPPING",
    "KNOWLEDGE_MAPPING",
    "LEXICAL_MAPPING",
    "MANUAL_MAPPING",
    "NARROW_MATCH",
    "REPLACED_BY",
    "SUBCLASS",
    "SUBPROPERTY",
    "UNSPECIFIED_MAPPING",
]


def _f(r: curies.NamableReference, *, keep_name: bool = False) -> Reference:
    return Reference(prefix=r.prefix, identifier=r.identifier, name=r.name if keep_name else None)


#: A reference to skos:exactMatch
EXACT_MATCH = _f(v.exact_match)
#: A reference to skos:broadMatch
BROAD_MATCH = _f(v.broad_match)
#: A reference to skos:narrowMatch
NARROW_MATCH = _f(v.narrow_match)
#: A reference to skos:closeMatch
CLOSE_MATCH = _f(v.close_match)
#: A reference to rdfs:subClassOf
SUBCLASS = _f(v.is_a)
#: A reference to rdfs:subPropertyOf
SUBPROPERTY = _f(v.subproperty_of)
#: A reference to oboInOwl:hasDbXref
DB_XREF = _f(v.has_dbxref)
#: A reference to owl:equivalentClass
EQUIVALENT_TO = _f(v.equivalent_class)
#: A reference to owl:equivalentProperty
EQUIVALENT_PROPERTY = _f(v.equivalent_property)
#: A reference to owl:sameAs
SAME_AS = _f(v.same_as)
#: A reference to IAO:0100001 (term replaced by)
REPLACED_BY = _f(v.term_replaced_by)

#: A reference to ``semapv:ManualMappingCuration`` that can be used as a mapping justification, see also :data:`semra.rules.JUSTIFICATIONS`.
MANUAL_MAPPING = _f(v.manual_mapping_curation)
#: A reference to ``semapv:LexicalMatchingProcess`` that can be used as a mapping justification, see also :data:`semra.rules.JUSTIFICATIONS`.
LEXICAL_MAPPING = _f(v.lexical_matching_process)
#: A reference to ``semapv:UnspecifiedMatchingProcess`` that can be used as a mapping justification, see also :data:`semra.rules.JUSTIFICATIONS`.
UNSPECIFIED_MAPPING = _f(v.unspecified_matching_process)
#: A reference to ``semapv:MappingInversion`` that can be used as a mapping justification, see also :data:`semra.rules.JUSTIFICATIONS`.
INVERSION_MAPPING = _f(v.mapping_inversion)
#: A reference to ``semapv:MappingChaining`` that can be used as a mapping justification, see also :data:`semra.rules.JUSTIFICATIONS`.
CHAIN_MAPPING = _f(v.mapping_chaining)
#: A reference to ``semapv:BackgroundKnowledgeBasedMatching`` that can be used as a mapping justification, see also :data:`semra.rules.JUSTIFICATIONS`.
KNOWLEDGE_MAPPING = _f(v.background_knowledge_based_matching_process)

#: A reference to Charles Tapley Hoyt, the author of SeMRA
CHARLIE = _f(v.charlie, keep_name=True)
BEN_REFERENCE = Reference.from_curie("orcid:0000-0001-9439-5346", name="Benjamin M. Gyori")
