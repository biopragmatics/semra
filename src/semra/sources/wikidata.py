"""Get arbitrary Wikidata mappings."""

import typing as t

from curies import Reference

from semra.rules import EXACT_MATCH, UNSPECIFIED_MAPPING
from semra.struct import Mapping, MappingSet, SimpleEvidence

__all__ = ["get_wikidata_mappings"]


def get_wikidata_mappings(prop: str, predicate: t.Optional[Reference] = None) -> t.List[Mapping]:
    """Get mappings from Wikidata."""
    import bioregistry

    prop_to_prefix = bioregistry.get_registry_invmap("wikidata")
    target_prefix = prop_to_prefix[prop]

    return _help(target_prefix=target_prefix, prop=prop, predicate=predicate)


def get_wikidata_mappings_by_prefix(prefix: str, predicate: t.Optional[Reference] = None) -> t.List[Mapping]:
    """Get mappings from Wikidata."""
    import bioregistry

    prefix_to_prop = bioregistry.get_registry_map("wikidata")
    prop = prefix_to_prop[prefix]

    return _help(target_prefix=prefix, prop=prop, predicate=predicate)


def _help(
    target_prefix: str, prop: str, *, predicate: t.Optional[Reference] = None, cache: bool = True
) -> t.List[Mapping]:
    """Get mappings from Wikidata."""
    from pyobo.xrefdb.sources.wikidata import iter_wikidata_mappings

    if predicate is None:
        predicate = EXACT_MATCH

    mapping_set = MappingSet(name="Wikidata", license="CC0", confidence=0.99)
    return [
        Mapping(
            s=Reference(prefix="wikidata", identifier=wikidata_id),
            p=predicate,
            o=Reference(prefix=target_prefix, identifier=xref_id),
            evidence=[SimpleEvidence(justification=UNSPECIFIED_MAPPING, mapping_set=mapping_set)],
        )
        for wikidata_id, xref_id in iter_wikidata_mappings(prop, cache=cache)
    ]
