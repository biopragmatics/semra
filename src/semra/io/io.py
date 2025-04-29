"""I/O functions for SeMRA."""

from __future__ import annotations

import gzip
import logging
import pickle
import typing as t
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TextIO, cast

import bioontologies
import bioregistry
import bioversions
import pandas as pd
import pydantic
import pyobo
import pyobo.utils
import requests
import yaml
from tqdm.autonotebook import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from .io_utils import get_confidence_str, get_name_by_curie, safe_open, safe_open_writer
from ..rules import UNSPECIFIED_MAPPING
from ..struct import Evidence, Mapping, MappingSet, ReasonedEvidence, Reference, SimpleEvidence

__all__ = [
    "from_bioontologies",
    "from_cache_df",
    "from_jsonl",
    "from_pickle",
    "from_pyobo",
    "from_sssom",
    "from_sssom_df",
    "get_sssom_df",
    "write_jsonl",
    "write_pickle",
    "write_sssom",
]

logger = logging.getLogger(__name__)

#: The default confidence for ontology-based mappings
DEFAULT_ONTOLOGY_CONFIDENCE = 0.9


def _safe_get_version(prefix: str) -> str | None:
    """Get a version from Bioversions, or return None if not possible."""
    try:
        return bioversions.get_version(prefix)
    except (KeyError, TypeError):
        return None


# TODO delete this
def from_cache_df(
    path: str | Path,
    source_prefix: str,
    *,
    prefixes: t.Collection[str] | None = None,
    standardize: bool = True,
    version: str | None = None,
    license: str | None = None,
    confidence: float | None = None,
    justification: Reference | None = None,
) -> list[Mapping]:
    """Get mappings from a :mod:`pyobo`-flavored cache file.

    :param path: The path to a dataframe containing mappings in the following columns:

        1. Local unique identifiers from the source prefix
        2. Cross-reference prefix
        3. Cross-reference local unique identifier
    :param source_prefix: The prefix of the ontology
    :param prefixes: A set of prefixes to subset the second column of cross-reference
        targets
    :param confidence: The confidence level for the mappings. Defaults to
        :data:`DEFAULT_ONTOLOGY_CONFIDENCE`
    :param standardize: Should the local unique identifiers in the first and third
        columns be standardized using :func:`bioregistry.standardize_identifier`?
        Defaults to false.
    :param version: The version of the ontology that's been loaded (does not proactively
        load, but you can use :func:`bioversions.get_version` to go along with PyOBO).
    :param license: The license of the ontology that's been loaded. If not given, will
        try and look up with :func:`bioregistry.get_license`.
    :param justification: The justification from the SEMAPV vocabulary (given as a
        Reference object). If not given, defaults to :data:`UNSPECIFIED_MAPPING`.

    :returns: A list of semantic mapping objects
    """
    logger.info("loading cached dataframe from PyOBO for %s", source_prefix)
    df = pd.read_csv(path, sep="\t")
    return _from_pyobo_sssom_df(
        df,
        prefix=source_prefix,
        prefixes=prefixes,
        standardize=standardize,
        version=version,
        license=license,
        confidence=confidence,
        justification=justification,
    )


def from_pyobo(
    prefix: str,
    target_prefix: str | None = None,
    *,
    standardize: bool = True,
    version: str | None = None,
    license: str | None = None,
    confidence: float | None = None,
    justification: Reference | None = None,
    force_process: bool = False,
    cache: bool = True,
) -> list[Mapping]:
    """Get mappings from a given ontology via :mod:`pyobo`.

    :param prefix: The prefix of the ontology to get semantic mappings from
    :param target_prefix: The optional prefix for targets for semantic mappings.
    :param standardize: Should the local unique identifiers in the first and third
        columns be standardized using :func:`bioregistry.standardize_identifier`?
        Defaults to true.
    :param confidence: The confidence level for the mappings. Defaults to
        :data:`DEFAULT_ONTOLOGY_CONFIDENCE`.
    :param version: The version of the ontology that's been loaded (does not proactively
        load, but you can use :func:`bioversions.get_version` to go along with PyOBO).
    :param license: The license of the ontology that's been loaded. If not given, will
        try and look up with :func:`bioregistry.get_license`.
    :param justification: The justification from the SEMAPV vocabulary (given as a
        Reference object). If not given, defaults to :data:`UNSPECIFIED_MAPPING`.
    :param force_process: force re-processing of the source data, e.g., the OBO file for
        external ontologies or the locally cached data for PyOBO custom sources
    :param cache: Should the ontology be automatically cached? Turn off to

    :returns: A list of semantic mapping objects
    """
    df: pd.DataFrame = pyobo.get_mappings_df(
        prefix, force_process=force_process, names=False, cache=cache
    )
    return _from_pyobo_sssom_df(
        df,
        prefix=prefix,
        prefixes={target_prefix} if target_prefix else None,
        standardize=standardize,
        version=version,
        license=license,
        confidence=confidence,
        justification=justification,
    )


