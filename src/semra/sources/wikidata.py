"""Get arbitrary Wikidata mappings."""

import datetime
from collections.abc import Iterable
from typing import Unpack

import bioregistry
import pystow
import sssom_pydantic
from curies import vocabulary as v
from pydantic import AnyUrl
from sssom_pydantic import MappingSet, SemanticMapping
from sssom_pydantic.constants import CC0_URL
from sssom_pydantic.contrib.wikidata import (
    get_equivalent_property_mappings,
    get_exact_match_mappings,
    get_mappings_by_property,
)
from tqdm import tqdm
from wikidata_client import QueryKwargs

__all__ = [
    "get_wikidata_mappings",
    "get_wikidata_mappings_by_prefix",
]


def get_wikidata_mappings(
    *, progress: bool = True, **kwargs: Unpack[QueryKwargs]
) -> list[SemanticMapping]:
    """Iterate over WikiData xref dataframes."""
    converter = bioregistry.get_default_converter()
    return [
        *get_equivalent_property_mappings(converter=converter, **kwargs),
        *get_exact_match_mappings(converter=converter, **kwargs),
        *_get_all_wikidata_mappings(progress=progress, **kwargs),
    ]


def _get_all_wikidata_mappings(
    *, progress: bool = True, **kwargs: Unpack[QueryKwargs]
) -> Iterable[SemanticMapping]:
    """Iterate over WikiData xref dataframes."""
    wikidata_properties = bioregistry.get_registry_map("wikidata")
    it = tqdm(sorted(wikidata_properties.items()), disable=not progress, desc="Wikidata properties")
    for prefix, wikidata_property in it:
        if prefix in {"pubmed", "pmc", "orcid", "inchi", "smiles"}:
            continue  # too many
        it.set_postfix({"prefix": prefix, "prop": wikidata_property})
        try:
            yield from get_wikidata_mappings_by_prefix(prefix=prefix, **kwargs)
        except OSError:
            tqdm.write(f"failed to get {prefix}/{wikidata_property}")
            continue


def get_wikidata_mappings_by_prefix(
    prefix: str, **kwargs: Unpack[QueryKwargs]
) -> Iterable[SemanticMapping]:
    """Get mappings from Wikidata."""
    property_id = bioregistry.get_registry_map("wikidata")[prefix]
    path = pystow.join("wikidata", "mappings", name=f"{prefix}-{property_id}.sssom.tsv.gz")
    if path.is_file():
        tqdm.write(f"reading cache for {prefix}/{property_id} at {path}")
        with sssom_pydantic.read_iterable(path) as file:
            for record in file.mappings:
                if isinstance(record, SemanticMapping):
                    yield record
    else:
        metadata = MappingSet(
            id=AnyUrl(
                f"https://w3id.org/biopragmatics/mappings/wikidata/{property_id}.sssom.tsv.gz"
            ),
            license=AnyUrl(CC0_URL),
            creators=[v.charlie],
            confidence=0.99,
            publication_date=datetime.date.today(),
        )
        converter = bioregistry.get_default_converter()
        mappings = list(get_mappings_by_property(prefix=prefix, property_id=property_id, **kwargs))
        sssom_pydantic.write(mappings=mappings, path=path, metadata=metadata, converter=converter)
        yield from mappings


if __name__ == "__main__":
    get_wikidata_mappings()
