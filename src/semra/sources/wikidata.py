"""Get arbitrary Wikidata mappings."""

from collections.abc import Iterable
from textwrap import dedent

import bioregistry
import pystow
import requests
import sssom_pydantic
import wikidata_client
from pydantic import AnyUrl
from sssom_pydantic import MappingSet, SemanticMapping
from tqdm import tqdm

from semra.constants import CC0_URL, Reference
from semra.vocabulary import CHARLIE, EXACT_MATCH, UNSPECIFIED_MAPPING

__all__ = [
    "get_wikidata_mappings",
    "get_wikidata_mappings_by_prefix",
]

WIKIDATA_MAPPING_DIRECTORY = pystow.module("wikidata", "mappings")


def get_all_wikidata_mappings(
    *, progress: bool = True, endpoint: str | None = None
) -> list[SemanticMapping]:
    """Iterate over WikiData xref dataframes."""
    return list(_get_all_wikidata_mappings(endpoint=endpoint, progress=progress))


def _get_all_wikidata_mappings(
    *, progress: bool = True, endpoint: str | None = None
) -> Iterable[SemanticMapping]:
    """Iterate over WikiData xref dataframes."""
    wikidata_properties = bioregistry.get_registry_map("wikidata")
    it = tqdm(sorted(wikidata_properties.items()), disable=not progress, desc="Wikidata properties")
    for prefix, wikidata_property in it:
        if prefix in {"pubmed", "pmc", "orcid", "inchi", "smiles"}:
            continue  # too many
        it.set_postfix({"prefix": prefix, "prop": wikidata_property})
        try:
            yield from get_wikidata_mappings_by_prefix(prefix=prefix, endpoint=endpoint)
        except requests.exceptions.JSONDecodeError:
            tqdm.write(f"faild to get {prefix}/{wikidata_property}")
            continue


def get_wikidata_mappings(prop: str, *, endpoint: str | None = None) -> list[SemanticMapping]:
    """Get mappings from Wikidata."""
    prop_to_prefix = bioregistry.get_registry_invmap("wikidata")
    target_prefix = prop_to_prefix[prop]
    return list(_help(prefix=target_prefix, prop=prop))


def get_wikidata_mappings_by_prefix(
    prefix: str, *, endpoint: str | None = None
) -> Iterable[SemanticMapping]:
    """Get mappings from Wikidata."""
    prefix_to_prop = bioregistry.get_registry_map("wikidata")
    prop = prefix_to_prop[prefix]
    path = WIKIDATA_MAPPING_DIRECTORY.join(name=f"{prefix}-{prop}.sssom.tsv.gz")
    if path.is_file():
        tqdm.write(f"reading cache for {prefix}/{prop} at {path}")
        with sssom_pydantic.read_iterable(path) as file:
            for record in file.mappings:
                if isinstance(record, SemanticMapping):
                    yield record
    else:
        metadata = MappingSet(
            id=AnyUrl(f"https://w3id.org/biopragmatics/mappings/wikidata/{prop}.sssom.tsv.gz"),
            license=AnyUrl(CC0_URL),
            creators=[CHARLIE],
            confidence=0.99,
        )
        converter = bioregistry.get_default_converter()
        mappings = list(_help(prefix=prefix, prop=prop, endpoint=endpoint))
        sssom_pydantic.write(mappings=mappings, path=path, metadata=metadata, converter=converter)
        yield from mappings


def _help(
    prefix: str,
    prop: str,
    *,
    confidence: float = 0.99,
    timeout: int = 300,
    endpoint: str | None = None,
) -> Iterable[SemanticMapping]:
    """Get mappings from Wikidata."""
    source = Reference(prefix="bioregistry", identifier="wikidata")
    sparql = dedent(f"""\
        SELECT ?entity ?entityLabel ?id
        WHERE {{
            ?entity wdt:{prop} ?id .
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],mul,en". }}
        }}
    """)
    rows = wikidata_client.query(sparql, timeout=timeout, endpoint=endpoint)
    for row in rows:
        if not row["entity"].startswith("Q"):
            continue
        try:
            obj = Reference(prefix=prefix, identifier=_clean_xref_id(prefix, row["id"]))
        except ValueError:
            continue
        yield SemanticMapping(
            subject=Reference(prefix="wikidata", identifier=row["entity"], name=row["entityLabel"]),
            predicate=EXACT_MATCH,
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


if __name__ == "__main__":
    for _ in _get_all_wikidata_mappings():
        pass
