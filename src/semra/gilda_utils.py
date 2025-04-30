"""Utilities for working with Gilda."""

from __future__ import annotations

import itertools as itt
import logging
import typing as t
from collections import defaultdict
from typing import cast

import bioregistry
import gilda
import gilda.term
from tabulate import tabulate
from tqdm.auto import tqdm
from tqdm.contrib.concurrent import process_map

from semra.api import assert_projection
from semra.struct import Mapping

__all__ = [
    "update_terms",
]

logger = logging.getLogger(__name__)

#: A mapping from gilda prefixes to Bioregistry prefixes
GILDA_TO_BIOREGISTRY = {
    "EFO": "efo",
    "HP": "hp",
    "CHEBI": "chebi",
    "ECO": "eco",
    "PF": "pfam",
    "CL": "cl",
    "DOID": "doid",
    "OMIT": "omit",
    "MESH": "mesh",
    "BTO": "bto",
    "TAXONOMY": "ncbitaxon",
    "GO": "go",
    "HGNC": "hgnc",
    "NCIT": "ncit",
    "UBERON": "uberon",
    "UP": "uniprot",
    "PUBCHEM": "pubchem.compound",
    "IP": "interpro",
    "FPLX": "fplx",
}
REVERSE_GILDA_MAP = {v: k for k, v in GILDA_TO_BIOREGISTRY.items()}


def update_terms(terms: list[gilda.Term], mappings: list[Mapping]) -> list[gilda.Term]:
    """Use a priority mapping to re-write terms with priority groundings.

    :param terms: A list of Gilda term objects
    :param mappings: A list of SeMRA mapping objects, constituting a priority mapping.
        This means that each mapping has a unique subject.

    :returns: A new list of Gilda term objects that have been remapped

    .. code-block:: python

        from itertools import chain

        from gilda import Grounder
        from gilda.term import filter_out_duplicates
        from pyobo.gilda_utils import get_gilda_terms

        from semra import Configuration, Input
        from semra.gilda_utils import update_terms

        prefixes = ["doid", "mondo", "efo"]

        # 1. Get terms
        terms = chain.from_iterable(get_gilda_terms(p) for p in prefixes)
        terms = filter_out_duplicates(list(terms))

        # 2. Get mappings
        configuration = Configuration.from_prefixes(name="Diseases", prefixes=prefixes)
        mappings = configuration.get_mappings()

        # 3. Update terms and use them (i.e., to construct a grounder)
        new_terms = update_terms(terms, mappings)
        grounder = Grounder(new_terms)
    """
    assert_projection(mappings)

    terms_index = defaultdict(list)
    for term in terms:
        terms_index[term.db, term.id].append(term)

    for mapping in tqdm(mappings, unit="mapping", unit_scale=True, desc="applying mappings"):
        source_terms = terms_index.pop(mapping.subject.pair, None)
        if source_terms:
            terms_index[mapping.object.pair].extend(
                make_new_term(term, mapping.object.prefix, mapping.object.identifier)
                for term in source_terms
            )

    # Unwind the terms index
    new_terms = list(itt.chain.from_iterable(terms_index.values()))
    return cast(list[gilda.Term], gilda.term.filter_out_duplicates(new_terms))


def standardize_terms(
    terms: t.Iterable[gilda.Term], *, multiprocessing: bool = True
) -> list[gilda.Term]:
    """Standardize a list of terms."""
    if not multiprocessing:
        return [standardize_term(t) for t in terms]
    return cast(
        list[gilda.Term],
        process_map(
            standardize_term,
            terms,
            unit="term",
            unit_scale=True,
            desc="standardizing",
            chunksize=40_000,
        ),
    )


def standardize_term(term: gilda.Term) -> gilda.Term:
    """Standardize a term's prefix and identifier to the Bioregistry standard."""
    prefix = bioregistry.normalize_prefix(term.db)
    if prefix is None:
        raise ValueError(term)
    term.db = prefix
    term.id = bioregistry.standardize_identifier(term.db, term.id)
    if term.source_db:
        source_db = bioregistry.normalize_prefix(term.source_db)
        if source_db is None:
            raise ValueError(term)
        term.source_db = source_db
        term.source_id = bioregistry.standardize_identifier(term.source_db, term.source_id)
    return term


def make_new_term(
    term: gilda.Term,
    target_db: str,
    target_id: str,
    target_name: str | None = None,
) -> gilda.Term:
    """Make a new gilda term object by replacing the database, identifier, and name."""
    if target_name is None:
        from indra.ontology.bio import bio_ontology

        target_name = bio_ontology.get_name(target_db, target_id)
    return gilda.Term(
        norm_text=term.norm_text,
        text=term.text,
        db=target_db,
        id=target_id,
        entry_name=target_name or term.entry_name,
        status=term.status,
        source=term.source,
        organism=term.organism,
        source_db=term.db,
        source_id=term.id,
    )


def print_scored_matches(scored_matches: list[gilda.ScoredMatch]) -> None:
    """Print a table of scored matches."""
    rows = [
        (
            scored_match.term.entry_name,
            scored_match.term.db,
            scored_match.term.id,
            scored_match.term.norm_text,
            scored_match.term.status,
            round(scored_match.score, 4),
            scored_match.term.source_db,
            scored_match.term.source_id,
        )
        for scored_match in scored_matches
    ]
    text = tabulate(
        rows,
        headers=[
            "name",
            "prefix",
            "identifier",
            "norm_text",
            "status",
            "score",
            "source_prefix",
            "source_id",
        ],
    )
    print(text)  # noqa:T201
