from __future__ import annotations

import importlib.metadata
import logging
import pickle
from pathlib import Path
from textwrap import dedent
from typing import TextIO

import bioontologies
import bioregistry
import bioversions
import click
import pandas as pd
import pyobo
import pyobo.utils
from tqdm.auto import tqdm

from semra.rules import DB_XREF, MANUAL_MAPPING
from semra.struct import Evidence, Mapping, MappingSet, ReasonedEvidence, Reference, SimpleEvidence

__all__ = [
    "from_cache_df",
    "from_biomappings",
    "from_pyobo",
    "from_bioontologies",
    "from_sssom",
    #
    "get_sssom_df",
    "write_sssom",
    "write_pickle",
    "write_neo4j",
]

logger = logging.getLogger(__name__)


def from_biomappings(mapping_dicts, confidence: float = 0.999) -> list[Mapping]:
    biomappings_version = importlib.metadata.version("biomappings")
    rv = []
    for mapping_dict in tqdm(mapping_dicts, unit_scale=True, unit="mapping", desc="Loading biomappings", leave=False):
        try:
            p = Reference.from_curie(mapping_dict["relation"])
        except ValueError:
            continue  # TODO fix speciesSpecific
        source_prefix = mapping_dict["source prefix"]
        source_identifier = bioregistry.standardize_identifier(source_prefix, mapping_dict["source identifier"])
        target_prefix = mapping_dict["target prefix"]
        target_identifier = bioregistry.standardize_identifier(target_prefix, mapping_dict["target identifier"])
        author = Reference.from_curie(mapping_dict["source"])
        mm = Mapping(
            s=Reference(prefix=source_prefix, identifier=source_identifier),
            p=p,
            o=Reference(prefix=target_prefix, identifier=target_identifier),
            evidence=[
                SimpleEvidence(
                    justification=Reference.from_curie(mapping_dict["type"]),
                    mapping_set=MappingSet(
                        name="biomappings", confidence=confidence, license="CC0", version=biomappings_version
                    ),
                    author=author,
                    # TODO configurable confidence globally per author or based on author's self-reported confidence
                )
            ],
        )
        rv.append(mm)
    return rv


def _safe_get_version(prefix: str) -> str | None:
    try:
        return bioversions.get_version(prefix)
    except (KeyError, TypeError):
        return None


def _from_pyobo_prefix(
    source_prefix: str,
    *,
    confidence=None,
    standardize: bool = False,
    version: str | None = None,
    license: str | None = None,
    **kwargs,
) -> list[Mapping]:
    if not version:
        version = _safe_get_version(source_prefix)
    if not license:
        license = bioregistry.get_license(source_prefix)
    logger.debug("loading mappings with PyOBO from %s v%s", source_prefix, version)
    df = pyobo.get_xrefs_df(source_prefix, version=version, **kwargs)
    return _from_df(
        df,
        source_prefix=source_prefix,
        standardize=standardize,
        confidence=confidence,
        version=version,
        license=license,
    )


def _from_pyobo_pair(
    source_prefix: str,
    target_prefix: str,
    *,
    confidence=None,
    version: str | None = None,
    license: str | None = None,
    **kwargs,
) -> list[Mapping]:
    if not version:
        version = _safe_get_version(source_prefix)
    if not license:
        license = bioregistry.get_license(source_prefix)
    logger.debug("loading mappings with PyOBO from %s v%s", source_prefix, version)
    df = pyobo.get_xrefs(source_prefix, target_prefix, version=version, **kwargs)
    mappings = [
        Mapping(
            s=Reference(
                prefix=source_prefix,
                identifier=bioregistry.standardize_identifier(source_prefix, source_id),
            ),
            p=DB_XREF,
            o=Reference(
                prefix=target_prefix,
                identifier=bioregistry.standardize_identifier(target_prefix, target_id),
            ),
            evidence=[
                SimpleEvidence(
                    justification=MANUAL_MAPPING,
                    mapping_set=MappingSet(name=source_prefix, confidence=confidence, version=version, license=license),
                )
            ],
        )
        for source_id, target_id in df.items()
    ]
    return mappings


