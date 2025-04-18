"""Assemble a database."""

import csv
import subprocess
import time
from operator import attrgetter
from pathlib import Path

import bioregistry
import click
import pyobo
import pystow
import requests
from bioontologies.obograph import write_warned
from bioontologies.robot import write_getter_warnings
from curies.vocabulary import charlie
from pyobo.getters import NoBuildError
from tqdm.auto import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from zenodo_client import Creator, Metadata, ensure_zenodo

from semra import Mapping
from semra.io import (
    from_pickle,
    from_pyobo,
    write_neo4j,
    write_pickle,
    write_sssom,
)
from semra.pipeline import REFRESH_SOURCE_OPTION, UPLOAD_OPTION
from semra.sources import SOURCE_RESOLVER
from semra.sources.wikidata import get_wikidata_mappings_by_prefix

MODULE = pystow.module("semra", "database")
SOURCES = MODULE.module("sources")
LOGS = MODULE.module("logs")
SSSOM_PATH = MODULE.join(name="mappings.sssom.tsv.gz")
PICKLE_PATH = MODULE.join(name="mappings.pkl.gz")
WARNINGS_PATH = LOGS.join(name="warnings.tsv")
ERRORS_PATH = LOGS.join(name="errors.tsv")
SUMMARY_PATH = LOGS.join(name="summary.tsv")
EMPTY_PATH = LOGS.join(name="empty.txt")
NEO4J_DIR = MODULE.join("neo4j")

EMPTY = []
summaries = []

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
}
skip_prefixes = {
    "kegg",
    "pubchem",
}
skip_wikidata_prefixes = {
    "pubmed",  # too big! need paging?
    "doi",  # too big! need paging?
    "inchi",  # too many funny characters
    "smiles",  # too many funny characters
}


