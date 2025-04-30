"""Get mappings from PubChem."""

from __future__ import annotations

import logging

import bioversions
import pyobo
import requests
from pyobo import Reference

from semra.rules import EXACT_MATCH, UNSPECIFIED_MAPPING
from semra.struct import Mapping, MappingSet, SimpleEvidence

__all__ = [
    "get_pubchem_mesh_mappings",
]


logger = logging.getLogger(__name__)


def get_pubchem_mesh_mappings(version: str | None = None) -> list[Mapping]:
    """Get a mapping from PubChem compound identifiers to their equivalent MeSH terms."""
    if version is None:
        version = bioversions.get_version("pubchem")

    mesh_name_to_id = pyobo.get_name_id_mapping("mesh")
    needs_curation: set[str] = set()

    url = f"https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Monthly/{version}/Extras/CID-MeSH"
    res = requests.get(url, stream=True, timeout=600)

    rv = []
    for line in res.iter_lines():
        # on a small number of entries, there are multiple names. their impact is negligible
        pubchem, mesh_name, *_ = line.decode("utf8").strip().split("\t")
        mesh_id = mesh_name_to_id.get(mesh_name)
        if mesh_id is None:
            if mesh_name not in needs_curation:
                needs_curation.add(mesh_name)
                logger.debug("[mesh] needs curating: %s", mesh_name)
            continue
        mapping = Mapping(
            subject=Reference(prefix="pubchem.compound", identifier=pubchem),
            object=Reference(prefix="mesh", identifier=mesh_id),
            predicate=EXACT_MATCH,
            evidence=[
                SimpleEvidence(
                    justification=UNSPECIFIED_MAPPING,
                    # Data is in public domain: https://www.ncbi.nlm.nih.gov/home/about/policies/
                    mapping_set=MappingSet(
                        name="pubchem", version=version, confidence=0.99, license="CC0"
                    ),
                )
            ],
        )
        rv.append(mapping)

    logger.warning("[pubchem-mesh] %d MeSH names need manual curation", len(needs_curation))
    return rv
