"""Get arbitrary Wikidata mappings."""

from curies import Reference

from semra.rules import EXACT_MATCH, UNSPECIFIED_MAPPING
from semra.struct import Mapping, MappingSet, SimpleEvidence

__all__ = [
    "get_wikidata_mappings",
    "get_wikidata_mappings_by_prefix",
]


def get_wikidata_mappings(*, prop: str, predicate: Reference | None = None) -> list[Mapping]:
    """Get mappings from Wikidata."""
    import bioregistry

    prop_to_prefix = bioregistry.get_registry_invmap("wikidata")
    target_prefix = prop_to_prefix[prop]

    return _help(target_prefix=target_prefix, prop=prop, predicate=predicate)


def get_wikidata_mappings_by_prefix(
    prefix: str, predicate: Reference | None = None
) -> list[Mapping]:
    """Get mappings from Wikidata."""
    import bioregistry

    prefix_to_prop = bioregistry.get_registry_map("wikidata")
    prop = prefix_to_prop[prefix]

    return _help(target_prefix=prefix, prop=prop, predicate=predicate)


def _help(
    target_prefix: str, prop: str, *, predicate: Reference | None = None, cache: bool = True
) -> list[Mapping]:
    """Get mappings from Wikidata."""
    from pyobo.xrefdb.sources.wikidata import iter_wikidata_mappings

    if predicate is None:
        predicate = EXACT_MATCH

    mapping_set = MappingSet(name="wikidata", license="CC0", confidence=0.99)
    return [
        Mapping(
            s=Reference(prefix="wikidata", identifier=wikidata_id),
            p=predicate,
            o=Reference(prefix=target_prefix, identifier=_clean_xref_id(target_prefix, xref_id)),
            evidence=[SimpleEvidence(justification=UNSPECIFIED_MAPPING, mapping_set=mapping_set)],
        )
        for wikidata_id, xref_id in iter_wikidata_mappings(prop, cache=cache)
    ]


def _clean_xref_id(prefix: str, identifier: str) -> str:
    if identifier.lower().startswith(f"{prefix}_"):
        identifier = identifier[len(prefix) + 1 :]
    return identifier