def _from_pyobo_sssom_df(
    df: pd.DataFrame,
    prefix: str,
    *,
    prefixes: str | t.Collection[str] | None = None,
    confidence: float | None = None,
    standardize: bool = True,
    version: str | None = None,
    license: str | None = None,
    justification: Reference | None = None,
    mapping_set_name: str | None = None,
) -> list[Mapping]:
    """Get mappings from a :mod:`pyobo`-flavored cache file.

    :param df: A dataframe containing mappings in the following columns:

        1. Local unique identifiers from the source prefix
        2. Cross-reference prefix
        3. Cross-reference local unique identifier
    :param prefix: The prefix of the ontology
    :param prefixes: A set of prefixes to subset the second column of cross-reference
        targets
    :param confidence: The confidence level for the mappings. Defaults to
        :data:`DEFAULT_ONTOLOGY_CONFIDENCE`
    :param standardize: Should the local unique identifiers in the first and third
        columns be standardized using :func:`bioregistry.standardize_identifier`?
        Defaults to false.
    :param version: The version of the ontology that's been loaded (does not proactively
        load, but you can use :func:`bioversions.get_version` to go along with PyOBO).
    :param license: The license of the ontology that's been loaded. If not given, will
        try and look up with :func:`bioregistry.get_license`.
    :param justification: The justification from the SEMAPV vocabulary (given as a
        Reference object). If not given, defaults to :data:`UNSPECIFIED_MAPPING`.

    :returns: A list of semantic mapping objects
    """
    if justification is None:
        justification = UNSPECIFIED_MAPPING
    if confidence is None:
        confidence = DEFAULT_ONTOLOGY_CONFIDENCE
    if license is None:
        license = bioregistry.get_license(prefix)
    if mapping_set_name is None:
        mapping_set_name = bioregistry.get_name(prefix)
    if prefixes:
        df = _filter_sssom_by_prefixes(df, prefixes)
    return from_sssom_df(
        df,
        standardize=standardize,
        license=license,
        version=version,
        justification=justification,
        mapping_set_confidence=confidence,
        mapping_set_name=mapping_set_name,  # TODO rename to mapping_set_title align with SSSOM
    )


def _filter_sssom_by_prefixes(df: pd.DataFrame, prefixes: str | t.Collection[str]) -> pd.DataFrame:
    if isinstance(prefixes, str):
        prefix_ = prefixes + ":"
        idx = df["object_id"].str.startswith(prefix_)
    else:
        prefix_tuple = tuple(set(prefixes))
        idx = df["object_id"].map(
            lambda curie: any(curie.startswith(f"{prefix}:") for prefix in prefix_tuple)
        )
    return df[idx]


def from_bioontologies(
    prefix: str, confidence: float | None = None, **kwargs: Any
) -> list[Mapping]:
    """Get mappings from a given ontology via :mod:`bioontologies`."""
    if confidence is None:
        confidence = DEFAULT_ONTOLOGY_CONFIDENCE
    o = bioontologies.get_obograph_by_prefix(prefix, **kwargs)
    g = o.guess(prefix)
    # note that we don't extract stuff from edges so just node standardization is good enough
    for node in tqdm(
        g.nodes, desc=f"[{prefix}] standardizing", unit="node", unit_scale=True, leave=False
    ):
        node.standardize()
    br_license = bioregistry.get_license(prefix)
    mappings = []
    for subject, predicate, obj in tqdm(
        g.get_xrefs(), unit="mapping", unit_scale=True, leave=False
    ):
        if predicate.curie == "oboinowl:hasDbXref":
            predicate = Reference(
                prefix="oboInOwl", identifier="hasDbXref", name="has database cross-reference"
            )
        elif predicate.curie == "skos:exactMatch":
            predicate = Reference(prefix="skos", identifier="exactMatch", name="exact match")
        mapping = Mapping.from_triple(
            (subject, predicate, obj),
            evidence=[
                SimpleEvidence(
                    justification=UNSPECIFIED_MAPPING,
                    mapping_set=MappingSet(
                        name=prefix, version=g.version, confidence=confidence, license=br_license
                    ),
                )
            ],
        )
        mappings.append(mapping)
    return mappings


