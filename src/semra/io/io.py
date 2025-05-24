"""I/O functions for SeMRA."""

from __future__ import annotations

import gzip
import logging
import pickle
import typing as t
import uuid
from collections.abc import Generator, Iterable
from pathlib import Path
from typing import Any, Literal, NamedTuple, TextIO, TypeVar, cast, overload

import bioregistry
import pandas as pd
import pydantic
import requests
import yaml
from tqdm.autonotebook import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from .io_utils import (
    CONFIDENCE_PRECISION,
    get_confidence_str,
    get_name_by_curie,
    safe_open,
    safe_open_writer,
)
from ..rules import CURIE_TO_JUSTIFICATION, CURIE_TO_RELATION, UNSPECIFIED_MAPPING
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

X = TypeVar("X", bound=pydantic.BaseModel)


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
    import pyobo

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
    mapping_set_title: str | None = None,
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
    if mapping_set_name is not None:
        if mapping_set_title:
            raise ValueError
        mapping_set_title = mapping_set_name
    if mapping_set_title is None:
        mapping_set_title = bioregistry.get_name(prefix)
    if prefixes:
        df = _filter_sssom_by_prefixes(df, prefixes)
    return from_sssom_df(
        df,
        standardize=standardize,
        license=license,
        justification=justification,
        mapping_set_confidence=confidence,
        mapping_set_title=mapping_set_title,
        mapping_set_version=version,
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
    import bioontologies

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
    mapping_set_title: str | None = None,
    mapping_set_name: str | None = None,
    mapping_set_confidence: float | None = None,
    mapping_set_version: str | None = None,
    license: str | None = None,
    justification: Reference | None = None,
    version: str | None = None,
    standardize: bool = True,
    metadata: str | None = None,
) -> list[Mapping]:
    """Get mappings from a path to a SSSOM TSV file.

    :param path: The local file path or URL to a SSSOM TSV file.
    :param mapping_set_title: The title for the SSSOM mapping set, if not given
        explicitly in each mapping row nor by ``metadata``
    :param mapping_set_name: A deprecated alias for ``mapping_set_title``
    :param mapping_set_confidence: The confidence associated with all mappings in the
        mapping set. This diverges from the SSSOM data model in that each mapping can
        specify its own confidence, but there is no global confidence at the set level.

        .. seealso::

            https://github.com/mapping-commons/sssom/issues/438

    :param mapping_set_version: The title for the SSSOM mapping set, if not given
        explicitly in each mapping row nor by ``metadata``.
    :param license: The license for the SSSOM mapping set, if not given explicitly in
        each mapping row nor by ``metadata``.
    :param justification: The mapping justification for all mappings in the SSSOM
        mapping set, if not given explicitly in each mapping row nor by ``metadata``.
        Given as a :class:`curies.Reference` object using ``semapv`` as the prefix.
    :param version: Deprecated name for ``mapping_set_version``
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
        mapping_set_id=mapping_set_id,
        mapping_set_title=mapping_set_title,
        mapping_set_name=mapping_set_name,
        mapping_set_confidence=mapping_set_confidence,
        mapping_set_version=mapping_set_version,
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
    mapping_set_title: str | None = None,
    mapping_set_confidence: float | None = None,
    mapping_set_version: str | None = None,
    license: str | None = None,
    justification: Reference | None = None,
    version: str | None = None,
    standardize: bool = True,
    metadata: str | None = None,
) -> list[Mapping]:
    """Get mappings from a SSSOM dataframe."""
    # deprecated
    if version:
        if mapping_set_version:
            raise ValueError(
                f"got both {version=} and {mapping_set_version=} when loading a SSSOM dataframe. Just use `mapping_set_version`"
            )
        else:
            logger.warning(
                "passing `version` when loading a SSSOM dataframe is deprecated. Use `mapping_set_version` instead"
            )
            mapping_set_version = version

    if mapping_set_name:
        if mapping_set_title:
            raise ValueError(
                f"got both {mapping_set_name=} and {mapping_set_title=} when loading a SSSOM dataframe. Just use `mapping_set_title`"
            )
        logger.warning(
            "passing `mapping_set_name` when loading a SSSOM dataframe is deprecated. Use `mapping_set_title` instead"
        )
        mapping_set_title = mapping_set_name

    df = df.rename(
        columns={
            "source_id": "subject_id",
            "source_label": "subject_label",
            "source_name": "subject_label",
            "target_id": "object_id",
            "target_label": "object_label",
            "target_name": "object_label",
            "justification": "mapping_justification",
            "mapping_set_name": "mapping_set_title",
            "mapping_set_license": "license",
        }
    )
    if metadata:
        metadata_dict = yaml.safe_load(requests.get(metadata, timeout=15).text)
        if mapping_set_id is None:
            mapping_set_id = metadata_dict.get("mapping_set_id")
        if mapping_set_title is None:
            mapping_set_title = metadata_dict.get("mapping_set_title")
        if mapping_set_confidence is None:
            mapping_set_confidence = metadata_dict.get("mapping_set_confidence")
        if mapping_set_version is None:
            mapping_set_version = metadata_dict.get("mapping_set_version")
        if license is None:
            license = metadata_dict.get("license")

    rv = []
    for index, row in tqdm(
        df.iterrows(),
        total=len(df.index),
        leave=False,
        unit_scale=True,
        unit="row",
        desc="Loading SSSOM dataframe",
    ):
        mapping = _parse_sssom_row(
            index,
            row,
            mapping_set_id=mapping_set_id,
            mapping_set_title=mapping_set_title,
            mapping_set_confidence=mapping_set_confidence,
            mapping_set_version=mapping_set_version,
            license=license,
            justification=justification,
            standardize=standardize,
        )
        if mapping is not None:
            rv.append(mapping)
    return rv


def _row_get(row: dict[str, Any], key: str) -> Any:
    if key not in row:
        return None
    value = row[key]
    if pd.isna(value):
        return None
    return value


def _parse_sssom_row(
    index: Any,
    row: dict[str, Any],
    mapping_set_id: str | None,
    mapping_set_title: str | None,
    mapping_set_confidence: float | None,
    mapping_set_version: str | None,
    license: str | None,
    justification: Reference | None,
    standardize: bool,
) -> Mapping | None:
    if "author_id" in row and pd.notna(row["author_id"]):
        author = _from_curie(
            row["author_id"], name=_row_get(row, "author_label"), standardize=standardize
        )
    else:
        author = None

    # See https://mapping-commons.github.io/sssom/mapping_set_title/
    if mapping_set_title is not None:
        pass
    elif "mapping_set_title" in row and pd.notna(row["mapping_set_title"]):
        mapping_set_title = row["mapping_set_title"]
    elif "mapping_set" in row and pd.notna(row["mapping_set"]):
        mapping_set_title = row["mapping_set"]
    elif mapping_set_title is None:
        raise KeyError("need a mapping set title. dataframe had columns")

    # note that ``mapping_set_confidence`` isn't actually part of the SSSOM standard (yet),
    # see https://github.com/mapping-commons/sssom/issues/438
    if mapping_set_confidence is not None:
        pass
    elif "mapping_set_confidence" in row and pd.notna(row["mapping_set_confidence"]):
        mapping_set_confidence = row["mapping_set_confidence"]
    else:
        mapping_set_confidence = 1.0

    # See https://mapping-commons.github.io/sssom/mapping_set_version/
    if mapping_set_version is not None:
        pass
    elif "mapping_set_version" in row and pd.notna(row["mapping_set_version"]):
        mapping_set_version = row["mapping_set_version"]

    # See https://mapping-commons.github.io/sssom/license/
    if license is not None:
        pass
    elif "license" in row and pd.notna(row["license"]):
        license = row["license"]

    # See https://mapping-commons.github.io/sssom/mapping_set_id/
    if mapping_set_id is not None:
        pass
    elif "mapping_set_id" in row and pd.notna(row["mapping_set_id"]):
        mapping_set_id = row["mapping_set_id"]

    mapping_set = MappingSet(
        purl=mapping_set_id,
        name=mapping_set_title,
        version=mapping_set_version,
        confidence=mapping_set_confidence,
        license=license,
    )

    if justification is not None:
        pass
    elif "mapping_justification" in row and pd.notna(row["mapping_justification"]):
        justification_curie = row["mapping_justification"]
        if justification_curie in CURIE_TO_JUSTIFICATION:
            justification = CURIE_TO_JUSTIFICATION[justification_curie]
        else:
            justification = Reference.from_curie(justification_curie)
    else:
        justification = UNSPECIFIED_MAPPING

    if "confidence" in row and pd.notna(row["confidence"]):
        confidence = row["confidence"]
    else:
        confidence = None

    try:
        subject = _from_curie(
            row["subject_id"], standardize=standardize, name=row.get("subject_label")
        )

        if (predicate_id := row["predicate_id"]) in CURIE_TO_RELATION:
            predicate = CURIE_TO_RELATION[predicate_id]
        else:
            predicate = _from_curie(
                predicate_id, standardize=standardize, name=row.get("predicate_label")
            )
        obj = _from_curie(row["object_id"], standardize=standardize, name=row.get("object_label"))
    except pydantic.ValidationError as exc:
        logger.warning("[%s] could not parse row: %s", index, exc)
        return None
    evidence_dict: dict[str, t.Any] = {
        "justification": justification,
        "mapping_set": mapping_set,
        "author": author,
        "confidence": confidence,
    }
    return Mapping(
        subject=subject,
        predicate=predicate,
        object=obj,
        evidence=[SimpleEvidence.model_validate(evidence_dict)],
    )


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


class SSSOMRow(NamedTuple):
    """A tuple representing a row in a SSSOM TSV file."""

    subject_id: str
    subject_label: str
    predicate_id: str
    object_id: str
    object_label: str
    mapping_justification: str
    mapping_set_id: str
    mapping_set_title: str
    mapping_set_version: str
    mapping_set_confidence: str
    confidence: str
    license: str
    author_id: str
    author_label: str
    comment: str


SSSOM_DEFAULT_COLUMNS = SSSOMRow._fields
FALLBACK_MAPPING_SET_ID_URI_PREFIX = "https://w3id.org/sssom/mappings/semra-"


def _get_fallback_mapping_set_id() -> str:
    return FALLBACK_MAPPING_SET_ID_URI_PREFIX + str(uuid.uuid4())


def get_sssom_df(
    mappings: Iterable[Mapping], *, add_labels: bool = False, prune: bool = True
) -> pd.DataFrame:
    """Get a SSSOM dataframe.

    Automatically prunes columns that aren't filled out.

    :param mappings: A list of mappings
    :param add_labels: Should labels be added for source and object via
        :func:`pyobo.get_name_by_curie`?

    :returns: A SSSOM dataframe in Pandas
    """
    fallback_mapping_set_id = _get_fallback_mapping_set_id()
    rows = [
        _get_sssom_row(mapping, evidence, fallback_mapping_set_id)
        for mapping in tqdm(
            mappings, desc="Preparing SSSOM", leave=False, unit="mapping", unit_scale=True
        )
        for evidence in mapping.evidence
    ]
    df = pd.DataFrame(rows, columns=SSSOM_DEFAULT_COLUMNS)
    if add_labels:
        with logging_redirect_tqdm():
            for label_column, id_column in [
                ("subject_label", "subject_id"),
                ("object_label", "object_id"),
            ]:
                df[label_column] = [
                    name or get_name_by_curie(curie)
                    for curie, name in df[[id_column, label_column]].values
                ]

    if prune:
        # remove empty columns
        for column in df.columns:
            if not df[column].map(bool).any():
                del df[column]

    return df


def _format_confidence(confidence: float) -> str:
    return str(round(confidence, CONFIDENCE_PRECISION))


def _get_sssom_row(mapping: Mapping, e: Evidence, fallback_mapping_set_id: str) -> SSSOMRow:
    if isinstance(e, SimpleEvidence):
        if e.mapping_set.purl:
            mapping_set_id = e.mapping_set.purl
        else:
            mapping_set_id = FALLBACK_MAPPING_SET_ID_URI_PREFIX + e.mapping_set.hexdigest()
        mapping_set_title = e.mapping_set.name
        mapping_set_version = e.mapping_set.version or ""
        mapping_set_confidence = get_confidence_str(e.mapping_set)
        license = e.mapping_set.license or ""
        confidence = _format_confidence(e.confidence) if e.confidence else ""
    elif isinstance(e, ReasonedEvidence):
        # warning: SeMRA's format is not possible to capture in SSSOM
        mapping_set_id = fallback_mapping_set_id
        mapping_set_title = "semra"
        mapping_set_version = ""
        mapping_set_confidence = "1.0"
        license = ""
        confidence = _format_confidence(e.confidence_factor)
    else:
        raise TypeError

    return SSSOMRow(
        subject_id=mapping.subject.curie,
        subject_label=mapping.subject.name or "",
        predicate_id=mapping.predicate.curie,
        object_id=mapping.object.curie,
        object_label=mapping.object.name or "",
        mapping_justification=e.justification.curie,
        mapping_set_id=mapping_set_id,
        mapping_set_title=mapping_set_title,
        mapping_set_version=mapping_set_version,
        mapping_set_confidence=mapping_set_confidence,
        confidence=confidence,
        license=license,
        author_id=e.author.curie if e.author else "",
        author_label=e.author.name if e.author and e.author.name else "",
        comment=e.explanation,
    )


# docstr-coverage:excused `overload`
@overload
def write_sssom(
    mappings: Iterable[Mapping],
    file: str | Path | TextIO,
    *,
    add_labels: bool = ...,
    prune: bool = ...,
    stream: Literal[True] = True,
) -> Generator[Mapping]: ...


# docstr-coverage:excused `overload`
@overload
def write_sssom(
    mappings: Iterable[Mapping],
    file: str | Path | TextIO,
    *,
    add_labels: bool = ...,
    prune: bool = ...,
    stream: Literal[False] = False,
) -> None: ...


def write_sssom(
    mappings: Iterable[Mapping],
    file: str | Path | TextIO,
    *,
    add_labels: bool = False,
    prune: bool = True,
    stream: bool = False,
) -> None | Generator[Mapping]:
    """Export mappings as an SSSOM file (could be lossy)."""
    if not add_labels and not prune:
        if stream:
            return _write_sssom_stream(mappings, file, stream=stream)
        else:
            return _write_sssom_stream(mappings, file, stream=stream)
    elif stream:
        raise ValueError
    else:
        df = get_sssom_df(mappings, add_labels=add_labels)
        df.to_csv(file, sep="\t", index=False)
        return None


# docstr-coverage:excused `overload`
@overload
def _write_sssom_stream(
    mappings: Iterable[Mapping], file: str | Path | TextIO, *, stream: Literal[False] = False
) -> None: ...


# docstr-coverage:excused `overload`
@overload
def _write_sssom_stream(
    mappings: Iterable[Mapping], file: str | Path | TextIO, *, stream: Literal[True] = True
) -> Generator[Mapping]: ...


def _write_sssom_stream(
    mappings: Iterable[Mapping], file: str | Path | TextIO, *, stream: bool = False
) -> Generator[Mapping] | None:
    fallback_mapping_set_id = _get_fallback_mapping_set_id()
    it = tqdm(mappings, desc="Writing SSSOM", leave=False, unit="mapping", unit_scale=True)
    if stream:
        return _stream_write_sssom(file, it, fallback_mapping_set_id)
    else:
        with safe_open_writer(file) as writer:
            writer.writerow(SSSOM_DEFAULT_COLUMNS)
            for mapping in it:
                for evidence in mapping.evidence:
                    writer.writerow(_get_sssom_row(mapping, evidence, fallback_mapping_set_id))
            return None


def _stream_write_sssom(
    path: str | Path | TextIO, mappings: Iterable[Mapping], fallback_mapping_set_id: str
) -> Generator[Mapping]:
    with safe_open_writer(path) as writer:
        writer.writerow(SSSOM_DEFAULT_COLUMNS)
        for mapping in mappings:
            for evidence in mapping.evidence:
                writer.writerow(_get_sssom_row(mapping, evidence, fallback_mapping_set_id))
            yield mapping


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


# docstr-coverage:excused `overload`
@overload
def write_jsonl(
    objects: Iterable[X],
    path: str | Path,
    *,
    show_progress: bool = ...,
    stream: Literal[False] = False,
) -> None: ...


# docstr-coverage:excused `overload`
@overload
def write_jsonl(
    objects: Iterable[X],
    path: str | Path,
    *,
    show_progress: bool = ...,
    stream: Literal[True] = True,
) -> Generator[X]: ...


def write_jsonl(
    objects: Iterable[X], path: str | Path, *, show_progress: bool = False, stream: bool = False
) -> None | Generator[X]:
    """Write a list of Pydantic objects into a JSONL file."""
    models = tqdm(
        objects,
        desc="Writing JSONL",
        leave=False,
        unit="object",
        unit_scale=True,
        disable=not show_progress,
    )
    if stream:
        return _stream_write_jsonl(models, path)
    else:
        with safe_open(path, read=False) as file:
            for model in models:
                file.write(f"{model.model_dump_json(exclude_none=True)}\n")
        return None


def _stream_write_jsonl(models: Iterable[X], path: str | Path) -> Generator[X]:
    with safe_open(path, read=False) as file:
        for model in models:
            file.write(f"{model.model_dump_json(exclude_none=True)}\n")
            yield model


# docstr-coverage:excused `overload`
@overload
def from_jsonl(
    path: str | Path, *, show_progress: bool = ..., stream: Literal[False] = False
) -> list[Mapping]: ...


# docstr-coverage:excused `overload`
@overload
def from_jsonl(
    path: str | Path, *, show_progress: bool = ..., stream: Literal[True] = True
) -> Iterable[Mapping]: ...


def from_jsonl(
    path: str | Path,
    *,
    show_progress: bool = False,
    stream: bool = False,
    failure_action: Literal["raise", "skip"] = "skip",
) -> list[Mapping] | Generator[Mapping]:
    """Read a list of Mapping objects from a JSONL file."""
    rv = _iter_read_jsonl(path, show_progress=show_progress, failure_action=failure_action)
    if stream:
        return rv
    else:
        return list(rv)


def _iter_read_jsonl(
    path: str | Path,
    *,
    show_progress: bool = False,
    failure_action: Literal["raise", "skip"] = "skip",
) -> Generator[Mapping]:
    """Stream mapping objects from a JSONL file."""
    with safe_open(path, read=True) as file:
        for i, line in enumerate(
            tqdm(
                file,
                desc="Reading mappings",
                leave=False,
                unit="mapping",
                unit_scale=True,
                disable=not show_progress,
            )
        ):
            try:
                yv = Mapping.model_validate_json(line.strip())
            except pydantic.ValidationError:
                if failure_action == "raise":
                    raise
                else:
                    logger.debug("[line:%d] failed to parse JSON", i)
                    continue
            else:
                yield yv
