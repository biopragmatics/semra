"""
An API wrapping SortedStringTrie from pytrie (see https://github.com/gsakkis/pytrie)
"""
import logging
from itertools import islice

from pytrie import SortedStringTrie


logger = logging.getLogger(__name__)


NodeData = dict[str, dict[str, str]]
Entry = tuple[str, str, str]


def get_concept_nodes(client) -> NodeData:
    """Get concept nodes from the Neo4j database

    :param client: The Neo4j client to use for querying the database.
    :type client: Neo4jClient
    :returns: A dictionary mapping concept CURIEs to their node data.
    """
    logging.info("Retrieving concept nodes from Neo4j")
    concept_query = "MATCH (n:concept) RETURN n.curie, n"
    concepts = {curie: dict(node) for curie, node in client.read_query(concept_query)}

    return concepts


class ConceptsTrie(SortedStringTrie):
    """A Trie structure that has case-insensitive search methods"""

    @classmethod
    def from_graph_db(cls):
        """Produce a NodesTrie instance from the with node names as keys

        :returns: An instance of a NodesTrie containing the node names of the
            graph as keys and the corresponding (name, ns, id, node degree)
            tuple as values
        """
        # from semra.client import Neo4jClient
        # client = Neo4jClient()
        # nodes = get_concept_nodes(client)
        #
        # name_indexing = {}
        #
        # logging.info(f"Indexing {len(nodes)} nodes for autocomplete")
        # for curie, node_dict in nodes.items():
        #     # Get node name in lowercase
        #     node_name = node_dict.get("name", "").lower()
        #
        #     # Skip if no name
        #     if not node_name:
        #         continue
        #
        #     # Get node data (first item is the name match)
        #     node_data = (node_name, node_dict["name"], curie)
        #     if node_name in name_indexing:
        #         ix = 1
        #         node_name_ = f"{node_name}_{ix}"
        #
        #         # Increase index until key is not present
        #         while node_name_ in name_indexing:
        #             ix += 1
        #             node_name_ = f"{node_name}_{ix}"
        #         node_name = node_name_
        #     name_indexing[node_name] = node_data

        # Mocked data for demonstration purposes
        name_indexing = {
            "example": ("Example", "Example", "example:123"),
            "test": ("Test", "Test", "test:456"),
            "sample": ("Sample", "Sample", "sample:789"),
            "concept": ("Concept", "Concept", "concept:101112"),
            "demo": ("Demo", "Demo", "demo:131415"),
            "node": ("Node", "Node", "node:161718"),
            "entity": ("Entity", "Entity", "entity:192021"),
            "item": ("Item", "Item", "item:222324"),
            "object": ("Object", "Object", "object:252627"),
            "resource": ("Resource", "Resource", "resource:282930"),
            "entity_1": ("Entity 1", "Entity 1", "entity:313233"),
            "entity_2": ("Entity 2", "Entity 2", "entity:343536"),
            "entity_3": ("Entity 3", "Entity 3", "entity:373839"),
            "entity_4": ("Entity 4", "Entity 4", "entity:404142"),
        }

        return cls(**name_indexing)

    def case_insensitive_search(self, prefix: str, top_n: int = 100) -> list[Entry]:
        """Get case-insensitive matches with the given prefix

        :param prefix: The prefix to search for.
        :param top_n: The maximum number of matches to return. Default: 100
        :returns: A list of all case-insensitive matches with the given prefix
        """
        prefix = prefix.lower()
        return list(islice(sorted(self.values(prefix)), top_n))
