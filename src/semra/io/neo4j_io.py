"""I/O for Neo4j."""

from __future__ import annotations

import csv
import gzip
from pathlib import Path
from textwrap import dedent
from typing import Literal

import click
from curies import Reference
from tqdm import tqdm

from ..struct import Mapping, ReasonedEvidence
from .io_utils import get_confidence_str, get_name_by_curie

__all__ = [
    "write_neo4j",
]


def write_neo4j(
    mappings: list[Mapping],
    directory: str | Path,
    *,
    docker_name: str | None = None,
    equivalence_classes: dict[Reference, bool] | None = None,
    add_labels: bool = False,
    startup_script_name: str = "startup.sh",
    run_script_name: str = "run_on_docker.sh",
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
    :param sort: Should the output nodes files be sorted?

    :raises NotADirectoryError: If the directory given does not already exist. It's
        suggested to use :mod:`pystow` to create deterministic directories.

    You can use this function to build your own database like in

    .. code-block:: python

        from semra.io import from_pyobo

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
    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise NotADirectoryError

    startup_path = directory.joinpath(startup_script_name)
    run_path = directory.joinpath(run_script_name)
    docker_path = directory.joinpath("Dockerfile")

    concept_nodes_path = directory.joinpath("concept_nodes.tsv.gz")
    concepts: set[Reference] = set()
    concept_nodes_header = ["curie:ID", "prefix", "name", "priority:boolean"]
    if equivalence_classes is None:
        equivalence_classes = {}

    mapping_nodes_path = directory.joinpath("mapping_nodes.tsv.gz")
    mapping_nodes_header = [
        "curie:ID",
        "prefix",
        "predicate",
        "confidence",
        "primary:boolean",
        "secondary:boolean",
        "tertiary:boolean",
    ]

    evidence_nodes_path = directory.joinpath("evidence_nodes.tsv.gz")
    evidences = {}
    evidence_nodes_header = [
        "curie:ID",
        "prefix",
        "type",
        "mapping_justification",
        "confidence:float",
    ]

    mapping_set_nodes_path = directory.joinpath("mapping_set_nodes.tsv.gz")
    mapping_sets = {}
    mapping_set_nodes_header = [
        "curie:ID",
        "prefix",
        "name",
        "license",
        "version",
        "confidence:float",
    ]

    mapping_edges_path = directory.joinpath("mapping_edges.tsv.gz")
    edges_header = [
        ":START_ID",
        ":TYPE",
        ":END_ID",
        "confidence:float",
        "primary:boolean",
        "secondary:boolean",
        "tertiary:boolean",
        "mapping_sets:string[]",
    ]
    edges_path = directory.joinpath("edges.tsv.gz")
    edges_supp_header = [
        ":START_ID",
        ":TYPE",
        ":END_ID",
    ]
    with gzip.open(mapping_edges_path, "wt") as file1, gzip.open(edges_path, "wt") as file2:
        mapping_writer = csv.writer(file1, delimiter="\t")
        mapping_writer.writerow(edges_header)

        edge_writer = csv.writer(file2, delimiter="\t")
        edge_writer.writerow(edges_supp_header)

        for mapping in tqdm(mappings, unit="mapping", unit_scale=True, desc="Preparing Neo4j"):
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
        concept_nodes_header,
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
        mapping_nodes_header,
        (
            (
                mapping.curie,
                "semra.mapping",
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
        mapping_set_nodes_header,
        (
            (
                mapping_set.curie,
                "semra.mappingset",
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
        evidence_nodes_header,
        (
            (
                evidence.curie,
                "semra.evidence",
                evidence.evidence_type,
                evidence.justification.curie,
                get_confidence_str(evidence),
            )
            for evidence in tqdm(
                sorted_evidences,
                desc="Writing evidence nodes",
                leave=False,
                unit_scale=True,
                unit="evidence",
            )
        ),
    )

    startup_commands = dedent(
        """\
        #!/bin/bash
        neo4j start

        # Get the port
        until [ "$(curl -s -w '%{http_code}' -o /dev/null "http://localhost:7474")" -eq 200 ]
        do
          sleep 5
        done

        neo4j status
        python3.11 -m uvicorn --host 0.0.0.0 --port 8773 --factory semra.wsgi:get_app
    """
    )
    startup_path.write_text(startup_commands)

    docker_commands = dedent(
        """\
        FROM ubuntu:20.04

        WORKDIR /sw

        # Install and configure neo4j and python environment
        RUN apt-get update && \\
            apt-get install -y apt-transport-https ca-certificates curl wget software-properties-common && \\
            curl -fsSL https://debian.neo4j.com/neotechnology.gpg.key | apt-key add - && \\
            add-apt-repository "deb https://debian.neo4j.com stable 4.4" && \\
            apt-get install -y neo4j

        # Install python
        RUN apt-get update && \\
            add-apt-repository ppa:deadsnakes/ppa && \\
            apt-get install -y git zip unzip bzip2 gcc pkg-config python3.11 && \\
            curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

        RUN python3.11 -m pip install "semra[web] @ git+https://github.com/biopragmatics/semra.git"

        # Add graph content
        COPY concept_nodes.tsv.gz /sw/concept_nodes.tsv.gz
        COPY mapping_nodes.tsv.gz /sw/mapping_nodes.tsv.gz
        COPY evidence_nodes.tsv.gz /sw/evidence_nodes.tsv.gz
        COPY mapping_set_nodes.tsv.gz /sw/mapping_set_nodes.tsv.gz
        COPY mapping_edges.tsv.gz /sw/mapping_edges.tsv.gz
        COPY edges.tsv.gz /sw/edges.tsv.gz

        # Ingest graph content into neo4j
        RUN sed -i 's/#dbms.default_listen_address/dbms.default_listen_address/' /etc/neo4j/neo4j.conf && \\
            sed -i 's/#dbms.security.auth_enabled/dbms.security.auth_enabled/' /etc/neo4j/neo4j.conf && \\
            neo4j-admin import --delimiter='TAB' --skip-duplicate-nodes=true --skip-bad-relationships=true \\
                --relationships /sw/mapping_edges.tsv \\
                --relationships /sw/edges.tsv \\
                --nodes=concept=/sw/concept_nodes.tsv \\
                --nodes=mapping=/sw/mapping_nodes.tsv \\
                --nodes=mappingset=/sw/mapping_set_nodes.tsv \\
                --nodes=evidence=/sw/evidence_nodes.tsv

        RUN rm /sw/concept_nodes.tsv.gz
        RUN rm /sw/mapping_nodes.tsv.gz
        RUN rm /sw/evidence_nodes.tsv.gz
        RUN rm /sw/mapping_set_nodes.tsv.gz
        RUN rm /sw/edges.tsv.gz
        RUN rm /sw/mapping_edges.tsv.gz

        COPY startup.sh startup.sh
        ENTRYPOINT ["/bin/bash", "/sw/startup.sh"]
    """
    )
    docker_path.write_text(docker_commands)

    if docker_name is None:
        docker_name = "semra"
    run_command = dedent(
        f"""\
        #!/bin/bash
        docker build --tag {docker_name} .
        # -t means allocate a pseudo-TTY, necessary to keep it running in the background
        docker run -t --detach -p 7474:7474 -p 7687:7687 -p 8773:8773 --name {docker_name} {docker_name}:latest
    """
    )
    run_path.write_text(run_command)
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


def _neo4j_bool(b: bool, /) -> Literal["true", "false"]:
    return "true" if b else "false"  # type:ignore


ANNOTATED_PROPERTY = Reference(prefix="owl", identifier="annotatedProperty")
ANNOTATED_SOURCE = Reference(prefix="owl", identifier="annotatedSource")
ANNOTATED_TARGET = Reference(prefix="owl", identifier="annotatedTarget")


#: The predicate used in the graph data model connecting a mapping node to an evidence node
#: The predicate used in the graph data model connecting an evidence node to a mapping set node
#: The predicate used in the graph data model connecting a reasoned evidence
#: node to the mapping node(s) from which it was derived

HAS_EVIDENCE_PREDICATE = "hasEvidence"
FROM_SET_PREDICATE = "fromSet"
DERIVED_PREDICATE = "derivedFromMapping"
HAS_AUTHOR_PREDICATE = "hasAuthor"


def _write_tsv_gz(path, header, rows) -> None:
    click.echo(f"writing to {path}")
    with gzip.open(path, "wt") as file:
        writer = csv.writer(file, delimiter="\t")
        writer.writerow(header)
        writer.writerows(rows)
