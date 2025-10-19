# SeMRA Anatomy Mappings Database

Supports the analysis of the landscape of anatomy nomenclature resources.
Created by:

<ul>
<li>
<a href="https://bioregistry.io/orcid:0000-0003-4423-4370">
Charles Tapley Hoyt (orcid:0000-0003-4423-4370)
</a>
</li>
</ul>

Artifacts from this resource can be downloaded from Zenodo at
[![](https://zenodo.org/badge/DOI/10.5281/zenodo.11091802.svg)](https://doi.org/10.5281/zenodo.11091802).

## Reproduction

The SeMRA Anatomy Mappings Database can be rebuilt with the following commands:

```console
$ git clone https://github.com/biopragmatics/semra.git
$ cd semra
$ uv pip install .[landscape]
$ python -m semra.landscape.anatomy
```

Note that downloading raw data resources can take on the order of hours to tens
of hours depending on your internet connection and the reliability of the
resources' respective servers.

A full resource refresh (i.e., re-download of resources) was run in an hour on
commodity hardware (e.g., a 2023 MacBook Pro with 36GB RAM).

## Resource Summary

The following resources are represented in processed mappings generated. They
are summarized in the following table that includes their
[Bioregistry](https://bioregistry.io) prefix, license, current version, and
number of terms (i.e., named concepts) they contain.

| prefix | name                                                      | license                                                                                              | version    | terms | status |
| :----- | :-------------------------------------------------------- | :--------------------------------------------------------------------------------------------------- | :--------- | ----: | :----- |
| uberon | Uber Anatomy Ontology                                     | CC-BY-3.0                                                                                            | 2025-05-28 | 15693 | full   |
| mesh   | Medical Subject Headings                                  | CC0-1.0                                                                                              | 2025       |  1797 | subset |
| bto    | BRENDA Tissue Ontology                                    | CC-BY-4.0                                                                                            | 2021-10-26 |  6566 | full   |
| caro   | Common Anatomy Reference Ontology                         | CC-BY-4.0                                                                                            | 2023-03-15 |    90 | full   |
| ncit   | NCI Thesaurus                                             | CC-BY-4.0                                                                                            | 25.06e     |  7579 | subset |
| umls   | Unified Medical Language System Concept Unique Identifier | https://www.nlm.nih.gov/research/umls/knowledge_sources/metathesaurus/release/license_agreement.html | 2025AA     |  7719 | subset |

There are a total of 39,444 terms across the 6 resources.

## Mapping Summary and Usage

### Raw Mappings

The raw mappings are the ones directly read from the 8 sources.

- This table is symmetric, i.e., taking into account mappings from both the
  source and target.
- Diagonals represent the number of entities in the resource (or the number that
  are observed in the mappings, in some cases)
- All predicate types are combined in this table.

| source_prefix | uberon | mesh |  bto | caro | ncit | umls |
| :------------ | -----: | ---: | ---: | ---: | ---: | ---: |
| uberon        |  15693 | 1080 | 1465 |    0 | 2527 |  280 |
| mesh          |   1080 | 1797 |    0 |    0 |   28 |  159 |
| bto           |   1465 |    0 | 6566 |    0 |    0 |    0 |
| caro          |      0 |    0 |    0 |   90 |    0 |    0 |
| ncit          |   2527 |   28 |    0 |    0 | 7579 |  519 |
| umls          |    280 |  159 |    0 |    0 |  519 | 7719 |

The raw mappings can be downloaded from
[![](https://zenodo.org/badge/DOI/10.5281/zenodo.11091802.svg)](https://doi.org/10.5281/zenodo.11091802).
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
confidence filtering. Before processing, only mappings with subjects and objects
whose references both use the following prefixes were retained:

<ul>
<li>uberon</li>
<li>mesh</li>
<li>bto</li>
<li>caro</li>
<li>ncit</li>
<li>umls</li>
</ul>
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
<tr>
<td>uberon</td>
<td>(all)</td>
<td>oboinowl:hasDbXref</td>
<td>skos:exactMatch</td>
<td align="right">0.8</td>
</tr>
<tr>
<td>bto</td>
<td>(all)</td>
<td>oboinowl:hasDbXref</td>
<td>skos:exactMatch</td>
<td align="right">0.65</td>
</tr>
<tr>
<td>caro</td>
<td>(all)</td>
<td>oboinowl:hasDbXref</td>
<td>skos:exactMatch</td>
<td align="right">0.8</td>
</tr>
<tr>
<td>ncit</td>
<td>(all)</td>
<td>oboinowl:hasDbXref</td>
<td>skos:exactMatch</td>
<td align="right">0.7</td>
</tr>
<tr>
<td>umls</td>
<td>(all)</td>
<td>oboinowl:hasDbXref</td>
<td>skos:exactMatch</td>
<td align="right">0.7</td>
</tr>
</tbody>
</table>

The processed mappings table has the following qualities:

- This table is symmetric, i.e., taking into account mappings from the source,
  target, and inference
- Diagonals represent the number of entities in the resource (or the number that
  are observed in the mappings, in some cases)
- Only exact matches are retained

| source_prefix | uberon | mesh |  bto | caro | ncit | umls |
| :------------ | -----: | ---: | ---: | ---: | ---: | ---: |
| uberon        |  15693 | 1107 | 1465 |    0 | 2536 |  344 |
| mesh          |   1107 | 1797 |  602 |    0 |  859 |  170 |
| bto           |   1465 |  602 | 6566 |    0 |  813 |  150 |
| caro          |      0 |    0 |    0 |   90 |    0 |    0 |
| ncit          |   2536 |  859 |  813 |    0 | 7579 |  547 |
| umls          |    344 |  170 |  150 |    0 |  547 | 7719 |

The processed mappings can be downloaded from
[![](https://zenodo.org/badge/DOI/10.5281/zenodo.11091802.svg)](https://doi.org/10.5281/zenodo.11091802).
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
<li><a href="https://bioregistry.io/uberon">Uber Anatomy Ontology (<code>uberon</code>)</a></li>
<li><a href="https://bioregistry.io/mesh">Medical Subject Headings (<code>mesh</code>)</a></li>
<li><a href="https://bioregistry.io/bto">BRENDA Tissue Ontology (<code>bto</code>)</a></li>
<li><a href="https://bioregistry.io/caro">Common Anatomy Reference Ontology (<code>caro</code>)</a></li>
<li><a href="https://bioregistry.io/ncit">NCI Thesaurus (<code>ncit</code>)</a></li>
<li><a href="https://bioregistry.io/umls">Unified Medical Language System Concept Unique Identifier (<code>umls</code>)</a></li>
</ol>

The priority mappings can be downloaded from
[![](https://zenodo.org/badge/DOI/10.5281/zenodo.11091802.svg)](https://doi.org/10.5281/zenodo.11091802).
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
   [![](https://zenodo.org/badge/DOI/10.5281/zenodo.11091802.svg)](https://doi.org/10.5281/zenodo.11091802)
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

| source_prefix | uberon | mesh | bto | caro | ncit | umls |
| :------------ | -----: | ---: | --: | ---: | ---: | ---: |
| uberon        |      0 |   27 |   0 |    0 |    9 |   64 |
| mesh          |     27 |    0 | 602 |    0 |  831 |   11 |
| bto           |      0 |  602 |   0 |    0 |  813 |  150 |
| caro          |      0 |    0 |   0 |    0 |    0 |    0 |
| ncit          |      9 |  831 | 813 |    0 |    0 |   28 |
| umls          |     64 |   11 | 150 |    0 |   28 |    0 |

Here's an alternative view on the number of mappings normalized to show
percentage gain. Note that:

- `inf` means that there were no mappings before and now there are a non-zero
  number of mappings
- `NaN` means there were no mappings before inference and continue to be no
  mappings after inference

| source_prefix | uberon |   mesh | bto | caro |   ncit | umls |
| :------------ | -----: | -----: | --: | ---: | -----: | ---: |
| uberon        |      0 |    2.5 |   0 |  nan |    0.4 | 22.9 |
| mesh          |    2.5 |      0 | inf |  nan | 2967.9 |  6.9 |
| bto           |      0 |    inf |   0 |  nan |    inf |  inf |
| caro          |    nan |    nan | nan |    0 |    nan |  nan |
| ncit          |    0.4 | 2967.9 | inf |  nan |      0 |  5.4 |
| umls          |   22.9 |    6.9 | inf |  nan |    5.4 |    0 |

### Landscape Analysis

Above, the comparison looked at the overlaps between each resource. Now, that
information is used to jointly estimate the number of terms in the landscape
itself, and estimate how much of the landscape each resource covers.

This estimates a total of 18,067 unique entities.

- 3,554 (19.7%) have at least one mapping.
- 14,513 (80.3%) are unique to a single resource.
- 1 (0.0%) appear in all 6 resources.

This estimate is susceptible to several caveats:

- Missing mappings inflates this measurement
- Generic resources like MeSH contain irrelevant entities that can't be mapped

Because there are 6 prefixes, there are 63 possible overlaps to consider.
Therefore, a Venn diagram is not possible, so an
[UpSet plot](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4720993) (Lex _et
al._, 2014) is used as a high-dimensional Venn diagram.

![](processed_landscape_upset.svg)

Next, the mappings are aggregated to estimate the number of unique entities and
number that appear in each group of resources.

![](processed_landscape_histogram.svg)

The landscape of 6 resources has 39,444 total terms. After merging redundant
nodes based on mappings, inference, and reasoning, there are 18,067 unique
concepts. Using the reduction formula
$\frac{{\text{{total terms}} - \text{{reduced terms}}}}{{\text{{total terms}}}}$,
this is a 54.20% reduction.

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
