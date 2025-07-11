# SeMRA Protein Complex Mappings Database

Analyze the landscape of protein complex nomenclature resources,
species-agnostic. Created by:

<ul>
<li>
<a href="https://bioregistry.io/orcid:0000-0003-4423-4370">
Charles Tapley Hoyt (orcid:0000-0003-4423-4370)
</a>
</li>
</ul>

Artifacts from this resource can be downloaded from Zenodo at
[![](https://zenodo.org/badge/DOI/10.5281/zenodo.11091421.svg)](https://doi.org/10.5281/zenodo.11091421).

## Reproduction

The SeMRA Protein Complex Mappings Database can be rebuilt with the following
commands:

```console
$ git clone https://github.com/biopragmatics/semra.git
$ cd semra
$ uv pip install .[landscape]
$ python -m semra.landscape.complex
```

Note that downloading raw data resources can take on the order of hours to tens
of hours depending on your internet connection and the reliability of the
resources' respective servers.

A full resource refresh (i.e., re-download of resources) was run in 3 minutes on
commodity hardware (e.g., a 2023 MacBook Pro with 36GB RAM).

## Resource Summary

The following resources are represented in processed mappings generated. They
are summarized in the following table that includes their
[Bioregistry](https://bioregistry.io) prefix, license, current version, and
number of terms (i.e., named concepts) they contain.

| prefix        | name                                | license      | version    | terms | status   |
| :------------ | :---------------------------------- | :----------- | :--------- | ----: | :------- |
| complexportal | Complex Portal                      | CC0-1.0      | 2025-03-28 |  5031 | full     |
| fplx          | FamPlex                             | CC0-1.0      |            |   782 | full     |
| go            | Gene Ontology                       | CC-BY-4.0    | 2025-06-01 |  2059 | subset   |
| chembl.target | ChEMBL target                       | CC-BY-SA-3.0 | 35         |   689 | subset   |
| wikidata      | Wikidata                            | CC0-1.0      |            | 48581 | observed |
| scomp         | Selventa Complexes                  | Apache-2.0   |            |   135 | full     |
| signor        | Signaling Network Open Resource     | CC-BY-NC-4.0 | 2025-07-01 |   856 | full     |
| intact        | IntAct protein interaction database | CC-BY-4.0    | 2025-03-28 |  3766 | full     |

There are a total of 61,899 terms across the 8 resources.

## Mapping Summary and Usage

### Raw Mappings

The raw mappings are the ones directly read from the 9 sources.

- This table is symmetric, i.e., taking into account mappings from both the
  source and target.
- Diagonals represent the number of entities in the resource (or the number that
  are observed in the mappings, in some cases)
- All predicate types are combined in this table.

| source_prefix | complexportal | fplx |   go | chembl.target | wikidata | scomp | signor | intact |
| :------------ | ------------: | ---: | ---: | ------------: | -------: | ----: | -----: | -----: |
| complexportal |          5031 |    5 |    0 |           203 |     4759 |     0 |    267 |   3315 |
| fplx          |             5 |  782 |   46 |             0 |        0 |    66 |    118 |      0 |
| go            |             0 |   46 | 2059 |             0 |        0 |     0 |      0 |      3 |
| chembl.target |           203 |    0 |    0 |           689 |        0 |     0 |      0 |      0 |
| wikidata      |          4759 |    0 |    0 |             0 |    48581 |     0 |      0 |      0 |
| scomp         |             0 |   66 |    0 |             0 |        0 |   135 |      0 |      0 |
| signor        |           267 |  118 |    0 |             0 |        0 |     0 |    856 |      0 |
| intact        |          3315 |    0 |    3 |             0 |        0 |     0 |      0 |   3766 |

The raw mappings can be downloaded from
[![](https://zenodo.org/badge/DOI/10.5281/zenodo.11091421.svg)](https://doi.org/10.5281/zenodo.11091421).
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
confidence filtering. The following prior knowledge was used during processing:

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
<tr>
<td>go</td>
<td>(all)</td>
<td>oboinowl:hasDbXref</td>
<td>skos:exactMatch</td>
<td align="right">0.95</td>
</tr>
</tbody>
</table>
After processing, only mappings with subjects and objects whose references both
use the following prefixes were retained:

<ul>
<li>complexportal</li>
<li>fplx</li>
<li>go</li>
<li>chembl.target</li>
<li>wikidata</li>
<li>scomp</li>
<li>signor</li>
<li>intact</li>
</ul>

The processed mappings table has the following qualities:

- This table is symmetric, i.e., taking into account mappings from the source,
  target, and inference
- Diagonals represent the number of entities in the resource (or the number that
  are observed in the mappings, in some cases)
- Only exact matches are retained

| source_prefix | complexportal | fplx |   go | chembl.target | wikidata | scomp | signor | intact |
| :------------ | ------------: | ---: | ---: | ------------: | -------: | ----: | -----: | -----: |
| complexportal |          5031 |    7 |    3 |           203 |     4761 |     2 |    267 |   3315 |
| fplx          |             7 |  782 |   50 |             0 |      411 |    66 |    118 |      5 |
| go            |             3 |   50 | 2059 |             0 |       44 |    25 |     11 |      5 |
| chembl.target |           203 |    0 |    0 |           689 |        0 |     0 |      0 |      0 |
| wikidata      |          4761 |  411 |   44 |             0 |    48581 |    60 |     86 |   2043 |
| scomp         |             2 |   66 |   25 |             0 |       60 |   135 |     14 |      2 |
| signor        |           267 |  118 |   11 |             0 |       86 |    14 |    856 |      0 |
| intact        |          3315 |    5 |    5 |             0 |     2043 |     2 |      0 |   3766 |

The processed mappings can be downloaded from
[![](https://zenodo.org/badge/DOI/10.5281/zenodo.11091421.svg)](https://doi.org/10.5281/zenodo.11091421).
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
<li><a href="https://bioregistry.io/complexportal">Complex Portal (<code>complexportal</code>)</a></li>
<li><a href="https://bioregistry.io/fplx">FamPlex (<code>fplx</code>)</a></li>
<li><a href="https://bioregistry.io/go">Gene Ontology (<code>go</code>)</a></li>
<li><a href="https://bioregistry.io/chembl.target">ChEMBL target (<code>chembl.target</code>)</a></li>
<li><a href="https://bioregistry.io/wikidata">Wikidata (<code>wikidata</code>)</a></li>
<li><a href="https://bioregistry.io/scomp">Selventa Complexes (<code>scomp</code>)</a></li>
<li><a href="https://bioregistry.io/signor">Signaling Network Open Resource (<code>signor</code>)</a></li>
<li><a href="https://bioregistry.io/intact">IntAct protein interaction database (<code>intact</code>)</a></li>
</ol>

The priority mappings can be downloaded from
[![](https://zenodo.org/badge/DOI/10.5281/zenodo.11091421.svg)](https://doi.org/10.5281/zenodo.11091421).
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

## Web Application

1. Download all artifacts from
   [![](https://zenodo.org/badge/DOI/10.5281/zenodo.11091421.svg)](https://doi.org/10.5281/zenodo.11091421)
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

| source_prefix | complexportal | fplx |  go | chembl.target | wikidata | scomp | signor | intact |
| :------------ | ------------: | ---: | --: | ------------: | -------: | ----: | -----: | -----: |
| complexportal |             0 |    2 |   3 |             0 |        2 |     2 |      0 |      0 |
| fplx          |             2 |    0 |   4 |             0 |      411 |     0 |      0 |      5 |
| go            |             3 |    4 |   0 |             0 |       44 |    25 |     11 |      2 |
| chembl.target |             0 |    0 |   0 |             0 |        0 |     0 |      0 |      0 |
| wikidata      |             2 |  411 |  44 |             0 |        0 |    60 |     86 |   2043 |
| scomp         |             2 |    0 |  25 |             0 |       60 |     0 |     14 |      2 |
| signor        |             0 |    0 |  11 |             0 |       86 |    14 |      0 |      0 |
| intact        |             0 |    5 |   2 |             0 |     2043 |     2 |      0 |      0 |

Here's an alternative view on the number of mappings normalized to show
percentage gain. Note that:

- `inf` means that there were no mappings before and now there are a non-zero
  number of mappings
- `NaN` means there were no mappings before inference and continue to be no
  mappings after inference

| source_prefix | complexportal | fplx |   go | chembl.target | wikidata | scomp | signor | intact |
| :------------ | ------------: | ---: | ---: | ------------: | -------: | ----: | -----: | -----: |
| complexportal |             0 |   40 |  inf |             0 |        0 |   inf |      0 |      0 |
| fplx          |            40 |    0 |  8.7 |           nan |      inf |     0 |      0 |    inf |
| go            |           inf |  8.7 |    0 |           nan |      inf |   inf |    inf |   66.7 |
| chembl.target |             0 |  nan |  nan |             0 |      nan |   nan |    nan |    nan |
| wikidata      |             0 |  inf |  inf |           nan |        0 |   inf |    inf |    inf |
| scomp         |           inf |    0 |  inf |           nan |      inf |     0 |    inf |    inf |
| signor        |             0 |    0 |  inf |           nan |      inf |   inf |      0 |    nan |
| intact        |             0 |  inf | 66.7 |           nan |      inf |   inf |    nan |      0 |

### Landscape Analysis

Above, the comparison looked at the overlaps between each resource. Now, that
information is used to jointly estimate the number of terms in the landscape
itself, and estimate how much of the landscape each resource covers.

This estimates a total of 8,475 unique entities.

- 5,278 (62.3%) have at least one mapping.
- 3,197 (37.7%) are unique to a single resource.
- 0 (0.0%) appear in all 8 resources.

This estimate is susceptible to several caveats:

- Missing mappings inflates this measurement
- Generic resources like MeSH contain irrelevant entities that can't be mapped

Because there are 8 prefixes, there are 255 possible overlaps to consider.
Therefore, a Venn diagram is not possible, so an
[UpSet plot](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4720993) (Lex _et
al._, 2014) is used as a high-dimensional Venn diagram.

![](processed_landscape_upset.svg)

Next, the mappings are aggregated to estimate the number of unique entities and
number that appear in each group of resources.

![](processed_landscape_histogram.svg)

The landscape of 8 resources has 61,899 total terms. After merging redundant
nodes based on mappings, inference, and reasoning, there are 8,475 unique
concepts. Using the reduction formula
$\frac{{\text{{total terms}} - \text{{reduced terms}}}}{{\text{{total terms}}}}$,
this is a 86.31% reduction.

This is only an estimate and is susceptible to a few things:

1. It can be artificially high because there are entities that _should_ be
   mapped, but are not
1. It can be artificially low because there are entities that are incorrectly
   mapped, e.g., as a result of inference. The frontend curation interface can
   help identify and remove these
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