@click.command()
@click.option(
    "--include-wikidata/--no-include-wikidata", is_flag=True, show_default=True, default=True
)
@click.option("--write-labels", is_flag=True)
@UPLOAD_OPTION
@REFRESH_SOURCE_OPTION
def build(include_wikidata: bool, upload: bool, refresh_source: bool, write_labels: bool) -> None:
    """Construct the full SeMRA database."""
    ontology_resources = []
    pyobo_resources = []
    for resource in bioregistry.resources():
        if (
            resource.is_deprecated()
            or resource.prefix in skip
            or resource.no_own_terms
            or resource.proprietary
        ):
            continue
        if any(resource.prefix.startswith(p) for p in skip_prefixes):
            continue
        if pyobo.has_nomenclature_plugin(resource.prefix):
            pyobo_resources.append(resource)
        elif resource.get_obofoundry_prefix() or resource.has_download():
            ontology_resources.append(resource)

    mappings = []

    click.secho("PyOBO Sources", fg="cyan", bold=True)
    it = tqdm(pyobo_resources, unit="prefix", desc="PyOBO sources")
    for resource in it:
        tqdm.write(click.style("\n" + resource.prefix, fg="green"))
        it.set_postfix(prefix=resource.prefix)
        pickle_gz_path = _get_pickle_path("pyobo", resource.prefix)
        start = time.time()
        if pickle_gz_path.is_file():
            resource_mappings = from_pickle(pickle_gz_path)
            tqdm.write(f"loaded {len(resource_mappings):,} from cache at {pickle_gz_path}")
        else:
            try:
                with logging_redirect_tqdm():
                    resource_mappings = from_pyobo(
                        resource.prefix, force_process=refresh_source, cache=False
                    )
            except Exception as e:
                tqdm.write(f"failed PyOBO parsing on {resource.prefix}: {e}")
                continue
            _write_source(resource_mappings, "pyobo", resource.prefix, write_labels=write_labels)

        mappings.extend(resource_mappings)
        summaries.append((resource.prefix, len(resource_mappings), time.time() - start, "pyobo"))
        _write_summary()

    click.secho("\nCustom SeMRA Sources", fg="cyan", bold=True)
    funcs = tqdm(
        sorted(SOURCE_RESOLVER, key=lambda f: f.__name__), unit="source", desc="Custom sources"
    )
    for func in funcs:
        resource_name = func.__name__.removeprefix("get_").removesuffix("_mappings")
        if resource_name == "wikidata":
            # this one needs extra informatzi
            continue
        pickle_gz_path = _get_pickle_path("custom", resource_name)
        start = time.time()
        if pickle_gz_path.is_file():
            resource_mappings = from_pickle(pickle_gz_path)
            tqdm.write(f"loaded {len(resource_mappings):,} from cache at {pickle_gz_path}")
        else:
            tqdm.write(click.style("\n" + resource_name, fg="green"))
            funcs.set_postfix(source=resource_name)
            with logging_redirect_tqdm():
                resource_mappings = func()
                _write_source(resource_mappings, "custom", resource_name, write_labels=write_labels)

        mappings.extend(resource_mappings)
        summaries.append((resource_name, len(resource_mappings), time.time() - start, "custom"))
        _write_summary()

    if include_wikidata:
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
            pickle_gz_path = _get_pickle_path("wikidata", resource_name)
            start = time.time()
            if pickle_gz_path.is_file():
                resource_mappings = from_pickle(pickle_gz_path)
                tqdm.write(f"loaded {len(resource_mappings):,} from cache at {pickle_gz_path}")
            else:
                try:
                    resource_mappings = get_wikidata_mappings_by_prefix(prefix)
                except requests.exceptions.JSONDecodeError as e:
                    tqdm.write(f"[{resource_name}] failed to get mappings from wikidata: {e}")
                    continue
                _write_source(
                    resource_mappings, "wikidata", resource_name, write_labels=write_labels
                )

            mappings.extend(resource_mappings)
            summaries.append(
                (resource_name, len(resource_mappings), time.time() - start, "wikidata")
            )
            _write_summary()

    click.secho("\nOntology Sources", fg="cyan", bold=True)
    it = tqdm(
        sorted(ontology_resources, key=attrgetter("prefix")),
        unit="ontology",
        desc="Ontology sources",
    )
    for resource in it:
        it.set_postfix(prefix=resource.prefix)
        tqdm.write(click.style("\n" + resource.prefix, fg="green"))
        pickle_gz_path = _get_pickle_path("ontology", resource.prefix)
        start = time.time()
        if pickle_gz_path.is_file():
            resource_mappings = from_pickle(pickle_gz_path)
            tqdm.write(f"loaded {len(resource_mappings):,} from cache at {pickle_gz_path}")
        else:
            try:
                with logging_redirect_tqdm():
                    resource_mappings = from_pyobo(
                        resource.prefix, force_process=refresh_source, cache=False
                    )
            except (ValueError, NoBuildError, subprocess.SubprocessError) as e:
                tqdm.write(f"[{resource.prefix}] failed ontology parsing: {e}")
                continue
            _write_source(resource_mappings, "ontology", resource.prefix, write_labels=write_labels)
            # this outputs on each iteration to get faster insight
            write_warned(WARNINGS_PATH)
            write_getter_warnings(ERRORS_PATH)

        mappings.extend(resource_mappings)
        summaries.append((resource.prefix, len(resource_mappings), time.time() - start, "pyobo"))
        _write_summary()

    click.echo(f"Writing Pickle to {PICKLE_PATH}")
    write_pickle(mappings, PICKLE_PATH)
    click.echo(f"Writing SSSOM to {SSSOM_PATH}")
    write_sssom(mappings, SSSOM_PATH)
    click.echo(f"Writing Neo4j folder to {NEO4J_DIR}")
    write_neo4j(mappings, NEO4J_DIR)

    if upload:
        # Define the metadata that will be used on initial upload
        zenodo_metadata = Metadata(
            title="SeMRA Mapping Database",
            upload_type="dataset",
            description=f"A compendium of mappings extracted from {len(summaries)} database/ontologies. "
            f"Note that primary mappings are marked with the license of their source (when available). "
            f"Inferred mappings are distributed under the CC0 license.",
            creators=[
                Creator(name="Hoyt, Charles Tapley", orcid=charlie.identifier),
            ],
        )
        res = ensure_zenodo(
            key="semra-database-test-1",
            data=zenodo_metadata,
            paths=[
                SSSOM_PATH,
                WARNINGS_PATH,
                ERRORS_PATH,
                SUMMARY_PATH,
                *NEO4J_DIR.iterdir(),
            ],
            sandbox=True,
        )
        click.echo(res.json()["links"]["html"])


def _write_source(
    mappings: list[Mapping], subdirectory: str, key: str, write_labels: bool = True
) -> None:
    if mappings:
        tqdm.write(f"produced {len(mappings):,} mappings")
        write_pickle(mappings, _get_pickle_path(subdirectory, key))
        write_sssom(
            mappings,
            SOURCES.join(subdirectory, name=f"{key}.sssom.tsv.gz"),
            add_labels=write_labels,
        )
    else:
        EMPTY.append(key)
        EMPTY_PATH.write_text("\n".join(EMPTY))


def _get_pickle_path(subdirectory: str, key: str) -> Path:
    return SOURCES.join(subdirectory, name=f"{key}.pkl.gz")


def _write_summary() -> None:
    with SUMMARY_PATH.open("w") as file:
        writer = csv.writer(file, delimiter="\t")
        writer.writerow(("prefix", "mappings", "seconds", "source_type"))
        for prefix, n_mappings, time_delta, source_type in summaries:
            writer.writerow((prefix, n_mappings, round(time_delta, 2), source_type))


if __name__ == "__main__":
    build()
