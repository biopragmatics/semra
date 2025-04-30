"""Declarative acquisition and processing of mapping sets."""

from __future__ import annotations

import logging
import time
import typing as t
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal

import click
import requests
from pydantic import BaseModel, Field, model_validator
from tqdm.auto import tqdm
from typing_extensions import Self

from semra.api import (
    assemble_evidences,
    filter_mappings,
    filter_prefixes,
    filter_self_matches,
    filter_subsets,
    hydrate_subsets,
    keep_prefixes,
    prioritize,
    validate_mappings,
)
from semra.inference import infer_chains, infer_mutual_dbxref_mutations, infer_reversible
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
from semra.rules import DB_XREF, EXACT_MATCH, IMPRECISE, SubsetConfiguration
from semra.sources import SOURCE_RESOLVER
from semra.sources.biopragmatics import (
    from_biomappings_negative,
    from_biomappings_predicted,
    get_biomappings_positive_mappings,
)
from semra.sources.gilda import get_gilda_mappings
from semra.sources.wikidata import get_wikidata_mappings_by_prefix
from semra.struct import Mapping, Reference

if t.TYPE_CHECKING:
    import zenodo_client

__all__ = [
    "Configuration",
    "Input",
    "Mutation",
    "SubsetConfiguration",
    "get_mappings_from_config",
    "get_raw_mappings",
    "process",
]

logger = logging.getLogger(__name__)

UPLOAD_OPTION = click.option("--upload", is_flag=True)
REFRESH_RAW_OPTION = click.option("--refresh-raw", is_flag=True)
REFRESH_PROCESSED_OPTION = click.option("--refresh-processed", is_flag=True)
REFRESH_SOURCE_OPTION = click.option(
    "--refresh-source",
    is_flag=True,
    help="Enable this to fully re-process source data, e.g., parse source OBO files and re-build mapping caches",
)
BUILD_DOCKER_OPTION = click.option("--build-docker", is_flag=True)


