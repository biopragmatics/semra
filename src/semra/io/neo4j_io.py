"""I/O for Neo4j."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal

import click
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pyobo import Reference
from tqdm import tqdm

from .io_utils import get_confidence_str, get_name_by_curie, safe_open_writer
from ..rules import (
    SEMRA_EVIDENCE_PREFIX,
    SEMRA_MAPPING_PREFIX,
    SEMRA_MAPPING_SET_PREFIX,
    SEMRA_NEO4J_CONCEPT_LABEL,
    SEMRA_NEO4J_EVIDENCE_LABEL,
    SEMRA_NEO4J_MAPPING_LABEL,
    SEMRA_NEO4J_MAPPING_SET_LABEL,
)
from ..struct import Evidence, Mapping, MappingSet, ReasonedEvidence, SimpleEvidence
from ..utils import gzip_path

__all__ = [
    "write_neo4j",
]

HERE = Path(__file__).parent.resolve()

TEMPLATES = HERE.joinpath("templates")
JINJA_ENV = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape())
STARTUP_TEMPLATE = JINJA_ENV.get_template("startup.sh")
DOCKERFILE_TEMPLATE = JINJA_ENV.get_template("Dockerfile")
RUN_ON_STARTUP_TEMPLATE = JINJA_ENV.get_template("run_on_startup.sh")

PYTHON = "python3.13"

CONCEPT_NODES_HEADER = ["curie:ID", "prefix", "name", "priority:boolean"]
MAPPING_NODES_HEADER = [
    "curie:ID",
    "prefix",
    "predicate",
    "confidence",
    "primary:boolean",
    "secondary:boolean",
    "tertiary:boolean",
]
EVIDENCE_NODES_HEADER = [
    "curie:ID",
    "prefix",
    "type",
    "mapping_justification",
    "confidence:float",
]
MAPPING_SET_NODES_HEADER = [
    "curie:ID",
    "prefix",
    "purl",
    "name",
    "license",
    "version",
    "confidence:float",
]
EDGES_HEADER = [
    ":START_ID",
    ":TYPE",
    ":END_ID",
    "confidence:float",
    "primary:boolean",
    "secondary:boolean",
    "tertiary:boolean",
    "mapping_sets:string[]",
]
# for extra edges that aren't mapping edges
EDGES_SUPPLEMENT_HEADER = [
    ":START_ID",
    ":TYPE",
    ":END_ID",
]

ANNOTATED_SOURCE = Reference(prefix="owl", identifier="annotatedSource")
ANNOTATED_SOURCE_CURIE = ANNOTATED_SOURCE.curie

ANNOTATED_TARGET = Reference(prefix="owl", identifier="annotatedTarget")
ANNOTATED_TARGET_CURIE = ANNOTATED_TARGET.curie

#: The predicate used in the graph data model connecting a mapping node to an evidence node
HAS_EVIDENCE_PREDICATE = "hasEvidence"
#: The predicate used in the graph data model connecting an evidence node to a mapping set node
FROM_SET_PREDICATE = "fromSet"
#: The predicate used in the graph data model connecting a reasoned evidence
DERIVED_PREDICATE = "derivedFromMapping"
#: node to the mapping node(s) from which it was derived
HAS_AUTHOR_PREDICATE = "hasAuthor"

CONCEPT_NODES_FILENAME = "concept_nodes.tsv"
MAPPING_NODES_FILENAME = "mapping_nodes.tsv"
EVIDENCE_NODES_FILENAME = "evidence_nodes.tsv"
MAPPING_SET_NODES_FILENAME = "mapping_set_nodes.tsv"
MAPPING_EDGES_FILENAME = "mapping_edges.tsv"
EDGES_FILENAME = "edges.tsv"


def write_neo4j(
    mappings: Iterable[Mapping],
    directory: str | Path,
    *,
    docker_name: str | None = None,
    equivalence_classes: dict[Reference, bool] | None = None,
    add_labels: bool = False,
    startup_script_name: str = "startup.sh",
    run_script_name: str = "run_on_docker.sh",
    dockerfile_name: str = "Dockerfile",
    pip_install: str = "semra[web] @ git+https://github.com/biopragmatics/semra.git",
    use_tqdm: bool = True,
    compress: None | Literal["during", "after"] = None,
) -> None:
    """Write all files needed to construct a Neo4j graph database from a set of mappings.

    :param mappings: A list of semantic mappings
    :param directory: The directory to write nodes files, edge files, startup shell
        script (``startup.sh``), run script (``run_on_docker.sh``), and a Dockerfile
    :param docker_name: The name of the Docker image. Defaults to "semra"
    :param equivalence_classes: A dictionary from references to booleans, where having
        ``True`` as a value denotes that it is the "primary" reference calculated from
        processed and prioritiized mappings.

        This argument is typically used internally - you should not have to pass it
        yourself.

        .. code-block:: python

            equivalence_classes = _get_equivalence_classes(processed_mappings, prioritized_mappings)

    :param add_labels: Should labels be looked up for concepts in the database and
        added? Defaults to false. If set to true, note that this relies on PyOBO to
        download and parse potentially many large resources.
    :param startup_script_name: The name of the startup script that the Dockerfile calls
    :param run_script_name: The name of the run script that you as the user should call
        to wrap building and running the Docker image
    :param dockerfile_name: The name of the Dockerfile produced
    :param pip_install: The package that's pip installed in the docker file

    You can use this function to build your own database like in

    .. code-block:: python

        from semra.io import from_pyobo, write_neo4j

        mappings = [*from_pyobo("doid"), *from_pyobo("mesh")]
        path = "~/Desktop/disease_output/"  # assume this exist already
        write_neo4j(mappings, path)

    Then, you can run from your shell:

    .. code-block:: shell

        cd ~/Desktop/disease_output/
        sh run_on_docker.sh

    Finally, you can navigate to the Neo4j frontend at http://localhost:7474, to the
    SeMRA web frontend at http://localhost:8773, or to the SeMRA JSON API at
    http://localhost:8773/api.
    """
    directory = Path(directory).expanduser().resolve()
    directory.mkdir(exist_ok=True)

    if docker_name is None:
        docker_name = "semra"
    if equivalence_classes is None:
        equivalence_classes = {}

    # keep track of the concepts that have been written
    # as we iterate through mappings, so we don't write
    # duplicates
    seen_concepts: set[Reference] = set()

    # keep track of the CURIEs for mapping sets
    mapping_set_curies: set[str] = set()

    def _join_gzip(name: str) -> Path:
        if compress == "during":
            return directory.joinpath(name + ".gz")
        else:
            return directory.joinpath(name)

    concept_nodes_path = _join_gzip(CONCEPT_NODES_FILENAME)
    mapping_nodes_path = _join_gzip(MAPPING_NODES_FILENAME)
    evidence_nodes_path = _join_gzip(EVIDENCE_NODES_FILENAME)
    mapping_set_nodes_path = _join_gzip(MAPPING_SET_NODES_FILENAME)
    mapping_edges_path = _join_gzip(MAPPING_EDGES_FILENAME)
    edges_path = _join_gzip(EDGES_FILENAME)

    node_paths = [
        (SEMRA_NEO4J_CONCEPT_LABEL, concept_nodes_path),
        (SEMRA_NEO4J_MAPPING_LABEL, mapping_nodes_path),
        (SEMRA_NEO4J_EVIDENCE_LABEL, evidence_nodes_path),
        (SEMRA_NEO4J_MAPPING_SET_LABEL, mapping_set_nodes_path),
    ]
    edge_paths = [mapping_edges_path, edges_path]

    with (
        safe_open_writer(mapping_edges_path) as mapping_edges_writer,
        safe_open_writer(edges_path) as edge_writer,
        safe_open_writer(concept_nodes_path) as concept_nodes_writer,
        safe_open_writer(mapping_nodes_path) as mapping_nodes_writer,
        safe_open_writer(evidence_nodes_path) as evidence_nodes_writer,
        safe_open_writer(mapping_set_nodes_path) as mapping_set_writer,
    ):
        mapping_edges_writer.writerow(EDGES_HEADER)
        edge_writer.writerow(EDGES_SUPPLEMENT_HEADER)
        concept_nodes_writer.writerow(CONCEPT_NODES_HEADER)
        mapping_nodes_writer.writerow(MAPPING_NODES_HEADER)
        evidence_nodes_writer.writerow(EVIDENCE_NODES_HEADER)
        mapping_set_writer.writerow(MAPPING_SET_NODES_HEADER)

        for mapping in tqdm(
            mappings,
            unit="mapping",
            unit_scale=True,
            desc="streaming writing to Neo4j",
            disable=not use_tqdm,
        ):
            mapping_curie = mapping.curie

            if mapping.subject not in seen_concepts:
                concept_nodes_writer.writerow(
                    _concept_to_row(mapping.subject, add_labels, equivalence_classes)
                )
                seen_concepts.add(mapping.subject)
            if mapping.object not in seen_concepts:
                concept_nodes_writer.writerow(
                    _concept_to_row(mapping.object, add_labels, equivalence_classes)
                )
                seen_concepts.add(mapping.object)

            mapping_nodes_writer.writerow(_mapping_to_node_row(mapping_curie, mapping))
            mapping_edges_writer.writerow(_mapping_to_edge_row(mapping))

            # these connect the node representing the mappings to the
            # subject and object using the RDF reified edge data model
            edge_writer.writerow((mapping_curie, ANNOTATED_SOURCE_CURIE, mapping.subject.curie))
            edge_writer.writerow((mapping_curie, ANNOTATED_TARGET_CURIE, mapping.object.curie))

            for evidence in mapping.evidence:
                evidence_curie = evidence.get_reference(mapping).curie

                # this connects the mapping to its evidence
                edge_writer.writerow((mapping_curie, HAS_EVIDENCE_PREDICATE, evidence_curie))

                # this creates a node for the evidence
                evidence_nodes_writer.writerow(_evidence_to_row(evidence_curie, evidence))

                match evidence:
                    case SimpleEvidence():
                        mapping_set_curie = evidence.mapping_set.curie
                        if mapping_set_curie not in mapping_set_curies:
                            mapping_set_writer.writerow(
                                _mapping_set_to_row(mapping_set_curie, evidence.mapping_set)
                            )
                            mapping_set_curies.add(mapping_set_curie)

                        edge_writer.writerow(
                            (evidence_curie, FROM_SET_PREDICATE, mapping_set_curie)
                        )
                    case ReasonedEvidence():
                        for mmm in evidence.mappings:
                            edge_writer.writerow((evidence_curie, DERIVED_PREDICATE, mmm.curie))

                # Add authorship information for the evidence, if available
                if evidence.author:
                    if evidence.author not in seen_concepts:
                        concept_nodes_writer.writerow(
                            _concept_to_row(evidence.author, add_labels, equivalence_classes)
                        )
                        seen_concepts.add(evidence.author)

                    edge_writer.writerow(
                        (evidence_curie, HAS_AUTHOR_PREDICATE, evidence.author.curie)
                    )

    startup_path = directory.joinpath(startup_script_name)
    startup_path.write_text(
        STARTUP_TEMPLATE.render(
            python=PYTHON,
        )
    )

    if compress == "after":
        node_names = [(label, gzip_path(path).relative_to(directory)) for label, path in node_paths]
        edge_names = [gzip_path(path).relative_to(directory) for path in edge_paths]
    else:
        node_names = [(label, path.relative_to(directory)) for label, path in node_paths]
        edge_names = [path.relative_to(directory) for path in edge_paths]

    docker_path = directory.joinpath(dockerfile_name)
    docker_path.write_text(
        DOCKERFILE_TEMPLATE.render(
            node_names=node_names,
            edge_names=edge_names,
            pip_install=pip_install,
            python=PYTHON,
        )
    )

    run_path = directory.joinpath(run_script_name)
    run_path.write_text(
        RUN_ON_STARTUP_TEMPLATE.render(
            docker_name=docker_name,
            python=PYTHON,
        )
    )

    click.secho("Run Neo4j with the following:", fg="green")
    click.secho(f"  cd {run_path.parent.absolute()}")
    click.secho(f"  sh {run_script_name}")


def _neo4j_bool(b: bool, /) -> str:
    """Get a boolean string that works in neo4j data files."""
    return "true" if b else "false"


def _concept_to_row(
    concept: Reference, add_labels: bool, equivalence_classes: dict[Reference, bool]
) -> Sequence[str]:
    concept_curie = concept.curie
    if add_labels:
        name = concept.name or get_name_by_curie(concept_curie) or ""
    else:
        name = concept.name or ""
    return (
        concept_curie,
        concept.prefix,
        name,
        _neo4j_bool(equivalence_classes.get(concept, False)),
    )


def _mapping_to_node_row(mapping_curie: str, mapping: Mapping) -> Sequence[str]:
    return (
        mapping_curie,
        SEMRA_MAPPING_PREFIX,
        mapping.predicate.curie,
        get_confidence_str(mapping),
        _neo4j_bool(mapping.has_primary),
        _neo4j_bool(mapping.has_secondary),
        _neo4j_bool(mapping.has_tertiary),
    )


def _evidence_to_row(evidence_curie: str, evidence: Evidence) -> Sequence[str]:
    return (
        evidence_curie,
        SEMRA_EVIDENCE_PREFIX,
        evidence.evidence_type,
        evidence.justification.curie,
        get_confidence_str(evidence),
    )


def _mapping_to_edge_row(mapping: Mapping) -> Sequence[str]:
    return (
        mapping.subject.curie,
        mapping.predicate.curie,
        mapping.object.curie,
        get_confidence_str(mapping),
        _neo4j_bool(mapping.has_primary),
        _neo4j_bool(mapping.has_secondary),
        _neo4j_bool(mapping.has_tertiary),
        "|".join(
            sorted(
                {evidence.mapping_set.name for evidence in mapping.evidence if evidence.mapping_set}
            )
        ),
    )


def _mapping_set_to_row(mapping_set_curie: str, mapping_set: MappingSet) -> Sequence[str]:
    return (
        mapping_set_curie,
        SEMRA_MAPPING_SET_PREFIX,
        mapping_set.purl or "",
        mapping_set.name,
        mapping_set.license or "",
        mapping_set.version or "",
        get_confidence_str(mapping_set),
    )
