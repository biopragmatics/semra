"""Utilities for SeMRA."""

from __future__ import annotations

import gzip
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar, cast

import bioregistry
from tqdm.auto import tqdm

if TYPE_CHECKING:
    import jinja2

__all__ = [
    "LANDSCAPE_FOLDER",
    "cleanup_prefixes",
    "get_jinja_environment",
    "get_jinja_template",
    "gzip_path",
    "semra_tqdm",
]

X = TypeVar("X")
HERE = Path(__file__).parent.resolve()
ROOT = HERE.parent.parent.resolve()
LANDSCAPE_FOLDER = ROOT.joinpath("notebooks", "landscape").resolve()


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


def get_jinja_environment() -> jinja2.Environment:
    """Get the jinja environment."""
    from humanize.time import naturaldelta
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    templates = HERE.joinpath("templates")
    environment = Environment(loader=FileSystemLoader(templates), autoescape=select_autoescape())
    environment.globals.update(naturaldelta=naturaldelta)
    return environment


def get_jinja_template(name: str) -> jinja2.Template:
    """Get a jinja template."""
    environment = get_jinja_environment()
    return environment.get_template(name)
