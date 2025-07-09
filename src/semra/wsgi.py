"""Run the app."""

from __future__ import annotations

import os
from typing import Literal, overload

import fastapi
from bioregistry import NormalizedNamedReference
from flask import Flask
from flask_bootstrap import Bootstrap5
from starlette.middleware.wsgi import WSGIMiddleware

from semra.client import BaseClient, Neo4jClient
from semra.web.fastapi_components import api_router
from semra.web.flask_components import flask_blueprint, index_biomapping
from semra.web.shared import State


# docstr-coverage:excused `overload`
@overload
def get_app(
    *,
    client: BaseClient | None = ...,
    return_flask: Literal[True] = True,
    use_biomappings: bool = ...,
) -> tuple[Flask, fastapi.FastAPI]: ...


# docstr-coverage:excused `overload`
@overload
def get_app(
    *,
    client: BaseClient | None = ...,
    return_flask: Literal[False] = False,
    use_biomappings: bool = ...,
) -> fastapi.FastAPI: ...


def get_app(
    *,
    client: BaseClient | None = None,
    return_flask: bool = False,
    use_biomappings: bool = True,
    add_autocomplete: bool = True,
) -> fastapi.FastAPI | tuple[Flask, fastapi.FastAPI]:
    """Get the SeMRA FastAPI app."""
    if client is None:
        client = Neo4jClient()

    biomappings_git_hash: str | None = None
    false_mapping_index: set[tuple[str, str]] = set()
    current_author: NormalizedNamedReference | None = None

    if use_biomappings:
        try:
            import biomappings
            import biomappings.resources
            import biomappings.utils
        except ImportError:
            pass
        else:
            current_author = biomappings.resources.get_current_curator(strict=False)
            if current_author:
                print("Loading biomappings resources")
                biomappings_git_hash = biomappings.utils.get_git_hash()
                for m in biomappings.load_false_mappings():
                    index_biomapping(false_mapping_index, m)

    print("Loading State for the app")
    name_query = "MATCH (n:concept) WHERE n.name IS NOT NULL RETURN n.name LIMIT 1"
    name_example = client.read_query(name_query)
    if name_example and len(name_example) > 0 and len(name_example[0]) > 0:
        name_example = name_example[0][0]
    else:
        name_example = None
    curie_query = "MATCH (n:concept) RETURN n.curie LIMIT 1"
    curie_example = client.read_query(curie_query)
    if curie_example and len(curie_example) > 0 and len(curie_example[0]) > 0:
        curie_example = curie_example[0][0]
    else:
        # There should always be at least one example concept in the database
        # with a curie
        raise ValueError("No curie example found in the database")
    state = State(
        client=client,
        summary=client.get_full_summary(),
        false_mapping_index=false_mapping_index,
        biomappings_hash=biomappings_git_hash,
        current_author=current_author,
        name_example=name_example,
        curie_example=curie_example,
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
    if add_autocomplete:
        print("Adding autocomplete router and building fulltext index")
        from semra.web.autocomplete.autocomplete_blueprint import auto_router
        fastapi_app.include_router(auto_router)
        # Create a fulltext index for concept names
        client.create_fulltext_index(
            "concept_curie_name_ft",
            "concept",
            ["name", "curie"],
            exist_ok=False,
        )
    fastapi_app.mount("/", WSGIMiddleware(flask_app))

    if return_flask:
        return flask_app, fastapi_app
    return fastapi_app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(get_app(return_flask=False), port=5000, host="0.0.0.0")  # noqa:S104
