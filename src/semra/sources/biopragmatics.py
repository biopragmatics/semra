"""Get mappings from Biomappings."""

from __future__ import annotations

from sssom_pydantic import SemanticMapping

from semra.constants import CC0_URL, Reference

__all__ = [
    "get_biomappings_negative_mappings",
    "get_biomappings_positive_mappings",
    "get_biomappings_predicted_mappings",
]

URL = "https://w3id.org/biopragmatics/biomappings/sssom/biomappings.sssom.tsv"
BIOMAPPINGS_WIKIDATA_ID = "Q111239110"


def get_biomappings_positive_mappings() -> list[SemanticMapping]:
    """Get positive mappings from Biomappings."""
    from biomappings import load_positive_mappings

    return _fix_biomappings(load_positive_mappings())


def get_biomappings_negative_mappings() -> list[SemanticMapping]:
    """Get negative mappings from Biomappings."""
    from biomappings import load_false_mappings

    return _fix_biomappings(load_false_mappings())


def get_biomappings_predicted_mappings() -> list[SemanticMapping]:
    """Get predicted mappings from Biomappings."""
    from biomappings import load_predictions

    return _fix_biomappings(load_predictions())


def _fix_biomappings(mappings: list[SemanticMapping]) -> list[SemanticMapping]:
    update = {
        "source": Reference(prefix="wikidata", identifier=BIOMAPPINGS_WIKIDATA_ID),
        "license": CC0_URL,
    }
    return [mapping.model_copy(update=update) for mapping in mappings]
