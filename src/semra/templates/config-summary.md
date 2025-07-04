# {{ configuration.name }}

{{ configuration.description }}

{%- if configuration.creators %} Created by:

<ul>
{%- for creator in configuration.creators %}
<li>
<a href="https://bioregistry.io/{{ creator.curie }}">
{%- if creator.name %}
{{ creator.name }} ({{ creator.curie }})
{%- else %}
{{ creator.curie }}
{%- endif %}
</a>
</li>
{%- endfor %}
</ul>
{%- endif %}

Artifacts from this resource can be downloaded from Zenodo at
[![](https://zenodo.org/badge/DOI/10.5281/zenodo.{{ configuration.zenodo_record }}.svg)](https://doi.org/10.5281/zenodo.{{ configuration.zenodo_record }}).

## Reproduction

The {{configuration.name }} can be rebuilt with the following commands:

```console
$ git clone https://github.com/biopragmatics/semra.git
$ cd semra
$ uv pip install .[landscape]
$ python -m semra.landscape.{{ configuration.key }}
```

Note that downloading raw data resources can take on the order of hours to tens
of hours depending on your internet connection and the reliability of
the resources' respective servers.

{% if refresh_source_timedelta %}
A full resource refresh (i.e., re-download of resources)
was run in {{ naturaldelta(refresh_source_timedelta)}}
{%- elif refresh_raw_timedelta %}
A refresh of raw mappings (i.e., re-processing of mappings)
was run in {{ naturaldelta(refresh_raw_timedelta)}}
{%- else %}
Processing and analysis can be run overnight
{%- endif %}
on commodity hardware (e.g., a 2023 MacBook Pro with 36GB RAM).

## Resource Summary

The following resources are represented in processed mappings generated. They
are summarized in the following table that includes their
[Bioregistry](https://bioregistry.io) prefix, license, current version, and
number of terms (i.e., named concepts) they contain.

{% if summary.number_pyobo_unavailable %}{{ summary.number_pyobo_unavailable }}
resources were not available through
[PyOBO](https://github.com/biopragmatics/pyobo). Therefore, the number of terms
in that resource are estimated based on the ones that are observed in mappings
assembled by SeMRA. Note that these are typically an underestimate.
{%- endif %}

{{ summary.summary_df.to_markdown() }}

There are a total of {{ "{:,}".format(summary.total) }} terms across the
{{ summary.summary_df.index | length }} resources.

## Mapping Summary and Usage

### Raw Mappings

The raw mappings are the ones directly read from the
{{ configuration.inputs | length }} sources.

- This table is symmetric, i.e., taking into account mappings from both the
  source and target.
- Diagonals represent the number of entities in the resource (or the number that
  are observed in the mappings, in some cases)
- All predicate types are combined in this table.

{{ overlap_results.raw_counts_df.to_markdown() }}

The raw mappings can be downloaded from
[![](https://zenodo.org/badge/DOI/10.5281/zenodo.{{ configuration.zenodo_record }}.svg)](https://doi.org/10.5281/zenodo.{{ configuration.zenodo_record }}).
then can be accessed via the [SeMRA](https://github.com/biopragmatics/semra)
Python Package using the following examples:

```python
import semra

# Load from JSONL
mappings_from_jsonl = semra.from_jsonl("raw.jsonl.gz")

# Load from SSSOM
mappings_from_sssom = semra.from_sssom("raw.sssom.tsv.gz")
```

<details>
<summary>Graph-based view of raw mappings</summary>

Note that this may contain many more prefixes than what's relevant for
processing. The configuration allows for specifying a prefix allowlist and
prefix blocklist.

![](raw_graph.svg)

</details>

### Processed Mappings

The processed mappings result from the application of inference, reasoning, and
confidence filtering.

{%- if configuration.keep_prefixes %}
Before processing, only mappings with subjects and objects whose references
both use the following prefixes were retained:

<ul>
{%- for prefix in configuration.keep_prefixes %}
<li>{{ prefix }}</li>
{%- endfor %}
</ul>
{%- endif %}

{%- if configuration.remove_prefixes %}
Before processing, mappings with subjects or objects whose references use the
following prefixes were removed:

<ul>
{%- for prefix in configuration.remove_prefixes %}
<li>{{ prefix }}</li>
{%- endfor %}
</ul>
{%- endif %}

{%- if configuration.mutations %}
The following prior knowledge was used during processing:

<table>
<thead>
<tr>
<th>Source Prefix</th>
<th>Target Prefix</th>
<th>Old Predicate</th>
<th>New Predicate</th>
<th align="right">Confidence</th>
</tr>
</thead>
<tbody>
{%- for mutation in configuration.mutations %}
<tr>
<td>{{ mutation.source }}</td>
<td>{% if mutation.target %}{{ mutation.target }}{% else %}(all){% endif %}</td>
<td>{{ mutation.old.curie }}</td>
<td>{{ mutation.new.curie }}</td>
<td align="right">{{ mutation.confidence }}</td>
</tr>
{%- endfor %}
</tbody>
</table>
{%- endif %}

{%- if configuration.post_keep_prefixes %}
After processing, only mappings with subjects and objects whose references both
use the following prefixes were retained:

<ul>
{%- for prefix in configuration.post_keep_prefixes %}
<li>{{ prefix }}</li>
{%- endfor %}
</ul>
{%- endif %}

{%- if configuration.post_remove_prefixes %}
After processing, mappings with subjects or objects whose references use the
following prefixes were removed:

<ul>
{%- for prefix in configuration.post_remove_prefixes %}
<li>{{ prefix }}</li>
{%- endfor %}
</ul>
{%- endif %}

The processed mappings table has the following qualities:

- This table is symmetric, i.e., taking into account mappings from the source,
  target, and inference
- Diagonals represent the number of entities in the resource (or the number that
  are observed in the mappings, in some cases)
- Only exact matches are retained

{{ overlap_results.processed_counts_df.to_markdown() }}

The processed mappings can be downloaded from
[![](https://zenodo.org/badge/DOI/10.5281/zenodo.{{ configuration.zenodo_record }}.svg)](https://doi.org/10.5281/zenodo.{{ configuration.zenodo_record }}).
then can be accessed via the [SeMRA](https://github.com/biopragmatics/semra)
Python Package using the following examples:

```python
import semra

# Load from JSONL
mappings_from_jsonl = semra.from_jsonl("processed.jsonl.gz")

# Load from SSSOM
mappings_from_sssom = semra.from_sssom("processed.sssom.tsv.gz")
```

Below is a graph-based view on the processed mappings.

![](processed_graph.svg)

### Priority Mappings

A prioritization mapping is a special subset of processed mappings constructed
using the prefix priority list. This mapping has the feature that every entity
appears as a subject exactly once, with the object of its mapping being the
priority entity. This creates a "star graph" for each priority entity.

The prioritization for this output is:

<ol>
{%- for prefix in configuration.priority %}
<li><a href="https://bioregistry.io/{{ prefix }}">{{ bioregistry.get_name(prefix) }} (<code>{{ prefix }}</code>)</a></li>
{%- endfor %}
</ol>

{#{{ overlap_results.priority_counts_df.to_markdown() }} #}

The priority mappings can be downloaded from
[![](https://zenodo.org/badge/DOI/10.5281/zenodo.{{ configuration.zenodo_record }}.svg)](https://doi.org/10.5281/zenodo.{{ configuration.zenodo_record }}).
then can be accessed via the [SeMRA](https://github.com/biopragmatics/semra)
Python Package using the following examples:

```python
import semra
import semra.api

# Load from JSONL
mappings_from_jsonl = semra.from_jsonl("priority.jsonl.gz")

# Load from SSSOM
mappings_from_sssom = semra.from_sssom("priority.sssom.tsv.gz")

# Apply in a data science scenario
df = ...
semra.api.prioritize_df(mappings_from_jsonl, df, column="source_column_id", target_column="target_column_id")
```

{# Below is a graph-based view on the priority mappings. #}
{# ![](priority_graph.svg) #}

## Web Application

1. Download all artifacts from [![](https://zenodo.org/badge/DOI/10.5281/zenodo.{{ configuration.zenodo_record }}.svg)](https://doi.org/10.5281/zenodo.{{ configuration.zenodo_record }})
   into a folder and `cd` into it
2. Run `sh run_on_docker.sh` from the command line
3. Navigate to http://localhost:8773 to see the SeMRA dashboard or to
   http://localhost:7474 for direct access to the Neo4j graph database

## Analyses

### Comparison Analysis

The following comparison shows the absolute number of mappings added by
processing/inference. Across the board, this process adds large numbers of
mappings to most resources, especially ones that were previously only connected
to a small number of other resources.

{{ overlap_results.gains_df.to_markdown() }}

Here's an alternative view on the number of mappings normalized to show
percentage gain. Note that:

- `inf` means that there were no mappings before and now there are a non-zero
  number of mappings
- `NaN` means there were no mappings before inference and continue to be no
  mappings after inference

{{ overlap_results.percent_gains_df.round(1).to_markdown() }}

### Landscape Analysis

Above, the comparison looked at the overlaps between each resource. Now, that
information is used to jointly estimate the number of terms in the landscape
itself, and estimate how much of the landscape each resource covers.

{{ landscape_results.get_description_markdown() | safe }}

Because there are {{ overlap_results.n_prefixes }} prefixes, there are
{{ "{:,}".format(overlap_results.number_overlaps) }} possible overlaps to
consider. Therefore, a Venn diagram is not possible, so an
[UpSet plot](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4720993) (Lex _et
al._, 2014) is used as a high-dimensional Venn diagram.

![](processed_landscape_upset.svg)

Next, the mappings are aggregated to estimate the number of unique entities and
number that appear in each group of resources.

![](processed_landscape_histogram.svg)

The landscape of {{ configuration.priority | length }} resources has
{{ "{:,}".format(landscape_results.total_term_count) }} total terms. After
merging redundant nodes based on mappings, inference, and reasoning, there are
{{ "{:,}".format(landscape_results.reduced_term_count) }} unique concepts. Using
the reduction formula
{% raw %}$\frac{{\text{{total terms}} - \text{{reduced terms}}}}{{\text{{total terms}}}}${% endraw %},
this is a {{ "{:.2%}".format(landscape_results.reduction_percent) }} reduction.

This is only an estimate and is susceptible to a few things:

1. It can be artificially high because there are entities that _should_ be
   mapped, but are not
1. It can be artificially low because there are entities that are incorrectly
   mapped, e.g., as a result of inference. The frontend curation interface can
   help identify and remove these
{%- if summary.number_pyobo_unavailable %}
1. It can be artificially low because for some vocabularies like SNOMED-CT, it's
   not possible to load a terms list, and therefore it's not possible to account
   for terms that aren't mapped. Therefore, a lower bound estimate is made based
   on the terms that appear in mappings.
{%- endif %}
1. It can be artificially high if a vocabulary is used that covers many domains
   and is not properly subset'd. For example, EFO covers many different domains,
   so when doing disease landscape analysis, it should be subset to only terms
   in the disease hierarchy (i.e., appearing under `efo:0000408`).
1. It can be affected by terminology issues, such as the confusion between
   Orphanet and ORDO
1. It can be affected by the existence of many-to-many mappings, which are
   filtered out during processing, which makes the estimate artificially high
   since some subset of those entities could be mapped, but it's not clear which
   should.

## Licensing

Mappings are licensed according to their primary resources. These are explicitly
annotated in the SSSOM file on each row (when available) and on the mapping set
level in the Neo4j graph database artifacts. All original mappings produced by
SeMRA are licensed under CC0-1.0.
