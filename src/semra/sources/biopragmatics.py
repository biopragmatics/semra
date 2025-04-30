"""Get mappings from Biomappings."""

from __future__ import annotations

import importlib.metadata
from collections.abc import Iterable
from typing import Any

import pandas as pd
from pyobo import Reference
from tqdm.asyncio import tqdm

from semra.struct import Mapping, MappingSet, SimpleEvidence

__all__ = [
    "from_biomappings_negative",
    "from_biomappings_predicted",
    "get_biomappings_positive_mappings",
]


def get_biomappings_positive_mappings() -> list[Mapping]:
    """Get positive mappings from Biomappings."""
    try:
        import biomappings
    except ImportError:
        return read_remote_tsv("mappings.tsv")
    else:
        return _process(biomappings.load_mappings())


def from_biomappings_negative() -> list[Mapping]:
    """Get negative mappings from Biomappings."""
    try:
        import biomappings
    except ImportError:
        return read_remote_tsv("incorrect.tsv")
    else:
        return _process(biomappings.load_false_mappings())


def from_biomappings_predicted() -> list[Mapping]:
    """Get predicted mappings from Biomappings."""
    try:
        import biomappings
    except ImportError:
        return read_remote_tsv("predictions.tsv")
    else:
        return _process(biomappings.load_predictions())


BASE_URL = "https://github.com/biopragmatics/biomappings/raw/master/src/biomappings/resources"


def read_remote_tsv(name: str) -> list[Mapping]:
    """Load a remote mapping file from the Biomappings github repository."""
    url = f"{BASE_URL}/{name}"
    df = pd.read_csv(url, sep="\t")
    mapping_dicts = df.to_json(orient="records")
    return _process(mapping_dicts)


def _process(mapping_dicts: Iterable[dict[str, Any]], confidence: float = 0.999) -> list[Mapping]:
    try:
        biomappings_version = importlib.metadata.version("biomappings")
    except Exception:
        biomappings_version = None
    mapping_set = MappingSet(
        name="biomappings", confidence=confidence, license="CC0", version=biomappings_version
    )
    rv = []
    for mapping_dict in tqdm(
        mapping_dicts, unit_scale=True, unit="mapping", desc="Loading biomappings", leave=False
    ):
        if (source := mapping_dict["source"]).startswith("orcid"):
            author = Reference.from_curie(source)
        else:
            author = None
        subject = Reference(
            prefix=mapping_dict["source prefix"],
            identifier=mapping_dict["source identifier"],
        )
        obj = Reference(
            prefix=mapping_dict["target prefix"],
            identifier=mapping_dict["target identifier"],
        )
        predicate = Reference.from_curie(mapping_dict["relation"])
        if predicate is None:
            continue
        # TODO remove below?
        if predicate.curie == "oboinowl:hasDbXref":
            predicate = Reference(
                prefix="oboInOwl", identifier="hasDbXref", name="has database cross-reference"
            )
        elif predicate.curie == "skos:exactMatch":
            predicate = Reference(prefix="skos", identifier="exactMatch", name="exact match")

        mm = Mapping(
            subject=subject,
            predicate=predicate,
            object=obj,
            evidence=[
                SimpleEvidence(
                    justification=Reference.from_curie(mapping_dict["type"]),
                    mapping_set=mapping_set,
                    author=author,
                    # TODO configurable confidence globally per author or
                    #  based on author's self-reported confidence
                )
            ],
        )
        rv.append(mm)
    return rv
