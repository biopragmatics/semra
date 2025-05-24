"""FastAPI parts."""

from __future__ import annotations

from typing import Annotated

import fastapi
import networkx as nx
from fastapi import HTTPException, Path, Query
from fastapi.responses import JSONResponse

from semra import Evidence, Mapping, MappingSet, Reference
from semra.client import BaseClient
from semra.web.shared import EXAMPLE_CONCEPTS

__all__ = ["api_router"]

api_router = fastapi.APIRouter(prefix="/api")


def _fastapi_get_client(request: fastapi.Request) -> BaseClient:
    return request.app.state.client  # type:ignore


AnnotatedClient = Annotated[BaseClient, fastapi.Depends(_fastapi_get_client)]


@api_router.get("/evidence/{evidence_id}", response_model=Evidence)
def get_evidence(
    client: AnnotatedClient,
    evidence_id: str = Path(description="An evidence's MD5 hex digest."),
) -> Evidence:
    """Get an evidence by its MD5 hex digest."""
    rv = client.get_evidence(evidence_id)
    if rv is None:
        raise HTTPException(status_code=404, detail="evidence not found")
    return rv


@api_router.get("/cytoscape/{curie}")
def get_concept_cytoscape(
    client: AnnotatedClient,
    curie: str = Path(
        description="the compact URI (CURIE) for a concept", examples=EXAMPLE_CONCEPTS
    ),
) -> JSONResponse:
    """Get the mapping graph surrounding the concept as a Cytoscape.js JSON object."""
    graph = client.get_connected_component_graph(curie)
    if graph is None:
        raise HTTPException(status_code=404, detail=f"concept not found: {curie}")
    cytoscape_json = nx.cytoscape_data(graph)["elements"]
    return JSONResponse(cytoscape_json)


@api_router.get("/exact/{curie}", response_model=list[Reference])
def get_exact_matches(
    client: AnnotatedClient,
    curie: str = Path(
        description="the compact URI (CURIE) for a concept", examples=EXAMPLE_CONCEPTS
    ),
    max_distance: int = Query(
        None, description="the distance in the mapping graph to traverse. Defaults to 7"
    ),
) -> list[Reference]:
    """Get the exact matches to the concept."""
    rv = client.get_exact_matches(curie, max_distance=max_distance)
    if rv is None:
        raise HTTPException(status_code=404, detail="concept not found")
    return list(rv)


@api_router.get("/mapping/{mapping_id}", response_model=Mapping)
def get_mapping(
    client: AnnotatedClient,
    mapping_id: str = Path(description="A mapping's MD5 hex digest."),
) -> Mapping:
    """Get the mapping by its MD5 hex digest."""
    mapping = client.get_mapping(mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="mapping not found")
    return mapping


@api_router.get("/mapping_set/{mapping_set_id}", response_model=MappingSet)
def get_mapping_set(
    client: AnnotatedClient,
    mapping_set_id: str = Path(
        description="A mapping set's MD5 hex digest.", examples=["7831d5bc95698099fb6471667e5282cd"]
    ),
) -> MappingSet:
    """Get a mapping set by its MD5 hex digest."""
    mapping_set = client.get_mapping_set(mapping_set_id)
    if mapping_set is None:
        raise HTTPException(status_code=404, detail="mapping set not found")
    return mapping_set


@api_router.get("/mapping_set/", response_model=list[MappingSet])
def get_mapping_sets(client: AnnotatedClient) -> list[MappingSet]:
    """Get all mapping sets."""
    return client.get_mapping_sets()
