"""Get arbitrary Wikidata mappings."""

import datetime
from collections.abc import Iterable

import bioregistry
import pystow
import sssom_pydantic
from curies import vocabulary as v
from pydantic import AnyUrl
from sssom_pydantic import MappingSet, SemanticMapping
from sssom_pydantic.constants import CC0_URL
from sssom_pydantic.contrib.wikidata import get_mappings_by_prefix, get_wikidata_property_mappings
from tqdm import tqdm

__all__ = [
    "get_wikidata_mappings",
    "get_wikidata_mappings_by_prefix",
]


def get_wikidata_mappings(
    *, progress: bool = True, endpoint: str | None = None
) -> list[SemanticMapping]:
    """Iterate over WikiData xref dataframes."""
    return [
        *get_wikidata_property_mappings(endpoint=endpoint),
        # TODO get exact matches
        *_get_all_wikidata_mappings(endpoint=endpoint, progress=progress),
    ]


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
        except OSError:
            tqdm.write(f"failed to get {prefix}/{wikidata_property}")
            continue


def get_wikidata_mappings_by_prefix(
    prefix: str, *, endpoint: str | None = None
) -> Iterable[SemanticMapping]:
    """Get mappings from Wikidata."""
    prefix_to_prop = bioregistry.get_registry_map("wikidata")
    prop = prefix_to_prop[prefix]
    path = pystow.join("wikidata", "mappings", name=f"{prefix}-{prop}.sssom.tsv.gz")
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
            creators=[v.charlie],
            confidence=0.99,
            publication_date=datetime.date.today(),
        )
        converter = bioregistry.get_default_converter()
        mappings = list(get_mappings_by_prefix(prefix=prefix, property_id=prop, endpoint=endpoint))
        sssom_pydantic.write(mappings=mappings, path=path, metadata=metadata, converter=converter)
        yield from mappings


if __name__ == "__main__":
    get_wikidata_mappings()
