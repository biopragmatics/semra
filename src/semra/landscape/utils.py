"""Landscape analysis utilities."""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from textwrap import dedent

import matplotlib.pyplot as plt
from IPython.display import SVG, Markdown, display
from matplotlib_inline.backend_inline import set_matplotlib_formats

from semra.landscape.summarize import LandscapeResult, OverlapResults, Summarizer
from semra.pipeline import Configuration

__all__ = [
    "notebook",
]


def _markdown(x: str) -> None:
    display(Markdown(dedent(x)))


def notebook(
    configuration: Configuration,
    *,
    output_directory: str | Path | None = None,
    matplotlib_formats: str | None = "svg",
    show: bool = True,
    minimum_count: int | None = None,
    show_progress: bool = False,
) -> tuple[OverlapResults, LandscapeResult]:
    """Run the landscape analysis inside a Jupyter notebook."""
    if matplotlib_formats:
        set_matplotlib_formats(matplotlib_formats)
    if output_directory is None:
        output_directory = configuration.directory
    output_directory = Path(output_directory).expanduser().resolve()

    if not configuration.configuration_path.is_file():
        configuration.configuration_path.write_text(
            configuration.model_dump_json(indent=2, exclude_none=True, exclude_unset=True)
        )

    summarizer = Summarizer(configuration, show_progress=show_progress)

    summary_df = summarizer.get_summary_df()
    summary_df.to_csv(output_directory.joinpath("summary.tsv"), sep="\t")
    number_pyobo_unavailable = (summary_df["terms"] == 0).sum()
    _markdown(
        """\
    ## Summarize the Resources

    We summarize the resources used in the landscape analysis, including their
    [Bioregistry](https://bioregistry.io) prefix, license, current version, and
    number of terms (i.e., named concepts) they contain.
    """
    )
    if number_pyobo_unavailable > 0:
        _markdown(
            f"""\
        {number_pyobo_unavailable} resources were not available through
        [PyOBO](https://github.com/biopragmatics/pyobo). Therefore, we estimate the number
        of terms in that resource based on the ones appearing in mappings. Note that these
        are typically an underestimate.
        """
        )

    display(summary_df)

    _summary_total = summary_df["terms"].sum()
    _markdown(
        f"There are a total of {_summary_total:,} terms across the {len(summary_df.index):,} "
        f"resources."
    )

    _markdown(
        """\
    ## Summarize the Mappings

    In order to summarize the mappings, we're going to load them, index them, and count
    the number of mappings between each pair of resources. The self-mapping column is
    the count of terms in the resource. We'll do this to the raw mappings first, then
    to the processed mappings, then compare them.
    """
    )
    overlap_results = summarizer.overlap_analysis(
        minimum_count=minimum_count,
        show_progress=show_progress,
    )
    overlap_results.write(output_directory)
    _markdown(
        "First, we summarize the raw mappings, i.e., the mappings that are directly available "
        "from the sources"
    )
    display(overlap_results.raw_counts_df)
    _markdown(
        "Next, we summarize the processed mappings, which include inference, reasoning, and "
        "confidence filtering."
    )
    display(overlap_results.processed_counts_df)
    _markdown("Below is an graph-based view on the processed mappings.")
    display(SVG(overlap_results.counts_drawing))
    _markdown(
        """\
    ## Comparison

    The following comparison shows the absolute number of mappings added by processing/inference.
    Across the board, this process adds large numbers of mappings to most resources, especially
    ones that were previously only connected to a small number of other resources.
    """
    )
    display(overlap_results.gains_df)
    _markdown(
        """\
    Here's an alternative view on the number of mappings normalized to show percentage gain.

    Note:

    - `inf` means that there were no mappings before and now there are a non-zero number of
       mappings
    - `NaN` means there were no mappings before inference and continue to be no mappings after
       inference
    """
    )
    display(overlap_results.percent_gains_df.round(1))
    _markdown(
        """\
        ## Landscape Analysis

        Before, we looked at the overlaps between each resource. Now, we use that information
        jointly to estimate the number of terms in the landscape itself, and estimate how much
        of the landscape each resource covers.
    """
    )

    # note we're using the sliced counts dataframe index instead of the
    # original priority since we threw a couple prefixes away along the way
    landscape_results = summarizer.landscape_analysis(overlap_results)

    _markdown(landscape_results.get_description_markdown())

    n_prefixes = len(overlap_results.processed_counts_df.index)
    number_overlaps = 2**n_prefixes - 1
    _markdown(
        f"""\
    Because there are {n_prefixes} prefixes, there are {number_overlaps:,} possible overlaps to consider.
    Therefore, a Venn diagram is not possible, so we
    we use an [UpSet plot](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4720993)
    (Lex *et al.*, 2014) as a high-dimensional Venn diagram.
    """
    )
    with warnings.catch_warnings():
        warnings.simplefilter(action="ignore", category=FutureWarning)
        # we have to wrap the upset plot functionality with the future
        # warning catching because it uses deprecated matplotlib and
        # pandas functionality. unfortunataely, it appears the upstream
        # https://github.com/jnothman/UpSetPlot is inactive
        landscape_results.plot_upset()
    plt.savefig(output_directory.joinpath("landscape_upset.svg"))
    if show:
        plt.show()

    _markdown(
        """\
        We now aggregate the mappings together to estimate the number of unique entities and number
        that appear in each group of resources.
        """
    )
    landscape_results.plot_distribution()
    plt.tight_layout()
    plt.savefig(output_directory.joinpath("landscape_histogram.svg"))
    if show:
        plt.show()

    _markdown(landscape_results.get_reduction_text(configuration))
    _markdown(
        """\
    This is only an estimate and is susceptible to a few things:

    1. It can be artificially high because there are entities that _should_ be mapped, but are not
    2. It can be artificially low because there are entities that are incorrectly mapped, e.g., as
       a result of inference. The frontend curation interface can help identify and remove these
    3. It can be artificially low because for some vocabularies like SNOMED-CT, it's not possible
       to load a terms list, and therefore it's not possible to account for terms that aren't
       mapped. Therefore, we make a lower bound estimate based on the terms that appear in
       mappings.
    4. It can be artificially high if a vocabulary is used that covers many domains and is not
       properly subset'd. For example, EFO covers many different domains, so when doing disease
       landscape analysis, it should be subset to only terms in the disease hierarchy
       (i.e., appearing under ``efo:0000408``).
    5. It can be affected by terminology issues, such as the confusion between Orphanet and ORDO
    6. It can be affected by the existence of many-to-many mappings, which are filtered out during
       processing, which makes the estimate artificially high since some subset of those entities
       could be mapped, but it's not clear which should.
    """
    )

    stats = {
        "raw_term_count": landscape_results.total_term_count,
        "unique_term_count": landscape_results.reduced_term_count,
        "reduction": landscape_results.reduction_percent,
        "distribution": landscape_results.distribution,
    }
    stats_path = output_directory.joinpath("stats.json")
    stats_path.write_text(json.dumps(stats, indent=2, sort_keys=True))

    return overlap_results, landscape_results
