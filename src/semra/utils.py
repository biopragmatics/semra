"""Utilities for SeMRA."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar, cast

import bioregistry
from pydantic import BeforeValidator
from tqdm.auto import tqdm

if TYPE_CHECKING:
    import jinja2

__all__ = [
    "LANDSCAPE_FOLDER",
    "PrefixListValidator",
    "PrefixPairListValidator",
    "PrefixValidator",
    "cleanup_prefixes",
    "get_jinja_environment",
    "get_jinja_template",
    "get_semra_uri",
    "semra_tqdm",
]

X = TypeVar("X")
HERE = Path(__file__).parent.resolve()
ROOT = HERE.parent.parent.resolve()
LANDSCAPE_FOLDER = ROOT.joinpath("landscape").resolve()


def semra_tqdm(
    mappings: Iterable[X],
    desc: str | None = None,
    *,
    progress: bool = True,
    leave: bool = False,
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


def _vv(prefix: str) -> None:
    resource = bioregistry.get_resource(prefix)
    if resource is None:
        raise ValueError(f"Invalid prefix: {prefix}")
    if resource.prefix != prefix:
        raise ValueError(f"non-standard prefix {prefix} should be {resource.prefix}")
    if resource.has_canonical:
        raise ValueError(
            f"non-standard prefix {prefix} should use canonical {resource.has_canonical}"
        )
    if resource.provides:
        raise ValueError(
            f"non-standard prefix {prefix} provides for {resource.provides} (should use {resource.provides})"
        )


def _validate_prefix(prefix: str | None) -> str | None:
    if prefix is None:
        return None
    _vv(prefix)
    return prefix


PrefixValidator = BeforeValidator(_validate_prefix)


def _validate_prefix_list(prefixes: list[str] | None) -> list[str] | None:
    if prefixes is None:
        return None
    for prefix in prefixes:
        _vv(prefix)
    return prefixes


PrefixListValidator = BeforeValidator(_validate_prefix_list)


def _validate_prefix_pair_list(
    prefixes: list[tuple[str, str]] | None,
) -> list[tuple[str, str]] | None:
    if prefixes is None:
        return None
    for left, right in prefixes:
        _vv(left)
        _vv(right)
    return prefixes


PrefixPairListValidator = BeforeValidator(_validate_prefix_pair_list)


def get_semra_uri(*keys: str, gzip: bool = False) -> str:
    """Get a SeMRA URI."""
    parts = "/".join(keys)
    rv = f"https://w3id.org/biopragmatics/semra/{parts}.sssom.tsv"
    if gzip:
        rv += ".gz"
    return rv
