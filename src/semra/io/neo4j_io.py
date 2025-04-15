"""I/O for Neo4j."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

import click
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pyobo import Reference
from tqdm import tqdm

from .io_utils import get_confidence_str, get_name_by_curie, safe_open_writer
from ..struct import Evidence, Mapping, MappingSet, ReasonedEvidence, SimpleEvidence

__all__ = [
    "write_neo4j",
]

HERE = Path(__file__).parent.resolve()

TEMPLATES = HERE.joinpath("templates")
JINJA_ENV = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape())
STARTUP_TEMPLATE = JINJA_ENV.get_template("startup.sh")
DOCKERFILE_TEMPLATE = JINJA_ENV.get_template("Dockerfile")
RUN_ON_STARTUP_TEMPLATE = JINJA_ENV.get_template("run_on_startup.sh")

SEMRA_MAPPING_PREFIX = "semra.mapping"
SEMRA_MAPPING_SET_PREFIX = "semra.mappingset"
SEMRA_EVIDENCE_PREFIX = "semra.evidence"

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
    sort: bool = False,
) -> None:
    """Write all files needed to construct a Neo4j graph database from a set of mappings.

    :param mappings: A list of semantic mappings
    :param directory: The directory to write nodes files, edge files, startup shell
        script (``startup.sh``), run script (``run_on_docker.sh``), and a Dockerfile
    :param docker_name: The name of the Docker image. Defaults to "semra"
    :param equivalence_classes: A dictionary of equivalence classes, calculated from
        processed and prioritized mappings. This argument is typically used internally.

        .. code-block:: python

            equivalence_classes = _get_equivalence_classes(processed_mappings, prioritized_mappings)

    :param add_labels: Should labels be looked up for concepts in the database and
        added? Defaults to false. If set to true, note that this relies on PyOBO to
        download and parse potentially many large resources.
    :param startup_script_name: The name of the startup script that the Dockerfile calls
    :param run_script_name: The name of the run script that you as the user should call
        to wrap building and running the Docker image
    :param dockerfile_name: The name of the Dockerfile produced
    :param sort: Should the output nodes files be sorted?

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

    concept_nodes_path = directory.joinpath("concept_nodes.tsv")
    mapping_nodes_path = directory.joinpath("mapping_nodes.tsv")
    evidence_nodes_path = directory.joinpath("evidence_nodes.tsv")
    mapping_set_nodes_path = directory.joinpath("mapping_set_nodes.tsv")
    mapping_edges_path = directory.joinpath("mapping_edges.tsv")
    edges_path = directory.joinpath("edges.tsv")

    node_paths = [
        ("concept", concept_nodes_path),
        ("mapping", mapping_nodes_path),
        ("evidence", evidence_nodes_path),
        ("mappingset", mapping_set_nodes_path),
    ]
    node_names = [
        (a, n.relative_to(directory)) for a, n in node_paths
    ]
    edge_paths = [mapping_edges_path, edges_path]
    edge_names = [n.relative_to(directory) for n in edge_paths]

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
            mappings, unit="mapping", unit_scale=True, desc="streaming writing to Neo4j"
        ):
            mapping_curie = mapping.curie

            if mapping.s not in seen_concepts:
                concept_nodes_writer.writerow(
                    _concept_to_row(mapping.s, add_labels, equivalence_classes)
                )
                seen_concepts.add(mapping.s)
            if mapping.o not in seen_concepts:
                concept_nodes_writer.writerow(
                    _concept_to_row(mapping.o, add_labels, equivalence_classes)
                )
                seen_concepts.add(mapping.o)

            mapping_nodes_writer.writerow(_mapping_to_node_row(mapping_curie, mapping))
            mapping_edges_writer.writerow(_mapping_to_edge_row(mapping))

            # these connect the node representing the mappings to the
            # subject and object using the RDF reified edge data model
            edge_writer.writerow((mapping_curie, ANNOTATED_SOURCE_CURIE, mapping.s.curie))
            edge_writer.writerow((mapping_curie, ANNOTATED_TARGET_CURIE, mapping.o.curie))

            for evidence in mapping.evidence:
                evidence_curie = evidence.curie

                # this connects the mapping to its evidence
                edge_writer.writerow((mapping_curie, HAS_EVIDENCE_PREDICATE, evidence_curie))

                # this creates a node for the evidence
                evidence_nodes_writer.writerow(_evidence_to_row(evidence_curie, evidence))

                match evidence:
                    case SimpleEvidence():
                        if evidence.mapping_set:
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
    startup_path.write_text(STARTUP_TEMPLATE.render())

    # TODO flag for swapping on version of semra / git installation
    docker_path = directory.joinpath(dockerfile_name)
    docker_path.write_text(DOCKERFILE_TEMPLATE.render(
        node_names=node_names,
        edge_names=edge_names,
    ))

    run_path = directory.joinpath(run_script_name)
    run_path.write_text(RUN_ON_STARTUP_TEMPLATE.render(docker_name=docker_name))

    click.secho("Run Neo4j with the following:", fg="green")
    click.secho(f"  cd {run_path.parent.absolute()}")
    click.secho(f"  sh {run_script_name}")

    # shell_command = dedent(f"""\
    #     neo4j-admin database import full \\
    #         --delimiter='TAB' \\
    #         --skip-duplicate-nodes=true \\
    #         --overwrite-destination=true \\
    #         --skip-bad-relationships=true \\
    #         --nodes {nodes_path.as_posix()} \\
    #         --relationships  {edges_path.as_posix()} \\
    #         neo4j
    # """)
    # command_path.write_text(shell_command)


def _neo4j_bool(b: bool, /) -> str:
    """Get a boolean string that works in neo4j data files."""
    return "true" if b else "false"  # type:ignore


def _concept_to_row(
    concept: Reference, add_labels: bool, equivalence_classes: dict[Reference, bool]
) -> Sequence[str]:
    return (
        concept.curie,
        concept.prefix,
        get_name_by_curie(concept.curie) or "" if add_labels else "",
        _neo4j_bool(equivalence_classes.get(concept, False)),
    )


def _mapping_to_node_row(mapping_curie: str, mapping: Mapping) -> Sequence[str]:
    return (
        mapping_curie,
        SEMRA_MAPPING_PREFIX,
        mapping.p.curie,
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
        mapping.s.curie,
        mapping.p.curie,
        mapping.o.curie,
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
        mapping_set.name,
        mapping_set.license or "",
        mapping_set.version or "",
        get_confidence_str(mapping_set),
    )
