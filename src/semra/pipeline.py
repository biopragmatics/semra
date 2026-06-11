"""The SeMRA assembly pipeline is a declarative way to say which sources should be used, which prior knowledge should be injected into processing, and how entities should be "prioritized" on output.

The assembly and inference of semantic mappings can solve the problem illustrated in the
image below where a combination of incomplete mappings can can lead to the
prioritization of an entity from a target namespace, and the creation of a priorization
mapping set (i.e., a star graph).

.. image:: img/pipeline.svg

In the following demo, which closely resembles the configuration in
:data:`semra.landscape.cell`, we show how to fill out a configuration in the Python DSL.

.. code-block:: python

    import pystow

    from semra import Configuration, Reference
    from semra.pipeline import AssembleReturnType, Input, Mutation, assemble
    from semra.vocabulary import CHARLIE

    configuration = Configuration(
        # the key is a short name for the configuration. this is required
        key="cell",
        # the name is a human-readable representation of the configuration
        name="SeMRA Cell and Cell Line Mappings Database",
        # an (optional) description of the reason the configuration was created
        description="Originally a reproduction of the EFO/Cellosaurus/DepMap/CCLE scenario posed in "
        "the Biomappings paper, this configuration imports several different cell and cell line "
        "resources and identifies mappings between them.",
        # an (optional) list of references for creators
        creators=[CHARLIE],
        # the places where data should be acquired
        inputs=[
            Input(source="biomappings"),
            Input(source="gilda"),
            Input(prefix="cellosaurus", source="pyobo", confidence=0.99),
            Input(prefix="bto", source="pyobo", confidence=0.99),
            Input(prefix="cl", source="pyobo", confidence=0.99),
            Input(prefix="clo", source="custom", confidence=0.65),
            Input(prefix="efo", source="pyobo", confidence=0.99),
            Input(
                prefix="depmap",
                source="pyobo",
                confidence=0.99,
                extras={"version": "22Q4", "license": "CC-BY-4.0"},
            ),
            Input(prefix="ccle", source="pyobo", confidence=0.99, extras={"version": "2019"}),
            Input(prefix="ncit", source="pyobo", confidence=0.99),
            Input(prefix="umls", source="pyobo", confidence=0.99),
        ],
        # configuration for how inputs should be subset'd. This is a dictionary
        # with keys that correspond to prefixes and values are collections of
        # references whose hierarhical descendants get kept. For example, this
        # is useful to take subsets from generic resources like NCIT, MeSH, and
        # UMLS
        subsets={
            "mesh": [Reference.from_curie("mesh:D002477")],
            "efo": [Reference.from_curie("efo:0000324")],
            "ncit": [Reference.from_curie("ncit:C12508")],
            "umls": [Reference.from_curie("sty:T025")],
        },
        # the prioritization of prefixes for creating star graphs. the prefixes
        # appearing earlier in the list are higher priority
        priority=[
            "mesh",
            "efo",
            "cellosaurus",
            "ccle",
            "depmap",
            "bto",
            "cl",
            "clo",
            "ncit",
            "umls",
        ],
        # only prefixes in this list are kept from raw mappings. If there are
        # relevant intermediate for mappings that you don't want to keep after
        # processing, use ``post_keep_prefixes``. This is often the same as the
        # priority list
        keep_prefixes=[],
        # should mappings in the imprecise mappings list (e.g., dbxrefs, rdfs:seeAlso)
        # be removed during processing? Defaults to True.
        remove_imprecise=False,
        # mutations allow you to specify your prior knowledge, for example, that
        # all dbxrefs in EFO should be upgraded to skos:exactMatch with a confidence
        # of 0.7. Mutations can be configured further to only apply to a subset
        # of targets, to change the source predicate from dbxref to something else,
        # or to change the target predicate from skos:exactMatch to somethign else
        mutations=[
            Mutation(source="efo", confidence=0.7),
            Mutation(source="bto", confidence=0.7),
            Mutation(source="cl", confidence=0.7),
            Mutation(source="clo", confidence=0.7),
            Mutation(source="depmap", confidence=0.7),
            Mutation(source="ccle", confidence=0.7),
            Mutation(source="cellosaurus", confidence=0.7),
            Mutation(source="ncit", confidence=0.7),
            Mutation(source="umls", confidence=0.7),
        ],
        # Should labels be looked up using PyOBO during SSSOM and Neo4j output?
        # this adds some build time. Defaults to False.
        add_labels=True,
        # If this configuration should get uploaded to Zenodo via the ``zenodo_client``
        # python package, use this record ID
        zenodo_record=...,
        # The directory where the results of build should get output. This is
        # required.
        directory=pystow.module("semra", "pipeline-example").base,
    )

    # these mappings induce a star graph based on the prioritization
    priority_mappings = assemble(configuration)

    # raw and processed mappings can be returned as well
    mapping_pack = assemble(
        configuration,
        return_type=AssembleReturnType.all,
    )

For reference, the :mod:`semra.landscape` module contains several pipeline
configurations.
"""

from __future__ import annotations

import datetime
import enum
import logging
import time
import typing as t
from collections.abc import Callable, Iterable
from functools import partial
from pathlib import Path
from typing import Annotated, Any, Literal, NamedTuple, Self, overload

