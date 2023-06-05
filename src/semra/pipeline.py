"""Declarative acquisition and processing of mapping sets."""

from __future__ import annotations

import logging
import pickle
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, root_validator
from tqdm.autonotebook import tqdm

from semra.api import prioritize, process
from semra.io import from_bioontologies, from_cache_df, from_pyobo, write_neo4j, write_pickle, write_sssom
from semra.rules import DB_XREF, EXACT_MATCH
from semra.sources.biopragmatics import from_biomappings_negative, from_biomappings_positive, from_biomappings_predicted
from semra.sources.gilda import from_gilda
from semra.struct import Mapping, Reference

__all__ = [
    # Configuration model
    "Configuration",
    "Input",
    "Mutation",
    # Functions
    "get_mappings_from_config",
    "get_raw_mappings",
]

logger = logging.getLogger(__name__)


class Input(BaseModel):
    """Represents the input to a mapping assembly."""

    source: Literal["pyobo", "bioontologies", "biomappings", "gilda", "custom"]
    prefix: str | None = None
    confidence: float = 1.0
    extras: dict[str, Any] | None = None


class Mutation(BaseModel):
    """Represents a mutation operation on a mapping set."""

    source: str = Field()
    confidence: float = 1.0
    old: Reference = Field(default=DB_XREF)
    new: Reference = Field(default=EXACT_MATCH)


class Configuration(BaseModel):
    """Represents the steps taken during mapping assembly."""

    inputs: list[Input]
    negative_inputs: list[Input] = Field(default=[Input(source="biomappings", prefix="negative")])
    priority: list[str] = Field(description="If no priority is given, is inferred from the order of inputs")
    mutations: list[Mutation] = Field(default_factory=list)
    remove_prefixes: list[str] | None = None

    raw_pickle_path: Path | None = None
    raw_sssom_path: Path | None = None
    raw_neo4j_path: Path | None = None
    raw_neo4j_name: str | None = None

    inferred_neo4j_path: Path | None = None
    inferred_neo4j_name: str | None = None

    processed_path: Path | None = None
    processed_sssom_path: Path | None = None

    @root_validator
    def infer_priority(cls, values):  # noqa:N805
        """Infer the priority from the input list of not given."""
        priority = values["priority"]
        if priority is None:
            values["priority"] = [inp.prefix for inp in values["inputs"].inputs if inp.prefix is not None]
        return values


def get_mappings_from_config(configuration: Configuration) -> list[Mapping]:
    """Run assembly based on a configuration."""
    if configuration.processed_path and configuration.processed_path.is_file():
        logger.info("loading cached processed mappings from %s", configuration.processed_path)
        return pickle.loads(configuration.processed_path.read_bytes())
    if configuration.raw_pickle_path and configuration.raw_pickle_path.is_file():
        start = time.time()
        logger.info("loading cached raw mappings from %s", configuration.raw_pickle_path)
        mappings = pickle.loads(configuration.raw_pickle_path.read_bytes())
        logger.info(
            "loaded cached raw mappings from %s in %.2f seconds", configuration.raw_pickle_path, time.time() - start
        )
    else:
        mappings = get_raw_mappings(configuration)
        if configuration.raw_pickle_path:
            write_pickle(mappings, configuration.raw_pickle_path)
        if configuration.raw_sssom_path:
            write_sssom(mappings, configuration.raw_sssom_path)
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
    if configuration.processed_path:
        configuration.processed_path.write_bytes(pickle.dumps(mappings, protocol=pickle.HIGHEST_PROTOCOL))
    if configuration.processed_sssom_path:
        write_sssom(mappings, configuration.processed_sssom_path)
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
            mappings.extend(from_bioontologies(inp.prefix, confidence=inp.confidence, **(inp.extras or {})))
        elif inp.source == "pyobo":
            if inp.prefix is None:
                raise ValueError
            mappings.extend(from_pyobo(inp.prefix, confidence=inp.confidence, **(inp.extras or {})))
        elif inp.source == "biomappings":
            if inp.prefix in {None, "positive"}:
                mappings.extend(from_biomappings_positive())
            elif inp.prefix == "negative":
                mappings.extend(from_biomappings_negative())
            elif inp.prefix == "predicted":
                mappings.extend(from_biomappings_predicted())
            else:
                raise ValueError
        elif inp.source == "gilda":
            mappings.extend(from_gilda(confidence=inp.confidence))
        elif inp.source == "custom":
            mappings.extend(from_cache_df(**(inp.extras or {})))
        else:
            raise ValueError
    return mappings
