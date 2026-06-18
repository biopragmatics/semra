"""I/O functions for SeMRA."""

from __future__ import annotations

import logging
import pickle
import warnings
from collections.abc import Generator, Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TextIO, TypeVar, cast, overload

import bioregistry
import curies
import pydantic
import sssom_pydantic
from bioregistry import NormalizedNamableReference as Reference
from pystow.utils import (
    iter_pydantic_jsonl,
    reyield,
    safe_open,
    stream_write_pydantic_jsonl,
    write_pydantic_jsonl,
)
from tqdm.autonotebook import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from typing_extensions import Unpack

from .io_utils import get_name_by_reference
from ..struct import Mapping

if TYPE_CHECKING:
    import pandas
    from pyobo.constants import GetOntologyKwargs

__all__ = [
    "from_jsonl",
    "from_pickle",
    "from_pyobo",
    "from_sssom",
    "from_sssom_pydantic",
    "from_sssom_pydantic_iter",
    "get_sssom_df",
    "to_sssom_pydantic",
    "write_jsonl",
    "write_pickle",
    "write_sssom",
]

logger = logging.getLogger(__name__)

#: The default confidence for ontology-based mappings
DEFAULT_ONTOLOGY_CONFIDENCE = 0.9

X = TypeVar("X", bound=pydantic.BaseModel)


def from_sssom_pydantic(
    mappings: Iterable[sssom_pydantic.SemanticMapping],
    mapping_set: sssom_pydantic.MappingSet | None = None,
    *,
    strict: bool = False,
) -> list[Mapping]:
    """Convert mappings from :mod:`sssom_pydantic`."""
    return list(from_sssom_pydantic_iter(mappings, mapping_set=mapping_set, strict=strict))


def from_sssom_pydantic_iter(
    mappings: Iterable[sssom_pydantic.SemanticMapping],
    mapping_set: sssom_pydantic.MappingSet | None = None,
    *,
    strict: bool = False,
) -> Iterable[Mapping]:
    """Convert mappings from :mod:`sssom_pydantic`."""
    for mapping in mappings:
        try:
            xx = Mapping.from_sssom_pydantic(mapping, mapping_set)
        except pydantic.ValidationError as e:
            logger.warning("failed to convert mapping: %s", e)
            if strict:
                raise
        else:
            yield xx


def from_pyobo(
    prefix: str,
    target_prefix: str | None = None,
    *,
    confidence: float | None = None,
    **kwargs: Unpack[GetOntologyKwargs],
) -> list[Mapping]:
    """Get mappings from a given ontology via :mod:`pyobo`.

    :param prefix: The prefix of the ontology to get semantic mappings from
    :param target_prefix: The optional prefix for targets for semantic mappings.
    :param confidence: The confidence level for the mappings. Defaults to
        :data:`DEFAULT_ONTOLOGY_CONFIDENCE`.
    :param kwargs: Keyword arguments for :func:`pyobo.get_semantic_mappings`.
        Automatically intercepts the version for lookup.

    :returns: A list of semantic mapping objects
    """
    import pyobo
    from pyobo.api.utils import get_version_from_kwargs

    kwargs["version"] = get_version_from_kwargs(prefix, kwargs)

    metadata = pyobo.get_semantic_mapping_metadata(
        prefix, confidence=confidence, version=kwargs["version"]
    )
    try:
        mappings = pyobo.get_semantic_mappings(prefix, **kwargs)
    except pyobo.getters.NoBuildError:
        return []
    if target_prefix:
        target_prefix = bioregistry.normalize_prefix(target_prefix, strict=True)
        mappings = [m for m in mappings if m.object.prefix == target_prefix]
    return from_sssom_pydantic(mappings, metadata)


def from_bioontologies(
    prefix: str, confidence: float | None = None, **kwargs: Any
) -> list[Mapping]:
    """Get mappings from a given ontology via :mod:`bioontologies`."""
    warnings.warn("use from_pyobo, which now wraps bioontologies", DeprecationWarning, stacklevel=2)
    return from_pyobo(prefix, confidence=confidence, **kwargs)


