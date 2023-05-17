"""Assemble a database."""

import bioregistry
import pystow
from bioontologies.obograph import write_warned
from tqdm.auto import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from semra.io import from_bioontologies, write_sssom

MODULE = pystow.module("semra")
DATABASE_PATH = MODULE.join(name="database.tsv")
WARNINGS_PATH = MODULE.join(name="warnings.tsv")


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
    resources = [
        resource
        for resource in bioregistry.resources()
        if resource.get_obofoundry_prefix() and not resource.is_deprecated() and resource.prefix not in skip
    ]
    mappings = []
    it = tqdm(resources, unit="ontology")
    for resource in it:
        it.set_postfix(prefix=resource.prefix)
        try:
            with logging_redirect_tqdm():
                resource_mappings = from_bioontologies(resource.prefix)
        except ValueError as e:
            tqdm.write(f"failed on {resource.prefix}: {e}")
            continue
        mappings.extend(resource_mappings)
        # this outputs on each iteration to get faster insight
        write_warned(WARNINGS_PATH)

    write_sssom(mappings, DATABASE_PATH)


if __name__ == "__main__":
    main()
