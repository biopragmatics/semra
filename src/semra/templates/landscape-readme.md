# Landscape Analysis

This folder contains results from a workflow for automating the analysis of the
landscape of a given domain, given a declarative configuration describing the
resources in that domain. It includes {{ configurations | length }} landscape
analyses:

<ol>
{%- for conf, conf_name in configurations %}
<li><a href="{{ conf.key }}/">{{ conf_name }}</a></li>
{%- endfor %}
</ol>

## Example

The example below highlights the disease landscape. Each analysis creates a
graph of the processed mappings.

![](disease/processed_graph.svg)

SeMRA automatically generates an UpSet plot like the one in
[How many rare diseases are there? (Haendel _et al._, 2020)](https://doi.org/10.1038/d41573-019-00180-y)
(a similar plot to the following appears in the
[supplementary info](https://media.nature.com/original/magazine-assets/d41573-019-00180-y/17308594)
and an explanation appears on [zenodo](https://zenodo.org/records/3478576)).
Note that this plot is about all diseases, not specifically rare ones:

![](disease/processed_landscape_upset.svg)

The following histogram estimates how many diseases there are. Importantly, it
shows how many show up in a single resource, how many show up in all resources,
and how many show up in a few

![](disease/processed_landscape_histogram.svg)

## Summary

The summary table over all landscapes can be generated with `semra landscape`.

{{ df.to_markdown(index=False, intfmt=",", floatfmt=".1%", colalign=["left", "right", "right", "right", "left"]) }}

## Rebuild

The `semra landscape` command rebuilds all landscape mapping files, calculates
summary statistics, and regenerates this file. It can be run with:

```console
$ git clone https://github.com/biopragmatics/semra.git
$ cd semra
$ uv pip install .[landscape]
$ semra landscape
```

To start off clean, use `--refresh-source` to re-download and re-parse resources
from scratch. Note that this takes on the order of hours to tens of hours,
depending on your internet connection speed and the server availability of
resources.

Outside of initial download of resources, which depends on internet connection
and availability and takes on the order of a few hours, this can be run on
commodity hardware overnight (e.g., a Macbook Pro 2023 with 36GB of RAM).

If you only want to re-run a specific configuration, use `--only` with the key,
like `--only disease`.

This script also outputs a LaTeX-ready string for the SeMRA manuscript.
