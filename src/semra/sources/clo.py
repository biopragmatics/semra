"""Process mappings from CLO."""

from __future__ import annotations

import bioregistry
import click
from pyobo import Reference
from tqdm.auto import tqdm

from semra.rules import DB_XREF, UNSPECIFIED_MAPPING
from semra.struct import Mapping, MappingSet, SimpleEvidence

__all__ = ["get_clo_mappings"]

SKIP_PREFIXES = {"omim"}
CLO_URI_PREFIX = "http://purl.obolibrary.org/obo/CLO_"


def _split(s: str) -> list[str]:
    return [
        p2.replace(" ", "").rstrip(")")
        for p1 in s.strip().split(";")
        for p2 in p1.strip().split(",")
    ]


def _removeprefix(s: str, prefix: str) -> str:
    if s.startswith(prefix):
        return s[len(prefix) :]
    return s


def get_clo_mappings(confidence: float = 0.8) -> list[Mapping]:
    """Get Cell Line Ontology mappings.

    :param confidence: How confidence are you in the quality of these mappings being
        exact? By default, is 0.8.

    :returns: Semantic mappings extracted from the CLO

    :raises ValueError: if a prefix is encountered that doesn't have a regular
        expression defined in the Bioregistry. If you get this error, please report it
        on the Bioregistry's issue tracker
        https://github.com/biopragmatics/bioregistry/issues/new?&labels=Update&template=update-misc.yml

    Note that this function exists because CLO doesn't use standard curation for xrefs
    and instead uses a combination of messy references inside rdfs:seeAlso annotations
    """
    import bioontologies

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
        clo_id = node.id[len(CLO_URI_PREFIX) :]
        for p in node.properties or []:
            if p.predicate_raw != "http://www.w3.org/2000/01/rdf-schema#seeAlso":
                continue
            for raw_curie in _split(p.value_raw):
                curie = _removeprefix(_removeprefix(raw_curie, "rrid:"), "RRID:")
                prefix: str | None
                identifier: str | None
                if curie.startswith("Sanger:COSMICID:"):
                    prefix, identifier = "cosmic.cell", _removeprefix(curie, "Sanger:COSMICID:")
                elif curie.startswith("RRID:CVCL_"):
                    prefix, identifier = "cellosaurus", _removeprefix(curie, "RRID:CVCL_")
                elif curie.startswith("RRID: CVCL_"):
                    prefix, identifier = "cellosaurus", _removeprefix(curie, "RRID: CVCL_")
                elif curie.startswith("atcc:COSMICID:"):
                    prefix, identifier = "cosmic.cell", _removeprefix(curie, "atcc:COSMICID:")
                elif curie.startswith("DSMZ:COSMICID:"):
                    prefix, identifier = "cosmic.cell", _removeprefix(curie, "DSMZ:COSMICID:")
                elif curie.startswith("COSMIC: COSMIC ID:"):
                    prefix, identifier = "cosmic.cell", _removeprefix(curie, "COSMIC: COSMIC ID:")
                elif curie.startswith("RIKEN:COSMICID:"):
                    prefix, identifier = "cosmic.cell", _removeprefix(curie, "RIKEN:COSMICID:")
                elif curie.startswith("COSMICID:"):
                    prefix, identifier = "cosmic.cell", _removeprefix(curie, "COSMICID:")
                elif curie.startswith("LINCS_HMS:"):
                    prefix, identifier = "hms.lincs.cell", _removeprefix(curie, "LINCS_HMS:")
                elif curie.startswith("HMSL: HMSL"):
                    prefix, identifier = "hms.lincs.cell", _removeprefix(curie, "HMSL: HMSL")
                elif curie.startswith("CHEMBL:"):
                    prefix, identifier = "chembl.cell", _removeprefix(curie, "CHEMBL:")
                elif curie.startswith("ChEMBL:"):
                    prefix, identifier = "chembl.cell", _removeprefix(curie, "ChEMBL:")
                elif curie.startswith("BTO_"):
                    prefix, identifier = "bto", _removeprefix(curie, "BTO_")
                elif curie.startswith("CVCL_"):
                    prefix, identifier = "cellosaurus", _removeprefix(curie, "CVCL_")
                elif curie.startswith("JHSF:"):
                    prefix, identifier = "jcrb", _removeprefix(curie, "JHSF:")
                elif curie.startswith("CRL-"):
                    prefix, identifier = "atcc", curie
                elif curie.startswith("jcrb:JHSF:"):
                    prefix, identifier = "jcrb", _removeprefix(curie, "jcrb:JHSF:")
                elif curie.startswith("JCRB"):
                    prefix, identifier = "jcrb", curie
                elif curie.startswith("JHSF:JCRB"):
                    prefix, identifier = "jcrb", _removeprefix(curie, "JHSF:")
                elif curie.startswith("ATCCCRL"):
                    prefix, identifier = "atcc", _removeprefix(curie, "ATCC")
                elif curie.startswith("bto:BAO_"):
                    prefix, identifier = "bao", _removeprefix(curie, "bto:BAO_")
                elif curie.startswith("ACC"):
                    prefix, identifier = "dsmz", curie
                elif curie.startswith("DSMZACC"):
                    prefix, identifier = "dsmz", _removeprefix(curie, "DSMZ")
                elif curie.startswith("dsmz:ACC"):
                    prefix, identifier = "dsmz", "ACC-" + _removeprefix(curie, "dsmz:ACC")
                elif curie.startswith("DSMZ:ACC"):
                    prefix, identifier = "dsmz", "ACC-" + _removeprefix(curie, "DSMZ:ACC")
                else:
                    prefix, identifier = bioregistry.parse_curie(curie)

                if prefix is None or identifier is None:
                    tqdm.write(
                        f"CLO:{clo_id} unparsed: {click.style(curie, fg='red')} "
                        f"from line:\n  {p.value_raw}"
                    )
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
                        subject=Reference(prefix="clo", identifier=clo_id),
                        predicate=DB_XREF,
                        object=Reference(prefix=prefix, identifier=identifier),
                        evidence=[
                            SimpleEvidence(
                                justification=UNSPECIFIED_MAPPING, mapping_set=mapping_set
                            )
                        ],
                    )
                )
    return mappings
