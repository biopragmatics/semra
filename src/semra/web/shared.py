"""Shared functionality across flask and fastapi."""

from __future__ import annotations

from dataclasses import dataclass, field

from pyobo import Reference

from semra.client import BaseClient, FullSummary

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
    example_reference: Reference | None = None
    biomappings_hash: str | None = None
    false_mapping_index: set[tuple[str, str]] = field(default_factory=set)
    current_author: Reference | None = None
