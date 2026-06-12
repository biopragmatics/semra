"""Command line interface for :mod:`semra`."""

import logging
from pathlib import Path

import click

from .database import build
from .landscape.cli import landscape

__all__ = [
    "main",
]

logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
def main() -> None:
    """CLI for SeMRA."""


main.add_command(build)
main.add_command(landscape)


@main.command()
@click.option("--uri")
@click.option("--port", default=8773, show_default=True)
@click.option("--host", default="0.0.0.0", show_default=True)  # noqa:S104
@click.option("--user")
@click.option("--password")
def web(uri: str | None, port: int, host: str, user: str | None, password: str | None) -> None:
    """Run the SeMRA web application."""
    from .wsgi import _run

    _run(uri=uri, port=port, host=host, user=user, password=password)


@main.command(name="neo4j-import")
@click.option(
    "-d",
    "--directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=Path.cwd,
)
@click.option("--brew-restart", is_flag=True)
def neo4j_import(directory: str, brew_restart: bool) -> None:
    """Import data into Neo4j 5+."""
    import os
    import time
    from textwrap import dedent

    directory_ = Path(directory).resolve()
    click.echo(f"importing from directory: {directory_}")

    mapping_edges_path = directory_ / "mapping_edges.tsv"
    edges_path = directory_ / "edges.tsv"
    concept_nodes_path = directory_ / "concept_nodes.tsv"
    mapping_nodes_path = directory_ / "mapping_nodes.tsv"
    evidence_nodes_path = directory_ / "evidence_nodes.tsv"
    mapping_set_nodes_path = directory_ / "mapping_set_nodes.tsv"

    if brew_restart:
        os.system("brew services stop neo4j")  # noqa:S605,S607
    command = dedent(f"""\
    neo4j-admin database import full \
        --delimiter='TAB' \
        --skip-duplicate-nodes=true \
        --relationships {mapping_edges_path} \
        --relationships {edges_path} \
        --nodes=concept={concept_nodes_path} \
        --nodes=mapping={mapping_nodes_path} \
        --nodes=evidence={evidence_nodes_path} \
        --nodes=mappingset={mapping_set_nodes_path} \
        --skip-bad-relationships=true \
        --overwrite-destination
    """)
    os.system(command)  # noqa:S605
    if brew_restart:
        os.system("brew services start neo4j")  # noqa:S605,S607
        time.sleep(3)
        os.system("neo4j status")  # noqa:S605,S607


if __name__ == "__main__":
    main()
