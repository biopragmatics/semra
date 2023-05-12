"""Get mappings from Biomappings."""

from __future__ import annotations

import biomappings

from semra import Mapping
from semra.io import from_biomappings

__all__ = [
    "from_biomappings_positive",
    "from_biomappings_negative",
    "from_biomappings_predicted",
]


def from_biomappings_positive() -> list[Mapping]:
    """Get positive mappings from Biomappings."""
    return from_biomappings(biomappings.load_mappings())


def from_biomappings_negative() -> list[Mapping]:
    """Get positive mappings from Biomappings."""
    return from_biomappings(biomappings.load_false_mappings())


def from_biomappings_predicted() -> list[Mapping]:
    """Get positive mappings from Biomappings."""
    return from_biomappings(biomappings.load_predictions())
