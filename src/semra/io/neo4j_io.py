"""I/O for Neo4j."""

from __future__ import annotations

import csv
import json
from collections.abc import Hashable, Iterable, Sequence
from pathlib import Path

import click
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pyobo import Reference
from tqdm import tqdm

from .io_utils import get_confidence_str, get_name_by_curie
from ..struct import Evidence, Mapping, MappingSet, ReasonedEvidence

__all__ = [
    "write_neo4j",
]

HERE = Path(__file__).parent.resolve()

TEMPLATES = HERE.joinpath("templates")
# STARTUP_PATH = TEMPLATES.joinpath("startup.sh")
# DOCKERFILE_PATH = TEMPLATES.joinpath("Dockerfile")
# RUN_ON_STARTUP_PATH = TEMPLATES.joinpath("run_on_startup.sh")

env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape())

STARTUP_TEMPLATE = env.get_template("startup.sh")
DOCKERFILE_TEMPLATE = env.get_template("Dockerfile")
RUN_ON_STARTUP_TEMPLATE = env.get_template("run_on_startup.sh")

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

ANNOTATED_PROPERTY = Reference(prefix="owl", identifier="annotatedProperty")
ANNOTATED_SOURCE = Reference(prefix="owl", identifier="annotatedSource")
ANNOTATED_TARGET = Reference(prefix="owl", identifier="annotatedTarget")

#: The predicate used in the graph data model connecting a mapping node to an evidence node
HAS_EVIDENCE_PREDICATE = "hasEvidence"
#: The predicate used in the graph data model connecting an evidence node to a mapping set node
FROM_SET_PREDICATE = "fromSet"
#: The predicate used in the graph data model connecting a reasoned evidence
DERIVED_PREDICATE = "derivedFromMapping"
#: node to the mapping node(s) from which it was derived
HAS_AUTHOR_PREDICATE = "hasAuthor"

mapping_nodes_filename = "mapping_nodes.tsv"
evidence_nodes_filename = "evidence_nodes.tsv"
mapping_set_nodes_filename = "mapping_set_nodes.tsv"
mapping_edges_filename = "mapping_edges.tsv"
edges_filename = "edges.tsv"
concept_nodes_filename = "concept_nodes.tsv"


def _concept_to_row(concept, add_labels, equivalence_classes):
    return (
        concept.curie,
        concept.prefix,
        get_name_by_curie(concept.curie) or "" if add_labels else "",
        _neo4j_bool(equivalence_classes.get(concept, False)),
    )