def from_sssom(
    path: str | Path, confidence: float | None = None, *, strict: bool = False, **kwargs: Any
) -> list[Mapping]:
    """Get mappings from a path to a SSSOM TSV file.

    :param path: The local file path or URL to a SSSOM TSV file.
    :param kwargs: Keyword arguments for :func:`sssom_pydantic.read`

    :returns: A list of SeMRA mapping objects

    Load a SSSOM file by URL that has external metadata

    .. code-block:: python

        mappings = from_sssom(
            "https://w3id.org/biopragmatics/biomappings/sssom/biomappings.sssom.tsv",
            mapping_set_confidence=0.85,
        )
    """
    if confidence is not None:
        raise NotImplementedError("setting registry confidence not implemented")
    mappings, _converter, metadata = sssom_pydantic.read(path, **kwargs)
    return from_sssom_pydantic(mappings, metadata, strict=strict)


def to_sssom_pydantic(
    mappings: Iterable[Mapping], *, add_labels: bool = False
) -> Iterable[sssom_pydantic.SemanticMapping]:
    """Iterate over SSSOM-Pydantic mappings."""
    for mapping in mappings:
        subject, obj = _get_subject_object(mapping, add_labels)
        for evidence in mapping.evidence:
            yield evidence._to_sssom_pydantic(mapping, subject=subject, object=obj)


def _get_subject_object(mapping: Mapping, add_labels: bool) -> tuple[Reference, Reference]:
    if not add_labels:
        return mapping.subject, mapping.object
    subject = mapping.subject
    obj = mapping.object
    with logging_redirect_tqdm():
        if subject_name := get_name_by_reference(subject):
            subject = subject.with_name(subject_name)
        if object_name := get_name_by_reference(obj):
            obj = obj.with_name(object_name)
    return subject, obj


def get_sssom_df(mappings: Iterable[Mapping], *, add_labels: bool = False) -> pandas.DataFrame:
    """Get a SSSOM dataframe.

    :param mappings: A list of mappings
    :param add_labels: Should labels be added for source and object via
        :func:`pyobo.get_name_by_curie`?

    :returns: A SSSOM dataframe in Pandas
    """
    return sssom_pydantic.to_dataframe(to_sssom_pydantic(mappings, add_labels=add_labels))


# docstr-coverage:excused `overload`
@overload
def write_sssom(
    mappings: Iterable[Mapping],
    file: str | Path | TextIO,
    *,
    add_labels: bool = ...,
    prune: bool = ...,
    stream: Literal[True] = ...,
    metadata: sssom_pydantic.MappingSet,
    converter: curies.Converter | None = ...,
) -> Generator[Mapping, None, None]: ...


# docstr-coverage:excused `overload`
@overload
def write_sssom(
    mappings: Iterable[Mapping],
    file: str | Path | TextIO,
    *,
    add_labels: bool = ...,
    prune: bool = ...,
    stream: Literal[False] = ...,
    metadata: sssom_pydantic.MappingSet,
    converter: curies.Converter | None = ...,
) -> None: ...


def write_sssom(
    mappings: Iterable[Mapping],
    file: str | Path | TextIO,
    *,
    add_labels: bool = False,
    prune: bool = True,
    stream: bool = False,
    metadata: sssom_pydantic.MappingSet,
    converter: curies.Converter | None = None,
) -> None | Generator[Mapping, None, None]:
    """Export mappings as an SSSOM file (could be lossy)."""
    if converter is None:
        converter = bioregistry.get_default_converter()

    if not prune:
        return _write_sssom_stream(  # type:ignore[no-any-return,call-overload]
            mappings,
            file,
            stream=stream,
            add_labels=add_labels,
            metadata=metadata,
            converter=converter,
        )
    elif stream:
        raise ValueError("can not prune and stream at the same time")
    else:
        _write_sssom(
            mappings,
            file=file,
            add_labels=add_labels,
            metadata=metadata,
            converter=converter,
        )
        return None


