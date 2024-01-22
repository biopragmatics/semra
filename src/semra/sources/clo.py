"""Process mappings from CLO."""

from typing import Optional

import bioontologies
import bioregistry
import click
from tqdm.auto import tqdm

from semra import DB_XREF, UNSPECIFIED_MAPPING, Mapping, MappingSet, Reference, SimpleEvidence

__all__ = ["get_clo_mappings"]

SKIP_PREFIXES = {"omim"}
CLO_URI_PREFIX = "http://purl.obolibrary.org/obo/CLO_"


def _split(s: str) -> list[str]:
    return [p2.replace(" ", "").rstrip(")") for p1 in s.strip().split(";") for p2 in p1.strip().split(",")]


def get_clo_mappings(confidence: float = 0.8) -> list[Mapping]:
    graph = bioontologies.get_obograph_by_prefix("clo", check=False).guess("clo")
    mapping_set = MappingSet(
        name="clo",
        version=graph.version,
        license=bioregistry.get_license("clo"),
        confidence=confidence,
    )

    mappings = []
    for node in tqdm(graph.nodes, unit_scale=True, unit="node"):
        if not node.id.startswith(CLO_URI_PREFIX):
            continue
        clo_id = node.id.removeprefix(CLO_URI_PREFIX)
        for p in node.properties or []:
            if p.predicate_raw != "http://www.w3.org/2000/01/rdf-schema#seeAlso":
                continue
            for raw_curie in _split(p.value_raw):
                curie = raw_curie.removeprefix("rrid:").removeprefix("RRID:")
                prefix: Optional[str]
                identifier: Optional[str]
                if curie.startswith("Sanger:COSMICID:"):
                    prefix, identifier = "cosmic.cell", curie.removeprefix("Sanger:COSMICID:")
                elif curie.startswith("atcc:COSMICID:"):
                    prefix, identifier = "cosmic.cell", curie.removeprefix("atcc:COSMICID:")
                elif curie.startswith("DSMZ:COSMICID:"):
                    prefix, identifier = "cosmic.cell", curie.removeprefix("DSMZ:COSMICID:")
                elif curie.startswith("COSMIC: COSMIC ID:"):
                    prefix, identifier = "cosmic.cell", curie.removeprefix("COSMIC: COSMIC ID:")
                elif curie.startswith("RIKEN:COSMICID:"):
                    prefix, identifier = "cosmic.cell", curie.removeprefix("RIKEN:COSMICID:")
                elif curie.startswith("COSMICID:"):
                    prefix, identifier = "cosmic.cell", curie.removeprefix("COSMICID:")
                elif curie.startswith("LINCS_HMS:"):
                    prefix, identifier = "hms.lincs.cell", curie.removeprefix("LINCS_HMS:")
                elif curie.startswith("CHEMBL:"):
                    prefix, identifier = "chembl.cell", curie.removeprefix("CHEMBL:")
                elif curie.startswith("ChEMBL:"):
                    prefix, identifier = "chembl.cell", curie.removeprefix("ChEMBL:")
                elif curie.startswith("BTO_"):
                    prefix, identifier = "bto", curie.removeprefix("BTO_")
                elif curie.startswith("CVCL_"):
                    prefix, identifier = "cellosaurus", curie.removeprefix("CVCL_")
                elif curie.startswith("JHSF:"):
                    prefix, identifier = "jcrb", curie.removeprefix("JHSF:")
                elif curie.startswith("CRL-"):
                    prefix, identifier = "atcc", curie
                elif curie.startswith("jcrb:JHSF:"):
                    prefix, identifier = "jcrb", curie.removeprefix("jcrb:JHSF:")
                elif curie.startswith("JCRB"):
                    prefix, identifier = "jcrb", curie
                elif curie.startswith("JHSF:JCRB"):
                    prefix, identifier = "jcrb", curie.removeprefix("JHSF:")
                elif curie.startswith("ATCCCRL"):
                    prefix, identifier = "atcc", curie.removeprefix("ATCC")
                elif curie.startswith("bto:BAO_"):
                    prefix, identifier = "bao", curie.removeprefix("bto:BAO_")
                elif curie.startswith("ACC"):
                    prefix, identifier = "dsmz", curie
                elif curie.startswith("DSMZACC"):
                    prefix, identifier = "dsmz", curie.removeprefix("DSMZ")
                elif curie.startswith("dsmz:ACC"):
                    prefix, identifier = "dsmz", "ACC-" + curie.removeprefix("dsmz:ACC")
                elif curie.startswith("DSMZ:ACC"):
                    prefix, identifier = "dsmz", "ACC-" + curie.removeprefix("DSMZ:ACC")
                else:
                    prefix, identifier = bioregistry.parse_curie(curie)

                if prefix is None or identifier is None:
                    tqdm.write(f"CLO:{clo_id} unparsed: {click.style(curie, fg='red')} from line:\n  {p.value_raw}")
                    continue
                if prefix in SKIP_PREFIXES:
                    continue
                if bioregistry.get_pattern(prefix) is None:
                    raise ValueError(f"Missing pattern for prefix `{prefix}`")
                if not bioregistry.is_valid_identifier(prefix, identifier):
                    c = click.style(f"{prefix}:{identifier}", fg="yellow")
                    tqdm.write(f"CLO:{clo_id} invalid: {c} from line:\n  {p.value_raw}")
                    continue

                mappings.append(
                    Mapping(
                        s=Reference(prefix="clo", identifier=clo_id),
                        p=DB_XREF,
                        o=Reference(prefix=prefix, identifier=identifier),
                        evidence=[SimpleEvidence(justification=UNSPECIFIED_MAPPING, mapping_set=mapping_set)],
                    )
                )
    return mappings
