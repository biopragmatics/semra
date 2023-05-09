"""Declarative acquisition and processing of mapping sets."""

from __future__ import annotations

import logging
import pickle
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, root_validator
from tqdm.auto import tqdm

from semra.api import prioritize, process, write_sssom
from semra.rules import DB_XREF, EXACT_MATCH
from semra.sources import from_biomappings_positive, from_bioontologies, from_gilda, from_pyobo
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

    source: Literal["pyobo", "bioontologies", "biomappings", "gilda"]
    prefix: str | None = None
    confidence: float = 1.0


class Mutation(BaseModel):
    """Represents a mutation operation on a mapping set."""

    source: str = Field()
    confidence: float = 1.0
    old: Reference = Field(default=DB_XREF)
    new: Reference = Field(default=EXACT_MATCH)


class Configuration(BaseModel):
    """Represents the steps taken during mapping assembly."""

    inputs: list[Input]
    priority: list[str] | None = Field(description="If no priority is given, is inferred from the order of inputs")
    mutations: list[Mutation] = Field(default_factory=list)
    remove_prefixes: list[str] | None = None
    raw_path: Path | None = None
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
    if configuration.raw_path and configuration.raw_path.is_file():
        start = time.time()
        logger.info("loading cached raw mappings from %s", configuration.raw_path)
        mappings = pickle.loads(configuration.raw_path.read_bytes())
        logger.info("loaded cached raw mappings from %s in %.2f seconds", configuration.raw_path, time.time() - start)
    else:
        mappings = get_raw_mappings(configuration)
        if configuration.raw_path:
            configuration.raw_path.write_bytes(pickle.dumps(mappings, protocol=pickle.HIGHEST_PROTOCOL))

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
            mappings.extend(from_bioontologies(inp.prefix, confidence=inp.confidence))
        elif inp.source == "pyobo":
            mappings.extend(from_pyobo(inp.prefix, confidence=inp.confidence))
        elif inp.source == "biomappings":
            mappings.extend(from_biomappings_positive())
        elif inp.source == "gilda":
            mappings.extend(from_gilda(confidence=inp.confidence))
        else:
            raise ValueError
    return mappings
