"""Shared I/O functions."""

from __future__ import annotations

import bioregistry
import curies
import pyobo

from ..utils import get_orcid_name

__all__ = [
    "get_name_by_reference",
]

SKIP_PREFIXES = {
    "pubchem",
    "pubchem.compound",
    "pubchem.substance",
    "kegg",
    "snomedct",
}
# Skip all ICD prefixes from the https://bioregistry.io/collection/0000004 collection
SKIP_PREFIXES.update(bioregistry.get_collection("0000004", strict=True).get_prefixes())


def get_name_by_reference(reference: curies.Reference) -> str | None:
    """Get a name from a CURIE."""
    if any(reference.prefix == p for p in SKIP_PREFIXES):
        return None
    if reference.prefix == "orcid":
        return get_orcid_name(reference.identifier)
    return pyobo.get_name(reference)
