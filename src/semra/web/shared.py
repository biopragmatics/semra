"""Shared functionality across flask and fastapi."""

from __future__ import annotations

from dataclasses import dataclass, field

from semra.client import BaseClient, ExampleMapping, FullSummary

__all__ = [
    "EXAMPLE_CONCEPTS",
    "State",
]

EXAMPLE_CONCEPTS = ["efo:0002142"]


@dataclass
class State:
    """Represents application state."""

    client: BaseClient
    summary: FullSummary
    biomappings_hash: str | None = None
    false_mapping_index: set[tuple[str, str]] = field(default_factory=set)

    def example_mappings(self) -> list[ExampleMapping]:
        """Extract example mappings."""
        return self.summary.example_mappings


def _figure_number(n: int) -> tuple[int | float, str]:
    if n > 1_000_000:
        lead = n / 1_000_000
        if lead < 10:
            return round(lead, 1), "M"
        else:
            return round(lead), "M"
    if n > 1_000:
        lead = n / 1_000
        if lead < 10:
            return round(lead, 1), "K"
        else:
            return round(lead), "K"
    else:
        return n, ""