def from_sssom(
    path: str | Path,
    *,
    mapping_set_id: str | None = None,
    mapping_set_name: str | None = None,
    mapping_set_confidence: float | None = None,
    license: str | None = None,
    justification: Reference | None = None,
    version: str | None = None,
    standardize: bool = True,
    metadata: str | None = None,
) -> list[Mapping]:
    """Get mappings from a path to a SSSOM TSV file.

    :param path: The local file path or URL to a SSSOM TSV file. This is also interpreted
        as the SSSOM ``mapping_set_id`` field.
    :param mapping_set_id: The ID for the SSSOM mapping set. If not given,
        the ``path`` is used.
    :param mapping_set_name: The title for the SSSOM mapping set, if not given
        explicitly in each mapping row nor by ``metadata``
    :param mapping_set_confidence:
        The confidence associated with all mappings in the
        mapping set. This diverges from the SSSOM data model in that each mapping can
        specify its own confidence, but there is no global confidence at the set level.

        .. seealso:: https://github.com/mapping-commons/sssom/issues/438
    :param license: The license for the SSSOM mapping set, if not given explicitly in
        each mapping row nor by ``metadata``.
    :param justification: The mapping justification for all mappings in the SSSOM
        mapping set, if not given explicitly in each mapping row nor by ``metadata``.
        Given as a :class:`curies.Reference` object using ``semapv`` as the prefix.
    :param version: The title for the SSSOM mapping set, if not given explicitly in each
        mapping row nor by ``metadata``.
    :param standardize: Should Bioregistry be applied to standardize all
    :param metadata: A URL to a SSSOM metadata file, which can contain an external
        definition of several of the relevant metadata fields accepted by this function.

    :returns: A list of SeMRA mapping objects

    Load a SSSOM file by URL that has external metadata

    .. code-block:: python

        mappings = from_sssom(
            "https://w3id.org/biopragmatics/biomappings/sssom/biomappings.sssom.tsv",
            mapping_set_confidence=0.85,
            metadata="https://w3id.org/biopragmatics/biomappings/sssom/biomappings.sssom.yml",
        )
    """
    # FIXME use sssom-py for this
    df = pd.read_csv(path, sep="\t", dtype=str)
    return from_sssom_df(
        df,
        mapping_set_id=mapping_set_id or (path.as_uri() if isinstance(path, Path) else path),
        mapping_set_name=mapping_set_name,
        mapping_set_confidence=mapping_set_confidence,
        license=license,
        justification=justification,
        version=version,
        standardize=standardize,
        metadata=metadata,
    )


def from_sssom_df(
    df: pd.DataFrame,
    *,
    mapping_set_id: str | None = None,
    mapping_set_name: str | None = None,
    mapping_set_confidence: float | None = None,
    license: str | None = None,
    justification: Reference | None = None,
    version: str | None = None,
    _uuid: uuid.UUID | None = None,
    standardize: bool = True,
    metadata: str | None = None,
) -> list[Mapping]:
    """Get mappings from a SSSOM dataframe."""
    df = df.rename(
        columns={
            "source_id": "subject_id",
            "source_label": "subject_label",
            "target_id": "object_id",
            "target_label": "object_label",
            "justification": "mapping_justification",
            "mapping_set_name": "mapping_set_title",
        }
    )
    if metadata:
        metadata_dict = yaml.safe_load(requests.get(metadata, timeout=15).text)
        if mapping_set_name is None:
            mapping_set_name = metadata_dict.get("mapping_set_title")
        if mapping_set_id is None:
            mapping_set_name = metadata_dict.get("mapping_set_id")
        if version is None:
            version = metadata_dict.get("mapping_set_version")
        if license is None:
            license = metadata_dict.get("license")

    return [
        _parse_sssom_row(
            row,
            mapping_set_id=mapping_set_id,
            mapping_set_name=mapping_set_name,
            mapping_set_confidence=mapping_set_confidence,
            license=license,
            mapping_set_version=version,
            justification=justification,
            standardize=standardize,
            _uuid=_uuid,
        )
        for _, row in tqdm(
            df.iterrows(),
            total=len(df.index),
            leave=False,
            unit_scale=True,
            unit="row",
            desc="Loading SSSOM dataframe",
        )
    ]


