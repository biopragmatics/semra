from flask import Blueprint, request, jsonify

from semra.web.autocomplete import ConceptsTrie

auto_blueprint = Blueprint("autocomplete", __name__, url_prefix="/autocomplete")


# Initialize the autocomplete trie
trie = ConceptsTrie.from_graph_db()


@auto_blueprint.route("/search", methods=["GET"])
def autocomplete_search():
    """Get the autocomplete suggestions for a given prefix."""
    prefix = request.args.get("prefix")
    top_n = min(int(request.args.get("top_n", 100)), 100)

    return jsonify(
        trie.case_insensitive_search(prefix, top_n=top_n)
    )
