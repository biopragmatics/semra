from __future__ import annotations

import logging

import bioregistry
import pandas as pd
import pyobo
from tqdm.auto import tqdm

from semra.rules import DB_XREF
from semra.struct import Evidence, Mapping, Reference

__all__ = [
    "from_cache_df",
    "from_biomappings",
    "from_pyobo",
]

logger = logging.getLogger(__name__)


def from_biomappings(xxx) -> list[Mapping]:
    rv = []
    for m in tqdm(xxx, unit_scale=True, unit="mapping", desc="Loading biomappings"):
        # m["type"],
        # m["source"] or "",
        try:
            p = Reference.from_curie(m["relation"])
        except ValueError:
            continue  # TODO fix speciesSpecific
        source_prefix = m["source prefix"]
        source_identifier = bioregistry.standardize_identifier(source_prefix, m["source identifier"])
        target_prefix = m["target prefix"]
        target_identifier = bioregistry.standardize_identifier(target_prefix, m["target identifier"])
        mm = Mapping(
            s=Reference(prefix=source_prefix, identifier=source_identifier),
            p=p,
            o=Reference(prefix=target_prefix, identifier=target_identifier),
            evidence=[
                Evidence(
                    justification=Reference.from_curie("semapv:ManualMappingCuration"),  # FIXME base on m["type"]
                    mapping_set="biomappings",
                )
            ],
        )
        rv.append(mm)
    return rv


def _from_pyobo_prefix(source_prefix: str, **kwargs) -> list[Mapping]:
    df = pyobo.get_xrefs_df(source_prefix, **kwargs)
    return _from_df(df, source_prefix=source_prefix)


def _from_pyobo_pair(source_prefix: str, target_prefix: str, **kwargs) -> list[Mapping]:
    df = pyobo.get_xrefs(source_prefix, target_prefix, **kwargs)
    mappings = [
        Mapping(
            s=Reference(
                prefix=source_prefix,
                identifier=bioregistry.standardize_identifier(source_prefix, source_id),
            ),
            p=DB_XREF,
            o=Reference(
                prefix=target_prefix,
                identifier=bioregistry.standardize_identifier(target_prefix, target_id),
            ),
            evidence=[Evidence(mapping_set=source_prefix)],
        )
        for source_id, target_id in df.items()
    ]
    return mappings


def from_cache_df(path, source_prefix: str, *, prefixes=None, predicate: Reference | None = None) -> list[Mapping]:
    logger.info("loading cached dataframe from PyOBO for %s", source_prefix)
    df = pd.read_csv(path, sep="\t")
    if prefixes:
        df = df[df[df.columns[1]].isin(prefixes)]
    return _from_df(df, source_prefix=source_prefix, predicate=predicate)


def _from_df(df, source_prefix, predicate: Reference | None = None) -> list[Mapping]:
    if predicate is None:
        predicate = DB_XREF
    rv = []
    for source_id, target_prefix, target_id in tqdm(df.values, desc=f"Loading {source_prefix}", unit_scale=True):
        rv.append(
            Mapping(
                s=Reference(
                    prefix=source_prefix,
                    identifier=bioregistry.standardize_identifier(source_prefix, source_id),
                ),
                p=predicate,
                o=Reference(
                    prefix=target_prefix,
                    identifier=bioregistry.standardize_identifier(target_prefix, target_id),
                ),
                evidence=[Evidence(mapping_set=source_prefix)],
            )
        )
    return rv


def from_pyobo(prefix: str, target_prefix: str | None = None, **kwargs) -> list[Mapping]:
    logger.info("loading mappings with PyOBO from %s", prefix)
    if target_prefix:
        return _from_pyobo_pair(prefix, target_prefix, **kwargs)
    return _from_pyobo_prefix(prefix, **kwargs)