def stream_to_neo4j(
    directory,
    mappings_jsonl_path,
    equivalence_classes,
    add_labels: bool = False,
    startup_script_name: str = "startup.sh",
    run_script_name: str = "run_on_docker.sh",
    dockerfile_name: str = "Dockerfile",
    docker_name: str | None = None,
):
    """Stream a SeMRA JSONL file to Neo4j.

    :param mappings_jsonl_path: The path to the SeMRA JSONL file
    """
    if docker_name is None:
        docker_name = "semra"
    mapping_edges_path = directory.joinpath(mapping_edges_filename)
    edges_path = directory.joinpath(edges_filename)
    evidence_nodes_path = directory.joinpath(evidence_nodes_filename)
    concept_nodes_path = directory.joinpath(concept_nodes_filename)
    mapping_nodes_path = directory.joinpath(mapping_nodes_filename)
    mapping_sets: dict[str, MappingSet] = {}

    with (
        open(mappings_jsonl_path) as file,
        open(mapping_edges_path, "w") as file1,
        open(edges_path, "w") as file2,
        open(evidence_nodes_path, "w") as file3,
        open(mapping_nodes_path, "w") as file4,
        open(concept_nodes_path, "w") as file5,
    ):
        mapping_edge_writer = csv.writer(file1, delimiter="\t")
        mapping_edge_writer.writerow(EDGES_HEADER)

        edge_writer = csv.writer(file2, delimiter="\t")
        edge_writer.writerow(EDGES_SUPPLEMENT_HEADER)

        evidence_writer = csv.writer(file3, delimiter="\t")
        evidence_writer.writerow(EVIDENCE_NODES_HEADER)

        mapping_nodes_writer = csv.writer(file4, delimiter="\t")
        mapping_nodes_writer.writerow(MAPPING_NODES_HEADER)

        concept_nodes_writer = csv.writer(file5, delimiter="\t")
        concept_nodes_writer.writerow(CONCEPT_NODES_HEADER)

        seen_concepts = set()

        for line in tqdm(
            file,
            unit="mapping",
            unit_scale=True,
            desc="Streaming mappings into neo4j",
            total=43000000,
        ):
            mapping = Mapping.model_validate(json.loads(line), strict=False)

            if mapping.s.curie not in seen_concepts:
                concept_nodes_writer.writerow(
                    _concept_to_row(mapping.s, add_labels, equivalence_classes)
                )
                seen_concepts.add(mapping.s.curie)
            if mapping.o.curie not in seen_concepts:
                concept_nodes_writer.writerow(
                    _concept_to_row(mapping.o, add_labels, equivalence_classes)
                )
                seen_concepts.add(mapping.o.curie)

            mapping_edge_writer.writerow(
                (
                    mapping.s.curie,
                    mapping.p.curie,
                    mapping.o.curie,
                    get_confidence_str(mapping),
                    _neo4j_bool(mapping.has_primary),
                    _neo4j_bool(mapping.has_secondary),
                    _neo4j_bool(mapping.has_tertiary),
                    "|".join(
                        sorted(
                            {
                                evidence.mapping_set.name
                                for evidence in mapping.evidence
                                if evidence.mapping_set
                            }
                        )
                    ),
                )
            )
            edge_writer.writerow((mapping.curie, ANNOTATED_SOURCE.curie, mapping.s.curie))
            edge_writer.writerow((mapping.curie, ANNOTATED_TARGET.curie, mapping.o.curie))

            mapping_nodes_writer.writerow(
                (
                    mapping.curie,
                    SEMRA_MAPPING_PREFIX,
                    mapping.p.curie,
                    get_confidence_str(mapping),
                    _neo4j_bool(mapping.has_primary),
                    _neo4j_bool(mapping.has_secondary),
                    _neo4j_bool(mapping.has_tertiary),
                )
            )

            for evidence in mapping.evidence:
                evidence_curie = evidence.get_curie_with_mapping(mapping)
                edge_writer.writerow((mapping.curie, HAS_EVIDENCE_PREDICATE, evidence_curie))
                if evidence.mapping_set:
                    mapping_sets[evidence.mapping_set.name] = evidence.mapping_set
                    edge_writer.writerow(
                        (evidence_curie, FROM_SET_PREDICATE, evidence.mapping_set.curie)
                    )
                elif isinstance(evidence, ReasonedEvidence):
                    for mmm in evidence.mappings:
                        edge_writer.writerow((evidence_curie, DERIVED_PREDICATE, mmm.curie))
                # elif isinstance(evidence, SimpleEvidence):
                #     pass
                # else:
                #     raise TypeError

                # Add authorship information for the evidence, if available
                if evidence.author:
                    if evidence.author.curie not in seen_concepts:
                        concept_nodes_writer.writerow(
                            _concept_to_row(evidence.author, add_labels, equivalence_classes)
                        )
                        seen_concepts.add(evidence.author.curie)
                    edge_writer.writerow(
                        (evidence_curie, HAS_AUTHOR_PREDICATE, evidence.author.curie)
                    )
                evidence_writer.writerow(
                    (
                        evidence_curie,
                        SEMRA_EVIDENCE_PREFIX,
                        evidence.evidence_type,
                        evidence.justification.curie,
                        get_confidence_str(evidence),
                    )
                )

    # Dump all mapping set nodes
    mapping_set_nodes_path = directory.joinpath(mapping_set_nodes_filename)
    _write_tsv_gz(
        mapping_set_nodes_path,
        MAPPING_SET_NODES_HEADER,
        (
            (
                mapping_set.curie,
                SEMRA_MAPPING_SET_PREFIX,
                mapping_set.name,
                mapping_set.license or "",
                mapping_set.version or "",
                get_confidence_str(mapping_set),
            )
            for mapping_set in mapping_sets.values()
        ),
    )

    startup_path = directory.joinpath(startup_script_name)
    startup_path.write_text(STARTUP_TEMPLATE.render())

    # TODO flag for swapping on version of semra / git installation
    docker_path = directory.joinpath(dockerfile_name)
    docker_path.write_text(DOCKERFILE_TEMPLATE.render())

    run_path = directory.joinpath(run_script_name)
    run_path.write_text(RUN_ON_STARTUP_TEMPLATE.render(docker_name=docker_name))

    click.secho("Run Neo4j with the following:", fg="green")
    click.secho(f"  cd {run_path.parent.absolute()}")
    click.secho(f"  sh {run_script_name}")