def _parse_sssom_row(
    row: dict[str, Any],
    mapping_set_id: str | None,
    mapping_set_name: str | None,
    mapping_set_confidence: float | None,
    license: str | None,
    justification: Reference | None,
    mapping_set_version: str | None,
    standardize: bool,
    _uuid: uuid.UUID | None = None,
) -> Mapping:
    if "author_id" in row and pd.notna(row["author_id"]):
        author = _from_curie(row["author_id"], standardize=standardize)
    else:
        author = None

    # See https://mapping-commons.github.io/sssom/mapping_set_title/
    if mapping_set_name is not None:
        pass
    elif "mapping_set_title" in row and pd.notna(row["mapping_set_title"]):
        mapping_set_name = row["mapping_set_title"]
    elif "mapping_set" in row and pd.notna(row["mapping_set"]):
        mapping_set_name = row["mapping_set"]
    elif mapping_set_name is None:
        raise KeyError("need a mapping set name")

    # note that ``mapping_set_confidence`` isn't actually part of the SSSOM standard (yet),
    # see https://github.com/mapping-commons/sssom/issues/438
    if mapping_set_confidence is not None:
        pass
    elif "mapping_set_confidence" in row and pd.notna(row["mapping_set_confidence"]):
        mapping_set_confidence = row["mapping_set_confidence"]

    # See https://mapping-commons.github.io/sssom/mapping_set_version/
    if mapping_set_version is not None:
        pass
    elif "mapping_set_version" in row and pd.notna(row["mapping_set_version"]):
        mapping_set_version = row["mapping_set_version"]

    # See https://mapping-commons.github.io/sssom/mapping_set_id/
    if mapping_set_id is not None:
        pass
    elif "mapping_set_id" in row and pd.notna(row["mapping_set_id"]):
        mapping_set_id = row["mapping_set_id"]

    # See https://mapping-commons.github.io/sssom/license/
    if license is not None:
        pass
    elif "license" in row and pd.notna(row["license"]):
        license = row["license"]

    mapping_set = MappingSet(
        id=mapping_set_id,
        name=mapping_set_name,
        version=mapping_set_version,
        license=license,
        confidence=mapping_set_confidence,
    )

    if justification is not None:
        pass
    elif "mapping_justification" in row and pd.notna(row["mapping_justification"]):
        justification = Reference.from_curie(row["mapping_justification"])
    else:
        justification = UNSPECIFIED_MAPPING

    s = _from_curie(row["subject_id"], standardize=standardize, name=row.get("subject_label"))
    p = _from_curie(row["predicate_id"], standardize=standardize, name=row.get("predicate_label"))
    if p.curie == "oboinowl:hasDbXref":
        p = Reference(
            prefix="oboInOwl", identifier="hasDbXref", name="has database cross-reference"
        )
    elif p.curie == "skos:exactMatch":
        p = Reference(prefix="skos", identifier="exactMatch", name="exact match")
    o = _from_curie(row["object_id"], standardize=standardize, name=row.get("object_label"))
    e: dict[str, t.Any] = {
        "justification": justification,
        "mapping_set": mapping_set,
        "author": author,
        # TODO add mapping confidence here?
    }
    if _uuid:
        e["uuid"] = _uuid

    return Mapping(s=s, p=p, o=o, evidence=[SimpleEvidence.model_validate(e)])


def _from_curie(curie: str, *, standardize: bool, name: str | None = None) -> Reference:
    has_name = pd.notna(name) and name
    if not standardize:
        if has_name:
            return Reference.from_curie(curie, name=cast(str, name))
        else:
            return Reference.from_curie(curie)

    prefix, identifier = bioregistry.parse_curie(curie)
    if not prefix or not identifier:
        raise ValueError(f"could not standardize curie: {curie}")

    if has_name:
        return Reference(prefix=prefix, identifier=identifier, name=name)
    else:
        return Reference(prefix=prefix, identifier=identifier)


SSSOM_DEFAULT_COLUMNS = [
    "subject_id",
    "predicate_id",
    "object_id",
    "mapping_justification",
    "mapping_set",
    "mapping_set_version",
    "mapping_set_license",
    "mapping_set_confidence",
    "author_id",
    "comment",
]


