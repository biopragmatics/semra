# {{ configuration.name }}

{{ configuration.description }}

## Resource Summary

We summarize the resources used in the landscape analysis, including their
[Bioregistry](https://bioregistry.io) prefix, license, current version, and
number of terms (i.e., named concepts) they contain.

{% if number_pyobo_unavailable %}
{{ number_pyobo_unavailable }} resources were not available through
[PyOBO](https://github.com/biopragmatics/pyobo). Therefore, we estimate the number
of terms in that resource based on the ones appearing in mappings. Note that these
are typically an underestimate.
{% endif %}

{{ summary.summary_df.to_markdown() }}

There are a total of {{ "{:,}".format(summary.number_pyobo_unavailable) }} terms across
the {{ summary.summary_df.index | length }} resources.

## Mapping Summary and Usage

### Raw Mappings

The raw mappings are the ones directly read from the {{ configuration.inputs | length }} sources.

- This table is symmetric, i.e., taking into account mappings from both the source and target.
- Diagonals represent the number of entities in the resource (or the number that are observed
  in the mappings, in some cases)
- All predicate types are combined in this table.

{{ overlap_results.raw_counts_df.to_markdown() }}

The processed mappings can be accessed via the [SeMRA](https://github.com/biopragmatics/semra)
Python Package using the following examples:

```python
import semra.io

# Load from JSONL
mappings = semra.io.from_jsonl("raw.jsonl.gz")

# Load from SSSOM
mappings = semra.io.from_sssom("raw.sssom.tsv.gz")
```

Below is a graph-based view on the raw mappings.

![](raw_graph.svg)

### Processed Mappings

The processed mappings result from the application of inference, reasoning, and confidence
filtering.

{{ overlap_results.processed_counts_df.to_markdown() }}

The processed mappings can be accessed via the [SeMRA](https://github.com/biopragmatics/semra)
Python Package using the following examples:

```python
import semra.io

# Load from JSONL
mappings = semra.io.from_jsonl("processed.jsonl.gz")

# Load from SSSOM
mappings = semra.io.from_sssom("processed.sssom.tsv.gz")
```

Below is a graph-based view on the processed mappings.

![](processed_graph.svg)

### Priority Mappings

Following semantic mapping assembly, connected components of
equivalent entities are resolved to a single entity based on
the following prefix prioritization.

<ol>
{% for prefix in configuration.priority %}
<li>
{{ bioregistry.get_name(prefix) }} (`{{ prefix }}`)
</li>
{% endfor %}
</ol>

TODO

- What is a prioritization mapping (i.e., creates a star graph using processed mappings + prioritization order)
- give example usage in docs

```python
import semra.io
import semra.api

# Load from JSONL
mappings = semra.io.from_jsonl("priority.jsonl.gz")

# Load from SSSOM
mappings = semra.io.from_sssom("priority.sssom.tsv.gz")

# Apply in a data science scenario
df = ...
semra.api.prioritize_df(mappings, df, column="source_column_id", target_column="target_column_id")
```

## Web Application

1. Download all artifacts into a folder and `cd` into it
2. Run `sh run_on_docker.sh` from the command line
3. Navigate to http://localhost:8773 to see the SeMRA dashboard or to http://localhost:7474 for direct access to the
   Neo4j graph database

## Analyses

### Comparison

The following comparison shows the absolute number of mappings added by processing/inference.
Across the board, this process adds large numbers of mappings to most resources, especially
ones that were previously only connected to a small number of other resources.

{{ overlap_results.gains_df.to_markdown() }}

Here's an alternative view on the number of mappings normalized to show percentage gain. Note that:

- `inf` means that there were no mappings before and now there are a non-zero number of
  mappings
- `NaN` means there were no mappings before inference and continue to be no mappings after
  inference

{{ overlap_results.percent_gains_df.round(1).to_markdown() }}

### Landscape Analysis

Before, we looked at the overlaps between each resource. Now, we use that information
jointly to estimate the number of terms in the landscape itself, and estimate how much
of the landscape each resource covers.

{{ landscape_results.get_description_markdown() | safe }}

Because there are {{ overlap_results.n_prefixes }} prefixes,
there are {{ "{:,}".format(overlap_results.number_overlaps) }} possible overlaps to consider.
Therefore, a Venn diagram is not possible, so
we use an [UpSet plot](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4720993)
(Lex *et al.*, 2014) as a high-dimensional Venn diagram.

![](processed_landscape_upset.svg)

We now aggregate the mappings together to estimate the number of unique entities and number
that appear in each group of resources.

![](processed_landscape_histogram.svg)

The landscape of {{ configuration.priority | length }} resources has
{{ "{:,}".format(landscape_results.total_term_count) }} total terms.
After merging redundant nodes based on mappings, inference, and reasoning, there
are {{ "{:,}".format(landscape_results.reduced_term_count) }} unique concepts. Using the reduction formula
{% raw %}$\frac{{\text{{total terms}} - \text{{reduced terms}}}}{{\text{{total terms}}}}${% endraw %},
this is a {{ "{:.2%}".format(landscape_results.reduction_percent) }} reduction.

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

## Configuration Summary

### Sources

<ul>
{% for source in configuration.inputs %}
<li>{{ source }}</li>
{% endfor %}
</ul>

### Prior Knowledge

<ul>
{% for mutation in configuration.mutations %}
<li>{{ mutation }}</li>
{% endfor %}
</ul>

## Licensing

Mappings are licensed according to their primary resources. These are explicitly annotated in the SSSOM file on each
row (when available) and on the mapping set level in the Neo4j graph database artifacts.

## Extras

An automatically assembled dataset of raw semantic mappings produced by python -m semra.database. This incorporates
mappings from the following places:

- Ontologies indexed in the Bioregistry (primary)
- Databases integrated in PyOBO (primary)
- Biomappings (secondary)
- Wikidata (primary/secondary)
- Custom resources integrated in SeMRA (primary)