class Input(BaseModel):
    """Represents the input to a mapping assembly."""

    source: Literal["pyobo", "bioontologies", "biomappings", "custom", "sssom", "gilda", "wikidata"]
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

    name: str = Field(..., description="The name of the mapping set configuration")
    key: str = Field(
        ..., description="A short key describing the configuration used for logging purposes"
    )
    description: str | None = Field(
        None, description="An explanation of the purpose of the mapping set configuration"
    )
    creators: list[Reference] = Field(
        default_factory=list, description="A list of the ORCID identifiers for creators"
    )
    inputs: list[Input] = Field(..., description="A list of sources of mappings")
    negative_inputs: list[Input] = Field(
        default_factory=lambda: [Input(source="biomappings", prefix="negative")]
    )
    priority: list[str] = Field(
        default_factory=list,
        description="If no priority is given, is inferred from the order of inputs",
    )
    mutations: list[Mutation] = Field(default_factory=list)
    subsets: SubsetConfiguration | None = Field(
        None,
        description="A field to put restrictions on the sub-hierarchies from each resource."
        "For example, if you want to assemble cell mappings from MeSH, you don't need all "
        "possible mesh mappings, but only ones that have to do with terms in the cell hierarchy "
        "under the mesh:D002477 term. Therefore, this dictionary allows for specifying such "
        "restrictions",
        examples=[
            {"mesh": [Reference.from_curie("mesh:D002477")]},
        ],
    )

    exclude_pairs: list[tuple[str, str]] = Field(
        default_factory=list,
        description="A list of pairs of prefixes. Remove all mappings whose source "
        "prefix is the first in a pair and target prefix is second in a pair. Order matters.",
    )
    remove_prefixes: list[str] | None = Field(
        None, description="Prefixes to remove before processing"
    )
    keep_prefixes: list[str] | None = Field(None, description="Prefixes to keep before processing")
    post_remove_prefixes: list[str] | None = Field(
        None, description="Prefixes to remove after processing"
    )
    post_keep_prefixes: list[str] | None = Field(
        None, description="Prefixes to keep after processing"
    )
    remove_imprecise: bool = True
    validate_raw: bool = Field(
        default=False,
        description="Should the raw mappings be validated against Bioregistry "
        "prefixes and local unique identifier regular expressions (when available)?",
    )

    raw_pickle_path: Path | None = None
    raw_sssom_path: Path | None = None
    raw_neo4j_path: Path | None = Field(
        default=None, description="Directory in which Neo4j stuff goes"
    )
    raw_neo4j_name: str | None = Field(
        default=None, description="Directory for docker tag for Neo4j"
    )

    processed_pickle_path: Path | None = None
    processed_sssom_path: Path | None = None
    processed_neo4j_path: Path | None = Field(
        default=None, description="Directory in which Neo4j stuff goes"
    )
    processed_neo4j_name: str | None = Field(
        default=None, description="Directory for docker tag for Neo4j"
    )

    priority_pickle_path: Path | None = None
    priority_sssom_path: Path | None = None
    # note that making a priority neo4j doesn't make sense

    add_labels: bool = Field(
        default=False, description="Should PyOBO be used to look up labels for SSSOM output?"
    )

    configuration_path: Path | None = Field(
        None, description="The path where this configuration should be written."
    )

    zenodo_record: int | None = Field(None, description="The Zenodo record identifier")

    @model_validator(mode="before")
    def infer_priority(cls, values: dict[str, Any]) -> dict[str, Any]:  # noqa:N805
        """Infer the priority from the input list of not given."""
        priority = values["priority"]
        if not priority:
            values["priority"] = [
                inp.prefix for inp in values["inputs"].inputs if inp.prefix is not None
            ]
        return values

    def zenodo_url(self) -> str | None:
        """Get the zenodo URL, if available."""
        if self.zenodo_record is None:
            return None
        return f"https://bioregistry.io/zenodo.record:{self.zenodo_record}"

    @classmethod
    def from_prefixes(
        cls,
        *,
        key: str,
        name: str,
        prefixes: t.Iterable[str],
        include_biomappings: bool = True,
        include_gilda: bool = True,
    ) -> Self:
        """Get a configuration from ontology prefixes."""
        inputs = [Input(source="bioontologies", prefix=p) for p in prefixes]
        if include_biomappings:
            inputs.append(Input(source="biomappings"))
        if include_gilda:
            inputs.append(Input(source="gilda"))
        return cls(key=key, name=name, inputs=inputs)

    def get_mappings(
        self,
        *,
        refresh_raw: bool = False,
        refresh_processed: bool = False,
        refresh_source: bool = False,
    ) -> list[Mapping]:
        """Run assembly based on this configuration."""
        return get_mappings_from_config(
            self,
            refresh_source=refresh_source,
            refresh_raw=refresh_raw,
            refresh_processed=refresh_processed,
        )

    def read_raw_mappings(self) -> list[Mapping]:
        """Read raw mappings from pickle, if already cached."""
        if self.raw_pickle_path and self.raw_pickle_path.is_file():
            return from_pickle(self.raw_pickle_path)
        if self.raw_sssom_path and self.raw_sssom_path.is_file():
            return from_sssom(self.raw_sssom_path)
        if self.raw_pickle_path and not self.raw_pickle_path.is_file():
            raise FileNotFoundError(f"raw mappings pickle file not found: {self.raw_pickle_path}")
        if self.raw_sssom_path and not self.raw_sssom_path.is_file():
            raise FileNotFoundError(f"raw mappings SSSOM file not found: {self.raw_sssom_path}")
        raise ValueError("no raw pickle nor SSSOM file given")

    def read_processed_mappings(self) -> list[Mapping]:
        """Read processed mappings from pickle, if already cached."""
        if self.processed_pickle_path and self.processed_pickle_path.is_file():
            return from_pickle(self.processed_pickle_path)
        if self.processed_sssom_path and self.processed_sssom_path.is_file():
            return from_sssom(self.processed_sssom_path)
        if self.processed_pickle_path and not self.processed_pickle_path.is_file():
            raise FileNotFoundError(
                f"processed mappings pickle file not found: {self.processed_pickle_path}"
            )
        if self.processed_sssom_path and not self.processed_sssom_path.is_file():
            raise FileNotFoundError(
                f"processed mappings SSSOM file not found: {self.processed_sssom_path}"
            )
        raise ValueError("no processed pickle nor SSSOM file given")

    def get_hydrated_subsets(self, *, show_progress: bool = True) -> SubsetConfiguration:
        """Get the full subset filter lists based on the parent configuration."""
        if not self.subsets:
            return {}
        return hydrate_subsets(self.subsets, show_progress=show_progress)

    def _get_zenodo_metadata(self) -> zenodo_client.Metadata:
        if not self.creators:
            raise ValueError("Creating a Zenodo record requires annotating the creators field")
        import zenodo_client

        if self.name is None:
            raise ValueError("name must be given to upload to zenodo")
        if self.description is None:
            raise ValueError("description must be given to upload to zenodo")
        if not self.creators:
            raise ValueError("at least one creator must be given to upload to zenodo")

        return zenodo_client.Metadata(
            upload_type="dataset",
            title=self.name,
            description=self.description,
            creators=[
                zenodo_client.Creator(name=creator.name, orcid=creator.identifier)
                for creator in self.creators
                if creator.prefix == "orcid"
            ],
        )

    def _get_zenodo_paths(self, *, processed: bool = True) -> list[Path]:
        if self.configuration_path is not None and not self.configuration_path.is_file():
            self.configuration_path.write_text(
                self.model_dump_json(indent=2, exclude_none=True, exclude_unset=True)
            )
        paths = [
            self.configuration_path,
            self.raw_sssom_path,
            self.raw_pickle_path,
            self.processed_sssom_path,
            self.processed_pickle_path,
            self.priority_sssom_path,
            self.processed_pickle_path,
        ]
        for path in paths:
            if path is None:
                raise ValueError("Can't upload to Zenodo if not all output paths are configured")
            if not path.is_file():
                raise FileNotFoundError(path)
        if (
            processed
            and self.processed_neo4j_path is not None
            and self.processed_neo4j_path.is_dir()
        ):
            paths.extend(self.processed_neo4j_path.iterdir())
        elif self.raw_neo4j_path is not None and self.raw_neo4j_path.is_dir():
            paths.extend(self.raw_neo4j_path.iterdir())
        else:
            logger.debug("Not uploading neo4j")
        return t.cast(list[Path], paths)

    def ensure_zenodo(
        self,
        key: str,
        *,
        metadata: zenodo_client.Metadata | None = None,
        processed: bool = True,
        **kwargs: Any,
    ) -> requests.Response:
        """Ensure a zenodo record."""
        if self.zenodo_record is not None:
            raise ValueError(
                f"Refusing to create new Zenodo record since it already exists: "
                f"https://bioregistry.io/zenodo.record:{self.zenodo_record}.\n\n"
                f"Use `Configuration.upload_zenodo(processed={processed})` instead."
            )

        from zenodo_client import ensure_zenodo

        paths = self._get_zenodo_paths(processed=processed)
        res = ensure_zenodo(
            key=key, data=metadata or self._get_zenodo_metadata(), paths=paths, **kwargs
        )
        return res

    def upload_zenodo(self, processed: bool = True, **kwargs: Any) -> requests.Response:
        """Upload a Zenodo record."""
        if not self.zenodo_record:
            raise ValueError(
                "Can not upload to zenodo if no record is configured.\n\n"
                f"Use `Configuration.ensure_zenodo(key=..., processed={processed})` instead."
            )
        from zenodo_client import update_zenodo

        paths = self._get_zenodo_paths(processed=processed)
        res = update_zenodo(str(self.zenodo_record), paths=paths, **kwargs)
        return res

    def _build_docker(self) -> None:
        # this is mostly for testing purposes - normally, the neo4j export
        # will get called with `sh run_on_startup.sh`, which also includes
        # the build command. Adding --build-docker is useful for making sure
        # that the data all works properly
        import os
        import subprocess

        if self.processed_neo4j_name is None:
            click.secho("you should set the processed_neo4j_name", fg="red")
            name = "semra"
        else:
            name = self.processed_neo4j_name

        args = ["docker", "build", "--tag", name, "."]
        click.secho("Building dockerfile (automated)", fg="green")
        res = subprocess.run(  # noqa:S603
            args,
            check=True,
            cwd=str(self.processed_neo4j_path),
            env=dict(os.environ, DOCKER_CLI_HINTS="false"),
        )
        click.echo(f"Result: {res}")

    def cli(self, *args: Any) -> None:
        """Get and run a command line interface for this configuration."""
        self.get_cli()(*args)

    def get_cli(self) -> click.Command:
        """Get a command line interface for this configuration."""
        import click
        from more_click import verbose_option

        @click.command()
        @UPLOAD_OPTION
        @REFRESH_SOURCE_OPTION
        @REFRESH_RAW_OPTION
        @REFRESH_PROCESSED_OPTION
        @BUILD_DOCKER_OPTION
        @verbose_option  # type:ignore
        def main(
            upload: bool,
            refresh_source: bool,
            refresh_raw: bool,
            refresh_processed: bool,
            build_docker: bool,
        ) -> None:
            """Build the mapping database terms."""
            self.get_mappings(
                refresh_source=refresh_source,
                refresh_raw=refresh_raw,
                refresh_processed=refresh_processed,
            )
            if build_docker and self.processed_neo4j_path:
                self._build_docker()
            if upload:
                self._safe_upload()

        return main

    def _safe_upload(self) -> None:
        if not self.zenodo_record:
            click.secho("can't upload to Zenodo - no record configued", fg="red")
        else:
            res = self.upload_zenodo()
            url = res.json()["links"]["html"]
            click.echo(f"uploaded to {url}")


