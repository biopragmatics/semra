"""Flask parts."""

from __future__ import annotations

import typing as t
from typing import cast

import bioregistry
import flask
import werkzeug
from curies import Reference
from flask import Blueprint, current_app, render_template

from semra.client import BaseClient
from semra.web.shared import State, _figure_number

__all__ = [
    "flask_blueprint",
    "index_biomapping",
]

flask_blueprint = Blueprint("ui", __name__)


# TODO use replaced by relationship for rewiring


@flask_blueprint.get("/")
def home() -> str:
    """View the homepage, with a dashboard for several statistics over the database."""
    # TODO
    #  1. Mapping with most evidences
    #  7. Nodes with equivalent entity sharing its prefix
    state = _flask_get_state()
    client = _flask_get_client()
    mapping_sets = client.get_mapping_sets()
    return render_template(
        "home.html",
        example_mappings=state.summary.example_mappings,
        predicate_counter=state.summary.PREDICATE_COUNTER,
        mapping_set_counter=state.summary.MAPPING_SET_COUNTER,
        node_counter=state.summary.NODE_COUNTER,
        mapping_sets=mapping_sets,
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
        has_biomappings=_flask_get_biomappings_hash() is not None,
        false_mapping_index=_flask_get_false_mapping_index(),
    )


@flask_blueprint.get("/concept/<source>/invalidate/<target>")
def mark_exact_incorrect(source: str, target: str) -> werkzeug.Response:
    """Add a negative relationship to biomappings."""
    if _flask_get_biomappings_hash() is None:
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
    index_biomapping(_flask_get_false_mapping_index(), mapping)

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


def _flask_get_state() -> State:
    """Get the state for the flask app."""
    return cast(State, current_app.extensions["semra"])


def _flask_get_client() -> BaseClient:
    """Get a client for the flask app."""
    return _flask_get_state().client


def _flask_get_biomappings_hash() -> str | None:
    """Get the biomappings hash for the flask app."""
    return _flask_get_state().biomappings_hash


def _flask_get_false_mapping_index() -> set[tuple[str, str]]:
    """Get a false mapping_index for the flask app."""
    return _flask_get_state().false_mapping_index


def index_biomapping(
    mapping_index: set[tuple[str, str]], mapping_dict: t.Mapping[str, str]
) -> None:
    """Index a mapping from biomappings."""
    if mapping_dict["relation"] != "skos:exactMatch":
        return
    sp, si = mapping_dict["source prefix"], mapping_dict["source identifier"]
    tp, ti = mapping_dict["target prefix"], mapping_dict["target identifier"]
    si = bioregistry.standardize_identifier(sp, si)
    ti = bioregistry.standardize_identifier(tp, ti)
    s, t = f"{sp}:{si}", f"{tp}:{ti}"
    mapping_index.add((s, t))
    mapping_index.add((t, s))
