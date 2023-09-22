"""Declarative acquisition and processing of mapping sets."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Literal

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
    prioritize,
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

    source: Literal["pyobo", "bioontologies", "biomappings", "custom", "sssom"]
    prefix: str | None = None
    confidence: float = 1.0
    extras: dict[str, Any] = Field(default_factory=dict)


class Mutation(BaseModel):
    """Represents a mutation operation on a mapping set."""

    source: str = Field(..., description="The source type")
    confidence: float = 1.0
    old: Reference = Field(default=DB_XREF)
    new: Reference = Field(default=EXACT_MATCH)


class Configuration(BaseModel):
    """Represents the steps taken during mapping assembly."""

    inputs: list[Input]
    negative_inputs: list[Input] = Field(default=[Input(source="biomappings", prefix="negative")])
    priority: list[str] = Field(..., description="If no priority is given, is inferred from the order of inputs")
    mutations: list[Mutation] = Field(default_factory=list)
    exclude_pairs: list[tuple[str, str]] = Field(
        default_factory=list,
        description="A list of pairs of prefixes. Remove all mappings whose source "
        "prefix is the first in a pair and target prefix is second in a pair. Order matters.",
    )
    remove_prefixes: list[str] | None = None

    raw_pickle_path: Path | None = None
    raw_sssom_path: Path | None = None
    raw_neo4j_path: Path | None = None
    raw_neo4j_name: str | None = None

    inferred_neo4j_path: Path | None = None
    inferred_neo4j_name: str | None = None

    processed_pickle_path: Path | None = None
    processed_sssom_path: Path | None = None

    sssom_add_labels: bool = False

    @root_validator(skip_on_failure=True)
    def infer_priority(cls, values):  # noqa:N805
        """Infer the priority from the input list of not given."""
        priority = values["priority"]
        if priority is None:
            values["priority"] = [inp.prefix for inp in values["inputs"].inputs if inp.prefix is not None]
        return values


def get_mappings_from_config(
    configuration: Configuration,
    *,
    refresh_raw: bool = False,
    refresh_processed: bool = False,
) -> list[Mapping]:
    """Run assembly based on a configuration."""
    if (
        configuration.processed_pickle_path
        and configuration.processed_pickle_path.is_file()
        and not refresh_raw
        and not refresh_processed
    ):
        logger.info("loading cached processed mappings from %s", configuration.processed_pickle_path)
        return from_pickle(configuration.processed_pickle_path)
    if configuration.raw_pickle_path and configuration.raw_pickle_path.is_file() and not refresh_raw:
        start = time.time()
        logger.info("loading cached raw mappings from %s", configuration.raw_pickle_path)
        mappings = from_pickle(configuration.raw_pickle_path)
        logger.info(
            "loaded cached raw mappings from %s in %.2f seconds", configuration.raw_pickle_path, time.time() - start
        )
    else:
        mappings = get_raw_mappings(configuration)
        if configuration.raw_pickle_path:
            write_pickle(mappings, configuration.raw_pickle_path)
        if configuration.raw_sssom_path:
            write_sssom(mappings, configuration.raw_sssom_path, add_labels=configuration.sssom_add_labels)
        if configuration.raw_neo4j_path:
            write_neo4j(mappings, configuration.raw_neo4j_path, configuration.raw_neo4j_name)

    # click.echo(semra.api.str_source_target_counts(mappings, minimum=20))
    mappings = process(
        mappings,
        upgrade_prefixes=[  # TODO more carefully compile a set of mutations together for applying
            m.source for m in configuration.mutations
        ],
        remove_prefix_set=configuration.remove_prefixes,
    )
    mappings = prioritize(mappings, configuration.priority)
    if configuration.processed_pickle_path:
        write_pickle(mappings, configuration.processed_pickle_path)
    if configuration.processed_sssom_path:
        write_sssom(mappings, configuration.processed_sssom_path, add_labels=configuration.sssom_add_labels)
    return mappings


def get_raw_mappings(configuration: Configuration) -> list[Mapping]:
    """Get raw mappings based on the inputs in a configuration."""
    mappings = []
    for inp in tqdm(configuration.inputs, desc="Loading configured mappings", unit="source"):
        tqdm.write(f"Loading {inp.prefix} with {inp.source}")
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
    mappings: list[Mapping],
    upgrade_prefixes=None,
    remove_prefix_set=None,
    *,
    remove_imprecise: bool = True,
) -> list[Mapping]:
    """Run a full deduplication, reasoning, and inference pipeline over a set of mappings."""
    from semra.sources.biopragmatics import from_biomappings_negative

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
    logger.info("Removing self mappings (i.e., within a given semantic space)")
    before = len(mappings)
    start = time.time()
    mappings = filter_self_matches(mappings)
    _log_diff(before, mappings, verb="Filtered source internal", elapsed=time.time() - start)

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


def _log_diff(before: int, mappings: list[Mapping], *, verb: str, elapsed) -> None:
    logger.info(
        f"{verb} from {before:,} to {len(mappings):,} mappings (Δ={len(mappings) - before:,}) in %.2f seconds.",
        elapsed,
    )
