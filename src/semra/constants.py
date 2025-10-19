"""Constants for SeMRA."""

from __future__ import annotations

import bioregistry

__all__ = [
    "SEMRA_EVIDENCE_PREFIX",
    "SEMRA_MAPPING_PREFIX",
    "SEMRA_MAPPING_SET_PREFIX",
    "SEMRA_NEO4J_CONCEPT_LABEL",
    "SEMRA_NEO4J_EVIDENCE_LABEL",
    "SEMRA_NEO4J_MAPPING_LABEL",
    "SEMRA_NEO4J_MAPPING_SET_LABEL",
]

#: The label used for nodes representing mappings in SeMRA's Neo4j export
SEMRA_NEO4J_MAPPING_LABEL = "mapping"
#: The label used for nodes representing concepts (i.e., entities) in SeMRA's Neo4j export
SEMRA_NEO4J_CONCEPT_LABEL = "concept"
#: The label used for nodes representing evidences in SeMRA's Neo4j export
SEMRA_NEO4J_EVIDENCE_LABEL = "evidence"
#: The label used for nodes representing mapping sets in SeMRA's Neo4j export
SEMRA_NEO4J_MAPPING_SET_LABEL = "mappingset"

#: The prefix used in CURIEs representing mappings
SEMRA_MAPPING_PREFIX = "semra.mapping"
SEMRA_MAPPING = bioregistry.Resource(prefix=SEMRA_MAPPING_PREFIX, name="SeMRA Mapping")

#: The prefix used in CURIEs representing evidences
SEMRA_EVIDENCE_PREFIX = "semra.evidence"
SEMRA_EVIDENCE = bioregistry.Resource(prefix=SEMRA_EVIDENCE_PREFIX, name="SeMRA Evidence")

#: The prefix used in CURIEs representing mappings sets
SEMRA_MAPPING_SET_PREFIX = "semra.mappingset"
SEMRA_MAPPING_SET = bioregistry.Resource(prefix=SEMRA_MAPPING_SET_PREFIX, name="SeMRA Mapping Set")

for resource in [SEMRA_MAPPING, SEMRA_EVIDENCE, SEMRA_MAPPING_SET]:
    bioregistry.add_resource(resource)
