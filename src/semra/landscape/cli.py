"""CLI for landscape builds."""

import os
from functools import lru_cache

import bioversions
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
    Configuration,
)
from semra.utils import LANDSCAPE_FOLDER, get_jinja_template

__all__ = [
    "compile_landscape_metaanalysis",
    "landscape",
]


@lru_cache(1)
def _get_functions() -> list[tuple[Configuration, click.Command]]:
    from . import (
        ANATOMY_CONFIGURATION,
        CELL_CONFIGURATION,
        COMPLEX_CONFIGURATION,
        DISEASE_CONFIGURATION,
        GENE_CONFIGURATION,
        TAXRANK_CONFIGURATION,
    )
    from .cell import cell_consolidation_hook

    functions: list[tuple[Configuration, click.Command]] = [
        (DISEASE_CONFIGURATION, DISEASE_CONFIGURATION.get_cli(copy_to_landscape=True)),
        (
            CELL_CONFIGURATION,
            CELL_CONFIGURATION.get_cli(copy_to_landscape=True, hooks=[cell_consolidation_hook]),
        ),
        (ANATOMY_CONFIGURATION, ANATOMY_CONFIGURATION.get_cli(copy_to_landscape=True)),
        (COMPLEX_CONFIGURATION, COMPLEX_CONFIGURATION.get_cli(copy_to_landscape=True)),
        (GENE_CONFIGURATION, GENE_CONFIGURATION.get_cli(copy_to_landscape=True)),
        (TAXRANK_CONFIGURATION, TAXRANK_CONFIGURATION.get_cli(copy_to_landscape=True)),
    ]
    return functions


@click.command()
@REFRESH_SOURCE_OPTION
@REFRESH_RAW_OPTION
@REFRESH_PROCESSED_OPTION
@click.option(
    "--upload",
    is_flag=True,
    help="If enabled, upload each landscape to their respective Zenodo records.",
)
@BUILD_DOCKER_OPTION
@verbose_option  # type:ignore
@click.option("--only", help="if given, only runs this configuration", multiple=True)
@click.option("--readme-only", is_flag=True, help="if given, only creat ethe readme")
@click.pass_context
def landscape(
    ctx: click.Context,
    upload: bool,
    refresh_source: bool,
    refresh_raw: bool,
    refresh_processed: bool,
    build_docker: bool,
    only: list[str] | None,
    readme_only: bool,
) -> None:
    """Construct pre-configured domain-specific mapping databases and run landscape analyses."""
    if not readme_only:
        if build_docker:
            pass  # TODO check if docker is running

        click.echo("caching versions w/ Bioversions")
        list(bioversions.iter_versions(use_tqdm=True))

        functions = _get_functions()
        with logging_redirect_tqdm():
            tqdm(functions, unit="configuration", desc="landscape analysis")
            for conf, func in functions:
                if only and conf.key not in only:
                    continue
                tqdm.write(click.style(conf.key, bold=True, fg="green"))
                ctx.invoke(
                    func,
                    upload=upload,
                    refresh_source=refresh_source,
                    refresh_raw=refresh_raw,
                    refresh_processed=refresh_processed,
                    build_docker=build_docker,
                )

    compile_landscape_metaanalysis()


def compile_landscape_metaanalysis() -> None:
    """Compile the landscape meta-analysis and write the README file.

    This function is also run as part of the :func:`landscape` CLI functionality.
    """
    df = _get_metaanalysis_df()
    configurations = [
        (conf, _get_name(conf))
        for conf, _ in _get_functions()
        # filter out folders that aren't ready for prime time
        if LANDSCAPE_FOLDER.joinpath(conf.key).is_dir()
    ]

    template = get_jinja_template("landscape-readme.md")
    text = template.render(df=df, configurations=configurations)

    path = LANDSCAPE_FOLDER.joinpath("README.md").resolve()
    path.write_text(text)
    os.system(  # noqa:S605
        f'npx --yes prettier --write --prose-wrap always "{path.as_posix()}"'
    )

    click.echo("\nTable as LaTeX for paper\n")
    click.echo(df.to_latex(label="landscape-summary-table", caption="", index=False))


def _get_metaanalysis_df() -> pd.DataFrame:
    from ..summarize import Statistics, _copy_into_landscape_folder

    rows = []

    for conf, _ in _get_functions():
        if conf.key not in {"gene", "taxrank"}:
            _copy_into_landscape_folder(conf, conf._get_landscape_paths())

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


def _get_name(conf: Configuration) -> str:
    return conf.name.removeprefix("SeMRA").removesuffix("Mappings Database").strip()


if __name__ == "__main__":
    landscape()
