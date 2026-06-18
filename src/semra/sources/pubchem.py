"""Get mappings from PubChem."""

from __future__ import annotations

import logging

import bioversions
import pyobo
import requests
from pydantic import AnyUrl
from sssom_pydantic import SemanticMapping

from semra.constants import CC0_URL, Reference
from semra.vocabulary import EXACT_MATCH, UNSPECIFIED_MAPPING

__all__ = [
    "get_pubchem_mesh_mappings",
]


logger = logging.getLogger(__name__)


def get_pubchem_mesh_mappings(
    version: str | None = None, confidence: float = 0.99
) -> list[SemanticMapping]:
    """Get a mapping from PubChem compound identifiers to their equivalent MeSH terms."""
    if version is None:
        version = bioversions.get_version("pubchem")

    mesh_name_to_id = pyobo.get_name_id_mapping("mesh")
    needs_curation: set[str] = set()

    url = f"https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Monthly/{version}/Extras/CID-MeSH"

    provider = AnyUrl(url)
    source = Reference(prefix="bioregistry", identifier="pubchem.compound")

    rv = []
    with requests.get(url, stream=True, timeout=600) as res:
        for line in res.iter_lines():
            # on a small number of entries, there are multiple names. their impact is negligible
            pubchem, mesh_name, *_ = line.decode("utf8").strip().split("\t")
            mesh_id = mesh_name_to_id.get(mesh_name)
            if mesh_id is None:
                if mesh_name not in needs_curation:
                    needs_curation.add(mesh_name)
                    logger.debug("[mesh] needs curating: %s", mesh_name)
                continue
            mapping = SemanticMapping(
                subject=Reference(prefix="pubchem.compound", identifier=pubchem),
                subject_source_version=version,
                object=Reference(prefix="mesh", identifier=mesh_id),
                predicate=EXACT_MATCH,
                justification=UNSPECIFIED_MAPPING,
                confidence=confidence,
                # Data is in public domain: https://www.ncbi.nlm.nih.gov/home/about/policies/
                license=CC0_URL,
                source=source,
                provider=provider,
            )
            rv.append(mapping)

    logger.warning("[pubchem-mesh] %d MeSH names need manual curation", len(needs_curation))
    return rv
