"""Assemble a database."""

import bioregistry
import pyobo
import pystow
from bioontologies.obograph import write_warned
from tqdm.auto import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from semra.io import from_bioontologies, from_pyobo, write_neo4j, write_sssom
from semra.sources import SOURCE_RESOLVER

MODULE = pystow.module("semra", "database")
DATABASE_PATH = MODULE.join(name="sssom.tsv")
WARNINGS_PATH = MODULE.join(name="warnings.tsv")
NEO4J_DIR = MODULE.join("neo4j")


def main():
    skip = {
        "ado",
        "epio",  # trash
        "chebi",
        "pr",
        "ncbitaxon",
        "ncit",  # too big
        "plana",  # JSON export broken, missing val for synonyms
    }

    ontology_resources = []
    pyobo_resources = []
    for resource in bioregistry.resources():
        if resource.is_deprecated() or resource.prefix in skip:
            continue
        if resource.prefix.startswith("kegg"):
            continue
        if pyobo.has_nomenclature_plugin(resource.prefix):
            pyobo_resources.append(resource)
        elif resource.get_obofoundry_prefix() or resource.has_download():
            ontology_resources.append(resource.prefix)

    mappings = []

    it = tqdm(pyobo_resources, unit="prefix", desc="PyOBO sources")
    for resource in it:
        it.set_postfix(prefix=resource.prefix)
        try:
            with logging_redirect_tqdm():
                resource_mappings = from_pyobo(resource.prefix)
        except Exception as e:
            tqdm.write(f"failed PyOBO parsing on {resource.prefix}: {e}")
            continue
        mappings.extend(resource_mappings)

    it = tqdm(list(SOURCE_RESOLVER), unit="source", desc="Custom sources")
    for func in it:
        it.set_postfix(source=func.__name__.removeprefix("get_").removesuffix("_mappings"))
        with logging_redirect_tqdm():
            mappings.extend(func())

    it = tqdm(ontology_resources, unit="ontology", desc="Ontology sources")
    for resource in it:
        it.set_postfix(prefix=resource.prefix)
        try:
            with logging_redirect_tqdm():
                resource_mappings = from_bioontologies(resource.prefix)
        except ValueError as e:
            tqdm.write(f"failed ontology parsing on {resource.prefix}: {e}")
            continue
        mappings.extend(resource_mappings)
        # this outputs on each iteration to get faster insight
        write_warned(WARNINGS_PATH)

    write_sssom(mappings, DATABASE_PATH)
    write_neo4j(mappings, NEO4J_DIR)


if __name__ == "__main__":
    main()
