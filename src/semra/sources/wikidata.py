"""Get arbitrary Wikidata mappings."""

import typing as t

from curies import Reference

from semra.rules import EXACT_MATCH, UNSPECIFIED_MAPPING
from semra.struct import Mapping, MappingSet, SimpleEvidence

__all__ = ["get_wikidata_mappings"]


def get_wikidata_mappings(property: str, predicate: t.Optional[Reference] = None) -> t.List[Mapping]:
    """Get mappings from Wikidata."""
    import bioregistry
    from pyobo.xrefdb.sources.wikidata import _run_query

    if predicate is None:
        predicate = EXACT_MATCH

    query = f"SELECT ?item ?xref WHERE {{ ?item wdt:{property} ?xref }}"
    rv = []

    prop_to_prefix = bioregistry.get_registry_invmap("wikidata")
    target_prefix = prop_to_prefix[property]

    mapping_set = MappingSet(name="Wikidata", license="CC0", confidence=0.99)
    for row in _run_query(query):
        wikidata_id = row["item"]["value"][len("http://wikidata.org/entity/") :]
        mapping = Mapping(
            s=Reference(prefix="wikidata", identifier=wikidata_id),
            p=predicate,
            o=Reference(prefix=target_prefix, identifier=row["xref"]["value"]),
            evidence=[SimpleEvidence(justification=UNSPECIFIED_MAPPING, mapping_set=mapping_set)],
        )
        rv.append(mapping)
    return rv