def get_mappings_from_config(
    configuration: Configuration,
    *,
    refresh_source: bool = False,
    refresh_raw: bool = False,
    refresh_processed: bool = False,
) -> list[Mapping]:
    """Run assembly based on a configuration."""
    if refresh_source:
        refresh_raw = True
    if refresh_raw:
        refresh_processed = True

    if (
        configuration.priority_pickle_path
        and configuration.priority_pickle_path.is_file()
        and not refresh_raw
        and not refresh_processed
    ):
        logger.info("loading cached priority mappings from %s", configuration.priority_pickle_path)
        return from_pickle(configuration.priority_pickle_path)

    if (
        configuration.raw_pickle_path
        and configuration.raw_pickle_path.is_file()
        and not refresh_raw
    ):
        start = time.time()
        logger.info("loading cached raw mappings from %s", configuration.raw_pickle_path)
        raw_mappings = from_pickle(configuration.raw_pickle_path)
        logger.info(
            "loaded cached raw mappings from %s in %.2f seconds",
            configuration.raw_pickle_path,
            time.time() - start,
        )
    else:
        if configuration.configuration_path is not None:
            configuration.configuration_path.write_text(
                configuration.model_dump_json(exclude_none=True, exclude_unset=True, indent=2)
            )

        raw_mappings = get_raw_mappings(configuration, refresh_source=refresh_source)
        if not raw_mappings:
            raise ValueError(f"no raw mappings found for configuration: {configuration.name}")
        if configuration.validate_raw:
            validate_mappings(raw_mappings)
        if configuration.raw_pickle_path:
            write_pickle(raw_mappings, configuration.raw_pickle_path)
        if configuration.raw_sssom_path:
            write_sssom(
                raw_mappings,
                configuration.raw_sssom_path,
                # add_labels=configuration.add_labels
            )
        if configuration.raw_neo4j_path:
            write_neo4j(
                raw_mappings,
                configuration.raw_neo4j_path,
                docker_name=configuration.raw_neo4j_name,
                add_labels=False,  # configuration.add_labels,
            )

    # click.echo(semra.api.str_source_target_counts(mappings, minimum=20))
    processed_mappings = process(
        raw_mappings,
        upgrade_prefixes=[  # TODO more carefully compile a set of mutations together for applying
            m.source for m in configuration.mutations
        ],
        remove_prefix_set=configuration.remove_prefixes,
        keep_prefix_set=configuration.keep_prefixes,
        post_remove_prefixes=configuration.post_remove_prefixes,
        post_keep_prefixes=configuration.post_keep_prefixes,
        remove_imprecise=configuration.remove_imprecise,
        subsets=configuration.get_hydrated_subsets(),
    )
    prioritized_mappings = prioritize(processed_mappings, configuration.priority)

    if configuration.processed_pickle_path:
        write_pickle(processed_mappings, configuration.processed_pickle_path)
    if configuration.processed_sssom_path:
        write_sssom(
            processed_mappings,
            configuration.processed_sssom_path,
            add_labels=configuration.add_labels,
        )
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
        write_sssom(
            prioritized_mappings,
            configuration.priority_sssom_path,
            add_labels=configuration.add_labels,
        )

    return prioritized_mappings