import bioregistry
import click
import humanize
import requests
import sssom_pydantic
from curies.triples import keep_prefixes_both
from pydantic import BaseModel, Field, model_validator
from pystow.utils import read_pydantic_json
from sssom_pydantic import MappingSet
from tqdm.auto import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from semra.api import (
    Mutation,
    apply_mutations,
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
    from_jsonl,
    from_pickle,
    from_pyobo,
    from_sssom,
    from_sssom_pydantic,
    write_jsonl,
    write_neo4j,
    write_sssom,
)
from semra.rules import IMPRECISE, SubsetConfiguration
from semra.sources import SOURCE_RESOLVER, normalize_custom_func_name
from semra.sources.biopragmatics import (
    get_biomappings_negative_mappings,
    get_biomappings_positive_mappings,
    get_biomappings_predicted_mappings,
)
from semra.sources.gilda import get_gilda_mappings
from semra.sources.wikidata import get_wikidata_mappings_by_prefix
from semra.struct import Mapping, Reference, Statistics
from semra.utils import (
    PrefixListValidator,
    PrefixPairListValidator,
    get_jinja_template,
)

if t.TYPE_CHECKING:
    import zenodo_client

__all__ = [
    "AssembleReturnType",
    "Configuration",
    "Input",
    "Mutation",
    "SubsetConfiguration",
    "assemble",
    "get_raw_mappings",
    "process_raw_mappings",
]

logger = logging.getLogger(__name__)

HERE = Path(__file__).parent.resolve()

REFRESH_PROCESSED_OPTION = click.option(
    "--refresh-processed",
    is_flag=True,
    help="Re-process raw mappings. This is the least aggressive 'refresh' option.",
)
REFRESH_RAW_OPTION = click.option(
    "--refresh-raw",
    is_flag=True,
    help="Re-process mapping sources to produce raw mappings and process them "
    "again. This is more aggressive than --refresh-process.",
)
REFRESH_SOURCE_OPTION = click.option(
    "--refresh-source",
    is_flag=True,
    help="Enable this to fully re-process source data, e.g., parse source OBO "
    "files and re-build mapping caches. This is more aggressive than "
    "--refresh-process and --refresh-raw",
)

BUILD_DOCKER_OPTION = click.option(
    "--build-docker",
    is_flag=True,
    help="If activated, `docker build` is invoked as a test to make sure that "
    "the construction of the Neo4j database works correctly. E.g., this can "
    "catch data issues that result in invalid Neo4j nodes or edges files.",
)

STATS_FILE_NAME = "stats.json"
CONFIG_FILE_NAME = "configuration.json"


class AssembleReturnType(enum.Enum):
    """An enumeration for the return values for :func:`assemble`."""

    none = enum.auto()
    all = enum.auto()
    priority = enum.auto()


class Input(BaseModel):
    """Represents the input to a mapping assembly."""

    source: Literal["pyobo", "bioontologies", "biomappings", "custom", "sssom", "gilda", "wikidata"]
    prefix: str | None = None
    confidence: float = Field(
        1.0,
        description="confidence the creator of the configuration has in the source",
        ge=0.0,
        le=1.0,
    )
    extras: dict[str, Any] | None = None
    pre_filter_prefixes: bool | None = Field(
        None,
        description="should the raw mappings be filtered by the priority prefix list? if not set, will default to false.",
    )

    @model_validator(mode="after")
    def validate_after(self) -> Self:
        """Check prefixes are okay."""
        if self.source not in {"pyobo", "bioontologies", "wikidata"}:
            return self
        if self.prefix is None:
            raise ValueError
        assert_bioregistry_canonical(self.prefix)
        return self

    def load(self, *, refresh_source: bool) -> list[Mapping] | None:
        """Load mappings from the source."""
        if self.source is None:
            return None
        elif self.source in {"pyobo", "bioontologies"}:
            if self.prefix is None:
                raise ValueError
            rv = from_pyobo(
                self.prefix,
                confidence=self.confidence,
                force_process=refresh_source,
                **(self.extras or {}),
            )
        elif self.source == "biomappings":
            if self.pre_filter_prefixes is None:
                self.pre_filter_prefixes = True
            if self.prefix in {None, "positive"}:
                rv = from_sssom_pydantic(get_biomappings_positive_mappings())
            elif self.prefix == "negative":
                rv = from_sssom_pydantic(get_biomappings_negative_mappings())
            elif self.prefix == "predicted":
                rv = from_sssom_pydantic(get_biomappings_predicted_mappings())
            else:
                raise ValueError(f"invalid prefix for biomappings: {self.prefix}")
        elif self.source == "gilda":
            if self.pre_filter_prefixes is None:
                self.pre_filter_prefixes = True
            # TODO fold into custom source
            rv = from_sssom_pydantic(get_gilda_mappings())
        elif self.source == "custom":
            func = SOURCE_RESOLVER.make(self.prefix, self.extras)
            func_name = normalize_custom_func_name(func)
            rv = from_sssom_pydantic(
                func(),
                mapping_set=MappingSet(
                    id=f"https://w3id.org/biopragmatics/semra/custom/{func_name}.sssom.tsv"
                ),
            )
        elif self.source == "wikidata":
            if self.prefix is None:
                raise ValueError("prefix is required to be set when wikidata is used as a source")
            rv = from_sssom_pydantic(
                get_wikidata_mappings_by_prefix(self.prefix, **(self.extras or {}))
            )
        elif self.source == "sssom":
            if self.prefix is None:
                raise ValueError
            rv = from_sssom(self.prefix, **(self.extras or {}))
        else:
            raise ValueError
        return rv


