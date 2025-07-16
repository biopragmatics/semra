"""
The SeMRA Raw Semantic Mappings Database contains unprocessed semantic mappings
assembled from hundreds of ontologies and databases through :mod:`pyobo`.

Reproduction
************

The SeMRA Raw Semantic Mappings Database can be rebuilt with the following commands:

.. code-block:: console

    $ uv pip install semra
    $ semra build

The ``semra build`` command downloads and process all resource and constructs
a database of unprocessed mappings.

.. note::

    Downloading raw data resources can take on the order of hours to tens
    of hours depending on your internet connection and the reliability of
    the resources' respective servers.

    Processing and analysis can be run overnight on commodity hardware
    (e.g., a 2023 MacBook Pro with 36GB RAM).

Web Application
***************

The SeMRA Raw Semantic Mappings Database can be downloaded from Zenodo at |raw|.
After downloading all files and unzipping then, a web application wrapping
the SeMRA Raw Semantic Mappings Database run locally on Docker with:

.. code-block:: console

    $ sh run_on_docker.sh

Navigate to http://localhost:8773 to see the web application.

.. |raw| image:: https://zenodo.org/badge/DOI/10.5281/zenodo.11082038.svg
  :target: https://doi.org/10.5281/zenodo.11082038

"""  # noqa: D205

import os
import subprocess
import time
from collections.abc import Iterable
from operator import attrgetter
from pathlib import Path
from typing import Any, Literal, overload

import bioontologies.robot
import bioregistry
import bioversions
import click
import pyobo
import pystow
import requests
from bioontologies.obograph import write_warned
from bioontologies.robot import write_getter_warnings
from pydantic import BaseModel
from pyobo.getters import NoBuildError
from tabulate import tabulate
from tqdm.auto import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from zenodo_client import update_zenodo

from semra import Mapping
from semra.io import from_jsonl, from_pyobo, write_jsonl, write_neo4j, write_sssom
from semra.io.io_utils import safe_open_writer
from semra.pipeline import REFRESH_RAW_OPTION, REFRESH_SOURCE_OPTION
from semra.sources import SOURCE_RESOLVER
from semra.sources.wikidata import get_wikidata_mappings_by_prefix
from semra.utils import get_jinja_template, gzip_path

__all__ = [
    "build",
]

MODULE = pystow.module("semra", "database")
SOURCES = MODULE.module("sources")
LOGS = MODULE.module("logs")
SSSOM_PATH = MODULE.join(name="mappings.sssom.tsv")
JSONL_PATH = MODULE.join(name="mappings.jsonl")
STATS_PATH = MODULE.join(name="statistics.json")
README_PATH = MODULE.join(name="README.md")
BIOONTOLOGIES_WARNINGS_PATH = LOGS.join(name="warnings.tsv")
BIOONTOLOGIES_ERRORS_PATH = LOGS.join(name="errors.tsv")
SUMMARY_PATH = LOGS.join(name="summary.tsv")
EMPTY_PATH = LOGS.join(name="empty.txt")
NEO4J_DIR = MODULE.join("neo4j")


class SourceSummary(BaseModel):
    """A summary row."""

    resource_name: str
    mapping_count: int
    time: float
    label: str

    def _as_row(self) -> tuple[Any, ...]:
        return (self.resource_name, self.mapping_count, round(self.time, 2), self.label)


#: A list of prefixes that did not produce any semantic mappings
EMPTY: list[str] = []

skip = {
    "ado",  # trash
    "epio",  # trash
    "pr",  # too big
    "ncbitaxon",  # too big
    "ncbigene",  # too big
    # duplicates of EDAM
    "edam.data",
    "edam.format",
    "edam.operation",
    "edam.topic",
    "gwascentral.phenotype",  # added on 2024-04-24, service down
    "gwascentral.study",  # added on 2024-04-24, service down
    "conso",
    "atol",  # broken download
    "eol",  # broken download
    "addicto",  # TODO
}
skip_prefixes = {
    "kegg",
    "pubchem",
    "snomedct",
}
skip_wikidata_prefixes = {
    "pubmed",  # too big! need paging?
    "doi",  # too big! need paging?
    "inchi",  # too many funny characters
    "smiles",  # too many funny characters
}
skip_pyobo = {
    "antibodyregistry": "waiting on update from klas",
    "drugbank": "no longer free to access",
    "drugbank.salt": "no longer free to access",
    "icd10": "no mappings in here",
}


