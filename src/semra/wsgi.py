"""Run the app."""

import fastapi
from fastapi import Path
from flask import Flask, render_template
from flask_bootstrap import Bootstrap5
from starlette.middleware.wsgi import WSGIMiddleware

from semra import Evidence, Mapping, MappingSet
from semra.client import Neo4jClient

client = Neo4jClient()

api_router = fastapi.APIRouter()

flask_app = Flask(__name__)
Bootstrap5(flask_app)

#  Could group this in a function later
app = fastapi.FastAPI()
app.include_router(api_router)
api_router.mount("/", WSGIMiddleware(flask_app))

EXAMPLE_MAPPINGS = ["25b67912bc720127a43a06ce4688b672", "5a56bf7ac409d8de84c3382a99e17715"]


PREDICATE_COUNTER = client.summarize_predicates()
MAPPING_SET_COUNTER = client.summarize_mapping_sets()
NODE_COUNTER = client.summarize_nodes()
JUSTIFICATION_COUNTER = client.summarize_justifications()
EVIDENCE_TYPE_COUNTER = client.summarize_evidence_types()


def _figure_number(n: int):
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


@flask_app.get("/")
def home():
    # TODO
    #  1. Mapping with most evidences
    #  2. Number of reasoned vs. simple evidences
    #  3. Author contributions (also including mapping sets when no author available)
    #  5. Number of mappings that don't come from a mapping set (should be equivalent to # reasoned)
    #  6. Nodes with most equivalent entities / nodes with more than 6 equivalent entities
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
    )


@flask_app.get("/mapping/<curie>")
def view_mapping(curie: str):
    """View a mapping."""
    m = client.get_mapping(curie)
    return render_template("mapping.html", mapping=m)


@flask_app.get("/mapping_set/<curie>")
def view_mapping_set(curie: str):
    """View a mapping."""
    m = client.get_mapping_set(curie)
    # TODO sample 10 mappings
    return render_template("mapping_set.html", mapping_set=m)


@api_router.get("/api/evidence/{curie}", response_model=Evidence)
def get_evidence(curie: str = Path(description="An evidence's MD5 hex digest.")):  # noqa:B008
    return client.get_evidence(curie)


@api_router.get("/api/mapping/{mapping}", response_model=Mapping)
def get_mapping(
    mapping: str = Path(  # noqa:B008
        description="A mapping's MD5 hex digest.",
        examples=EXAMPLE_MAPPINGS,
    )
):
    return client.get_mapping(mapping)


@api_router.get("/api/mapping_set/{mapping_set}", response_model=MappingSet)
def get_mapping_set(
    mapping_set: str = Path(  # noqa:B008
        description="A mapping set's MD5 hex digest.", examples=["7831d5bc95698099fb6471667e5282cd"]
    )
):
    return client.get_mapping_set(mapping_set)


@api_router.get("/api/mapping_set/", response_model=list[MappingSet])
def get_mapping_sets():
    return client.get_mapping_sets()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(api_router, port=5000, host="0.0.0.0")  # noqa:S104