def assert_bioregistry_canonical(prefix: str) -> None:
    """Assert the prefix is canonical."""
    resource = bioregistry.get_resource(prefix, strict=True)
    if resource.prefix != prefix:
        raise ValueError(f"{prefix} should be standardized to {resource.prefix}")
    if resource.provides:
        raise ValueError(
            f"{resource.prefix} provides for {resource.provides} - should use {resource.provides}"
        )
    if resource.part_of:
        raise ValueError(
            f"{resource.prefix} is part of {resource.part_of} - should use {resource.part_of}"
        )
    if resource.has_canonical:
        raise ValueError(
            f"{resource.prefix} has canonical resource {resource.has_canonical} - should use {resource.has_canonical}"
        )


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
    priority: Annotated[list[str], PrefixListValidator] = Field(
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

    exclude_pairs: Annotated[list[tuple[str, str]], PrefixPairListValidator] = Field(
        default_factory=list,
        description="A list of pairs of prefixes. Remove all mappings whose source "
        "prefix is the first in a pair and target prefix is second in a pair. Order matters.",
    )
    remove_prefixes: Annotated[list[str] | None, PrefixListValidator] = Field(
        None, description="Prefixes to remove before processing"
    )
    keep_prefixes: Annotated[list[str] | None, PrefixListValidator] = Field(
        None, description="Prefixes to keep before processing"
    )
    post_remove_prefixes: list[str] | None = Field(
        None, description="Prefixes to remove after processing"
    )
    post_keep_prefixes: Annotated[list[str] | None, PrefixListValidator] = Field(
        None, description="Prefixes to keep after processing"
    )
    remove_imprecise: bool = True
    validate_raw: bool = Field(
        default=False,
        description="Should the raw mappings be validated against Bioregistry "
        "prefixes and local unique identifier regular expressions (when available)?",
    )

    directory: Path = Field(..., description="The directory where contents are written")

    write_raw_neo4j: bool = Field(
        default=False, description="Should a neo4j directory be written for raw mappings?"
    )
    neo4j_gzip: None | Literal["during", "after"] = Field(
        default="during",
        description="When should gzipping be applied? Defaults to during write, but if the files are big and it causes memory issues, then change to 'after'. If no gzipping is desired, explicilty set to None.",
    )
    add_labels: bool = Field(
        default=False, description="Should PyOBO be used to look up labels for SSSOM output?"
    )

    zenodo_record: int | None = Field(None, description="The Zenodo record identifier")

    purl_base: str = "https://w3id.org/biopragmatics/semra/"

    def _get_header_text(self) -> str:
        """Get header text for SemRA built-in configuration."""
        from tabulate import tabulate

        template = get_jinja_template("landscape-header.rst")
        rows = [
            (
                f"`{prefix} <https://bioregistry.io/{prefix}>`_",
                bioregistry.get_name(prefix, strict=True),
            )
            for prefix in self.priority
        ]
        return template.render(
            configuration=self, table=tabulate(rows, tablefmt="rst", headers=["Prefix", "Name"])
        )

    @property
    def raw_pickle_path(self) -> Path:
        """Get the path to raw mappings as a gzipped pickle file."""
        return self.directory.joinpath("raw.pkl.gz")

    @property
    def raw_sssom_path(self) -> Path:
        """Get the path to raw mappings as a gzipped SSSOM TSV file."""
        return self.directory.joinpath("raw.sssom.tsv.gz")

    @property
    def raw_jsonl_path(self) -> Path:
        """Get the path to raw mappings as a gzipped JSON lines file."""
        return self.directory.joinpath("raw.jsonl.gz")

    def has_raw_path(self) -> bool:
        """Check if the configuration has cached raw mappings."""
        return any(
            p.is_file() for p in [self.raw_jsonl_path, self.raw_pickle_path, self.raw_sssom_path]
        )

    @property
    def processed_pickle_path(self) -> Path:
        """Get the path to processed mappings as a gzipped pickle file."""
        return self.directory.joinpath("processed.pkl.gz")

    @property
    def processed_sssom_path(self) -> Path:
        """Get the path to processed mappings as a gzipped SSSOM TSV file."""
        return self.directory.joinpath("processed.sssom.tsv.gz")

    @property
    def processed_jsonl_path(self) -> Path:
        """Get the path to processed mappings as a gzipped JSON lines file."""
        return self.directory.joinpath("processed.jsonl.gz")

    def has_processed_path(self) -> bool:
        """Check if the configuration has cached priority mappings."""
        return any(
            p.is_file()
            for p in [
                self.processed_jsonl_path,
                self.processed_pickle_path,
                self.processed_sssom_path,
            ]
        )

    @property
    def priority_pickle_path(self) -> Path:
        """Get the path to priority mappings as a gzipped pickle file."""
        return self.directory.joinpath("priority.pkl.gz")

    @property
    def priority_sssom_path(self) -> Path:
        """Get the path to priority mappings as a gzipped SSSOM TSV file."""
        return self.directory.joinpath("priority.sssom.tsv.gz")

    @property
    def priority_jsonl_path(self) -> Path:
        """Get the path to priority mappings as a gzipped JSON lines file."""
        return self.directory.joinpath("priority.jsonl.gz")

    def has_priority_path(self) -> bool:
        """Check if the configuration has cached priority mappings."""
        return any(
            p.is_file()
            for p in [self.priority_jsonl_path, self.priority_pickle_path, self.priority_sssom_path]
        )

    @property
    def configuration_path(self) -> Path:
        """Get the path to the configuration file."""
        return self.directory.joinpath(CONFIG_FILE_NAME)

    @property
    def raw_neo4j_path(self) -> Path:
        """Get the path to the raw neo4j directory."""
        return self.directory.joinpath("neo4j_raw")

    @property
    def processed_neo4j_path(self) -> Path:
        """Get the path to the processed neo4j directory."""
        return self.directory.joinpath("neo4j")

    @property
    def processed_neo4j_name(self) -> str:
        """Get the name for the processed mappings Neo4j docker image."""
        return f"semra-{self.key}"

    @property
    def raw_neo4j_name(self) -> str:
        """Get the name for the raw mappings Neo4j docker image."""
        return f"semra-{self.key}-raw"

    @property
    def processed_landscape_upset_path(self) -> Path:
        """Get the path to the processed landscape UpSet plot."""
        return self.directory.joinpath("processed_landscape_upset.svg")

    @property
    def processed_landscape_histogram_path(self) -> Path:
        """Get the path to the processed landscape histogram plot."""
        return self.directory.joinpath("processed_landscape_histogram.svg")

    @property
    def source_summary_path(self) -> Path:
        """Get the path to the source summary TSV file."""
        return self.directory.joinpath("source_summary.tsv")

    @property
    def raw_counts_path(self) -> Path:
        """Get the path to the raw counts summary TSV."""
        return self.directory / "raw_counts.tsv"

    @property
    def processed_counts_path(self) -> Path:
        """Get the path to the processed counts summary TSV."""
        return self.directory / "processed_counts.tsv"

    @property
    def priority_counts_path(self) -> Path:
        """Get the path to the priority counts summary TSV."""
        return self.directory / "priority_counts.tsv"

    @property
    def raw_graph_path(self) -> Path:
        """Get the path to the raw counts graph depiction."""
        return self.directory.joinpath("raw_graph.svg")

    @property
    def processed_graph_path(self) -> Path:
        """Get the path to the processed counts graph depiction."""
        return self.directory.joinpath("processed_graph.svg")

    @property
    def priority_graph_path(self) -> Path:
        """Get the path to the priority counts graph depiction."""
        return self.directory.joinpath("priority_graph.svg")

    @property
    def readme_path(self) -> Path:
        """Get the path to the summary README file."""
        return self.directory.joinpath("README.md")

    @property
    def stats_path(self) -> Path:
        """Get the path to the statistics summary JSON file."""
        return self.directory.joinpath(STATS_FILE_NAME)

    def _get_landscape_paths(self) -> list[Path]:
        return [
            self.raw_counts_path,
            self.raw_graph_path,
            # processed
            self.processed_counts_path,
            self.processed_graph_path,
            self.processed_landscape_upset_path,
            self.processed_landscape_histogram_path,
            # priority
            self.priority_counts_path,
            self.priority_graph_path,
            # summaries
            self.source_summary_path,
            self.readme_path,
            self.stats_path,
        ]

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
        prefixes: t.Sequence[str],
        include_biomappings: bool = True,
        include_gilda: bool = True,
        directory: Path,
    ) -> Self:
        """Get a configuration from ontology prefixes."""
        inputs = [Input(source="pyobo", prefix=p) for p in prefixes]
        if include_biomappings:
            inputs.append(Input(source="biomappings"))
        if include_gilda:
            inputs.append(Input(source="gilda"))
        return cls(key=key, name=name, inputs=inputs, directory=directory, priority=prefixes)

    # docstr-coverage: inherited
    @overload
    def get_mappings(
        self,
        *,
        refresh_raw: bool = ...,
        refresh_processed: bool = ...,
        refresh_source: bool = ...,
        return_type: Literal[AssembleReturnType.none] = AssembleReturnType.none,
        progress: bool = ...,
    ) -> None: ...

    # docstr-coverage: inherited
    @overload
    def get_mappings(
        self,
        *,
        refresh_raw: bool = ...,
        refresh_processed: bool = ...,
        refresh_source: bool = ...,
        return_type: Literal[AssembleReturnType.all] = AssembleReturnType.all,
        progress: bool = ...,
    ) -> MappingPack: ...

    # docstr-coverage: inherited
    @overload
    def get_mappings(
        self,
        *,
        refresh_raw: bool = ...,
        refresh_processed: bool = ...,
        refresh_source: bool = ...,
        return_type: Literal[AssembleReturnType.priority] = AssembleReturnType.priority,
        progress: bool = ...,
    ) -> list[Mapping]: ...

    def get_mappings(
        self,
        *,
        refresh_raw: bool = False,
        refresh_processed: bool = False,
        refresh_source: bool = False,
        return_type: AssembleReturnType = AssembleReturnType.none,
        progress: bool = True,
    ) -> list[Mapping] | MappingPack | None:
        """Run assembly based on this configuration, see :func:`assemble`."""
        return assemble(  # type:ignore[no-any-return,call-overload]
            self,
            refresh_source=refresh_source,
            refresh_raw=refresh_raw,
            refresh_processed=refresh_processed,
            return_type=return_type,
            progress=progress,
        )

    def _read_stats(self) -> Statistics:
        return read_pydantic_json(self.stats_path, Statistics)

    def read_raw_mappings(self, *, show_progress: bool = False) -> list[Mapping]:
        """Read raw mappings from pickle, if already cached."""
        statistics = self._read_stats()
        progress_kwargs = {
            "total": statistics.raw_mappings,
            "desc": f"[{self.key}] reading raw mappings",
        }

        paths: list[tuple[Path, Callable[[Path], list[Mapping]]]] = [
            (
                self.raw_jsonl_path,
                partial(from_jsonl, show_progress=show_progress, tqdm_kwargs=progress_kwargs),
            ),
            (self.raw_pickle_path, from_pickle),
            (
                self.raw_sssom_path,
                partial(from_sssom, progress=True, progress_kwargs=progress_kwargs),
            ),
        ]
        for path, opener in paths:
            if path.is_file():
                logger.info("loading cached raw mappings from %s", path)
                return opener(path)
        raise ValueError(f"raw mappings have not yet been cached in {self.directory}")

    def read_processed_mappings(self, *, show_progress: bool = False) -> list[Mapping]:
        """Read processed mappings from pickle, if already cached."""
        statistics = self._read_stats()
        progress_kwargs = {
            "total": statistics.processed_mappings,
            "desc": f"[{self.key}] reading processed mappings",
        }

        paths: list[tuple[Path, Callable[[Path], list[Mapping]]]] = [
            (
                self.processed_jsonl_path,
                partial(from_jsonl, show_progress=show_progress, tqdm_kwargs=progress_kwargs),
            ),
            (self.processed_pickle_path, from_pickle),
            (
                self.processed_sssom_path,
                partial(from_sssom, progress=True, progress_kwargs=progress_kwargs),
            ),
        ]
        for path, opener in paths:
            if path.is_file():
                logger.info("loading cached processed mappings from %s", path)
                return opener(path)
        raise ValueError(f"processed mappings have not yet been cached in {self.directory}")

    def read_priority_mappings(self, *, show_progress: bool = False) -> list[Mapping]:
        """Read priority mappings from pickle, if already cached."""
        statistics = self._read_stats()
        progress_kwargs = {
            "total": statistics.priority_mappings,
            "desc": f"[{self.key}] reading priority mappings",
        }

        paths: list[tuple[Path, Callable[[Path], list[Mapping]]]] = [
            (
                self.priority_jsonl_path,
                partial(from_jsonl, show_progress=show_progress, tqdm_kwargs=progress_kwargs),
            ),
            (self.priority_pickle_path, from_pickle),
            (
                self.priority_sssom_path,
                partial(from_sssom, progress=True, progress_kwargs=progress_kwargs),
            ),
        ]
        for path, opener in paths:
            if path.is_file():
                logger.info("loading cached priority mappings from %s", path)
                return opener(path)
        raise ValueError(f"priority mappings have not yet been cached in {self.directory}")

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
        if not self.configuration_path.is_file():
            self.configuration_path.write_text(
                self.model_dump_json(indent=2, exclude_none=True, exclude_unset=True)
            )
        paths = [
            self.configuration_path,
            self.raw_sssom_path,
            self.raw_jsonl_path,
            self.processed_sssom_path,
            self.processed_jsonl_path,
            self.priority_sssom_path,
            self.priority_jsonl_path,
            # TODO add summaries?
        ]
        for path in paths:
            if path is None:
                raise ValueError("Can't upload to Zenodo if not all output paths are configured")
            if not path.is_file():
                raise FileNotFoundError(path)
        if processed and self.processed_neo4j_path.is_dir():
            paths.extend(self.processed_neo4j_path.iterdir())
        # elif self.raw_neo4j_path is not None and self.raw_neo4j_path.is_dir():
        #    paths.extend(self.raw_neo4j_path.iterdir())
        else:
            logger.debug("Not uploading neo4j")
        return paths

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

        name = f"semra-{self.key}"

        args = ["docker", "build", "--tag", name, "."]
        click.secho("Building dockerfile (automated)", fg="green")
        res = subprocess.run(  # noqa:S603
            args,
            check=True,
            cwd=str(self.processed_neo4j_path),
            env=dict(os.environ, DOCKER_CLI_HINTS="false", DOCKER_BUILDKIT="1"),
        )
        click.echo(f"Result: {res}")

    def cli(
        self,
        *args: Any,
        write_summary: bool = True,
        copy_to_landscape: bool = False,
        hooks: list[Callable[[Configuration, MappingPack], None]] | None = None,
    ) -> None:
        """Get and run a command line interface for this configuration."""
        self.get_cli(copy_to_landscape=copy_to_landscape, write_summary=write_summary)(*args)

    def get_cli(
        self,
        *,
        write_summary: bool = True,
        copy_to_landscape: bool = False,
        hooks: list[Callable[[Configuration, MappingPack], None]] | None = None,
    ) -> click.Command:
        """Get a command line interface for this configuration."""
        import click
        from more_click import verbose_option

        @click.command()
        @click.option(
            "--upload",
            is_flag=True,
            help=f"If true, uploads to {self.zenodo_url()}"
            if self.zenodo_record
            else "Is disregaded, because this configuration does not specify a `zenodo_record`",
        )
        @REFRESH_SOURCE_OPTION
        @REFRESH_RAW_OPTION
        @REFRESH_PROCESSED_OPTION
        @BUILD_DOCKER_OPTION
        @verbose_option
        def main(
            upload: bool,
            refresh_source: bool,
            refresh_raw: bool,
            refresh_processed: bool,
            build_docker: bool,
        ) -> None:
            """Build the mapping database terms."""
            start = time.time()
            with logging_redirect_tqdm():
                pack = self.get_mappings(
                    refresh_source=refresh_source,
                    refresh_raw=refresh_raw,
                    refresh_processed=refresh_processed,
                    return_type=AssembleReturnType.all,
                )
            timedelta = time.time() - start
            if build_docker and self.processed_neo4j_path:
                self._build_docker()

            if write_summary:
                from . import summarize

                click.secho("summarizing mappings", fg="green")
                start = time.time()
                summarize.write_summary(
                    self,
                    show_progress=True,
                    copy_to_landscape=copy_to_landscape,
                    raw_mappings=pack.raw,
                    processed_mappings=pack.processed,
                    priority_mappings=pack.priority,
                    refresh_raw_timedelta=timedelta if refresh_raw and not refresh_source else None,
                    refresh_source_timedelta=timedelta if refresh_source else None,
                )
                click.secho(
                    f"done summarizing mappings in {humanize.naturaldelta(time.time() - start)}",
                    fg="green",
                )

            for hook in hooks or []:
                hook(self, pack)

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