class Statistics(BaseModel):
    """Statistics for the SeMRA Raw Semantic Mappings Database build."""

    no_refresh_timedelta: float | None = None
    refresh_raw_timedelta: float | None = None
    refresh_source_timedelta: float | None = None
    summaries: list[SourceSummary]

    def tabulate_summaries(self) -> str:
        """Tabulate summaries."""
        return tabulate(
            [summary._as_row() for summary in self.summaries if summary.mapping_count],
            tablefmt="github",
            headers=["Source", "Mapping Count", "Time", "Resource Type"],
        )


@click.command()
@click.option(
    "--include-wikidata/--no-include-wikidata", is_flag=True, show_default=True, default=True
)
@click.option(
    "--write-labels",
    is_flag=True,
    help="If set to true, writes subject and object labels in the SSSOM file.",
)
@click.option(
    "--prune-sssom",
    is_flag=True,
    help="If true, will try and prune unused SSSOM columns during output. Note that this significantly increases memory requirement during construction, but results in a smaller database file.",
)
@click.option(
    "--upload",
    is_flag=True,
    help="If set to true, upload the generated artifacts to the SeMRA Raw Semantic Mappings Database record on Zenodo (https://doi.org/10.5281/zenodo.11082038)",
)
@REFRESH_SOURCE_OPTION
@REFRESH_RAW_OPTION
@click.option("--test", is_flag=True, help="Run in test mode on a subset of resources.")
@click.option("--skip-below")
def build(
    include_wikidata: bool,
    upload: bool,
    refresh_source: bool,
    refresh_raw: bool,
    write_labels: bool,
    prune_sssom: bool,
    test: bool,
    skip_below: str | None,
) -> None:
    """Construct the SeMRA Raw Semantic Mappings Database."""
    start = time.time()
    if not test:
        click.echo("caching versions w/ Bioversions")
        list(bioversions.iter_versions(use_tqdm=True))

    ontology_resources: list[bioregistry.Resource] = []
    pyobo_resources: list[bioregistry.Resource] = []
    for resource in bioregistry.resources():
        if (
            resource.is_deprecated()
            or resource.prefix in skip
            or resource.no_own_terms
            or resource.proprietary
        ):
            continue
        if skip_below and resource.prefix < skip_below:
            continue
        if any(resource.prefix.startswith(p) for p in skip_prefixes):
            continue
        if pyobo.has_nomenclature_plugin(resource.prefix):
            pyobo_resources.append(resource)
        elif resource.get_obofoundry_prefix() or resource.has_download():
            ontology_resources.append(resource)

    summaries: list[SourceSummary] = []
    if test:
        mappings = _yield_ontology_resources(
            [bioregistry.get_resource(p, strict=True) for p in ("taxrank", "go")],
            refresh_source=refresh_source,
            refresh_raw=refresh_raw,
            write_labels=write_labels,
            summaries=summaries,
        )
    else:
        mappings = _yield_mappings(
            ontology_resources,
            pyobo_resources,
            refresh_source=refresh_source,
            refresh_raw=refresh_raw,
            write_labels=write_labels,
            include_wikidata=include_wikidata,
            summaries=summaries,
        )
    mappings = write_jsonl(mappings, JSONL_PATH, stream=True)
    mappings = write_sssom(mappings, SSSOM_PATH, add_labels=False, prune=False, stream=True)
    # neo4j doesn't need to stream since it's last. to avoid SIGKILLs,
    # write the file to disk, then compress after.
    write_neo4j(mappings, NEO4J_DIR, compress="after")

    # gzip these after the fact to avoid SIGKILLs
    jsonl_gz_path = gzip_path(JSONL_PATH)
    sssom_gz_path = gzip_path(SSSOM_PATH)

    timedelta = time.time() - start
    statistics = Statistics(
        no_refresh_timedelta=timedelta if not refresh_raw and not refresh_source else None,
        refresh_raw_timedelta=timedelta if refresh_raw and not refresh_source else None,
        refresh_source_timedelta=timedelta if refresh_source else None,
        summaries=summaries,
    )
    STATS_PATH.write_text(statistics.model_dump_json(indent=2))

    # Write out a README file
    template = get_jinja_template("raw-database-readme.md")
    README_PATH.write_text(template.render(statistics=statistics))
    os.system(f'npx --yes prettier --write --prose-wrap always "{README_PATH}"')  # noqa:S605

    if upload:
        res = update_zenodo(
            deposition_id="11082038",
            paths=[
                jsonl_gz_path,
                sssom_gz_path,
                README_PATH,
                STATS_PATH,
                *NEO4J_DIR.iterdir(),
            ],
        )
        click.echo(res.json()["links"]["html"])