def _get_equivalence_classes(
    mappings: Iterable[Mapping], prioritized_mappings: Iterable[Mapping]
) -> dict[Reference, bool]:
    priority_references = {mapping.object for mapping in prioritized_mappings}
    rv = {}
    for mapping in mappings:
        rv[mapping.subject] = mapping.subject in priority_references
        rv[mapping.object] = mapping.object in priority_references
    return rv


def get_raw_mappings(
    configuration: Configuration,
    show_progress: bool = True,
    refresh_source: bool = False,
) -> list[Mapping]:
    """Get raw mappings based on the inputs in a configuration."""
    mappings = []
    for i, inp in enumerate(
        tqdm(
            configuration.inputs,
            desc=f"[{configuration.key}] getting raw mappings",
            unit="source",
            disable=not show_progress,
        ),
        start=1,
    ):
        tqdm.write(
            f"[{configuration.key}] {i}/{len(configuration.inputs)} "
            + click.style(f"Loading mappings from {inp.source}", fg="green")
            + (f" ({inp.prefix})" if inp.prefix else "")
        )
        if inp.source is None:
            continue
        elif inp.source == "bioontologies":
            if inp.prefix is None:
                raise ValueError
            mappings.extend(from_bioontologies(inp.prefix, confidence=inp.confidence, **inp.extras))
        elif inp.source == "pyobo":
            if inp.prefix is None:
                raise ValueError
            mappings.extend(
                from_pyobo(
                    inp.prefix,
                    confidence=inp.confidence,
                    force_process=refresh_source,
                    **inp.extras,
                )
            )
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
        elif inp.source == "wikidata":
            if inp.prefix is None:
                raise ValueError("prefix is required to be set when wikidata is used as a source")
            mappings.extend(get_wikidata_mappings_by_prefix(inp.prefix, **inp.extras))
        elif inp.source == "sssom":
            mappings.extend(from_sssom(inp.prefix, **inp.extras))
        elif inp.source == "cache":
            mappings.extend(from_cache_df(**inp.extras))
        else:
            raise ValueError
    return mappings


