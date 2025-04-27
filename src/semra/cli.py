"""Command line interface for :mod:`semra`."""

import logging

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
# TODO add web command


if __name__ == "__main__":
    main()
