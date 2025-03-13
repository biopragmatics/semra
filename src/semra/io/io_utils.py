"""Shared I/O functions."""

from __future__ import annotations

from functools import cache
from typing import cast

import bioregistry
import pyobo
import requests

from ..struct import ConfidenceMixin

__all__ = [
    "get_confidence_str",
    "get_name_by_curie",
    "get_orcid_name",
]

SKIP_PREFIXES = {
    "pubchem",
    "pubchem.compound",
    "pubchem.substance",
    "kegg",
    "snomedct",
}
# Skip all ICD prefixes from the https://bioregistry.io/collection/0000004 collection
SKIP_PREFIXES.update(cast(bioregistry.Collection, bioregistry.get_collection("0000004")).resources)


def get_name_by_curie(curie: str) -> str | None:
    """Get a name from a CURIE."""
    if any(curie.startswith(p) for p in SKIP_PREFIXES):
        return None
    if curie.startswith("orcid:"):
        return get_orcid_name(curie)
    return pyobo.get_name_by_curie(curie)


@cache
def get_orcid_name(orcid: str) -> str | None:
    """Retrieve a researcher's name from ORCID's API."""
    if orcid.startswith("orcid:"):
        orcid = orcid[len("orcid:") :]

    try:
        res = requests.get(
            f"https://orcid.org/{orcid}", headers={"Accept": "application/json"}, timeout=5
        ).json()
    except OSError:  # e.g., ReadTimeout
        return None
    name = res.get("person", {}).get("name")
    if name is None:
        return None
    if credit_name := name.get("credit-name"):
        return credit_name["value"]
    if (given_names := name.get("given-names")) and (family_name := name.get("family-name")):
        return f"{given_names['value']} {family_name['value']}"
    return None


#: The precision for confidences used before exporting to the graph data model
CONFIDENCE_PRECISION = 5


def get_confidence_str(x: ConfidenceMixin) -> str:
    """Safely get a confidence from an evidence."""
    confidence = x.get_confidence()
    return str(round(confidence, CONFIDENCE_PRECISION))
