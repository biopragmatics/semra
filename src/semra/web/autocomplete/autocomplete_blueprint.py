import fastapi

from typing import Annotated
from semra.client import BaseClient

auto_router = fastapi.APIRouter(prefix="/autocomplete")


def _fastapi_get_client(request: fastapi.Request) -> BaseClient:
    return request.app.state.client  # type:ignore


AnnotatedClient = Annotated[BaseClient, fastapi.Depends(_fastapi_get_client)]

@auto_router.get("/search", response_model=list[list[str]])
def autocomplete_search(
    client: AnnotatedClient,
    prefix: str,
    top_n: int = 100,
):
    """Get the autocomplete suggestions for a given prefix."""
    prefix_clause = f"{prefix}* OR {prefix}~"
    top_n = min(top_n, 100)

    query = f"""\
    CALL db.index.fulltext.queryNodes("concept_curie_name_ft", $prefix) YIELD node
    RETURN toLower(node.name), node.name, node.curie
    LIMIT $top_n
    """
    res = client.read_query(query, top_n=top_n, prefix=prefix_clause)
    return res
