"""CLI for landscape builds."""

import click
from more_click import verbose_option
from tqdm.contrib.logging import logging_redirect_tqdm

from semra.pipeline import REFRESH_PROCESSED_OPTION, REFRESH_RAW_OPTION, UPLOAD_OPTION

from . import anatomy, cells, complexes, diseases, genes

__all__ = [
    "FUNCTIONS",
    "landscape",
]

FUNCTIONS: list[tuple[str, click.Command]] = [
    ("Complexes", complexes.CONFIGURATION.get_cli()),
    ("Anatomy", anatomy.CONFIGURATION.get_cli()),
    ("Cells and Cell Lines", cells.main),
    ("Diseases", diseases.CONFIGURATION.get_cli()),
    ("Genes", genes.CONFIGURATION.get_cli()),
]


@click.command()
@REFRESH_RAW_OPTION
@REFRESH_PROCESSED_OPTION
@UPLOAD_OPTION
@verbose_option
@click.pass_context
def landscape(ctx: click.Context, upload: bool, refresh_raw: bool, refresh_processed: bool):
    """Run all landscape builds."""
    with logging_redirect_tqdm():
        for label, func in FUNCTIONS:
            click.secho(label, bold=True, fg="green")
            ctx.invoke(
                func, upload=upload, refresh_raw=refresh_raw, refresh_processed=refresh_processed
            )


if __name__ == "__main__":
    landscape()
