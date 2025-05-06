"""CLI for landscape builds."""

import click
from more_click import verbose_option
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from semra.pipeline import (
    BUILD_DOCKER_OPTION,
    REFRESH_PROCESSED_OPTION,
    REFRESH_RAW_OPTION,
    REFRESH_SOURCE_OPTION,
    UPLOAD_OPTION,
)

__all__ = [
    "landscape",
]


@click.command()
@REFRESH_SOURCE_OPTION
@REFRESH_RAW_OPTION
@REFRESH_PROCESSED_OPTION
@UPLOAD_OPTION
@BUILD_DOCKER_OPTION
@verbose_option  # type:ignore
@click.pass_context
def landscape(
    ctx: click.Context,
    upload: bool,
    refresh_source: bool,
    refresh_raw: bool,
    refresh_processed: bool,
    build_docker: bool,
) -> None:
    """Run all landscape builds."""
    if build_docker:
        pass  # TODO check if docker is running

    from . import anatomy, cells, complexes, diseases, genes, taxrank

    functions: list[tuple[str, click.Command]] = [
        (taxrank.CONFIGURATION.key, taxrank.CONFIGURATION.get_cli()),
        (complexes.CONFIGURATION.key, complexes.CONFIGURATION.get_cli()),
        (anatomy.CONFIGURATION.key, anatomy.CONFIGURATION.get_cli()),
        (cells.CONFIGURATION.key, cells.main),
        (diseases.CONFIGURATION.key, diseases.CONFIGURATION.get_cli()),
        (genes.CONFIGURATION.key, genes.CONFIGURATION.get_cli()),
    ]

    with logging_redirect_tqdm():
        it = tqdm(functions, unit="configuration", desc="landscape analysis")
        for label, func in it:
            tqdm.write(click.style(label, bold=True, fg="green"))
            ctx.invoke(
                func,
                upload=upload,
                refresh_source=refresh_source,
                refresh_raw=refresh_raw,
                refresh_processed=refresh_processed,
                build_docker=build_docker,
            )


if __name__ == "__main__":
    landscape()
