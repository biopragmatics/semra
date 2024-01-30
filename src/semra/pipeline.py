"""Declarative acquisition and processing of mapping sets."""

from __future__ import annotations

import logging
import time
import typing as t
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, root_validator
from tqdm.autonotebook import tqdm

from semra.api import (
    assemble_evidences,
    filter_mappings,
    filter_prefixes,
    filter_self_matches,
    infer_chains,
    infer_mutual_dbxref_mutations,
    infer_reversible,
    keep_prefixes,
    prioritize,
    validate_mappings,
)
from semra.io import (
    from_bioontologies,
    from_cache_df,
    from_pickle,
    from_pyobo,
    from_sssom,
    write_neo4j,
    write_pickle,
    write_sssom,
)
from semra.rules import DB_XREF, EXACT_MATCH, IMPRECISE
from semra.sources import SOURCE_RESOLVER
from semra.sources.biopragmatics import (
    from_biomappings_negative,
    from_biomappings_predicted,
    get_biomappings_positive_mappings,
)
from semra.sources.gilda import get_gilda_mappings
from semra.struct import Mapping, Reference

__all__ = [
    # Configuration model
    "Configuration",
    "Input",
    "Mutation",
    # Functions
    "get_mappings_from_config",
    "get_raw_mappings",
    "process",
]

logger = logging.getLogger(__name__)


class Input(BaseModel):
    """Represents the input to a mapping assembly."""

    source: Literal["pyobo", "bioontologies", "biomappings", "custom", "sssom", "gilda"]
    prefix: Optional[str] = None
    confidence: float = 1.0
    extras: t.Dict[str, Any] = Field(default_factory=dict)


class Mutation(BaseModel):
    """Represents a mutation operation on a mapping set."""

    source: str = Field(..., description="The source type")
    confidence: float = 1.0
    old: Reference = Field(default=DB_XREF)
    new: Reference = Field(default=EXACT_MATCH)


class Configuration(BaseModel):
    """Represents the steps taken during mapping assembly."""

    name: str = Field(description="The name of the mapping set configuration")
    description: Optional[str] = Field(
        None, description="An explanation of the purpose of the mapping set configuration"
    )
    inputs: t.List[Input] = Field(..., description="A list of sources of mappings")
    negative_inputs: t.List[Input] = Field(default=[Input(source="biomappings", prefix="negative")])
    priority: t.List[str] = Field(
        default_factory=list, description="If no priority is given, is inferred from the order of inputs"
    )
    mutations: t.List[Mutation] = Field(default_factory=list)

    exclude_pairs: t.List[t.Tuple[str, str]] = Field(
        default_factory=list,
        description="A list of pairs of prefixes. Remove all mappings whose source "
        "prefix is the first in a pair and target prefix is second in a pair. Order matters.",
    )
    remove_prefixes: Optional[t.List[str]] = None
    keep_prefixes: Optional[t.List[str]] = None
    remove_imprecise: bool = True
    validate_raw: bool = Field(
        default=False,
        description="Should the raw mappings be validated against Bioregistry "
        "prefixes and local unique identifier regular expressions (when available)?",
    )

    raw_pickle_path: Optional[Path] = None
    raw_sssom_path: Optional[Path] = None
    raw_neo4j_path: Optional[Path] = Field(default=None, description="Directory in which Neo4j stuff goes")
    raw_neo4j_name: Optional[str] = Field(default=None, description="Directory for docker tag for Neo4j")

    processed_pickle_path: Optional[Path] = None
    processed_sssom_path: Optional[Path] = None
    processed_neo4j_path: Optional[Path] = Field(default=None, description="Directory in which Neo4j stuff goes")
    processed_neo4j_name: Optional[str] = Field(default=None, description="Directory for docker tag for Neo4j")

    priority_pickle_path: Optional[Path] = None
    priority_sssom_path: Optional[Path] = None
    # note that making a priority neo4j doesn't make sense

    add_labels: bool = Field(default=False, description="Should PyOBO be used to look up labels for SSSOM output?")

    @root_validator(skip_on_failure=True)
    def infer_priority(cls, values):  # noqa:N805
        """Infer the priority from the input list of not given."""
        priority = values["priority"]
        if not priority:
            values["priority"] = [inp.prefix for inp in values["inputs"].inputs if inp.prefix is not None]
        return values

    @classmethod
    def from_prefixes(
        cls, *, name: str, prefixes: t.Iterable[str], include_biomappings: bool = True, include_gilda: bool = True
    ):
        """Get a configuration from ontology prefixes."""
        inputs = [Input(source="bioontologies", prefix=p) for p in prefixes]
        if include_biomappings:
            inputs.append(Input(source="biomappings"))
        if include_gilda:
            inputs.append(Input(source="gilda"))
        return cls(name=name, inputs=inputs)

    def get_mappings(
        self,
        *,
        refresh_raw: bool = False,
        refresh_processed: bool = False,
    ) -> t.List[Mapping]:
        """Run assembly based on this configuration."""
        return get_mappings_from_config(self, refresh_raw=refresh_raw, refresh_processed=refresh_processed)


