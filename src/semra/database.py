"""Assemble a database."""

import csv
import time
import typing as t

import bioregistry
import click
import pyobo
import pystow
import requests
from bioontologies.obograph import write_warned
from bioontologies.robot import write_getter_warnings
from tqdm.auto import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from zenodo_client import Creator, Metadata, ensure_zenodo

from semra import Mapping
from semra.io import (
    from_bioontologies,
    from_pickle,
    from_pyobo,
    write_neo4j,
    write_pickle,
    write_sssom,
)
from semra.rules import CHARLIE_NAME, CHARLIE_ORCID
from semra.sources import SOURCE_RESOLVER
from semra.sources.wikidata import get_wikidata_mappings_by_prefix

MODULE = pystow.module("semra", "database")
SOURCES = MODULE.module("sources")
LOGS = MODULE.module("logs")
SSSOM_PATH = MODULE.join(name="sssom.tsv")
WARNINGS_PATH = LOGS.join(name="warnings.tsv")
ERRORS_PATH = LOGS.join(name="errors.tsv")
SUMMARY_PATH = LOGS.join(name="summary.tsv")
EMPTY_PATH = LOGS.join(name="empty.txt")
NEO4J_DIR = MODULE.join("neo4j")

EMPTY = []
summaries = []


@click.command()
def main():
    """Construct the full SeMRA database."""
    skip = {
        "ado",  # trash
        "epio",  # trash
        "chebi",  # too big
        "pr",  # too big
        "ncbitaxon",  # too big
        "ncit",  # too big
        "ncbigene",  # too big
        # duplicates of EDAM
        "edam.data",
        "edam.format",
        "edam.operation",
        "edam.topic",
        "gwascentral.phenotype",  # added on 2024-04-24, service down
        "gwascentral.study",  # added on 2024-04-24, service down
    }
    #: A set of prefixes whose obo files need to be parsed without ROBOT checks
    loose = {
        "caloha",
        "foodon",
        "cellosaurus",
    }

    ontology_resources = []
    pyobo_resources = []
    for resource in bioregistry.resources():
        if resource.is_deprecated() or resource.prefix in skip or resource.no_own_terms or resource.proprietary:
            continue
        if resource.prefix.startswith("kegg") or resource.prefix.startswith("pubchem"):
            continue
        if pyobo.has_nomenclature_plugin(resource.prefix):
            pyobo_resources.append(resource)
        elif resource.get_obofoundry_prefix() or resource.has_download():
            ontology_resources.append(resource)

    mappings = []

    it = tqdm(pyobo_resources, unit="prefix", desc="PyOBO sources")
    for resource in it:
        it.set_postfix(prefix=resource.prefix)
        start = time.time()
        try:
            with logging_redirect_tqdm():
                resource_mappings = from_pyobo(resource.prefix)
        except Exception as e:
            tqdm.write(f"failed PyOBO parsing on {resource.prefix}: {e}")
            continue
        _write_source(resource_mappings, resource.prefix)
        mappings.extend(resource_mappings)
        summaries.append((resource.prefix, len(resource_mappings), time.time() - start, "pyobo"))
        _write_summary()

    it = tqdm(list(SOURCE_RESOLVER), unit="source", desc="Custom sources")
    for func in it:
        start = time.time()
        resource_name = func.__name__.removeprefix("get_").removesuffix("_mappings")
        if resource_name == "wikidata":
            # this one needs extra informatzi
            continue
        it.set_postfix(source=resource_name)
        with logging_redirect_tqdm():
            resource_mappings = func()
            _write_source(resource_mappings, resource_name)
            mappings.extend(resource_mappings)
        summaries.append((resource_name, len(resource_mappings), time.time() - start, "custom"))
        _write_summary()

    skip_wikidata_prefixes = {"pubmed", "doi"}  # too big! need paging?
    for prefix in tqdm(bioregistry.get_registry_map("wikidata"), unit="property", desc="Wikidata"):
        it.set_postfix(prefix=prefix)
        if prefix in skip_wikidata_prefixes:
            continue
        start = time.time()
        resource_name = f"wikidata_{prefix}"
        try:
            resource_mappings = get_wikidata_mappings_by_prefix(prefix)
        except requests.exceptions.JSONDecodeError as e:
            tqdm.write(f"[{resource_name}] failed to get mappings from wikidata: {e}")
            continue
        _write_source(resource_mappings, resource_name)
        mappings.extend(resource_mappings)
        summaries.append((resource_name, len(resource_mappings), time.time() - start, "wikidata"))
        _write_summary()

    it = tqdm(ontology_resources, unit="ontology", desc="Ontology sources")
    for resource in it:
        it.set_postfix(prefix=resource.prefix)
        path = SOURCES.join(name=f"{resource.prefix}.pkl.gz")
        if path.is_file():
            resource_mappings = from_pickle(path)
        else:
            start = time.time()
            try:
                with logging_redirect_tqdm():
                    resource_mappings = from_bioontologies(resource.prefix, check=resource.prefix not in loose)
            except ValueError as e:
                tqdm.write(f"[{resource.prefix}] failed ontology parsing: {e}")
                continue
            _write_source(resource_mappings, resource.prefix)
            # this outputs on each iteration to get faster insight
            write_warned(WARNINGS_PATH)
            write_getter_warnings(ERRORS_PATH)
            summaries.append((resource.prefix, len(resource_mappings), time.time() - start, "bioontologies"))
            _write_summary()

        mappings.extend(resource_mappings)

    click.echo(f"Writing SSSOM to {SSSOM_PATH}")
    write_sssom(mappings, SSSOM_PATH)
    click.echo(f"Writing Neo4j folder to {SSSOM_PATH}")
    write_neo4j(mappings, NEO4J_DIR)

    # Define the metadata that will be used on initial upload
    zenodo_metadata = Metadata(
        title="SeMRA Mapping Database",
        upload_type="dataset",
        description=f"A compendium of mappings extracted from {len(summaries)} database/ontologies. "
        f"Note that primary mappings are marked with the license of their source (when available). "
        f"Inferred mappings are distributed under the CC0 license.",
        creators=[
            Creator(name=CHARLIE_NAME, orcid=CHARLIE_ORCID.identifier),
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


def _write_source(mappings: t.List[Mapping], key: str) -> None:
    write_pickle(mappings, SOURCES.join(name=f"{key}.pkl.gz"))
    if mappings:
        write_sssom(mappings, SOURCES.join(name=f"{key}.sssom.tsv"))
    else:
        EMPTY.append(key)
        EMPTY_PATH.write_text("\n".join(EMPTY))


def _write_summary() -> None:
    with SUMMARY_PATH.open("w") as file:
        writer = csv.writer(file, delimiter="\t")
        writer.writerow(("prefix", "mappings", "seconds", "source_type"))
        for prefix, n_mappings, time_delta, source_type in summaries:
            writer.writerow((prefix, n_mappings, round(time_delta, 2), source_type))


if __name__ == "__main__":
    main()
