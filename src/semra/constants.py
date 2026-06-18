"""Constants for SeMRA."""

from __future__ import annotations

import bioregistry
from pyobo import Reference
from sssom_pydantic.api import MAPPING_HASH_CURIE_PREFIX as SEMRA_EVIDENCE_PREFIX
from sssom_pydantic.api import MAPPING_HASH_URI_PREFIX as SEMRA_EVIDENCE_URI_PREFIX
from sssom_pydantic.api import (
    TRIPLE_HASH_CURIE_PREFIX as SEMRA_MAPPING_PREFIX,
)
from sssom_pydantic.api import (
    TRIPLE_HASH_URI_PREFIX as SEMRA_MAPPING_URI_PREFIX,
)

__all__ = [
    "SEMRA_EVIDENCE_PREFIX",
    "SEMRA_EVIDENCE_URI_PREFIX",
    "SEMRA_MAPPING_PREFIX",
    "SEMRA_MAPPING_SET_PREFIX",
    "SEMRA_MAPPING_URI_PREFIX",
    "SEMRA_NEO4J_CONCEPT_LABEL",
    "SEMRA_NEO4J_EVIDENCE_LABEL",
    "SEMRA_NEO4J_MAPPING_LABEL",
    "SEMRA_NEO4J_MAPPING_SET_LABEL",
    "SEMRA_SOURCE",
    "Reference",
]

#: The label used for nodes representing mappings in SeMRA's Neo4j export
SEMRA_NEO4J_MAPPING_LABEL = "mapping"
#: The label used for nodes representing concepts (i.e., entities) in SeMRA's Neo4j export
SEMRA_NEO4J_CONCEPT_LABEL = "concept"
#: The label used for nodes representing evidences in SeMRA's Neo4j export
SEMRA_NEO4J_EVIDENCE_LABEL = "evidence"
#: The label used for nodes representing mapping sets in SeMRA's Neo4j export
SEMRA_NEO4J_MAPPING_SET_LABEL = "mappingset"

SEMRA_MAPPING = bioregistry.Resource(
    prefix=SEMRA_MAPPING_PREFIX, name="SeMRA Mapping", uri_format=f"{SEMRA_MAPPING_URI_PREFIX}$1"
)

SEMRA_EVIDENCE = bioregistry.Resource(
    prefix=SEMRA_EVIDENCE_PREFIX, name="SeMRA Evidence", uri_format=f"{SEMRA_EVIDENCE_URI_PREFIX}$1"
)

#: The prefix used in CURIEs representing mappings sets
SEMRA_MAPPING_SET_PREFIX = "semra.mappingset"
SEMRA_MAPPING_SET_URI_PREFIX = "https://w3id.org/biopragmatics/semra/mapping-set/"
SEMRA_MAPPING_SET = bioregistry.Resource(
    prefix=SEMRA_MAPPING_SET_PREFIX,
    name="SeMRA Mapping Set",
    uri_format=f"{SEMRA_MAPPING_SET_URI_PREFIX}$1",
)


for resource in [SEMRA_MAPPING, SEMRA_EVIDENCE, SEMRA_MAPPING_SET]:
    bioregistry.add_resource(resource)

CC0_URL = "https://creativecommons.org/publicdomain/zero/1.0/"

SEMRA_SOURCE = Reference(prefix="wikidata", identifier="Q127259663", name="SeMRA")