def get_mappings_from_config(
    configuration: Configuration,
    *,
    refresh_raw: bool = False,
    refresh_processed: bool = False,
) -> t.List[Mapping]:
    """Run assembly based on a configuration."""
    if (
        configuration.priority_pickle_path
        and configuration.priority_pickle_path.is_file()
        and not refresh_raw
        and not refresh_processed
    ):
        logger.info("loading cached priority mappings from %s", configuration.priority_pickle_path)
        return from_pickle(configuration.priority_pickle_path)

    if configuration.raw_pickle_path and configuration.raw_pickle_path.is_file() and not refresh_raw:
        start = time.time()
        logger.info("loading cached raw mappings from %s", configuration.raw_pickle_path)
        raw_mappings = from_pickle(configuration.raw_pickle_path)
        logger.info(
            "loaded cached raw mappings from %s in %.2f seconds", configuration.raw_pickle_path, time.time() - start
        )
    else:
        raw_mappings = get_raw_mappings(configuration)
        if configuration.validate_raw:
            validate_mappings(raw_mappings)
        if configuration.raw_pickle_path:
            write_pickle(raw_mappings, configuration.raw_pickle_path)
        if configuration.raw_sssom_path:
            write_sssom(raw_mappings, configuration.raw_sssom_path, add_labels=configuration.add_labels)
        if configuration.raw_neo4j_path:
            write_neo4j(
                raw_mappings,
                configuration.raw_neo4j_path,
                docker_name=configuration.raw_neo4j_name,
                add_labels=configuration.add_labels,
            )

    # click.echo(semra.api.str_source_target_counts(mappings, minimum=20))
    processed_mappings = process(
        raw_mappings,
        upgrade_prefixes=[  # TODO more carefully compile a set of mutations together for applying
            m.source for m in configuration.mutations
        ],
        remove_prefix_set=configuration.remove_prefixes,
        keep_prefix_set=configuration.keep_prefixes,
        remove_imprecise=configuration.remove_imprecise,
    )
    prioritized_mappings = prioritize(processed_mappings, configuration.priority)

    if configuration.processed_pickle_path:
        write_pickle(processed_mappings, configuration.processed_pickle_path)
    if configuration.processed_sssom_path:
        write_sssom(processed_mappings, configuration.processed_sssom_path, add_labels=configuration.add_labels)
    if configuration.processed_neo4j_path:
        equivalence_classes = _get_equivalence_classes(processed_mappings, prioritized_mappings)
        write_neo4j(
            processed_mappings,
            configuration.processed_neo4j_path,
            docker_name=configuration.processed_neo4j_name,
            equivalence_classes=equivalence_classes,
            add_labels=configuration.add_labels,
        )

    if configuration.priority_pickle_path:
        write_pickle(prioritized_mappings, configuration.priority_pickle_path)
    if configuration.priority_sssom_path:
        write_sssom(prioritized_mappings, configuration.priority_sssom_path, add_labels=configuration.add_labels)

    return prioritized_mappings


def _get_equivalence_classes(mappings, prioritized_mappings) -> dict[Reference, bool]:
    priority_references = {mapping.o for mapping in prioritized_mappings}
    rv = {}
    for mapping in mappings:
        rv[mapping.s] = mapping.s in priority_references
        rv[mapping.o] = mapping.o in priority_references
    return rv