def _write_sssom(
    mappings: Iterable[Mapping],
    /,
    file: str | Path | TextIO,
    *,
    add_labels: bool = False,
    prune: bool = True,
    stream: bool = False,
    metadata: sssom_pydantic.MappingSet,
    converter: curies.Converter | None = None,
    **kwargs: Any,
) -> None:
    sssom_pydantic.write(
        to_sssom_pydantic(mappings, add_labels=add_labels),
        file,
        metadata=metadata,
        converter=converter,
        exclude_columns={"predicate_label"},
        **kwargs,
    )


# docstr-coverage:excused `overload`
@overload
def _write_sssom_stream(
    mappings: Iterable[Mapping],
    file: str | Path | TextIO,
    *,
    stream: Literal[False] = False,
    add_labels: bool = ...,
    metadata: sssom_pydantic.MappingSet,
    converter: curies.Converter | None = ...,
) -> None: ...


# docstr-coverage:excused `overload`
@overload
def _write_sssom_stream(
    mappings: Iterable[Mapping],
    file: str | Path | TextIO,
    *,
    stream: Literal[True] = True,
    add_labels: bool = ...,
    metadata: sssom_pydantic.MappingSet,
    converter: curies.Converter | None = ...,
) -> Generator[Mapping, None, None]: ...


def _write_sssom_stream(
    mappings: Iterable[Mapping],
    file: str | Path | TextIO,
    *,
    stream: bool = False,
    add_labels: bool = False,
    metadata: sssom_pydantic.MappingSet,
    converter: curies.Converter | None = None,
) -> Generator[Mapping, None, None] | None:
    yv = reyield(
        _write_sssom,
        mappings,
        file=file,
        add_labels=add_labels,
        metadata=metadata,
        converter=converter,
        condense=False,
        reduce_prefix_map=False,
        columns=SSSOM_STREAMING_COLUMNS,
    )
    if stream:
        return yv
    else:
        for _ in yv:
            pass
        return None


SSSOM_STREAMING_COLUMNS = [
    "record_id",
    "subject_id",
    "subject_label",
    "predicate_id",
    "object_id",
    "object_label",
    "mapping_justification",
    "confidence",
    "license",
    "author_id",
    "comment",
    "derived_from",
]


def write_pickle(mappings: list[Mapping], path: str | Path) -> None:
    """Write the mappings as a pickle."""
    with safe_open(path, representation="binary", operation="write") as file:
        pickle.dump(mappings, file, protocol=pickle.HIGHEST_PROTOCOL)


def from_pickle(path: str | Path) -> list[Mapping]:
    """Read the mappings from a pickle."""
    with safe_open(path, representation="binary") as file:
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
    # need this to include the evidence_type
    kwargs = {"exclude_defaults": False, "exclude_unset": False}
    if stream:
        return stream_write_pydantic_jsonl(models, path, **kwargs)
    else:
        write_pydantic_jsonl(models, path, **kwargs)
        return None


# docstr-coverage:excused `overload`
@overload
def from_jsonl(
    path: str | Path,
    *,
    show_progress: bool = ...,
    stream: Literal[False] = False,
    failure_action: Literal["raise", "skip"] = ...,
    tqdm_kwargs: dict[str, Any] | None = ...,
) -> list[Mapping]: ...


# docstr-coverage:excused `overload`
@overload
def from_jsonl(
    path: str | Path,
    *,
    show_progress: bool = ...,
    stream: Literal[True] = True,
    failure_action: Literal["raise", "skip"] = ...,
    tqdm_kwargs: dict[str, Any] | None = ...,
) -> Iterable[Mapping]: ...


def from_jsonl(
    path: str | Path,
    *,
    show_progress: bool = False,
    stream: bool = False,
    failure_action: Literal["raise", "skip"] = "skip",
    tqdm_kwargs: dict[str, Any] | None = None,
) -> list[Mapping] | Generator[Mapping]:
    """Read a list of Mapping objects from a JSONL file."""
    rv = iter_pydantic_jsonl(
        path,
        Mapping,
        progress=show_progress,
        failure_action=failure_action,
        tqdm_kwargs=tqdm_kwargs,
    )
    if stream:
        return rv  # type:ignore[return-value]
    else:
        return list(rv)