def _yield_mappings(
    ontology_resources: list[bioregistry.Resource],
    pyobo_resources: list[bioregistry.Resource],
    *,
    refresh_source: bool,
    refresh_raw: bool,
    write_labels: bool,
    include_wikidata: bool,
    summaries: list[SourceSummary],
) -> Iterable[Mapping]:
    yield from _yield_ontology_resources(
        ontology_resources,
        refresh_source=refresh_source,
        refresh_raw=refresh_raw,
        write_labels=write_labels,
        summaries=summaries,
    )
    yield from _yield_pyobo(
        pyobo_resources,
        refresh_source=refresh_source,
        refresh_raw=refresh_raw,
        write_labels=write_labels,
        summaries=summaries,
    )
    yield from _yield_custom(
        write_labels=write_labels,
        summaries=summaries,
    )
    if include_wikidata:
        yield from _yield_wikidata(write_labels=write_labels, summaries=summaries)


def _yield_custom(*, write_labels: bool, summaries: list[SourceSummary]) -> Iterable[Mapping]:
    click.secho("\nCustom SeMRA Sources", fg="cyan", bold=True)
    funcs = tqdm(
        sorted(SOURCE_RESOLVER, key=lambda f: f.__name__), unit="source", desc="Custom sources"
    )
    for func in funcs:
        resource_name = func.__name__.removeprefix("get_").removesuffix("_mappings")
        if resource_name == "wikidata":
            # this one needs extra informatzi
            continue

        tqdm.write(click.style("\n" + resource_name, fg="green"))
        funcs.set_postfix(source=resource_name)

        start = time.time()
        count = 0
        if (jsonl_path := _get_jsonl_path("custom", resource_name)).is_file():
            for mapping in from_jsonl(jsonl_path, stream=True):
                count += 1
                yield mapping
        else:
            with logging_redirect_tqdm():
                resource_mappings = func()
                for mapping in _write_source(
                    resource_mappings,
                    "custom",
                    resource_name,
                    write_labels=write_labels,
                    stream=True,
                ):
                    count += 1
                    yield mapping

                # try to reclaim memory
                del resource_mappings

        summaries.append(
            SourceSummary(
                resource_name=resource_name,
                mapping_count=count,
                time=time.time() - start,
                label="custom",
            )
        )
        _write_summary(summaries)


def _yield_pyobo(
    pyobo_resources: list[bioregistry.Resource],
    *,
    refresh_source: bool,
    refresh_raw: bool,
    write_labels: bool,
    summaries: list[SourceSummary],
) -> Iterable[Mapping]:
    click.secho("PyOBO Sources", fg="cyan", bold=True)
    it = tqdm(pyobo_resources, unit="prefix", desc="PyOBO sources")
    for resource in it:
        if resource.prefix in skip_pyobo:
            continue

        tqdm.write(click.style("\n" + resource.prefix, fg="green"))
        it.set_postfix(prefix=resource.prefix)

        start = time.time()
        count = 0
        if (jsonl_path := _get_jsonl_path("pyobo", resource.prefix)).is_file() and not refresh_raw:
            for mapping in from_jsonl(jsonl_path, stream=True):
                count += 1
                yield mapping
        else:
            try:
                with logging_redirect_tqdm():
                    resource_mappings = from_pyobo(
                        resource.prefix, force_process=refresh_source, cache=False
                    )
            except Exception as e:
                tqdm.write(f"[{resource.prefix}] failed PyOBO parsing: ({type(e)}) {e}")
                continue
            else:
                for mapping in _write_source(
                    resource_mappings,
                    "pyobo",
                    resource.prefix,
                    write_labels=write_labels,
                    stream=True,
                ):
                    count += 1
                    yield mapping

                # try to reclaim memory
                del resource_mappings

        summaries.append(
            SourceSummary(
                resource_name=resource.prefix,
                mapping_count=count,
                time=time.time() - start,
                label="pyobo",
            )
        )
        _write_summary(summaries)


def _yield_wikidata(*, write_labels: bool, summaries: list[SourceSummary]) -> Iterable[Mapping]:
    click.secho("\nWikidata Sources", fg="cyan", bold=True)
    wikidata_prefix_it = tqdm(
        bioregistry.get_registry_map("wikidata").items(), unit="property", desc="Wikidata"
    )
    for prefix, wikidata_property in wikidata_prefix_it:
        if prefix in skip_wikidata_prefixes:
            continue

        wikidata_prefix_it.set_postfix(prefix=prefix)
        tqdm.write(click.style(f"\n{prefix} ({wikidata_property})", fg="green"))
        resource_name = f"wikidata_{prefix}"

        start = time.time()
        count = 0
        if (jsonl_path := _get_jsonl_path("wikidata", resource_name)).is_file():
            for mapping in from_jsonl(jsonl_path, stream=True):
                count += 1
                yield mapping
        else:
            try:
                resource_mappings = get_wikidata_mappings_by_prefix(prefix)
            except requests.exceptions.JSONDecodeError as e:
                tqdm.write(
                    f"[{resource_name}] failed to get mappings from wikidata: ({type(e)}) {e}"
                )
                continue
            else:
                for mapping in _write_source(
                    resource_mappings, "wikidata", resource_name, write_labels=write_labels
                ):
                    count += 1
                    yield mapping
                # try to reclaim memory
                del resource_mappings

        summaries.append(
            SourceSummary(
                resource_name=resource_name,
                mapping_count=count,
                time=time.time() - start,
                label="wikidata",
            )
        )
        _write_summary(summaries)


