# SeMRA Cell and Cell Line Mappings Database

Originally a reproduction of the EFO/Cellosaurus/DepMap/CCLE scenario posed in
the Biomappings paper, this configuration imports several different cell and
cell line resources and identifies mappings between them. Created by:

<ul>
<li>
<a href="https://bioregistry.io/orcid:0000-0003-4423-4370">
Charles Tapley Hoyt (orcid:0000-0003-4423-4370)
</a>
</li>
</ul>

## Reproduction

The SeMRA Cell and Cell Line Mappings Database can be rebuilt with the following commands:

```console
$ git clone https://github.com/biopragmatics/semra.git
$ cd semra
$ uv pip install .[landscape]
$ python -m semra.landscape.cell
```

Note that downloading raw data resources can take on the order of hours to tens
of hours depending on your internet connection and the reliability of
the resources' respective servers.

Processing and analysis can be run overnight on commodity hardware
(e.g., a 2023 MacBook Pro with 36GB RAM).

## Resource Summary

The following resources are represented in processed mappings generated. They
are summarized in the following table that includes their
[Bioregistry](https://bioregistry.io) prefix, license, current version, and
number of terms (i.e., named concepts) they contain.

| prefix      | name                                                      | license                                                                                              | version    |  terms | status |
| :---------- | :-------------------------------------------------------- | :--------------------------------------------------------------------------------------------------- | :--------- | -----: | :----- |
| mesh        | Medical Subject Headings                                  | CC0-1.0                                                                                              | 2025       |    636 | subset |
| efo         | Experimental Factor Ontology                              | Apache-2.0                                                                                           | 3.77.0     |     27 | subset |
| cellosaurus | Cellosaurus                                               | CC-BY-4.0                                                                                            | 52.0       | 163868 | full   |
| ccle        | Cancer Cell Line Encyclopedia Cells                       | ODbL-1.0                                                                                             |            |   1739 | full   |
| depmap      | DepMap Cell Lines                                         | CC-BY-4.0                                                                                            | 24Q4       |   1814 | full   |
| bto         | BRENDA Tissue Ontology                                    | CC-BY-4.0                                                                                            | 2021-10-26 |   6566 | full   |
| cl          | Cell Ontology                                             | CC-BY-4.0                                                                                            | 2025-04-10 |   3095 | full   |
| clo         | Cell Line Ontology                                        | CC-BY-3.0                                                                                            | 2.1.188    |  39099 | full   |
| ncit        | NCI Thesaurus                                             | CC-BY-4.0                                                                                            | 25.05d     |    503 | subset |
| umls        | Unified Medical Language System Concept Unique Identifier | https://www.nlm.nih.gov/research/umls/knowledge_sources/metathesaurus/release/license_agreement.html | 2025AA     |   6341 | subset |

There are a total of 223,688 terms across the 10 resources.

## Mapping Summary and Usage

### Raw Mappings

The raw mappings are the ones directly read from the 11 sources.

- This table is symmetric, i.e., taking into account mappings from both the
  source and target.
- Diagonals represent the number of entities in the resource (or the number that
  are observed in the mappings, in some cases)
- All predicate types are combined in this table.

| source_prefix | mesh | efo | cellosaurus | ccle | depmap |  bto |   cl |   clo | ncit | umls |
| :------------ | ---: | --: | ----------: | ---: | -----: | ---: | ---: | ----: | ---: | ---: |
| mesh          |  636 |   3 |          30 |    0 |      0 |    0 |   85 |    34 |    6 |  433 |
| efo           |    3 |  27 |           4 |    0 |      0 |    2 |    0 |     3 |    1 |    0 |
| cellosaurus   |   30 |   4 |      163868 |  114 |   1895 | 2436 |    0 | 34152 |    0 |    0 |
| ccle          |    0 |   0 |         114 | 1739 |   1700 |    2 |    0 |     0 |    0 |    0 |
| depmap        |    0 |   0 |        1895 | 1700 |   1814 |    0 |    0 |     0 |    0 |    0 |
| bto           |    0 |   2 |        2436 |    2 |      0 | 6566 |  330 |     6 |    0 |    0 |
| cl            |   85 |   0 |           0 |    0 |      0 |  330 | 3095 |     0 |    6 |    0 |
| clo           |   34 |   3 |       34152 |    0 |      0 |    6 |    0 | 39099 |    0 |    0 |
| ncit          |    6 |   1 |           0 |    0 |      0 |    0 |    6 |     0 |  503 |  497 |
| umls          |  433 |   0 |           0 |    0 |      0 |    0 |    0 |     0 |  497 | 6341 |

The processed mappings can be accessed via the
[SeMRA](https://github.com/biopragmatics/semra) Python Package using the
following examples:

```python
import semra.io

# Load from JSONL
mappings = semra.io.from_jsonl("raw.jsonl.gz")

# Load from SSSOM
mappings = semra.io.from_sssom("raw.sssom.tsv.gz")
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
<li>mesh</li>
<li>efo</li>
<li>cellosaurus</li>
<li>ccle</li>
<li>depmap</li>
<li>bto</li>
<li>cl</li>
<li>clo</li>
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
<td>efo</td>
<td>(all)</td>
<td>oboinowl:hasDbXref</td>
<td>skos:exactMatch</td>
<td align="right">0.7</td>
</tr>
<tr>
<td>bto</td>
<td>(all)</td>
<td>oboinowl:hasDbXref</td>
<td>skos:exactMatch</td>
<td align="right">0.7</td>
</tr>
<tr>
<td>cl</td>
<td>(all)</td>
<td>oboinowl:hasDbXref</td>
<td>skos:exactMatch</td>
<td align="right">0.7</td>
</tr>
<tr>
<td>clo</td>
<td>(all)</td>
<td>oboinowl:hasDbXref</td>
<td>skos:exactMatch</td>
<td align="right">0.7</td>
</tr>
<tr>
<td>depmap</td>
<td>(all)</td>
<td>oboinowl:hasDbXref</td>
<td>skos:exactMatch</td>
<td align="right">0.7</td>
</tr>
<tr>
<td>ccle</td>
<td>(all)</td>
<td>oboinowl:hasDbXref</td>
<td>skos:exactMatch</td>
<td align="right">0.7</td>
</tr>
<tr>
<td>cellosaurus</td>
<td>(all)</td>
<td>oboinowl:hasDbXref</td>
<td>skos:exactMatch</td>
<td align="right">0.7</td>
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

| source_prefix | mesh | efo | cellosaurus | ccle | depmap |  bto |   cl |   clo | ncit | umls |
| :------------ | ---: | --: | ----------: | ---: | -----: | ---: | ---: | ----: | ---: | ---: |
| mesh          |  636 |   3 |          32 |    6 |      6 |   62 |   85 |    34 |    7 |  433 |
| efo           |    3 |  27 |           4 |    0 |      0 |    2 |    0 |     5 |    1 |    1 |
| cellosaurus   |   32 |   4 |      163868 | 1699 |   1913 | 2436 |    1 | 34153 |    0 |    0 |
| ccle          |    6 |   0 |        1699 | 1739 |   1700 |  648 |    0 |  1417 |    0 |    0 |
| depmap        |    6 |   0 |        1913 | 1700 |   1814 |  668 |    0 |  1473 |    0 |    0 |
| bto           |   62 |   2 |        2436 |  648 |    668 | 6566 |  330 |  1436 |    7 |    7 |
| cl            |   85 |   0 |           1 |    0 |      0 |  330 | 3095 |     0 |    8 |    8 |
| clo           |   34 |   5 |       34153 | 1417 |   1473 | 1436 |    0 | 39099 |    0 |    0 |
| ncit          |    7 |   1 |           0 |    0 |      0 |    7 |    8 |     0 |  503 |  497 |
| umls          |  433 |   1 |           0 |    0 |      0 |    7 |    8 |     0 |  497 | 6341 |

The processed mappings can be accessed via the
[SeMRA](https://github.com/biopragmatics/semra) Python Package using the
following examples:

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

A prioritization mapping is a special subset of processed mappings constructed
using the prefix priority list. This mapping has the feature that every entity
appears as a subject exactly once, with the object of its mapping being the
priority entity. This creates a "star graph" for each priority entity.

The prioritization for this output is:

<ol>
<li><a href="https://bioregistry.io/mesh">Medical Subject Headings (<code>mesh</code>)</a></li>
<li><a href="https://bioregistry.io/efo">Experimental Factor Ontology (<code>efo</code>)</a></li>
<li><a href="https://bioregistry.io/cellosaurus">Cellosaurus (<code>cellosaurus</code>)</a></li>
<li><a href="https://bioregistry.io/ccle">Cancer Cell Line Encyclopedia Cells (<code>ccle</code>)</a></li>
<li><a href="https://bioregistry.io/depmap">DepMap Cell Lines (<code>depmap</code>)</a></li>
<li><a href="https://bioregistry.io/bto">BRENDA Tissue Ontology (<code>bto</code>)</a></li>
<li><a href="https://bioregistry.io/cl">Cell Ontology (<code>cl</code>)</a></li>
<li><a href="https://bioregistry.io/clo">Cell Line Ontology (<code>clo</code>)</a></li>
<li><a href="https://bioregistry.io/ncit">NCI Thesaurus (<code>ncit</code>)</a></li>
<li><a href="https://bioregistry.io/umls">Unified Medical Language System Concept Unique Identifier (<code>umls</code>)</a></li>
</ol>

The processed mappings can be accessed via the
[SeMRA](https://github.com/biopragmatics/semra) Python Package using the
following examples:

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
3. Navigate to http://localhost:8773 to see the SeMRA dashboard or to
   http://localhost:7474 for direct access to the Neo4j graph database

## Analyses

### Comparison Analysis

The following comparison shows the absolute number of mappings added by
processing/inference. Across the board, this process adds large numbers of
mappings to most resources, especially ones that were previously only connected
to a small number of other resources.

| source_prefix | mesh | efo | cellosaurus | ccle | depmap |  bto |  cl |  clo | ncit | umls |
| :------------ | ---: | --: | ----------: | ---: | -----: | ---: | --: | ---: | ---: | ---: |
| mesh          |    0 |   0 |           2 |    6 |      6 |   62 |   0 |    0 |    1 |    0 |
| efo           |    0 |   0 |           0 |    0 |      0 |    0 |   0 |    2 |    0 |    1 |
| cellosaurus   |    2 |   0 |           0 | 1585 |     18 |    0 |   1 |    1 |    0 |    0 |
| ccle          |    6 |   0 |        1585 |    0 |      0 |  646 |   0 | 1417 |    0 |    0 |
| depmap        |    6 |   0 |          18 |    0 |      0 |  668 |   0 | 1473 |    0 |    0 |
| bto           |   62 |   0 |           0 |  646 |    668 |    0 |   0 | 1430 |    7 |    7 |
| cl            |    0 |   0 |           1 |    0 |      0 |    0 |   0 |    0 |    2 |    8 |
| clo           |    0 |   2 |           1 | 1417 |   1473 | 1430 |   0 |    0 |    0 |    0 |
| ncit          |    1 |   0 |           0 |    0 |      0 |    7 |   2 |    0 |    0 |    0 |
| umls          |    0 |   1 |           0 |    0 |      0 |    7 |   8 |    0 |    0 |    0 |

Here's an alternative view on the number of mappings normalized to show
percentage gain. Note that:

- `inf` means that there were no mappings before and now there are a non-zero
  number of mappings
- `NaN` means there were no mappings before inference and continue to be no
  mappings after inference

| source_prefix | mesh |  efo | cellosaurus |   ccle | depmap |     bto |   cl |     clo | ncit | umls |
| :------------ | ---: | ---: | ----------: | -----: | -----: | ------: | ---: | ------: | ---: | ---: |
| mesh          |    0 |    0 |         6.7 |    inf |    inf |     inf |    0 |       0 | 16.7 |    0 |
| efo           |    0 |    0 |           0 |    nan |    nan |       0 |  nan |    66.7 |    0 |  inf |
| cellosaurus   |  6.7 |    0 |           0 | 1390.4 |    0.9 |       0 |  inf |       0 |  nan |  nan |
| ccle          |  inf |  nan |      1390.4 |      0 |      0 |   32300 |  nan |     inf |  nan |  nan |
| depmap        |  inf |  nan |         0.9 |      0 |      0 |     inf |  nan |     inf |  nan |  nan |
| bto           |  inf |    0 |           0 |  32300 |    inf |       0 |    0 | 23833.3 |  inf |  inf |
| cl            |    0 |  nan |         inf |    nan |    nan |       0 |    0 |     nan | 33.3 |  inf |
| clo           |    0 | 66.7 |           0 |    inf |    inf | 23833.3 |  nan |       0 |  nan |  nan |
| ncit          | 16.7 |    0 |         nan |    nan |    nan |     inf | 33.3 |     nan |    0 |    0 |
| umls          |    0 |  inf |         nan |    nan |    nan |     inf |  inf |     nan |    0 |    0 |

### Landscape Analysis

Above, the comparison looked at the overlaps between each resource. Now, that
information is used to jointly estimate the number of terms in the landscape
itself, and estimate how much of the landscape each resource covers.

This estimates a total of 44,114 unique entities.

- 35,711 (81.0%) have at least one mapping.
- 8,403 (19.0%) are unique to a single resource.
- 0 (0.0%) appear in all 10 resources.

This estimate is susceptible to several caveats:

- Missing mappings inflates this measurement
- Generic resources like MeSH contain irrelevant entities that can't be mapped

Because there are 10 prefixes, there are 1,023 possible overlaps to consider.
Therefore, a Venn diagram is not possible, so an
[UpSet plot](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4720993) (Lex _et
al._, 2014) is used as a high-dimensional Venn diagram.

![](processed_landscape_upset.svg)

Next, the mappings are aggregated to estimate the number of unique entities and
number that appear in each group of resources.

![](processed_landscape_histogram.svg)

The landscape of 10 resources has 223,688 total terms. After merging redundant
nodes based on mappings, inference, and reasoning, there are 44,114 unique
concepts. Using the reduction formula
$\frac{{\text{{total terms}} - \text{{reduced terms}}}}{{\text{{total terms}}}}$,
this is a 80.28% reduction.

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
