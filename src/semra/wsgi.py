"""Run the app."""

from __future__ import annotations

import os
import typing as t

import fastapi
import flask
import networkx as nx
from curies import Reference
from fastapi import Path
from fastapi.responses import JSONResponse
from flask import Flask, render_template
from flask_bootstrap import Bootstrap5
from starlette.middleware.wsgi import WSGIMiddleware

from semra import Evidence, Mapping, MappingSet
from semra.client import Neo4jClient

try:
    import biomappings.utils
except ImportError:
    BIOMAPPINGS_GIT_HASH = None
else:
    BIOMAPPINGS_GIT_HASH = biomappings.utils.get_git_hash()

client = Neo4jClient()

api_router = fastapi.APIRouter(prefix="/api")

flask_app = Flask(__name__)
flask_app.secret_key = os.urandom(8)
Bootstrap5(flask_app)


EXAMPLE_CONCEPTS = ["efo:0002142"]
EXAMPLE_MAPPINGS = ["25b67912bc720127a43a06ce4688b672", "5a56bf7ac409d8de84c3382a99e17715"]


PREDICATE_COUNTER = client.summarize_predicates()
MAPPING_SET_COUNTER = client.summarize_mapping_sets()
NODE_COUNTER = client.summarize_nodes()
JUSTIFICATION_COUNTER = client.summarize_justifications()
EVIDENCE_TYPE_COUNTER = client.summarize_evidence_types()
PREFIX_COUNTER = client.summarize_concepts()
AUTHOR_COUNTER = client.summarize_authors()
HIGH_MATCHES_COUNTER = client.get_highest_exact_matches()


# TODO use replaced by relationship for rewiring


def _figure_number(n: int):
    if n > 1_000_000:  # noqa:PLR2004
        lead = n / 1_000_000
        if lead < 10:  # noqa:PLR2004
            return round(lead, 1), "M"
        else:
            return round(lead), "M"
    if n > 1_000:  # noqa:PLR2004
        lead = n / 1_000
        if lead < 10:  # noqa:PLR2004
            return round(lead, 1), "K"
        else:
            return round(lead), "K"
    else:
        return n, ""


@flask_app.get("/")
def home():
    # TODO
    #  1. Mapping with most evidences
    #  7. Nodes with equivalent entity sharing its prefix
    return render_template(
        "home.html",
        example_mappings=EXAMPLE_MAPPINGS,
        predicate_counter=PREDICATE_COUNTER,
        mapping_set_counter=MAPPING_SET_COUNTER,
        node_counter=NODE_COUNTER,
        mapping_sets=client.get_mapping_sets(),
        format_number=_figure_number,
        justification_counter=JUSTIFICATION_COUNTER,
        evidence_type_counter=EVIDENCE_TYPE_COUNTER,
        prefix_counter=PREFIX_COUNTER,
        author_counter=AUTHOR_COUNTER,
        high_matches_counter=HIGH_MATCHES_COUNTER,
    )


@flask_app.get("/mapping/<curie>")
def view_mapping(curie: str):
    """View a mapping."""
    m = client.get_mapping(curie)
    return render_template("mapping.html", mapping=m)


@flask_app.get("/concept/<curie>")
def view_concept(curie: str):
    """View a concept."""
    reference = Reference.from_curie(curie)
    name = client.get_concept_name(curie)
    exact_matches = client.get_exact_matches(curie)
    # TODO when showing equivalence between two entities from same namespace, suggest curating a replaced by relation
    return render_template(
        "concept.html",
        reference=reference,
        curie=curie,
        name=name,
        exact_matches=exact_matches,
        has_biomappings=BIOMAPPINGS_GIT_HASH is not None,
    )


@flask_app.get("/concept/<source>/invalidate/<target>")
def mark_exact_incorrect(source: str, target: str):
    """
    Add a negative relationship to biomappings.
    """
    if not BIOMAPPINGS_GIT_HASH:
        flask.flash("Can't interact with biomappings", category="error")
        return flask.redirect(flask.url_for(view_concept.__name__, curie=source))

    import biomappings.resources

    source_reference = Reference.from_curie(source)
    target_reference = Reference.from_curie(target)

    mapping = {
        "source prefix": source_reference.prefix,
        "source identifier": source_reference.identifier,
        "source name": client.get_concept_name(source),
        "target prefix": target_reference.prefix,
        "target identifier": target_reference.identifier,
        "target name": client.get_concept_name(target),
        "relation": "skos:exactMatch",
        "type": "semapv:ManualMappingCuration",
        "source": "semra-web",  # TODO fix way this is retrieved
        "prediction_type": "",
        "prediction_source": "semra",
        "prediction_confidence": "",
    }
    biomappings.resources.append_false_mappings([mapping])

    flask.flash("Appended negative mapping")
    return flask.redirect(flask.url_for(view_concept.__name__, curie=source))


@flask_app.get("/mapping_set/<curie>")
def view_mapping_set(curie: str):
    """View a mapping."""
    m = client.get_mapping_set(curie)
    # TODO sample 10 mappings
    return render_template("mapping_set.html", mapping_set=m)


@api_router.get("/evidence/{curie}", response_model=Evidence)
def get_evidence(curie: str = Path(description="An evidence's MD5 hex digest.")):
    return client.get_evidence(curie)


@api_router.get("/cytoscape/{curie}")
def get_concept_cytoscape(
    curie: str = Path(description="the compact URI (CURIE) for a concept", examples=EXAMPLE_CONCEPTS)
):
    """Get the mapping graph surrounding the concept as a Cytoscape.js JSON object."""
    graph = client.get_connected_component_graph(curie)
    cytoscape_json = nx.cytoscape_data(graph)["elements"]
    return JSONResponse(cytoscape_json)


@api_router.get("/mapping/{mapping}", response_model=Mapping)
def get_mapping(mapping: str = Path(description="A mapping's MD5 hex digest.", examples=EXAMPLE_MAPPINGS)):
    return client.get_mapping(mapping)


@api_router.get("/mapping_set/{mapping_set}", response_model=MappingSet)
def get_mapping_set(
    mapping_set: str = Path(
        description="A mapping set's MD5 hex digest.", examples=["7831d5bc95698099fb6471667e5282cd"]
    )
):
    return client.get_mapping_set(mapping_set)


@api_router.get("/mapping_set/", response_model=t.List[MappingSet])
def get_mapping_sets():
    return client.get_mapping_sets()


def get_app():
    app = fastapi.FastAPI(
        title="Semantic Reasoning Assembler",
        description="A web app to access a SeMRA Neo4j database",
    )
    app.include_router(api_router)
    app.mount("/", WSGIMiddleware(flask_app))
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(get_app(), port=5000, host="0.0.0.0")  # noqa:S104
