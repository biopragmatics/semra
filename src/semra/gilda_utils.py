import itertools as itt
from collections import defaultdict
from typing import Iterable, Literal, Optional

import bioregistry
import gilda
from gilda import Term
from gilda.term import filter_out_duplicates
from pydantic import BaseModel
from tabulate import tabulate
from tqdm.auto import tqdm

from semra.sources import (
    from_biomappings_positive,
    from_bioontologies,
    from_gilda,
    from_pyobo,
)
from semra.struct import Mapping

#: A mapping from gilda prefixes to Bioregistry prefixes
GILDA_MAP = {
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
REVERSE_GILDA_MAP = {v: k for k, v in GILDA_MAP.items()}


def get_terms_index(terms: Iterable[Term]) -> dict[tuple[str, str], list[Term]]:
    """Index terms by their CURIEs."""
    terms_index = defaultdict(list)
    for term in terms:
        terms_index[term.db, term.id].append(term)
    return dict(terms_index)


def standardize_term(term: Term) -> Term:
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
    term: Term,
    target_db: str,
    target_id: str,
    target_name: Optional[str] = None,
) -> Term:
    if target_name is None:
        from indra.ontology.bio import bio_ontology

        target_name = bio_ontology.get_name(target_db, target_id)
    return Term(
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


def update_terms(terms: list[Term], mappings: list[Mapping]) -> list[Term]:
    """Use a priority mapping to re-write terms with priority groundings."""
    terms_index = get_terms_index(terms)
    for mapping in tqdm(mappings, unit="mapping", unit_scale=True, desc="applying mappings"):
        source_terms = terms_index.pop(mapping.s.pair, None)
        if source_terms:
            terms_index.setdefault(mapping.o.pair, []).extend(
                make_new_term(term, mapping.o.prefix, mapping.o.identifier) for term in source_terms
            )
    new_terms = list(itt.chain.from_iterable(terms_index.values()))
    return filter_out_duplicates(new_terms)


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
        rows, headers=["name", "prefix", "identifier", "norm_text", "status", "score", "source_prefix", "source_id"]
    )
    print(text)  # noqa:T201


class Input(BaseModel):
    prefix: str
    source: Literal["pyobo", "bioontologies"]
    confidence: float = 1.0


class Configuration(BaseModel):
    inputs: list[Input]
    priority: list[str]


def get_mappings_from_config(configuration: Configuration) -> list[Mapping]:
    mappings = []
    mappings.extend(from_gilda())
    mappings.extend(from_biomappings_positive())
    for inp in tqdm(configuration.inputs, desc="Loading configured mappings", unit="source"):
        tqdm.write(f"Loading {inp.prefix} with {inp.source}")
        if inp.source is None:
            continue
        elif inp.source == "bioontologies":
            mappings.extend(from_bioontologies(inp.prefix, confidence=inp.confidence))
        elif inp.source == "pyobo":
            mappings.extend(from_pyobo(inp.prefix, confidence=inp.confidence))
        else:
            raise ValueError
    return mappings