class MappingPack(NamedTuple):
    """A tuple of raw, processed, and priority mappings."""

    raw: list[Mapping]
    processed: list[Mapping]
    priority: list[Mapping]


# docstr-coverage: inherited
@overload
def assemble(
    configuration: Configuration,
    *,
    refresh_source: bool = ...,
    refresh_raw: bool = ...,
    refresh_processed: bool = ...,
    return_type: Literal[AssembleReturnType.none] = AssembleReturnType.none,
) -> None: ...


# docstr-coverage: inherited
@overload
def assemble(
    configuration: Configuration,
    *,
    refresh_source: bool = ...,
    refresh_raw: bool = ...,
    refresh_processed: bool = ...,
    return_type: Literal[AssembleReturnType.all] = AssembleReturnType.all,
) -> MappingPack: ...


# docstr-coverage: inherited
@overload
def assemble(
    configuration: Configuration,
    *,
    refresh_source: bool = ...,
    refresh_raw: bool = ...,
    refresh_processed: bool = ...,
    return_type: Literal[AssembleReturnType.priority] = AssembleReturnType.priority,
) -> list[Mapping]: ...


def assemble(
    configuration: Configuration,
    *,
    refresh_source: bool = False,
    refresh_raw: bool = False,
    refresh_processed: bool = False,
    return_type: AssembleReturnType = AssembleReturnType.none,
    progress: bool = True,
) -> None | list[Mapping] | MappingPack:
    """Get prioritized mappings based on an assembly configuration.

    :param configuration: The mapping assembly configuration
    :param refresh_processed: This the least aggressive option, where raw mappings are
        re-used if available and only re-processing and re-prioritization is done.
    :param refresh_raw: This is the medium aggressive option, where raw mappings are
        re-generaged by processing the source data.
    :param refresh_source: This is the most aggressive option, where the data sources
        are re-downloaded (and the other options ``refresh_processed`` and
        ``refresh_raw`` are automatically switched to true)
    :param return_type: What artifacts should be returned? This is controlled with the
        values in the :class:`GetMappingReturnType` enumeration.

        - :data:`GetMappingReturnType.none` returns nothing
        - :data:`GetMappingReturnType.priority` returns the priority mapping set
        - :data:`GetMappingReturnType.all` returns a data structure containing the raw
          mappings, processed mappings, and priority mappings as three seperate lists.
    :param progress: Should progress bars be shown during processing? Defaults to true.

    :returns: Returns based on the ``return_type``. By default, returns ``None``
    """
    if refresh_source:
        refresh_raw = True
    if refresh_raw:
        refresh_processed = True

    def _echo(s: str, *args: Any, **kwargs: Any) -> None:
        click.echo(f"[{configuration.key}] " + click.style(s, *args, **kwargs))

    if configuration.has_priority_path() and not refresh_raw and not refresh_processed:
        match return_type:
            case AssembleReturnType.none:
                return None
            case AssembleReturnType.all:
                if not configuration.has_raw_path():
                    raise FileNotFoundError
                if not configuration.has_processed_path():
                    raise FileNotFoundError
                return MappingPack(
                    raw=configuration.read_raw_mappings(show_progress=progress),
                    processed=configuration.read_processed_mappings(show_progress=progress),
                    priority=configuration.read_priority_mappings(show_progress=progress),
                )
            case AssembleReturnType.priority:
                return configuration.read_priority_mappings()

    if configuration.has_processed_path() and not refresh_raw and not refresh_processed:
        processed_mappings = configuration.read_processed_mappings()
    else:
        if configuration.has_raw_path() and not refresh_raw:
            start = time.time()
            raw_mappings = configuration.read_raw_mappings()
            logger.info(
                "loaded cached raw mappings from %s in %s",
                configuration.raw_pickle_path,
                humanize.naturaldelta(time.time() - start),
            )
        else:
            configuration.configuration_path.write_text(
                configuration.model_dump_json(exclude_none=True, exclude_unset=True, indent=2)
            )
            raw_mappings = get_raw_mappings(
                configuration, refresh_source=refresh_source, progress=progress
            )
            if not raw_mappings:
                raise ValueError(f"no raw mappings found for configuration: {configuration.name}")
            if configuration.validate_raw:
                validate_mappings(raw_mappings, progress=progress)

            # TODO stream?
            write_sssom(
                raw_mappings,
                configuration.raw_sssom_path,
                # add_labels=configuration.add_labels
                metadata=_mapping_set_from_conf(
                    configuration,
                    subtitle="Raw Mappings",
                    path=configuration.raw_sssom_path,
                ),
            )
            write_jsonl(
                raw_mappings,
                configuration.raw_jsonl_path,
                show_progress=progress,
            )
            if configuration.write_raw_neo4j:
                write_neo4j(
                    raw_mappings,
                    configuration.raw_neo4j_path,
                    docker_name=configuration.raw_neo4j_name,
                    add_labels=False,  # configuration.add_labels,
                    compress=configuration.neo4j_gzip,
                    use_tqdm=progress,
                )

        # click.echo(semra.api.str_source_target_counts(mappings, minimum=20))
        processed_mappings = process_raw_mappings(
            raw_mappings,
            mutations=configuration.mutations,
            remove_prefix_set=configuration.remove_prefixes,
            keep_prefix_set=configuration.keep_prefixes,
            post_remove_prefixes=configuration.post_remove_prefixes,
            post_keep_prefixes=configuration.post_keep_prefixes,
            remove_imprecise=configuration.remove_imprecise,
            subsets=configuration.get_hydrated_subsets(),
            progress=progress,
        )
        _echo("done processing raw mappings", fg="green")

    _echo("prioritizing mappings", fg="green")
    start = time.time()
    prioritized_mappings = prioritize(processed_mappings, configuration.priority, progress=progress)
    _echo(
        f"done prioritizing mappings in {humanize.naturaldelta(time.time() - start)}",
        fg="green",
    )

    _echo("calculating equivalence classes", fg="green")
    start = time.time()
    equivalence_classes = _get_equivalence_classes(processed_mappings, prioritized_mappings)
    _echo(
        f"done calculating equivalences classes in {humanize.naturaldelta(time.time() - start)}",
        fg="green",
    )

    _echo("writing SSSOM (processed mappings)", fg="green")
    start = time.time()
    write_sssom(
        processed_mappings,
        configuration.processed_sssom_path,
        add_labels=configuration.add_labels,
        metadata=_mapping_set_from_conf(
            configuration,
            subtitle="Processed Mappings",
            path=configuration.processed_sssom_path,
        ),
    )
    _echo(f"done writing SSSOM in {humanize.naturaldelta(time.time() - start)}", fg="green")

    _echo("writing JSONL (processed mappings)", fg="green")
    start = time.time()
    write_jsonl(
        processed_mappings,
        configuration.processed_jsonl_path,
        show_progress=progress,
    )
    _echo(f"done writing JSONL in {humanize.naturaldelta(time.time() - start)}", fg="green")

    _echo("writing Neo4j (processed mappings)", fg="green")
    start = time.time()
    write_neo4j(
        processed_mappings,
        configuration.processed_neo4j_path,
        docker_name=configuration.processed_neo4j_name,
        equivalence_classes=equivalence_classes,
        add_labels=configuration.add_labels,
        compress=configuration.neo4j_gzip,
        use_tqdm=progress,
    )
    _echo(f"done writing Neo4j in {humanize.naturaldelta(time.time() - start)}", fg="green")

    _echo("writing JSONL (prioritized mappings)", fg="green")
    start = time.time()
    write_jsonl(prioritized_mappings, configuration.priority_jsonl_path, show_progress=progress)
    _echo(
        f"done writing JSONL (prioritized mappings) in {humanize.naturaldelta(time.time() - start)}",
        fg="green",
    )

    _echo("writing SSSOM (prioritized mappings)", fg="green")
    start = time.time()
    write_sssom(
        prioritized_mappings,
        configuration.priority_sssom_path,
        add_labels=configuration.add_labels,
        metadata=_mapping_set_from_conf(
            configuration,
            subtitle="Priority Mappings",
            path=configuration.priority_sssom_path,
        ),
    )
    _echo(
        f"done writing SSSOM (prioritized mappings) in {humanize.naturaldelta(time.time() - start)}",
        fg="green",
    )

    match return_type:
        case AssembleReturnType.none:
            return None
        case AssembleReturnType.all:
            if not configuration.has_raw_path():
                raise FileNotFoundError
            if not configuration.has_processed_path():
                raise FileNotFoundError
            return MappingPack(
                raw=raw_mappings,
                processed=processed_mappings,
                priority=prioritized_mappings,
            )
        case AssembleReturnType.priority:
            return prioritized_mappings


