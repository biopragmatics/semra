"""Get arbitrary Wikidata mappings."""

import gzip
import json
from collections.abc import Iterable

import bioregistry
import curies
import pystow
import wikidata_client
from sssom_pydantic import SemanticMapping
from tqdm import tqdm

from semra.constants import CC0_URL, Reference
from semra.vocabulary import EXACT_MATCH, UNSPECIFIED_MAPPING

__all__ = [
    "get_wikidata_mappings",
    "get_wikidata_mappings_by_prefix",
]

WIKIDATA_MAPPING_DIRECTORY = pystow.module("wikidata", "mappings")


def get_all_wikidata_mappings(
    *, use_tqdm: bool = True, predicate: curies.Reference | None = None
) -> list[SemanticMapping]:
    """Iterate over WikiData xref dataframes."""
    if predicate is None:
        predicate = EXACT_MATCH

    wikidata_properties = bioregistry.get_registry_map("wikidata")

    it = tqdm(sorted(wikidata_properties.items()), disable=not use_tqdm, desc="Wikidata properties")
    rv: list[SemanticMapping] = []
    for prefix, wikidata_property in it:
        if prefix in {"pubmed", "pmc", "orcid", "inchi", "smiles"}:
            continue  # too many
        it.set_postfix({"prefix": prefix})
        rv.extend(_help(target_prefix=prefix, prop=wikidata_property, predicate=predicate))
    return rv


def get_wikidata_mappings(
    *, prop: str, predicate: curies.Reference | None = None
) -> list[SemanticMapping]:
    """Get mappings from Wikidata."""
    prop_to_prefix = bioregistry.get_registry_invmap("wikidata")
    target_prefix = prop_to_prefix[prop]

    return list(_help(target_prefix=target_prefix, prop=prop, predicate=predicate))


def get_wikidata_mappings_by_prefix(
    prefix: str, predicate: curies.Reference | None = None
) -> Iterable[SemanticMapping]:
    """Get mappings from Wikidata."""
    prefix_to_prop = bioregistry.get_registry_map("wikidata")
    prop = prefix_to_prop[prefix]

    return _help(target_prefix=prefix, prop=prop, predicate=predicate)


def _help(
    target_prefix: str,
    prop: str,
    *,
    predicate: curies.Reference | None = None,
    cache: bool = True,
    confidence: float = 0.99,
) -> Iterable[SemanticMapping]:
    """Get mappings from Wikidata."""
    if predicate is None:
        predicate = EXACT_MATCH
    else:
        predicate = Reference.from_reference(predicate)
    source = Reference(prefix="bioregistry", identifier="wikidata")
    for wikidata_id, xref_id in iter_wikidata_mappings(prop, cache=cache):
        if not wikidata_id.startswith("Q"):
            continue
        try:
            obj = Reference(prefix=target_prefix, identifier=_clean_xref_id(target_prefix, xref_id))
        except ValueError:
            continue
        yield SemanticMapping(
            subject=Reference(prefix="wikidata", identifier=wikidata_id),
            predicate=predicate,
            object=obj,
            justification=UNSPECIFIED_MAPPING,
            license=CC0_URL,
            confidence=confidence,
            source=source,
        )


def _clean_xref_id(prefix: str, identifier: str) -> str:
    if identifier.lower().startswith(f"{prefix}_"):
        identifier = identifier[len(prefix) + 1 :]
    return identifier


def iter_wikidata_mappings(
    wikidata_property: str, *, cache: bool = True
) -> Iterable[tuple[str, str]]:
    """Iterate over Wikidata xrefs."""
    path = WIKIDATA_MAPPING_DIRECTORY.join(name=f"{wikidata_property}.json.gz")
    if path.exists() and cache:
        with gzip.open(path, mode="rt") as file:
            rows = json.load(file)
    else:
        sparql = f"SELECT ?wikidata_id ?id WHERE {{?wikidata_id wdt:{wikidata_property} ?id}}"
        rows = wikidata_client.query(sparql, timeout=300)
        with gzip.open(path, mode="wt") as file:
            json.dump(rows, file)

    for row in rows:
        yield row["wikidata_id"], row["id"]