def _yield_ontology_resources(
    resources: list[bioregistry.Resource],
    *,
    refresh_source: bool,
    refresh_raw: bool,
    write_labels: bool,
    summaries: list[SourceSummary],
) -> Iterable[Mapping]:
    click.secho("\nOntology Sources", fg="cyan", bold=True)
    it = tqdm(
        sorted(resources, key=attrgetter("prefix")),
        unit="ontology",
        desc="Ontology sources",
    )
    for resource in it:
        it.set_postfix(prefix=resource.prefix)
        tqdm.write(click.style("\n" + resource.prefix, fg="green"))

        start = time.time()
        count = 0
        if (
            jsonl_path := _get_jsonl_path("ontology", resource.prefix)
        ).is_file() and not refresh_raw:
            for mapping in from_jsonl(jsonl_path, stream=True):
                count += 1
                yield mapping
        else:
            try:
                with logging_redirect_tqdm():
                    resource_mappings = from_pyobo(
                        resource.prefix, force_process=refresh_source, cache=False
                    )
            except (
                ValueError,
                NoBuildError,
                subprocess.SubprocessError,
                bioontologies.robot.ROBOTError,
            ) as e:
                tqdm.write(
                    click.style(
                        f"[{resource.prefix}] failed ontology parsing: ({type(e)}) {e}", fg="red"
                    )
                )
                continue
            else:
                for mapping in _write_source(
                    resource_mappings,
                    "ontology",
                    resource.prefix,
                    write_labels=write_labels,
                    stream=True,
                ):
                    count += 1
                    yield mapping

                # try to reclaim memory
                del resource_mappings
            # this outputs on each iteration to get faster insight
            write_warned(BIOONTOLOGIES_WARNINGS_PATH)
            write_getter_warnings(BIOONTOLOGIES_ERRORS_PATH)

        summaries.append(
            SourceSummary(
                resource_name=resource.prefix,
                mapping_count=count,
                time=time.time() - start,
                label="ontology",
            )
        )
        _write_summary(summaries)


@overload
def _write_source(
    mappings: list[Mapping],
    subdirectory: str,
    key: str,
    write_labels: bool,
    stream: Literal[True] = True,
) -> Iterable[Mapping]: ...


@overload
def _write_source(
    mappings: list[Mapping],
    subdirectory: str,
    key: str,
    write_labels: bool,
    stream: Literal[False] = False,
) -> None: ...


def _write_source(
    mappings: Iterable[Mapping],
    subdirectory: str,
    key: str,
    write_labels: bool,
    stream: bool = False,
) -> None | Iterable[Mapping]:
    jsonl_path = _get_jsonl_path(subdirectory, key)
    sssom_path = _get_sssom_path(subdirectory, key)
    if stream:
        mappings = write_jsonl(mappings, jsonl_path, stream=True)
        mappings = write_sssom(
            mappings, sssom_path, add_labels=write_labels, prune=False, stream=True
        )
        count = 0
        for mapping in mappings:
            yield mapping
            count += 1
    else:
        mappings = list(mappings)
        write_jsonl(mappings, jsonl_path, stream=False)
        write_sssom(mappings, sssom_path, add_labels=write_labels, prune=False, stream=False)
        count = len(mappings)

    if count:
        tqdm.write(f"produced {count:,} mappings")
    else:
        tqdm.write("produced no mappings")
        SOURCES.join(subdirectory, name=f"{key}.empty.txt").write_text("")
        EMPTY.append(key)
        EMPTY_PATH.write_text("\n".join(EMPTY))

    return None


def _get_sssom_path(subdirectory: str, key: str) -> Path:
    return SOURCES.join(subdirectory, name=f"{key}.sssom.tsv.gz")


def _get_jsonl_path(subdirectory: str, key: str) -> Path:
    return SOURCES.join(subdirectory, name=f"{key}.jsonl.gz")


def _write_summary(summaries: list[SourceSummary]) -> None:
    with safe_open_writer(SUMMARY_PATH) as writer:
        writer.writerow(("prefix", "mappings", "seconds", "source_type"))
        for summary in summaries:
            writer.writerow(summary._as_row())


if __name__ == "__main__":
    build()
