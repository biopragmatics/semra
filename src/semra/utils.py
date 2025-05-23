"""Utilities for SeMRA."""

from __future__ import annotations

import gzip
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import TypeVar, cast

import bioregistry
from tqdm.auto import tqdm

__all__ = [
    "cleanup_prefixes",
    "gzip_path",
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


def gzip_path(path: str | Path) -> Path:
    """Compress a file, then delete the original."""
    path = Path(path).expanduser().resolve()
    rv = path.with_suffix(path.suffix + ".gz")
    with open(path, "rb") as ip, gzip.open(rv, mode="wb") as op:
        shutil.copyfileobj(ip, op)
    path.unlink()
    return rv
