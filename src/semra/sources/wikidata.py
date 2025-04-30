"""Get arbitrary Wikidata mappings."""

import json
from collections.abc import Iterable
from typing import Any, cast

import bioregistry
import curies
import pystow
import requests
from tqdm import tqdm

from semra.rules import EXACT_MATCH, UNSPECIFIED_MAPPING
from semra.struct import Mapping, MappingSet, Reference, SimpleEvidence
from semra.version import get_version

__all__ = [
    "get_wikidata_mappings",
    "get_wikidata_mappings_by_prefix",
]

#: WikiData SPARQL endpoint. See https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service#Interfacing
URL = "https://query.wikidata.org/bigdata/namespace/wdq/sparql"

WIKIDATA_MAPPING_DIRECTORY = pystow.module("wikidata", "mappings")


def get_all_wikidata_mappings(
    *, use_tqdm: bool = True, predicate: curies.Reference | None = None
) -> list[Mapping]:
    """Iterate over WikiData xref dataframes."""
    if predicate is None:
        predicate = EXACT_MATCH

    wikidata_properties = bioregistry.get_registry_map("wikidata")

    it = tqdm(sorted(wikidata_properties.items()), disable=not use_tqdm, desc="Wikidata properties")
    rv = []
    for prefix, wikidata_property in it:
        if prefix in {"pubmed", "pmc", "orcid", "inchi", "smiles"}:
            continue  # too many
        it.set_postfix({"prefix": prefix})
        rv.extend(_help(target_prefix=prefix, prop=wikidata_property, predicate=predicate))
    return rv


def get_wikidata_mappings(*, prop: str, predicate: curies.Reference | None = None) -> list[Mapping]:
    """Get mappings from Wikidata."""
    prop_to_prefix = bioregistry.get_registry_invmap("wikidata")
    target_prefix = prop_to_prefix[prop]

    return _help(target_prefix=target_prefix, prop=prop, predicate=predicate)


def get_wikidata_mappings_by_prefix(
    prefix: str, predicate: curies.Reference | None = None
) -> list[Mapping]:
    """Get mappings from Wikidata."""
    prefix_to_prop = bioregistry.get_registry_map("wikidata")
    prop = prefix_to_prop[prefix]

    return _help(target_prefix=prefix, prop=prop, predicate=predicate)


def _help(
    target_prefix: str, prop: str, *, predicate: curies.Reference | None = None, cache: bool = True
) -> list[Mapping]:
    """Get mappings from Wikidata."""
    if predicate is None:
        predicate = EXACT_MATCH

    _predicate = Reference(prefix=predicate.prefix, identifier=predicate.identifier)

    mapping_set = MappingSet(name="wikidata", license="CC0", confidence=0.99)
    rv = []
    for wikidata_id, xref_id in iter_wikidata_mappings(prop, cache=cache):
        if not wikidata_id.startswith("Q"):
            continue
        try:
            obj = Reference(prefix=target_prefix, identifier=_clean_xref_id(target_prefix, xref_id))
        except ValueError:
            continue
        mapping = Mapping(
            subject=Reference(prefix="wikidata", identifier=wikidata_id),
            predicate=_predicate,
            object=obj,
            evidence=[SimpleEvidence(justification=UNSPECIFIED_MAPPING, mapping_set=mapping_set)],
        )
        rv.append(mapping)
    return rv


def _clean_xref_id(prefix: str, identifier: str) -> str:
    if identifier.lower().startswith(f"{prefix}_"):
        identifier = identifier[len(prefix) + 1 :]
    return identifier


def iter_wikidata_mappings(
    wikidata_property: str, *, cache: bool = True
) -> Iterable[tuple[str, str]]:
    """Iterate over Wikidata xrefs."""
    path = WIKIDATA_MAPPING_DIRECTORY.join(name=f"{wikidata_property}.json")
    if path.exists() and cache:
        with path.open() as file:
            rows = json.load(file)
    else:
        query = f"SELECT ?wikidata_id ?id WHERE {{?wikidata_id wdt:{wikidata_property} ?id}}"
        rows = _run_query(query)
        with path.open("w") as file:
            json.dump(rows, file, indent=2)

    for row in rows:
        wikidata_id = row["wikidata_id"]["value"].removeprefix("http://www.wikidata.org/entity/")
        wikidata_id = wikidata_id.removeprefix("http://wikidata.org/entity/")
        entity_id = row["id"]["value"]
        yield wikidata_id, entity_id


HEADERS = {
    "User-Agent": f"semra/{get_version()}",
}


def _run_query(query: str, base: str = URL) -> list[dict[str, Any]]:
    res = requests.get(base, params={"query": query, "format": "json"}, headers=HEADERS, timeout=45)
    res.raise_for_status()
    res_json = res.json()
    return cast(list[dict[str, Any]], res_json["results"]["bindings"])
