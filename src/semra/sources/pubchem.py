"""Get mappings from PubChem."""

import logging

import bioversions
import pandas as pd
import pyobo

from semra import EXACT_MATCH, Mapping, Reference, SimpleEvidence

__all__ = [
    "get_pubchem_mesh_mappings",
]

logger = logging.getLogger(__name__)


def get_pubchem_mesh_mappings(version: str | None = None) -> list[Mapping]:
    """Get a mapping from PubChem compound identifiers to their equivalent MeSH terms."""
    if version is None:
        version = bioversions.get_version("pubchem")
    url = f"ftp://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Monthly/{version}/Extras/CID-MeSH"
    df = pd.read_csv(
        url,
        dtype=str,
        header=None,
        names=["pubchem", "mesh"],
    )
    mesh_name_to_id = pyobo.get_name_id_mapping("mesh")
    needs_curation = set()
    mesh_ids = []
    for name in df["mesh"]:
        mesh_id = mesh_name_to_id.get(name)
        if mesh_id is None and name not in needs_curation:
            needs_curation.add(name)
            logger.debug("[mesh] needs curating: %s", name)
        mesh_ids.append(mesh_id)
    logger.info("[mesh] %d/%d need updating", len(needs_curation), len(mesh_ids))
    df["mesh"] = mesh_ids

    return [
        Mapping(
            s=Reference(prefix="pubchem.compound", identifier=pubchem),
            o=Reference(prefix="mesh", identifier=mesh),
            p=EXACT_MATCH,
            evidence=[SimpleEvidence(mapping_set="pubchem", mapping_set_verson=version)],
        )
        for pubchem, mesh in df.values
        if mesh is not None
    ]
