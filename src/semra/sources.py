from __future__ import annotations

import logging
from pathlib import Path

import bioontologies
import bioregistry
import pandas as pd
import pyobo
from tqdm.auto import tqdm

from semra.rules import BEN_ORCID, DB_XREF, EXACT_MATCH, MANUAL_MAPPING
from semra.struct import Mapping, Reference, SimpleEvidence

__all__ = [
    "from_cache_df",
    "from_biomappings",
    "from_pyobo",
    "from_bioontologies",
    "from_gilda",
]

logger = logging.getLogger(__name__)


def from_biomappings(mapping_dicts) -> list[Mapping]:
    rv = []
    for mapping_dict in tqdm(mapping_dicts, unit_scale=True, unit="mapping", desc="Loading biomappings"):
        # m["type"],
        # m["source"] or "",
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
            evidence=[SimpleEvidence(justification=MANUAL_MAPPING, mapping_set=source_prefix)],
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
                evidence=[SimpleEvidence(mapping_set=source_prefix, justification=MANUAL_MAPPING)],
            )
        )
    return rv


def from_pyobo(prefix: str, target_prefix: str | None = None, **kwargs) -> list[Mapping]:
    logger.info("loading mappings with PyOBO from %s", prefix)
    if target_prefix:
        return _from_pyobo_pair(prefix, target_prefix, **kwargs)
    return _from_pyobo_prefix(prefix, **kwargs)


GILDA_LOCAL = Path("/Users/cthoyt/dev/gilda/gilda/resources/mesh_mappings.tsv")
GILDA_MAPPINGS = "https://raw.githubusercontent.com/indralab/gilda/master/gilda/resources/mesh_mappings.tsv"


def from_gilda() -> list[Mapping]:
    """Get MeSH and potentially other mappings from Gilda."""
    df = pd.read_csv(
        GILDA_MAPPINGS if not GILDA_LOCAL.is_file() else GILDA_LOCAL,
        sep="\t",
        header=None,
        usecols=[0, 1, 3, 4],
        names=["source_prefix", "source_id", "target_prefix", "target_id"],
    )
    for k in "source_prefix", "target_prefix":
        df[k] = df[k].map(bioregistry.normalize_prefix)
    rv = []
    for sp, si, tp, ti in tqdm(df.values, desc="Loading Gilda", unit="mapping", unit_scale=True):
        if not sp or not tp:
            continue
        m = Mapping(
            s=Reference(prefix=sp, identifier=bioregistry.standardize_identifier(sp, si)),
            p=EXACT_MATCH,
            o=Reference(prefix=tp, identifier=bioregistry.standardize_identifier(tp, ti)),
            evidence=[SimpleEvidence(mapping_set="gilda_mesh", author=BEN_ORCID)],
        )
        rv.append(m)
    return rv


def from_bioontologies(prefix: str) -> list[Mapping]:
    """Load xrefs from a given ontology."""
    o = bioontologies.get_obograph_by_prefix(prefix)
    g = o.guess(prefix)
    g = g.standardize()
    rv = []
    for sp, si, tp, ti in tqdm(g.get_xrefs(), unit="mapping", unit_scale=True):
        m = Mapping(
            s=Reference(prefix=sp, identifier=bioregistry.standardize_identifier(sp, si)),
            p=DB_XREF,
            o=Reference(prefix=tp, identifier=bioregistry.standardize_identifier(tp, ti)),
            evidence=[SimpleEvidence(mapping_set="gilda_mesh")],
        )
        rv.append(m)
    # TODO there might be actual exact match terms somewhere too
    return rv
