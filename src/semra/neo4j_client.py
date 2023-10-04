from curies import Reference
import neo4j
from typing import Optional
import pystow
__all__ = [
    "Client",
]
class Client:
    #: The session
    session: Optional[neo4j.Session]

    def __init__(
            self,
            url: Optional[str] = None,
            auth: Optional[tuple[str, str]] = None,
            max_connection_lifetime: int = 3 * 60
    ):
        """Initialize the Neo4j client."""
        self.driver = None
        self.session = None
        if not url:
            url = pystow.get_config("semra", "neo4j_url", raise_on_missing=True)
        if not auth:
            user = pystow.get_config("semra", "neo4j_user")
            password = pystow.get_config("semra", "neo4j_password")
            if user and password:
                auth = (user, password)

        # Set max_connection_lifetime to something smaller than the timeouts
        # on the server or on the way to the server. See
        # https://github.com/neo4j/neo4j-python-driver/issues/316#issuecomment-564020680
        self.driver = neo4j.GraphDatabase.driver(
            url,
            auth=auth,
            max_connection_lifetime=max_connection_lifetime,
        )


    def are_equivalent(self, curie1: Reference, curie2: Reference) -> bool:
        raise NotImplementedError

    def __del__(self):
        # Safely shut down the driver as a Neo4jClient object is garbage collected
        # https://neo4j.com/docs/api/python-driver/current/api.html#driver-object-lifetime
        if self.driver is not None:
            self.driver.close()

    def create_tx(
        self,
        query: str,
        query_params: Optional[Mapping[str, Any]] = None,
    ):
        """Run a transaction which writes to the neo4j instance.

        Parameters
        ----------
        query :
            The query string to be executed.
        query_params :
            Parameters associated with the query.
        """
        with self.driver.session() as session:
            return session.write_transaction(
                do_cypher_tx, query, query_params=query_params
            )

    def query_dict(self, query: str, **query_params) -> Dict:
        """Run a read-only query that generates a dictionary."""
        return dict(self.query_tx(query, **query_params))

    def query_dict_value_json(self, query: str, **query_params) -> Dict:
        """Run a read-only query that generates a dictionary."""
        return {
            key: json.loads(j)
            for key, j in self.query_tx(query, **query_params)
        }

    def query_tx(
        self, query: str, squeeze: bool = False, **query_params
    ):
        """Run a read-only query and return the results.

        Parameters
        ----------
        query :
            The query string to be executed.
        squeeze :
            If true, unpacks the 0-indexed element in each value returned.
            Useful when only returning value per row of the results.
        query_params :
            kwargs to pass to query

        Returns
        -------
        values :
            A list of results where each result is a list of one or more
            objects (typically neo4j nodes or relations).
        """
        # For documentation on the session and transaction classes see
        # https://neo4j.com/docs/api/python-driver/4.4/api.html#session-construction
        # and
        # https://neo4j.com/docs/api/python-driver/4.4/api.html#explicit-transactions
        # Documentation on transaction functions are here:
        # https://neo4j.com/docs/python-manual/4.4/session-api/#python-driver-simple-transaction-fn
        with self.driver.session() as session:
            # do_cypher_tx is ultimately called as
            # `transaction_function(tx, *args, **kwargs)` in the neo4j code,
            # where *args and **kwargs are passed through unchanged, meaning
            # do_cypher_tx can expect query and **query_params
            values = session.read_transaction(
                do_cypher_tx, query, **query_params
            )

        if squeeze:
            values = [value[0] for value in values]
        return values


@neo4j.unit_of_work()
def do_cypher_tx(
        tx: neo4j.Transaction,
        query: str,
        **query_params
):
    # Follows example here:
    # https://neo4j.com/docs/python-manual/4.4/session-api/#python-driver-simple-transaction-fn
    # and from the docstring of neo4j.Session.read_transaction
    # 'parameters' and '**kwparameters' of tx.run are ultimately merged at query
    # run-time
    result = tx.run(query, parameters=query_params)
    return [record.values() for record in result]