def _mapping_set_from_conf(
    configuration: Configuration, *, path: Path, subtitle: str
) -> sssom_pydantic.MappingSet:
    sources: list[str] = []
    for input in configuration.inputs:
        match input.source:
            case "pyobo" if input.prefix is not None:
                resource = bioregistry.get_resource(input.prefix, strict=True)
                if download := resource.get_download():
                    sources.append(download)
            # FIXME need to be exhaustive
    return sssom_pydantic.MappingSet(
        id=f"{configuration.purl_base}{configuration.key}/{path.name}",
        title=f"{configuration.name} - {subtitle}",
        comment="Produced by SeMRA",
        publication_date=datetime.date.today(),
        creators=configuration.creators,
        sources=sources,
    )


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
    *,
    progress: bool = True,
    refresh_source: bool = False,
) -> list[Mapping]:
    """Get raw mappings based on the inputs in a configuration."""
    n_inputs = len(configuration.inputs)

    def _write(zz: int, txt: str, fg: str = "green") -> None:
        tqdm.write(f"[{configuration.key}] {zz}/{n_inputs} " + click.style(txt, fg=fg))

    rv = []
    for i, inp in enumerate(
        tqdm(
            configuration.inputs,
            desc=f"[{configuration.key}] getting raw mappings",
            unit="source",
            disable=not progress,
        ),
        start=1,
    ):
        _write(
            i, f"Loading mappings from {inp.source}" + (f" ({inp.prefix})" if inp.prefix else "")
        )
        start = time.time()
        mappings = inp.load(refresh_source=refresh_source)
        if mappings is None:
            _write(i, f"incorrect configuration for {inp.source}", fg="red")
            continue
        if inp.pre_filter_prefixes:
            mappings = list(keep_prefixes_both(mappings, configuration.priority))
        _write(
            i,
            f"Loaded {len(mappings):,} mappings from {inp.source} in {humanize.naturaldelta(time.time() - start)}"
            + (f" ({inp.prefix})" if inp.prefix else ""),
        )
        rv.extend(mappings)
    return rv


