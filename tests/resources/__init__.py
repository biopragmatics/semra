"""Neo4j test files."""

from pathlib import Path

HERE = Path(__file__).parent.resolve()

CONCEPT_NODES_TSV_PATH = HERE.joinpath("concept_nodes.tsv")
EVIDENCE_NODES_TSV_PATH = HERE.joinpath("evidence_nodes.tsv")
MAPPING_NODES_TSV_PATH = HERE.joinpath("mapping_nodes.tsv")
MAPPING_SET_NODES_TSV_PATH = HERE.joinpath("mapping_set_nodes.tsv")

MAPPING_EDGES_TSV_PATH = HERE.joinpath("mapping_edges.tsv")
EDGES_TSV_PATH = HERE.joinpath("edges.tsv")
