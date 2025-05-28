"""CLI for landscape builds."""

import os
from functools import lru_cache

import click
import pandas as pd
from more_click import verbose_option
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from semra.pipeline import (
    BUILD_DOCKER_OPTION,
    REFRESH_PROCESSED_OPTION,
    REFRESH_RAW_OPTION,
    REFRESH_SOURCE_OPTION,
    STATS_FILE_NAME,
    UPLOAD_OPTION,
    Configuration,
)
from semra.utils import LANDSCAPE_FOLDER, get_jinja_template

__all__ = [
    "landscape",
]


@lru_cache(1)
def _get_functions() -> list[tuple[Configuration, click.Command]]:
    from . import anatomy, cells, complexes, diseases, genes, taxrank

    functions: list[tuple[Configuration, click.Command]] = [
        (diseases.CONFIGURATION, diseases.CONFIGURATION.get_cli(copy_to_landscape=True)),
        (cells.CONFIGURATION, cells.main),
        (anatomy.CONFIGURATION, anatomy.CONFIGURATION.get_cli(copy_to_landscape=True)),
        (complexes.CONFIGURATION, complexes.CONFIGURATION.get_cli(copy_to_landscape=True)),
        (genes.CONFIGURATION, genes.CONFIGURATION.get_cli(copy_to_landscape=True)),
        (taxrank.CONFIGURATION, taxrank.CONFIGURATION.get_cli(copy_to_landscape=True)),
    ]
    return functions


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

    functions = _get_functions()
    with logging_redirect_tqdm():
        tqdm(functions, unit="configuration", desc="landscape analysis")
        for conf, func in functions:
            tqdm.write(click.style(conf.key, bold=True, fg="green"))
            ctx.invoke(
                func,
                upload=upload,
                refresh_source=refresh_source,
                refresh_raw=refresh_raw,
                refresh_processed=refresh_processed,
                build_docker=build_docker,
            )


def _get_name(conf: Configuration) -> str:
    return conf.name.removeprefix("SeMRA").removesuffix("Mappings Database").strip()


def _get_metaanalysis_df() -> pd.DataFrame:
    from ..summarize import Statistics

    rows = []

    for conf, _ in _get_functions():
        directory = LANDSCAPE_FOLDER.joinpath(conf.key)
        if not directory.is_dir():
            click.echo(f"[{conf.key}] directory is missing: {directory}")
            continue

        statistics_path = directory.joinpath(STATS_FILE_NAME)
        if not statistics_path.is_file():
            raise FileNotFoundError(f"missing statistics file: {statistics_path}")
        statistics = Statistics.model_validate_json(statistics_path.read_text())

        row = {
            **statistics.model_dump(),
            "name": _get_name(conf),
            "zenodo": conf.zenodo_url(),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    df = df[["name", "raw_term_count", "unique_term_count", "reduction", "zenodo"]]
    df = df.rename(
        columns={
            "name": "Domain",
            "raw_term_count": "Raw Concepts",
            "unique_term_count": "Unique Concepts",
            "reduction": "Reduction Ratio",
            "zenodo": "Download Link",
        }
    )
    return df


def compile_landscape_metaanalysis() -> None:
    """Compile the landscape meta-analysis and write the README file."""
    df = _get_metaanalysis_df()
    configurations = [
        (conf, _get_name(conf))
        for conf, _ in _get_functions()
        # filter out folders that aren't ready for prime time
        if LANDSCAPE_FOLDER.joinpath(conf.key).is_dir()
    ]

    template = get_jinja_template("landscape-readme.md")
    text = template.render(df=df, configurations=configurations)

    path = LANDSCAPE_FOLDER.joinpath("README.md")
    path.write_text(text)
    os.system(  # noqa:S605
        f'npx --yes prettier --write --prose-wrap always "{path.as_posix()}"'
    )

    click.echo("\nTable as LaTeX for paper\n")
    click.echo(df.to_latex(label="landscape-summary-table", caption="", index=False))


if __name__ == "__main__":
    landscape()
