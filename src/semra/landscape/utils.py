"""Landscape analysis utilities."""

from __future__ import annotations

import json
from pathlib import Path

import bioregistry
import matplotlib.pyplot as plt

from semra.landscape.summarize import LandscapeResult, OverlapResults, Summarizer
from semra.pipeline import Configuration

HERE = Path(__file__).parent.resolve()


__all__ = [
    "notebook",
]


def notebook(
    configuration: Configuration,
    *,
    output_directory: str | Path | None = None,
    minimum_count: int | None = None,
    show_progress: bool = False,
) -> tuple[OverlapResults, LandscapeResult]:
    """Run the landscape analysis inside a Jupyter notebook."""
    if output_directory is None:
        output_directory = configuration.directory
    output_directory = Path(output_directory).expanduser().resolve()

    if not configuration.configuration_path.is_file():
        configuration.configuration_path.write_text(
            configuration.model_dump_json(indent=2, exclude_none=True, exclude_unset=True)
        )

    results_path = output_directory.joinpath("README.md")

    summarizer = Summarizer(configuration, show_progress=show_progress)

    summary_df = summarizer.get_summary_df()
    summary_df.to_csv(output_directory.joinpath("summary.tsv"), sep="\t")
    number_pyobo_unavailable = (summary_df["terms"] == 0).sum()

    overlap_results = summarizer.overlap_analysis(
        minimum_count=minimum_count,
        show_progress=show_progress,
    )
    overlap_results.processed_counts_df.to_csv(
        output_directory / "counts.tsv", sep="\t", index=True
    )
    overlap_results.raw_counts_df.to_csv(output_directory / "raw_counts.tsv", sep="\t", index=True)
    output_directory.joinpath("graph.svg").write_bytes(overlap_results.counts_drawing)

    # note we're using the sliced counts dataframe index instead of the
    # original priority since we threw a couple prefixes away along the way
    landscape_results = summarizer.landscape_analysis(overlap_results)

    landscape_results.plot_upset()
    plt.savefig(output_directory.joinpath("landscape_upset.svg"))
    plt.savefig(output_directory.joinpath("landscape_upset.png"))

    landscape_results.plot_distribution()
    plt.tight_layout()
    plt.savefig(output_directory.joinpath("landscape_histogram.svg"))
    plt.savefig(output_directory.joinpath("landscape_histogram.png"))

    from jinja2 import Environment, FileSystemLoader, select_autoescape

    templates = HERE.parent.joinpath("templates")
    environment = Environment(loader=FileSystemLoader(templates), autoescape=select_autoescape())
    template = environment.get_template("config-summary.md")

    vv = template.render(
        configuration=configuration,
        bioregistry=bioregistry,
        summary_df=summary_df,
        number_pyobo_unavailable=number_pyobo_unavailable,
        overlap_results=overlap_results,
        landscape_results=landscape_results,
    )
    results_path.write_text(vv)

    stats = {
        "raw_term_count": landscape_results.total_term_count,
        "unique_term_count": landscape_results.reduced_term_count,
        "reduction": landscape_results.reduction_percent,
        "distribution": landscape_results.distribution,
    }
    stats_path = output_directory.joinpath("stats.json")
    stats_path.write_text(json.dumps(stats, indent=2, sort_keys=True))

    return overlap_results, landscape_results


if __name__ == "__main__":
    from semra.landscape.taxrank import CONFIGURATION

    notebook(CONFIGURATION)
