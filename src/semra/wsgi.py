"""Run the app."""

from __future__ import annotations

import os
import typing as t
from dataclasses import dataclass
from typing import Annotated, Literal, cast, overload

import bioregistry
import fastapi
import flask
import networkx as nx
import werkzeug
from curies import Reference
from fastapi import HTTPException, Path, Query
from fastapi.responses import JSONResponse
from flask import Blueprint, Flask, current_app, render_template
from flask_bootstrap import Bootstrap5
from starlette.middleware.wsgi import WSGIMiddleware

from semra import Evidence, Mapping, MappingSet
from semra.client import BaseClient, ExampleMapping, FullSummary, Neo4jClient

EXAMPLE_CONCEPTS = ["efo:0002142"]


def _index_mapping(mapping_index: set[tuple[str, str]], mapping_dict: t.Mapping[str, str]) -> None:
    if mapping_dict["relation"] != "skos:exactMatch":
        return
    sp, si = mapping_dict["source prefix"], mapping_dict["source identifier"]
    tp, ti = mapping_dict["target prefix"], mapping_dict["target identifier"]
    si = bioregistry.standardize_identifier(sp, si)
    ti = bioregistry.standardize_identifier(tp, ti)
    s, t = f"{sp}:{si}", f"{tp}:{ti}"
    mapping_index.add((s, t))
    mapping_index.add((t, s))


try:
    import biomappings.utils
except ImportError:
    BIOMAPPINGS_GIT_HASH = None
    false_mapping_index: set[tuple[str, str]] = set()
else:
    BIOMAPPINGS_GIT_HASH = biomappings.utils.get_git_hash()
    false_mapping_index = set()
    # for m in biomappings.load_false_mappings():
    #    _index_mapping(false_mapping_index, m)

api_router = fastapi.APIRouter(prefix="/api")

flask_blueprint = Blueprint("ui", __name__)


# TODO use replaced by relationship for rewiring


def _figure_number(n: int) -> tuple[int | float, str]:
    if n > 1_000_000:
        lead = n / 1_000_000
        if lead < 10:
            return round(lead, 1), "M"
        else:
            return round(lead), "M"
    if n > 1_000:
        lead = n / 1_000
        if lead < 10:
            return round(lead, 1), "K"
        else:
            return round(lead), "K"
    else:
        return n, ""


@flask_blueprint.get("/")
def home() -> str:
    """View the homepage, with a dashboard for several statistics over the database."""
    # TODO
    #  1. Mapping with most evidences
    #  7. Nodes with equivalent entity sharing its prefix
    state = _flask_get_state()
    client = _flask_get_client()
    return render_template(
        "home.html",
        example_mappings=state.summary.example_mappings,
        predicate_counter=state.summary.PREDICATE_COUNTER,
        mapping_set_counter=state.summary.MAPPING_SET_COUNTER,
        node_counter=state.summary.NODE_COUNTER,
        mapping_sets=client.get_mapping_sets(),
        format_number=_figure_number,
        justification_counter=state.summary.JUSTIFICATION_COUNTER,
        evidence_type_counter=state.summary.EVIDENCE_TYPE_COUNTER,
        prefix_counter=state.summary.PREFIX_COUNTER,
        author_counter=state.summary.AUTHOR_COUNTER,
        high_matches_counter=state.summary.HIGH_MATCHES_COUNTER,
    )


@flask_blueprint.get("/mapping/<curie>")
def view_mapping(curie: str) -> str:
    """View a mapping."""
    m = _flask_get_client().get_mapping(curie)
    return render_template("mapping.html", mapping=m)


@flask_blueprint.get("/concept/<curie>")
def view_concept(curie: str) -> str:
    """View a concept."""
    reference = Reference.from_curie(curie)
    client = _flask_get_client()
    name = client.get_concept_name(curie)
    # TODO include evidence for each for better debugging
    exact_matches = client.get_exact_matches(curie)
    # TODO when showing equivalence between two entities from same
    #  namespace, suggest curating a replaced by relation
    return render_template(
        "concept.html",
        reference=reference,
        curie=curie,
        name=name,
        exact_matches=exact_matches,
        has_biomappings=BIOMAPPINGS_GIT_HASH is not None,
        false_mapping_index=false_mapping_index,
    )


