"""Run the app."""

from __future__ import annotations

import logging
import os
import sys
from typing import Literal, overload

import fastapi
from bioregistry import NormalizedNamedReference
from flask import Flask
from flask_bootstrap import Bootstrap5
from starlette.middleware.wsgi import WSGIMiddleware

from semra.client import BaseClient, Neo4jClient
from semra.web.fastapi_components import api_router, auto_router
from semra.web.flask_components import flask_blueprint, index_biomapping
from semra.web.shared import State

# Set up logging separately from uvicorn
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter(
    "%(levelname)s: [%(asctime)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)
file_handler = logging.FileHandler("info.log")
file_handler.setFormatter(formatter)
logger.addHandler(stream_handler)
logger.addHandler(file_handler)


# docstr-coverage:excused `overload`
@overload
def get_app(
    *,
    client: BaseClient | None = ...,
    return_flask: Literal[True] = True,
    use_biomappings: bool = ...,
    add_autocomplete: bool = ...,
) -> tuple[Flask, fastapi.FastAPI]: ...


# docstr-coverage:excused `overload`
@overload
def get_app(
    *,
    client: BaseClient | None = ...,
    return_flask: Literal[False] = False,
    use_biomappings: bool = ...,
    add_autocomplete: bool = ...,
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
                logger.info("Using biomappings resources")
                biomappings_git_hash = biomappings.utils.get_git_hash()
                for m in biomappings.load_false_mappings():
                    index_biomapping(false_mapping_index, m)

    logger.info("Loading State for the app")

    state = State(
        client=client,
        summary=client.get_full_summary(),
        false_mapping_index=false_mapping_index,
        biomappings_hash=biomappings_git_hash,
        current_author=current_author,
        example_reference=client.get_example_concept(),
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
        logger.info("Adding autocomplete router and building fulltext index")
        client.initialize_autocomplete()
        fastapi_app.include_router(auto_router)

    fastapi_app.mount("/", WSGIMiddleware(flask_app))

    if return_flask:
        return flask_app, fastapi_app
    return fastapi_app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(get_app(return_flask=False), port=5000, host="0.0.0.0")  # noqa:S104