def from_cache_df(
    path,
    source_prefix: str,
    *,
    prefixes=None,
    predicate: Reference | None = None,
    standardize: bool = True,
    version: str | None = None,
    license: str | None = None,
    confidence: float | None = None,
) -> list[Mapping]:
    logger.info("loading cached dataframe from PyOBO for %s", source_prefix)
    df = pd.read_csv(path, sep="\t")
    if prefixes:
        df = df[df[df.columns[1]].isin(prefixes)]
    return _from_df(
        df,
        source_prefix=source_prefix,
        predicate=predicate,
        standardize=standardize,
        version=version,
        license=license,
        confidence=confidence,
    )


def _from_df(
    df,
    source_prefix,
    predicate: Reference | None = None,
    *,
    confidence: float | None = None,
    standardize: bool = False,
    version: str | None = None,
    license: str | None = None,
    leave_progress: bool = False,
) -> list[Mapping]:
    if predicate is None:
        predicate = DB_XREF
    rv = []
    if standardize:
        df[df.columns[0]] = df[df.columns[0]].map(lambda s: bioregistry.standardize_identifier(source_prefix, s))
        df[df.columns[2]] = [
            bioregistry.standardize_identifier(target_prefix, target_id)
            for target_prefix, target_id in df[df.columns[1:]].values
        ]
    for source_id, target_prefix, target_id in tqdm(
        df.values, desc=f"Loading {source_prefix}", unit_scale=True, leave=leave_progress
    ):
        rv.append(
            Mapping(
                s=Reference(
                    prefix=source_prefix,
                    identifier=source_id,
                ),
                p=predicate,
                o=Reference(
                    prefix=target_prefix,
                    identifier=target_id,
                ),
                evidence=[
                    SimpleEvidence(
                        mapping_set=MappingSet(
                            name=source_prefix, version=version, confidence=confidence, license=license
                        ),
                        justification=MANUAL_MAPPING,
                    ),
                ],
            )
        )
    return rv


def from_pyobo(prefix: str, target_prefix: str | None = None, *, standardize: bool = False, **kwargs) -> list[Mapping]:
    if target_prefix:
        return _from_pyobo_pair(prefix, target_prefix, standardize=standardize, **kwargs)
    return _from_pyobo_prefix(prefix, standardize=standardize, **kwargs)


def from_bioontologies(prefix: str, confidence=None, **kwargs) -> list[Mapping]:
    """Load xrefs from a given ontology."""
    o = bioontologies.get_obograph_by_prefix(prefix, **kwargs)
    g = o.guess(prefix)
    # note that we don't extract stuff from edges so just node standardization is good enough
    for node in tqdm(g.nodes, desc=f"[{prefix}] standardizing", unit="node", unit_scale=True, leave=False):
        node.standardize()
    br_license = bioregistry.get_license(prefix)
    return [
        Mapping.from_triple(
            triple,
            evidence=[
                SimpleEvidence(
                    justification=MANUAL_MAPPING,
                    mapping_set=MappingSet(name=prefix, version=g.version, confidence=confidence, license=br_license),
                )
            ],
        )
        for triple in tqdm(g.get_xrefs(), unit="mapping", unit_scale=True, leave=False)
        if triple[0].prefix == prefix
    ]


def from_sssom(path, mapping_set_name) -> list[Mapping]:
    df = pd.read_csv(path, sep="\t", dtype=str)
    columns = [
        "subject_id",
        "predicate_id",
        "object_id",
        "mapping_justification",
        # TODO add more
    ]
    rv = []
    for s, p, o, justification, *_ in df[columns].values:
        rv.append(
            Mapping(
                s=Reference.from_curie(s),
                p=Reference.from_curie(p),
                o=Reference.from_curie(o),
                evidence=[
                    SimpleEvidence(
                        justification=Reference.from_curie(justification), mapping_set=MappingSet(name=mapping_set_name)
                    )
                ],
            )
        )
    return rv


