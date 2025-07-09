import fastapi

from semra.web.autocomplete import ConceptsTrie, Entry

auto_router = fastapi.APIRouter(prefix="/autocomplete")


# Initialize the autocomplete trie
trie = ConceptsTrie.from_graph_db()


@auto_router.get("/search", response_model=list[Entry])
def autocomplete_search(prefix: str, top_n: int = 100):
    """Get the autocomplete suggestions for a given prefix."""
    top_n = min(top_n, 100)
    return trie.case_insensitive_search(prefix, top_n=top_n)