def get_raw_mappings(configuration: Configuration) -> t.List[Mapping]:
    """Get raw mappings based on the inputs in a configuration."""
    mappings = []
    for inp in tqdm(configuration.inputs, desc="Loading configured mappings", unit="source"):
        tqdm.write(f"Loading {inp.source}" + (f" ({inp.prefix})" if inp.prefix else ""))
        if inp.source is None:
            continue
        elif inp.source == "bioontologies":
            if inp.prefix is None:
                raise ValueError
            mappings.extend(from_bioontologies(inp.prefix, confidence=inp.confidence, **inp.extras))
        elif inp.source == "pyobo":
            if inp.prefix is None:
                raise ValueError
            mappings.extend(from_pyobo(inp.prefix, confidence=inp.confidence, **inp.extras))
        elif inp.source == "biomappings":
            if inp.prefix in {None, "positive"}:
                mappings.extend(get_biomappings_positive_mappings())
            elif inp.prefix == "negative":
                mappings.extend(from_biomappings_negative())
            elif inp.prefix == "predicted":
                mappings.extend(from_biomappings_predicted())
            else:
                raise ValueError
        elif inp.source == "gilda":
            mappings.extend(get_gilda_mappings(confidence=inp.confidence))
        elif inp.source == "custom":
            func = SOURCE_RESOLVER.make(inp.prefix, inp.extras)
            mappings.extend(func())
        elif inp.source == "sssom":
            mappings.extend(from_sssom(inp.prefix, **inp.extras))
        elif inp.source == "cache":
            mappings.extend(from_cache_df(**inp.extras))
        else:
            raise ValueError
    return mappings


def process(
    mappings: t.List[Mapping],
    upgrade_prefixes=None,
    remove_prefix_set=None,
    keep_prefix_set=None,
    *,
    remove_imprecise: bool = True,
) -> t.List[Mapping]:
    """Run a full deduplication, reasoning, and inference pipeline over a set of mappings."""
    from semra.sources.biopragmatics import from_biomappings_negative

    if keep_prefix_set:
        mappings = keep_prefixes(mappings, keep_prefix_set)

    if remove_prefix_set:
        mappings = filter_prefixes(mappings, remove_prefix_set)

    start = time.time()
    negatives = from_biomappings_negative()
    logger.info(f"Loaded {len(negatives):,} negative mappings in %.2f seconds", time.time() - start)

    before = len(mappings)
    start = time.time()
    mappings = filter_mappings(mappings, negatives)
    _log_diff(before, mappings, verb="Filtered negative mappings", elapsed=time.time() - start)

    # deduplicate
    before = len(mappings)
    start = time.time()
    mappings = assemble_evidences(mappings)
    _log_diff(before, mappings, verb="Assembled", elapsed=time.time() - start)

    # only keep relevant prefixes
    # mappings = filter_prefixes(mappings, PREFIXES)
    # logger.debug(f"Filtered to {len(mappings):,} mappings")

    # remove mapping between self, such as EFO-EFO
    # TODO handle self-mappings better using "replaced by" relations
    # logger.info("Removing self mappings (i.e., within a given semantic space)")
    # before = len(mappings)
    # start = time.time()
    # mappings = filter_self_matches(mappings)
    # _log_diff(before, mappings, verb="Filtered source internal", elapsed=time.time() - start)

    if upgrade_prefixes:
        logger.info("Inferring mapping upgrades")
        # 2. using the assumption that primary mappings from each of these
        # resources to each other are exact matches, rewrite the prefixes
        before = len(mappings)
        start = time.time()
        mappings = infer_mutual_dbxref_mutations(mappings, upgrade_prefixes, confidence=0.95)
        _log_diff(before, mappings, verb="Inferred upgrades", elapsed=time.time() - start)

    # remove dbxrefs
    if remove_imprecise:
        logger.info("Removing unqualified database xrefs")
        before = len(mappings)
        start = time.time()
        mappings = [m for m in mappings if m.p not in IMPRECISE]
        _log_diff(before, mappings, verb="Filtered non-precise", elapsed=time.time() - start)

    # 3. Inference based on adding reverse relations then doing multi-chain hopping
    logger.info("Inferring reverse mappings")
    before = len(mappings)
    start = time.time()
    mappings = infer_reversible(mappings)
    _log_diff(before, mappings, verb="Inferred", elapsed=time.time() - start)

    logger.info("Inferring based on chains")
    before = len(mappings)
    time.time()
    mappings = infer_chains(mappings)
    _log_diff(before, mappings, verb="Inferred", elapsed=time.time() - start)

    # 4/5. Filtering negative
    logger.info("Filtering out negative mappings")
    before = len(mappings)
    start = time.time()
    mappings = filter_mappings(mappings, negatives)
    _log_diff(before, mappings, verb="Filtered negative mappings", elapsed=time.time() - start)

    # filter out self mappings again, just in case
    mappings = filter_self_matches(mappings)

    return mappings


def _log_diff(before: int, mappings: t.List[Mapping], *, verb: str, elapsed) -> None:
    logger.info(
        f"{verb} from {before:,} to {len(mappings):,} mappings (Δ={len(mappings) - before:,}) in %.2f seconds.",
        elapsed,
    )