def process(
    mappings: list[Mapping],
    upgrade_prefixes: Iterable[str] | None = None,
    remove_prefix_set: t.Collection[str] | None = None,
    keep_prefix_set: t.Collection[str] | None = None,
    post_remove_prefixes: t.Collection[str] | None = None,
    post_keep_prefixes: t.Collection[str] | None = None,
    subsets: SubsetConfiguration | None = None,
    *,
    remove_imprecise: bool = True,
) -> list[Mapping]:
    """Run a full deduplication, reasoning, and inference pipeline over a set of mappings."""
    from semra.sources.biopragmatics import from_biomappings_negative

    if keep_prefix_set:
        mappings = keep_prefixes(mappings, keep_prefix_set)

    if remove_prefix_set:
        mappings = filter_prefixes(mappings, remove_prefix_set)

    if subsets:
        mappings = list(filter_subsets(mappings, subsets))

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

    # remove database cross-references
    if remove_imprecise:
        logger.info("Removing unqualified database xrefs")
        before = len(mappings)
        start = time.time()
        mappings = [m for m in mappings if m.predicate not in IMPRECISE]
        _log_diff(before, mappings, verb="Filtered non-precise", elapsed=time.time() - start)

    # 3. Inference based on adding reverse relations then doing multichain hopping
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

    if post_keep_prefixes:
        mappings = keep_prefixes(mappings, post_keep_prefixes)

    if post_remove_prefixes:
        mappings = filter_prefixes(mappings, post_remove_prefixes)

    return mappings


def _log_diff(before: int, mappings: list[Mapping], *, verb: str, elapsed: float) -> None:
    logger.info(
        f"{verb} from {before:,} to {len(mappings):,} mappings "
        f"(Δ={len(mappings) - before:,}) in %.2f seconds.",
        elapsed,
    )
