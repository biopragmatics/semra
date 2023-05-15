from __future__ import annotations

import logging
from pathlib import Path
from typing import TextIO

import bioontologies
import bioregistry
import pandas as pd
import pyobo
from tqdm.auto import tqdm

from semra.rules import DB_XREF, MANUAL_MAPPING
from semra.struct import Evidence, Mapping, Reference, SimpleEvidence

__all__ = [
    "from_cache_df",
    "from_biomappings",
    "from_pyobo",
    "from_bioontologies",
    "from_sssom",
    "get_sssom_df",
    "write_sssom",
]

logger = logging.getLogger(__name__)


def from_biomappings(mapping_dicts, confidence: float = 0.99) -> list[Mapping]:
    rv = []
    for mapping_dict in tqdm(mapping_dicts, unit_scale=True, unit="mapping", desc="Loading biomappings"):
        try:
            p = Reference.from_curie(mapping_dict["relation"])
        except ValueError:
            continue  # TODO fix speciesSpecific
        source_prefix = mapping_dict["source prefix"]
        source_identifier = bioregistry.standardize_identifier(source_prefix, mapping_dict["source identifier"])
        target_prefix = mapping_dict["target prefix"]
        target_identifier = bioregistry.standardize_identifier(target_prefix, mapping_dict["target identifier"])
        author = Reference.from_curie(mapping_dict["source"])
        mm = Mapping(
            s=Reference(prefix=source_prefix, identifier=source_identifier),
            p=p,
            o=Reference(prefix=target_prefix, identifier=target_identifier),
            evidence=[
                SimpleEvidence(
                    justification=Reference.from_curie(mapping_dict["type"]),
                    mapping_set="biomappings",
                    author=author,
                    confidence=confidence,
                    # TODO configurable confidence globally per author or based on author's self-reported confidence
                )
            ],
        )
        rv.append(mm)
    return rv


def _from_pyobo_prefix(source_prefix: str, *, confidence=None, standardize: bool = False, **kwargs) -> list[Mapping]:
    df = pyobo.get_xrefs_df(source_prefix, **kwargs)
    return _from_df(df, source_prefix=source_prefix, standardize=standardize, confidence=confidence)


def _from_pyobo_pair(source_prefix: str, target_prefix: str, *, confidence=None, **kwargs) -> list[Mapping]:
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
            evidence=[SimpleEvidence(justification=MANUAL_MAPPING, mapping_set=source_prefix, confidence=confidence)],
        )
        for source_id, target_id in df.items()
    ]
    return mappings


def from_cache_df(
    path,
    source_prefix: str,
    *,
    prefixes=None,
    predicate: Reference | None = None,
    standardize: bool = True,
) -> list[Mapping]:
    logger.info("loading cached dataframe from PyOBO for %s", source_prefix)
    df = pd.read_csv(path, sep="\t")
    if prefixes:
        df = df[df[df.columns[1]].isin(prefixes)]
    return _from_df(df, source_prefix=source_prefix, predicate=predicate, standardize=standardize)


def _from_df(
    df, source_prefix, predicate: Reference | None = None, *, confidence=None, standardize: bool = False
) -> list[Mapping]:
    if predicate is None:
        predicate = DB_XREF
    rv = []
    if standardize:
        df[df.columns[0]] = df[df.columns[0]].map(lambda s: bioregistry.standardize_identifier(source_prefix, s))
        df[df.columns[2]] = [
            bioregistry.standardize_identifier(target_prefix, target_id)
            for target_prefix, target_id in df[df.columns[1:]].values
        ]
    for source_id, target_prefix, target_id in tqdm(df.values, desc=f"Loading {source_prefix}", unit_scale=True):
        rv.append(
            Mapping(
                s=Reference(
                    prefix=source_prefix,
                    identifier=source_id,
                ),
                p=predicate,
                o=Reference(
                    prefix=target_prefix,
                    identifier=target_id,
                ),
                evidence=[
                    SimpleEvidence(mapping_set=source_prefix, justification=MANUAL_MAPPING, confidence=confidence)
                ],
            )
        )
    return rv


def from_pyobo(prefix: str, target_prefix: str | None = None, *, standardize: bool = False, **kwargs) -> list[Mapping]:
    logger.info("loading mappings with PyOBO from %s", prefix)
    if target_prefix:
        return _from_pyobo_pair(prefix, target_prefix, standardize=standardize, **kwargs)
    return _from_pyobo_prefix(prefix, standardize=standardize, **kwargs)


def from_bioontologies(prefix: str, confidence=None) -> list[Mapping]:
    """Load xrefs from a given ontology."""
    o = bioontologies.get_obograph_by_prefix(prefix)
    g = o.guess(prefix)
    g = g.standardize()
    rv = []
    evidence = SimpleEvidence(mapping_set=prefix, confidence=confidence)
    for sp, si, tp, ti in tqdm(g.get_xrefs(), unit="mapping", unit_scale=True):
        m = Mapping(
            s=Reference(prefix=sp, identifier=bioregistry.standardize_identifier(sp, si)),
            p=DB_XREF,
            o=Reference(prefix=tp, identifier=bioregistry.standardize_identifier(tp, ti)),
            evidence=[evidence],
        )
        rv.append(m)
    # TODO there might be actual exact match terms somewhere too
    return rv


def from_sssom(path) -> list[Mapping]:
    df = pd.read_csv(path, sep="\t", dtype=str)
    columns = [
        "subject_id",
        "predicate_id",
        "object_id",
        "mapping_justification",
        # TODO add more
    ]
    rv = []
    for s, p, o, justification, *_ in df[columns].values:
        rv.append(
            Mapping(
                s=Reference.from_curie(s),
                p=Reference.from_curie(p),
                o=Reference.from_curie(o),
                evidence=[SimpleEvidence(justification=Reference.from_curie(justification))],
            )
        )
    return rv


def get_sssom_df(mappings: list[Mapping]) -> pd.DataFrame:
    import pandas as pd

    rows = [_get_sssom_row(m, e) for m in mappings for e in m.evidence]
    columns = [
        "subject_id",
        "predicate_id",
        "object_id",
        "mapping_justification",
        "mapping_set",
        "author_id",
        "confidence",
        "comments",
    ]
    return pd.DataFrame(rows, columns=columns)


def _get_sssom_row(mapping: Mapping, e: Evidence):
    # TODO increase this
    return (
        mapping.s.curie,
        mapping.p.curie,
        mapping.o.curie,
        e.justification.curie if e.justification else "",
        e.mapping_set or "",
        e.author.curie if e.author else "",
        round(e.confidence, 4) if e.confidence else "",
        e.explanation,
    )


def write_sssom(mappings: list[Mapping], file: str | Path | TextIO) -> None:
    """Export mappings as an SSSOM file (may be lossy)."""
    df = get_sssom_df(mappings)
    df.to_csv(file, sep="\t", index=False)