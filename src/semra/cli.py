"""Command line interface for :mod:`semra`."""

import logging

import click

__all__ = [
    "main",
]

logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
def main():
    """CLI for semra."""


if __name__ == "__main__":
    main()
