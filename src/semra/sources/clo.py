"""Process mappings from CLO."""

from __future__ import annotations

import tempfile
from pathlib import Path

import bioregistry
import click
import curies
import obographs
import robot_obo_tool
from pydantic import AnyUrl
from sssom_pydantic import SemanticMapping
from tqdm.auto import tqdm

from semra.constants import Reference
from semra.vocabulary import DB_XREF, UNSPECIFIED_MAPPING

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


CLO_OWL_URL = "http://purl.obolibrary.org/obo/clo.owl"


def get_clo_mappings(confidence: float = 0.8) -> list[SemanticMapping]:
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
    converter = bioregistry.get_default_converter()
    with tempfile.TemporaryDirectory() as tmpdir:
        clo_json_path = Path(tmpdir).joinpath("clo.json")
        robot_obo_tool.convert(CLO_OWL_URL, clo_json_path)
        graph = obographs.read(clo_json_path, squeeze=True).standardize(converter)

    license_url = bioregistry.get_license_url("clo")
    source = Reference(prefix="bioregistry", identifier="clo")
    provider = AnyUrl("http://purl.obolibrary.org/obo/clo.owl")

    mappings = []
    for node in tqdm(graph.nodes, unit_scale=True, unit="node"):
        if not node.reference.prefix == "clo" or node.meta is None:
            continue
        for prop in node.meta.properties or []:
            if prop.predicate.curie != "rdfs:seeAlso" or isinstance(prop.value, curies.Reference):
                continue
            for raw_curie in _split(prop.value):
                curie = raw_curie.removeprefix("rrid:").removeprefix("RRID:")
                prefix: str | None
                identifier: str | None
                if curie.startswith("Sanger:COSMICID:"):
                    prefix, identifier = "cosmic.cell", curie.removeprefix("Sanger:COSMICID:")
                elif curie.startswith("RRID:CVCL_"):
                    prefix, identifier = "cellosaurus", curie.removeprefix("RRID:CVCL_")
                elif curie.startswith("RRID: CVCL_"):
                    prefix, identifier = "cellosaurus", curie.removeprefix("RRID: CVCL_")
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
                elif curie.startswith("HMSL: HMSL"):
                    prefix, identifier = "hms.lincs.cell", curie.removeprefix("HMSL: HMSL")
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
                    try:
                        prefix, identifier = bioregistry.parse_curie(curie)
                    except Exception:
                        tqdm.write(
                            f"{node.reference.curie} unparsed: {click.style(curie, fg='red')} "
                            f"from line:\n  {prop.value}"
                        )
                        continue

                if prefix is None or identifier is None:
                    tqdm.write(
                        f"{node.reference.curie} unparsed: {click.style(curie, fg='red')} "
                        f"from line:\n  {prop.value}"
                    )
                    continue
                if prefix in SKIP_PREFIXES:
                    continue
                if bioregistry.get_pattern(prefix) is None:
                    raise ValueError(f"Missing pattern for prefix `{prefix}`")
                if not bioregistry.is_valid_identifier(prefix, identifier):
                    c = click.style(f"{prefix}:{identifier}", fg="yellow")
                    tqdm.write(f"{node.reference.curie} invalid: {c} from line:\n  {prop.value}")
                    continue

                mappings.append(
                    SemanticMapping(
                        subject=Reference.from_reference(node.reference),
                        subject_source_version=graph.version,
                        predicate=DB_XREF,
                        object=Reference(prefix=prefix, identifier=identifier),
                        justification=UNSPECIFIED_MAPPING,
                        confidence=confidence,
                        source=source,
                        provider=provider,
                        license=license_url,
                    )
                )
    return mappings