def process_raw_mappings(
    mappings: list[Mapping],
    upgrade_prefixes: t.Collection[str] | None = None,
    mutations: t.Collection[Mutation] | None = None,
    remove_prefix_set: t.Collection[str] | None = None,
    keep_prefix_set: t.Collection[str] | None = None,
    post_remove_prefixes: t.Collection[str] | None = None,
    post_keep_prefixes: t.Collection[str] | None = None,
    subsets: SubsetConfiguration | None = None,
    *,
    remove_imprecise: bool = True,
    progress: bool = True,
) -> list[Mapping]:
    """Run a full deduplication, reasoning, and inference pipeline over a set of mappings."""
    if keep_prefix_set:
        mappings = keep_prefixes(mappings, keep_prefix_set, progress=progress)

    if remove_prefix_set:
        mappings = filter_prefixes(mappings, remove_prefix_set, progress=progress)

    if subsets:
        mappings = list(filter_subsets(mappings, subsets))

    start = time.time()
    negatives = from_sssom_pydantic(get_biomappings_negative_mappings())
    logger.info(
        f"Loaded {len(negatives):,} negative mappings in %s",
        humanize.naturaldelta(time.time() - start),
    )

    before = len(mappings)
    start = time.time()
    mappings = filter_mappings(mappings, negatives, progress=progress)
    _log_diff(before, mappings, verb="Filtered negative mappings", elapsed=time.time() - start)

    # deduplicate
    before = len(mappings)
    start = time.time()
    mappings = assemble_evidences(mappings, progress=progress)
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

    if mutations:
        logger.info("Applying mutations")
        before = len(mappings)
        start = time.time()
        mappings = list(apply_mutations(mappings, mutations, progress=progress))
        _log_diff(before, mappings, verb="Applied mutations", elapsed=time.time() - start)

    if upgrade_prefixes and len(upgrade_prefixes) > 1:
        logger.info("Inferring mapping upgrades")
        # 2. using the assumption that primary mappings from each of these
        # resources to each other are exact matches, rewrite the prefixes
        before = len(mappings)
        start = time.time()
        mappings = infer_mutual_dbxref_mutations(
            mappings, upgrade_prefixes, confidence=0.95, progress=progress
        )
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
    mappings = infer_reversible(mappings, progress=progress)
    _log_diff(before, mappings, verb="Inferred", elapsed=time.time() - start)

    logger.info("Inferring based on chains")
    before = len(mappings)
    time.time()
    mappings = infer_chains(mappings, progress=progress)
    _log_diff(before, mappings, verb="Inferred", elapsed=time.time() - start)

    # 4/5. Filtering negative
    logger.info("Filtering out negative mappings")
    before = len(mappings)
    start = time.time()
    mappings = filter_mappings(mappings, negatives, progress=progress)
    _log_diff(before, mappings, verb="Filtered negative mappings", elapsed=time.time() - start)

    # filter out self mappings again, just in case
    mappings = filter_self_matches(mappings, progress=progress)

    if post_keep_prefixes:
        mappings = keep_prefixes(mappings, post_keep_prefixes, progress=progress)

    if post_remove_prefixes:
        mappings = filter_prefixes(mappings, post_remove_prefixes, progress=progress)

    return mappings


def _log_diff(before: int, mappings: list[Mapping], *, verb: str, elapsed: float) -> None:
    logger.info(
        f"{verb} from {before:,} to {len(mappings):,} mappings "
        f"(Δ={len(mappings) - before:,}) in s.",
        humanize.naturaldelta(elapsed),
    )