def get_sssom_df(
    mappings: list[Mapping], *, add_labels: bool = False, prune: bool = True
) -> pd.DataFrame:
    """Get a SSSOM dataframe.

    Automatically prunes columns that aren't filled out.

    :param mappings: A list of mappings
    :param add_labels: Should labels be added for source and object via
        :func:`pyobo.get_name_by_curie`?

    :returns: A SSSOM dataframe in Pandas
    """
    rows = [
        _get_sssom_row(m, e)
        for m in tqdm(
            mappings, desc="Preparing SSSOM", leave=False, unit="mapping", unit_scale=True
        )
        for e in m.evidence
    ]
    df = pd.DataFrame(rows, columns=SSSOM_DEFAULT_COLUMNS)
    if add_labels:
        with logging_redirect_tqdm():
            for label_column, id_column in [
                ("subject_label", "subject_id"),
                ("object_label", "object_id"),
            ]:
                df[label_column] = df[id_column].map(get_name_by_curie)
        df = df[
            [
                "subject_id",
                "subject_label",
                "predicate_id",
                "object_id",
                "object_label",
                "mapping_justification",
                "mapping_set",
                "mapping_set_version",
                "mapping_set_license",
                "mapping_set_confidence",
                "author_id",
                "comment",
            ]
        ]

    if prune:
        # remove empty columns
        for column in df.columns:
            if not df[column].map(bool).any():
                del df[column]

    return df


def _get_sssom_row(mapping: Mapping, e: Evidence) -> tuple[str, ...]:
    # TODO increase this
    if isinstance(e, SimpleEvidence):
        mapping_set_version = e.mapping_set.version or ""
        mapping_set_license = e.mapping_set.license or ""
    elif isinstance(e, ReasonedEvidence):
        mapping_set_version = ""
        mapping_set_license = ""
    else:
        raise TypeError
    return (
        mapping.s.curie,
        mapping.p.curie,
        mapping.o.curie,
        e.justification.curie,
        ",".join(sorted(e.mapping_set_names)),
        mapping_set_version,
        mapping_set_license,
        get_confidence_str(e),
        e.author.curie if e.author else "",
        e.explanation,
    )


def write_sssom(
    mappings: list[Mapping],
    file: str | Path | TextIO,
    *,
    add_labels: bool = False,
    prune: bool = True,
) -> None:
    """Export mappings as an SSSOM file (could be lossy)."""
    if not add_labels and not prune:
        _write_sssom_stream(mappings, file)
    df = get_sssom_df(mappings, add_labels=add_labels)
    df.to_csv(file, sep="\t", index=False)


def _write_sssom_stream(mappings: Iterable[Mapping], file: str | Path | TextIO) -> None:
    with safe_open_writer(file) as writer:
        writer.writerow(SSSOM_DEFAULT_COLUMNS)
        writer.writerows(
            _get_sssom_row(m, e)
            for m in tqdm(
                mappings, desc="Writing SSSOM", leave=False, unit="mapping", unit_scale=True
            )
            for e in m.evidence
        )


def write_pickle(mappings: list[Mapping], path: str | Path) -> None:
    """Write the mappings as a pickle."""
    path = Path(path).resolve()
    if path.suffix.endswith(".gz"):
        with gzip.open(path, "wb") as file:
            pickle.dump(mappings, file, protocol=pickle.HIGHEST_PROTOCOL)
    else:
        with path.open("wb") as file:
            pickle.dump(mappings, file, protocol=pickle.HIGHEST_PROTOCOL)


def from_pickle(path: str | Path) -> list[Mapping]:
    """Read the mappings from a pickle."""
    path = Path(path).resolve()
    if path.suffix.endswith(".gz"):
        with gzip.open(path, "rb") as file:
            return cast(list[Mapping], pickle.load(file))
    else:
        with path.open("rb") as file:
            return cast(list[Mapping], pickle.load(file))


def write_jsonl(
    objects: Iterable[pydantic.BaseModel], path: str | Path, *, show_progress: bool = False
) -> None:
    """Write a list of Pydantic objects into a JSONL file."""
    with safe_open(path, read=False) as file:
        for obj in tqdm(
            objects,
            desc="Writing JSONL",
            leave=False,
            unit="object",
            unit_scale=True,
            disable=not show_progress,
        ):
            file.write(f"{obj.model_dump_json(exclude_none=True)}\n")


def from_jsonl(path: str | Path, *, show_progress: bool = False) -> list[Mapping]:
    """Read a list of Mapping objects from a JSONL file."""
    return list(_iter_read_jsonl(path, show_progress=show_progress))


def _iter_read_jsonl(path: str | Path, *, show_progress: bool = False) -> Iterable[Mapping]:
    """Stream mapping objects from a JSONL file."""
    with safe_open(path, read=True) as file:
        for line in tqdm(
            file,
            desc="Reading mappings",
            leave=False,
            unit="mapping",
            unit_scale=True,
            disable=not show_progress,
        ):
            yield Mapping.model_validate_json(line.strip())
