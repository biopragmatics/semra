"""Utilities for SeMRA."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar, cast

import bioregistry
from tqdm.auto import tqdm

__all__ = [
    "cleanup_prefixes",
    "semra_tqdm",
]

X = TypeVar("X")


def semra_tqdm(
    mappings: Iterable[X],
    desc: str | None = None,
    *,
    progress: bool = True,
    leave: bool = True,
) -> Iterable[X]:
    """Wrap an iterable with default kwargs."""
    return cast(
        Iterable[X],
        tqdm(
            mappings,
            unit_scale=True,
            unit="mapping",
            desc=desc,
            leave=leave,
            disable=not progress,
        ),
    )


def cleanup_prefixes(prefixes: str | Iterable[str]) -> set[str]:
    """Standardize a prefix or set of prefixes via :func:`bioregistry.normalize_prefix`."""
    if isinstance(prefixes, str):
        prefixes = [prefixes]
    return {bioregistry.normalize_prefix(prefix, strict=True) for prefix in prefixes}