def write_neo4j(
    mappings: list[Mapping],
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

    concept_nodes_path = directory.joinpath(concept_nodes_filename)
    concepts: set[Reference] = set()

    evidences: dict[Hashable, Evidence] = {}
    mapping_sets: dict[str, MappingSet] = {}

    mapping_nodes_path = directory.joinpath(mapping_nodes_filename)
    evidence_nodes_path = directory.joinpath(evidence_nodes_filename)
    mapping_set_nodes_path = directory.joinpath(mapping_set_nodes_filename)
    mapping_edges_path = directory.joinpath(mapping_edges_filename)
    edges_path = directory.joinpath(edges_filename)

    with open(mapping_edges_path, "w") as file1, open(edges_path, "w") as file2:
        mapping_writer = csv.writer(file1, delimiter="\t")
        mapping_writer.writerow(EDGES_HEADER)

        edge_writer = csv.writer(file2, delimiter="\t")
        edge_writer.writerow(EDGES_SUPPLEMENT_HEADER)

        for mapping in tqdm(mappings, unit="mapping", unit_scale=True, desc="preparing Neo4j"):
            concepts.add(mapping.s)
            concepts.add(mapping.o)

            mapping_writer.writerow(
                (
                    mapping.s.curie,
                    mapping.p.curie,
                    mapping.o.curie,
                    get_confidence_str(mapping),
                    _neo4j_bool(mapping.has_primary),
                    _neo4j_bool(mapping.has_secondary),
                    _neo4j_bool(mapping.has_tertiary),
                    "|".join(
                        sorted(
                            {
                                evidence.mapping_set.name
                                for evidence in mapping.evidence
                                if evidence.mapping_set
                            }
                        )
                    ),
                )
            )
            edge_writer.writerow((mapping.curie, ANNOTATED_SOURCE.curie, mapping.s.curie))
            edge_writer.writerow((mapping.curie, ANNOTATED_TARGET.curie, mapping.o.curie))
            for evidence in mapping.evidence:
                edge_writer.writerow((mapping.curie, HAS_EVIDENCE_PREDICATE, evidence.curie))
                evidences[evidence.key()] = evidence
                if evidence.mapping_set:
                    mapping_sets[evidence.mapping_set.name] = evidence.mapping_set
                    edge_writer.writerow(
                        (evidence.curie, FROM_SET_PREDICATE, evidence.mapping_set.curie)
                    )
                elif isinstance(evidence, ReasonedEvidence):
                    for mmm in evidence.mappings:
                        edge_writer.writerow((evidence.curie, DERIVED_PREDICATE, mmm.curie))
                # elif isinstance(evidence, SimpleEvidence):
                #     pass
                # else:
                #     raise TypeError

                # Add authorship information for the evidence, if available
                if evidence.author:
                    concepts.add(evidence.author)
                    edge_writer.writerow(
                        (evidence.curie, HAS_AUTHOR_PREDICATE, evidence.author.curie)
                    )

    sorted_concepts = sorted(concepts, key=lambda n: n.curie) if sort else list(concepts)
    _write_tsv_gz(
        concept_nodes_path,
        CONCEPT_NODES_HEADER,
        (
            (
                concept.curie,
                concept.prefix,
                get_name_by_curie(concept.curie) or "" if add_labels else "",
                _neo4j_bool(equivalence_classes.get(concept, False)),
            )
            for concept in tqdm(
                sorted_concepts, desc="writing concept nodes", unit_scale=True, unit="concept"
            )
        ),
    )

    sorted_mappings = sorted(mappings, key=lambda n: n.curie) if sort else mappings
    _write_tsv_gz(
        mapping_nodes_path,
        MAPPING_NODES_HEADER,
        (
            (
                mapping.curie,
                SEMRA_MAPPING_PREFIX,
                mapping.p.curie,
                get_confidence_str(mapping),
                _neo4j_bool(mapping.has_primary),
                _neo4j_bool(mapping.has_secondary),
                _neo4j_bool(mapping.has_tertiary),
            )
            for mapping in tqdm(
                sorted_mappings, desc="writing mapping nodes", unit_scale=True, unit="mapping"
            )
        ),
    )

    sorted_mapping_sets = (
        sorted(mapping_sets.values(), key=lambda n: n.curie)
        if sort
        else list(mapping_sets.values())
    )
    _write_tsv_gz(
        mapping_set_nodes_path,
        MAPPING_SET_NODES_HEADER,
        (
            (
                mapping_set.curie,
                SEMRA_MAPPING_SET_PREFIX,
                mapping_set.name,
                mapping_set.license or "",
                mapping_set.version or "",
                get_confidence_str(mapping_set),
            )
            for mapping_set in sorted_mapping_sets
        ),
    )

    sorted_evidences = (
        sorted(evidences.values(), key=lambda row: row.curie) if sort else list(evidences.values())
    )
    _write_tsv_gz(
        evidence_nodes_path,
        EVIDENCE_NODES_HEADER,
        (
            (
                evidence.curie,
                SEMRA_EVIDENCE_PREFIX,
                evidence.evidence_type,
                evidence.justification.curie,
                get_confidence_str(evidence),
            )
            for evidence in tqdm(
                sorted_evidences,
                desc="writing evidence nodes",
                leave=False,
                unit_scale=True,
                unit="evidence",
            )
        ),
    )

    # TODO: Gzip all the dumped files

    startup_path = directory.joinpath(startup_script_name)
    startup_path.write_text(STARTUP_TEMPLATE.render())

    # TODO flag for swapping on version of semra / git installation
    docker_path = directory.joinpath(dockerfile_name)
    docker_path.write_text(DOCKERFILE_TEMPLATE.render())

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


def _write_tsv_gz(path: str | Path, header: Sequence[str], rows: Iterable[Sequence[str]]) -> None:
    click.echo(f"writing to {path}")
    with open(path, "w") as file:
        writer = csv.writer(file, delimiter="\t")
        writer.writerow(header)
        writer.writerows(rows)