def get_sssom_df(mappings: list[Mapping], *, add_labels: bool = False) -> pd.DataFrame:
    """Get a SSSOM dataframe.

    Automatically prunes columns that aren't filled out.

    :param mappings: A list of mappings
    :param add_labels: Should labels be added for source and object via :func:`pyobo.get_name_by_curie`?
    :return: A SSSOM dataframe in Pandas
    """
    rows = [
        _get_sssom_row(m, e)
        for m in tqdm(mappings, desc="Preparing SSSOM", leave=False, unit="mapping", unit_scale=True)
        for e in m.evidence
    ]
    columns = [
        "subject_id",
        "predicate_id",
        "object_id",
        "mapping_justification",
        "mapping_set",
        "mapping_set_version",
        "mapping_set_license",
        "mapping_set_confidence",
        "author_id",
        "comments",
    ]
    df = pd.DataFrame(rows, columns=columns)
    if add_labels:
        for label_column, id_column in [("subject_label", "subject_id"), ("object_label", "object_id")]:
            df[label_column] = df[id_column].map(pyobo.get_name_by_curie)  # type:ignore
        df = df[
            [
                "subject_id",
                "subject_label",
                "predicate_id",
                "object_id",
                "object_label",
                "mapping_justification",
                "mapping_set",
                "mapping_set_version",
                "mapping_set_license",
                "mapping_set_confidence",
                "author_id",
                "comments",
            ]
        ]

    # remove empty columns
    for column in df.columns:
        if not df[column].map(bool).any():
            del df[column]

    return df


def _get_sssom_row(mapping: Mapping, e: Evidence):
    # TODO increase this
    if isinstance(e, SimpleEvidence):
        mapping_set_version = e.mapping_set.version
        mapping_set_license = e.mapping_set.license
    elif isinstance(e, ReasonedEvidence):
        mapping_set_version = ""
        mapping_set_license = ""
    else:
        raise TypeError
    return (
        mapping.s.curie,
        mapping.p.curie,
        mapping.o.curie,
        e.justification.curie if e.justification else "",
        ",".join(sorted(e.mapping_set_names)),
        mapping_set_version,
        mapping_set_license,
        round(confidence, 4) if (confidence := e.confidence) is not None else "",
        e.author.curie if e.author else "",
        e.explanation,
    )


def write_sssom(mappings: list[Mapping], file: str | Path | TextIO) -> None:
    """Export mappings as an SSSOM file (may be lossy)."""
    df = get_sssom_df(mappings)
    df.to_csv(file, sep="\t", index=False)


def write_pickle(mappings: list[Mapping], path: str | Path) -> None:
    """Write the mappings as a pickle."""
    path = Path(path).resolve()
    path.write_bytes(pickle.dumps(mappings, protocol=pickle.HIGHEST_PROTOCOL))


ANNOTATED_PROPERTY = Reference(prefix="owl", identifier="annotatedProperty")
ANNOTATED_SOURCE = Reference(prefix="owl", identifier="annotatedSource")
ANNOTATED_TARGET = Reference(prefix="owl", identifier="annotatedTarget")


def _edge_key(t):
    s, p, o, c = t
    return s, p, o, 1 if isinstance(c, float) else 0, t


