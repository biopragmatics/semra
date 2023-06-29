"""Assemble a database."""

import pickle
import time

import bioregistry
import click
import pyobo
import pystow
from bioontologies.obograph import write_warned
from bioontologies.robot import write_getter_warnings
from tqdm.auto import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from semra.io import from_bioontologies, from_pyobo, write_neo4j, write_pickle, write_sssom
from semra.sources import SOURCE_RESOLVER

MODULE = pystow.module("semra", "database")
SOURCES = MODULE.module("sources")
DATABASE_PATH = MODULE.join(name="sssom.tsv")
WARNINGS_PATH = MODULE.join("logs", name="warnings.tsv")
ERRORS_PATH = MODULE.join("logs", name="errors.tsv")
SUMMARY_PATH = MODULE.join("logs", name="summary.tsv")
EMPTY_PATH = MODULE.join("logs", name="empty.txt")
NEO4J_DIR = MODULE.join("neo4j")

EMPTY = []

summaries = []


@click.command()
def main():
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
        summaries.append((resource.prefix, len(resource_mappings), time.time() - start))
        _write_summary()

    it = tqdm(list(SOURCE_RESOLVER), unit="source", desc="Custom sources")
    for func in it:
        start = time.time()
        resource_name = func.__name__.removeprefix("get_").removesuffix("_mappings")
        it.set_postfix(source=resource_name)
        with logging_redirect_tqdm():
            resource_mappings = func()
            _write_source(resource_mappings, resource_name)
            mappings.extend(resource_mappings)
        summaries.append((resource_name, len(resource_mappings), time.time() - start))
        _write_summary()

    it = tqdm(ontology_resources, unit="ontology", desc="Ontology sources")
    for resource in it:
        it.set_postfix(prefix=resource.prefix)
        path = SOURCES.join(name=f"{resource.prefix}.pkl")
        if path.is_file():
            resource_mappings = pickle.loads(path.read_bytes())
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
            summaries.append((resource.prefix, len(resource_mappings), time.time() - start))
            _write_summary()

        mappings.extend(resource_mappings)

    click.echo(f"Writing SSSOM to {DATABASE_PATH}")
    write_sssom(mappings, DATABASE_PATH)
    click.echo(f"Writing Neo4j folder to {DATABASE_PATH}")
    write_neo4j(mappings, NEO4J_DIR)


def _write_source(mappings, key):
    write_pickle(mappings, SOURCES.join(name=f"{key}.pkl"))
    if mappings:
        write_sssom(mappings, SOURCES.join(name=f"{key}.sssom.tsv"))
    else:
        EMPTY.append(key)
        EMPTY_PATH.write_text("\n".join(EMPTY))


def _write_summary():
    SUMMARY_PATH.write_text("\n".join(f"{p}\t{n:,}\t{round(delta, 3)}" for p, n, delta in summaries))


if __name__ == "__main__":
    main()