@flask_blueprint.get("/concept/<source>/invalidate/<target>")
def mark_exact_incorrect(source: str, target: str) -> werkzeug.Response:
    """Add a negative relationship to biomappings."""
    if not BIOMAPPINGS_GIT_HASH:
        flask.flash("Can't interact with biomappings", category="error")
        return flask.redirect(flask.url_for(view_concept.__name__, curie=source))

    client = _flask_get_client()

    import biomappings.resources
    from biomappings.wsgi import _manual_source

    source_reference = Reference.from_curie(source)
    target_reference = Reference.from_curie(target)

    mapping: dict[str, str] = {
        "source prefix": source_reference.prefix,
        "source identifier": source_reference.identifier,
        "target prefix": target_reference.prefix,
        "target identifier": target_reference.identifier,
        "relation": "skos:exactMatch",
        "type": "semapv:ManualMappingCuration",
        "source": _manual_source(),
        "prediction_type": "",
        "prediction_source": "semra",
        "prediction_confidence": "",
    }
    if source_name := client.get_concept_name(source):
        mapping["source name"] = source_name
    if target_name := client.get_concept_name(target):
        mapping["target name"] = target_name

    mapping = biomappings.resources._standardize_mapping(mapping)
    biomappings.resources.append_false_mappings([mapping])
    _index_mapping(false_mapping_index, mapping)

    flask.flash("Appended negative mapping")
    return flask.redirect(flask.url_for(view_concept.__name__, curie=source))


@flask_blueprint.get("/mapping_set/<mapping_set_id>")
def view_mapping_set(mapping_set_id: str) -> str:
    """View a mapping set by its ID."""
    client = _flask_get_client()
    mapping_set = client.get_mapping_set(mapping_set_id)
    examples = client.sample_mappings_from_set(mapping_set_id, n=10)
    return render_template(
        "mapping_set.html",
        mapping_set=mapping_set,
        mapping_examples=examples,
    )


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
    return list(client.get_exact_matches(curie, max_distance=max_distance))


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


@dataclass
class State:
    """Represents application state."""

    client: BaseClient
    summary: FullSummary

    def example_mappings(self) -> list[ExampleMapping]:
        """Extract example mappings."""
        return self.summary.example_mappings


def _flask_get_state() -> State:
    """Get the state for the flask app."""
    return cast(State, current_app.extensions["semra"])


def _flask_get_client() -> BaseClient:
    """Get a client for the flask app."""
    return _flask_get_state().client


# docstr-coverage:excused `overload`
@overload
def get_app(
    *, client: BaseClient | None = ..., return_flask: Literal[True] = True
) -> tuple[Flask, fastapi.FastAPI]: ...


# docstr-coverage:excused `overload`
@overload
def get_app(
    *, client: BaseClient | None = ..., return_flask: Literal[False] = False
) -> fastapi.FastAPI: ...


def get_app(
    *, client: BaseClient | None = None, return_flask: bool = False
) -> fastapi.FastAPI | tuple[Flask, fastapi.FastAPI]:
    """Get the SeMRA FastAPI app."""
    if client is None:
        client = Neo4jClient()

    state = State(
        client=client,
        summary=client.get_full_summary(),
    )

    flask_app = Flask(__name__)
    flask_app.secret_key = os.urandom(8)
    flask_app.extensions["semra"] = state
    Bootstrap5(flask_app)

    flask_app.register_blueprint(flask_blueprint)

    fastapi_app = fastapi.FastAPI(
        title="Semantic Reasoning Assembler",
        description="A web app to access a SeMRA Neo4j database",
    )
    fastapi_app.state = state  # type:ignore
    fastapi_app.include_router(api_router)
    fastapi_app.mount("/", WSGIMiddleware(flask_app))

    if return_flask:
        return flask_app, fastapi_app
    return fastapi_app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(get_app(return_flask=False), port=5000, host="0.0.0.0")  # noqa:S104
