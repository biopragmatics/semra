"""Reprocess the gilda default lexical index."""

import click
import gilda
import pystow
from gilda import Grounder
from gilda.grounder import load_entries_from_terms_file
from gilda.resources import get_grounding_terms

from semra.gilda_utils import (
    GILDA_TO_BIOREGISTRY,
    print_scored_matches,
    standardize_gilda_terms,
    update_gilda_terms,
)
from semra.pipeline import AssembleReturnType, Configuration, Input, Mutation, assemble

MODULE = pystow.module("semra", "gilda-demo")
PROCESSED_GILDA_TERMS_PATH = MODULE.join(name="grounding_terms_standardized.tsv.gz")

PRIORITY = [
    "HP",
    "CHEBI",
    "ECO",
    "CL",
    "DOID",
    "TAXONOMY",
    "GO",
    "HGNC",
    "UBERON",
    "BTO",
    "UP",
    "PUBCHEM",
    "IP",
    "PF",
    "FPLX",
    "EFO",
    "NCIT",
    "MESH",
    "OMIT",
]
PRIORITY = [GILDA_TO_BIOREGISTRY[p] for p in PRIORITY]

CONFIGURATION = Configuration(
    key="gilda",
    name="Gilda Reprocessing",
    inputs=[
        Input(source="biomappings"),
        Input(source="gilda"),
        Input(prefix="hp", source="pyobo", confidence=0.95),
        Input(prefix="efo", source="pyobo", confidence=0.95),
        Input(prefix="doid", source="pyobo", confidence=0.95),
        Input(prefix="uberon", source="pyobo", confidence=0.95),
        Input(prefix="mondo", source="pyobo", confidence=0.95),
        Input(prefix="cl", source="pyobo", confidence=0.95),
        Input(prefix="go", source="pyobo", confidence=0.95),
        Input(prefix="bto", source="pyobo", confidence=0.95),
        Input(prefix="clo", source="bioontologies", confidence=0.95),
    ],
    priority=PRIORITY,
    mutations=[
        Mutation(source="efo", confidence=0.95),
        Mutation(source="hp", confidence=0.95),
        Mutation(source="doid", confidence=0.95),
        Mutation(source="mondo", confidence=0.95),
    ],
    directory=MODULE.base,
)


def _get_terms() -> list[gilda.Term]:
    if PROCESSED_GILDA_TERMS_PATH.is_file():
        return list(load_entries_from_terms_file(PROCESSED_GILDA_TERMS_PATH))
    from gilda.generate_terms import dump_terms

    terms: list[gilda.Term] = list(load_entries_from_terms_file(get_grounding_terms()))
    terms = standardize_gilda_terms(terms)
    dump_terms(terms, PROCESSED_GILDA_TERMS_PATH)
    return terms


def main() -> None:
    """Reprocess the gilda default lexical index."""
    mappings = assemble(CONFIGURATION, return_type=AssembleReturnType.priority)
    if not mappings:
        raise ValueError("Bad mapping priority definition resulted in no mappings")

    terms = _get_terms()

    # Do some integrity checking
    prefixes = {term.db for term in terms}
    missing = prefixes.difference(CONFIGURATION.priority)
    if missing:
        raise ValueError(f"Missing: {sorted(missing)}")

    terms = update_gilda_terms(terms, mappings)

    grounder = Grounder(terms)
    s = "Pelvic lipomatosis"
    scored_matches = grounder.ground(s)

    click.secho("Vanilla Gilda", fg="green", bold=True)
    print_scored_matches(gilda.ground(s))

    click.secho("\n\nProcessed Gilda", fg="green", bold=True)
    print_scored_matches(scored_matches)


if __name__ == "__main__":
    main()