def write_neo4j(mappings: list[Mapping], directory: str | Path, docker_name: str | None = None) -> None:
    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise NotADirectoryError

    startup_path = directory.joinpath("startup.sh")
    run_path = directory.joinpath("run_on_docker.sh")
    docker_path = directory.joinpath("Dockerfile")

    concept_nodes_path = directory.joinpath("concept_nodes.tsv")
    concepts: set[Reference] = set()
    concept_nodes_header = ["curie:ID", ":LABEL", "prefix"]

    mapping_nodes_path = directory.joinpath("mapping_nodes.tsv")
    mapping_nodes_header = ["curie:ID", ":LABEL", "prefix", "predicate", "confidence"]

    evidence_nodes_path = directory.joinpath("evidence_nodes.tsv")
    evidences = {}
    evidence_nodes_header = [
        "curie:ID",
        ":LABEL",
        "prefix",
        "type",
        "mapping_justification",
        "confidence:float",
    ]

    mapping_set_nodes_path = directory.joinpath("mapping_set_nodes.tsv")
    mapping_sets = {}
    mapping_set_nodes_header = ["curie:ID", ":LABEL", "prefix", "name", "license", "version", "confidence:float"]

    edges_path = directory.joinpath("edges.tsv")
    edges: list[tuple[str, str, str, str | float]] = []
    edges_header = [":START_ID", ":TYPE", ":END_ID", "confidence:float"]

    for mapping in tqdm(mappings, unit="mapping", unit_scale=True, desc="Preparing Neo4j"):
        concepts.add(mapping.s)
        concepts.add(mapping.o)
        edges.append(
            (
                mapping.s.curie,
                mapping.p.curie,
                mapping.o.curie,
                round(c, 4) if (c := mapping.confidence) is not None else "",
            )
        )
        edges.append((mapping.curie, ANNOTATED_SOURCE.curie, mapping.s.curie, ""))
        edges.append((mapping.curie, ANNOTATED_TARGET.curie, mapping.o.curie, ""))
        for evidence in mapping.evidence:
            edges.append((mapping.curie, "hasEvidence", evidence.curie, ""))
            evidences[evidence.key()] = evidence
            if evidence.mapping_set:
                mapping_sets[evidence.mapping_set.name] = evidence.mapping_set
                edges.append((evidence.curie, "fromSet", evidence.mapping_set.curie, ""))
            elif isinstance(evidence, ReasonedEvidence):
                for mmm in evidence.mappings:
                    edges.append((evidence.curie, "derivedFromMapping", mmm.curie, ""))
            elif isinstance(evidence, SimpleEvidence):
                pass
            else:
                raise TypeError

            # Add authorship information for the evidence, if available
            if evidence.author:
                concepts.add(evidence.author)
                edges.append((evidence.curie, "hasAuthor", evidence.author.curie, ""))

    _write_tsv(
        concept_nodes_path,
        concept_nodes_header,
        ((concept.curie, "concept", concept.prefix) for concept in sorted(concepts, key=lambda n: n.curie)),
    )
    _write_tsv(
        mapping_nodes_path,
        mapping_nodes_header,
        (
            (mapping.curie, "mapping", "semra.mapping", mapping.p.curie, mapping.confidence)
            for mapping in sorted(mappings, key=lambda n: n.curie)
        ),
    )
    _write_tsv(
        mapping_set_nodes_path,
        mapping_set_nodes_header,
        (
            (
                mapping_set.curie,
                "mappingset",
                "semra.mappingset",
                mapping_set.name,
                mapping_set.license or "",
                mapping_set.version or "",
                c if (c := mapping_set.confidence) is not None else "",
            )
            for mapping_set in sorted(mapping_sets.values(), key=lambda n: n.curie)
        ),
    )
    _write_tsv(
        evidence_nodes_path,
        evidence_nodes_header,
        (
            (
                evidence.curie,
                "evidence",
                "semra.evidence",
                evidence.evidence_type,
                evidence.justification.curie,
                c if (c := evidence.confidence) is not None else "",
            )
            for evidence in sorted(evidences.values(), key=lambda row: row.curie)
        ),
    )
    _write_tsv(edges_path, edges_header, sorted(set(edges), key=_edge_key))

    startup_commands = dedent(
        """\
        #!/bin/bash
        neo4j start
        sleep 100
        neo4j status
        python3.11 -m uvicorn --host 0.0.0.0 --port 8773 semra.wsgi:app
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

        ARG twiddle1=dee
        RUN python3.11 -m pip install git+https://github.com/biopragmatics/semra.git

        # Add graph content
        ARG twiddle2=dee
        COPY concept_nodes.tsv /sw/concept_nodes.tsv
        COPY mapping_nodes.tsv /sw/mapping_nodes.tsv
        COPY evidence_nodes.tsv /sw/evidence_nodes.tsv
        COPY mapping_set_nodes.tsv /sw/mapping_set_nodes.tsv
        COPY edges.tsv /sw/edges.tsv

        # Ingest graph content into neo4j
        RUN sed -i 's/#dbms.default_listen_address/dbms.default_listen_address/' /etc/neo4j/neo4j.conf && \\
            sed -i 's/#dbms.security.auth_enabled/dbms.security.auth_enabled/' /etc/neo4j/neo4j.conf && \\
            neo4j-admin import --delimiter='TAB' --skip-duplicate-nodes=true --skip-bad-relationships=true \\
                --relationships /sw/edges.tsv \\
                --nodes /sw/concept_nodes.tsv \\
                --nodes /sw/mapping_nodes.tsv \\
                --nodes /sw/mapping_set_nodes.tsv \\
                --nodes /sw/evidence_nodes.tsv

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
        docker run -t --detach -p 7474:7474 -p 7687:7687 -p 8773:8773 {docker_name}
    """
    )
    run_path.write_text(run_command)

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


def _write_tsv(path, header, rows) -> None:
    click.echo(f"writing to {path}")
    with path.open("w") as file:
        print(*header, sep="\t", file=file)
        for row in rows:
            print(*row, sep="\t", file=file)
