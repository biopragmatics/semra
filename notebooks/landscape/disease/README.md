# SeMRA Disease Mappings Database

Supports the analysis of the landscape of disease nomenclature resources.
Created by:

<ul>
<li>
<a href="https://bioregistry.io/orcid:0000-0003-4423-4370">
Charles Tapley Hoyt (orcid:0000-0003-4423-4370)
</a>
</li>
</ul>

## Resource Summary

The following resources are represented in processed mappings generated. They
are summarized in the following table that includes their
[Bioregistry](https://bioregistry.io) prefix, license, current version, and
number of terms (i.e., named concepts) they contain.

2 resources were not available through
[PyOBO](https://github.com/biopragmatics/pyobo). Therefore, the number of terms
in that resource are estimated based on the ones that are observed in mappings
assembled by SeMRA. Note that these are typically an underestimate.

| prefix        | name                                                                             | license                                                                                                  | version    |  terms | status   |
| :------------ | :------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------- | :--------- | -----: | :------- |
| doid          | Human Disease Ontology                                                           | CC0-1.0                                                                                                  | 2025-05-30 |  14372 | full     |
| mondo         | Mondo Disease Ontology                                                           | CC-BY-4.0                                                                                                | 2025-04-01 |  30086 | full     |
| efo           | Experimental Factor Ontology                                                     | Apache-2.0                                                                                               | 3.77.0     |   2126 | subset   |
| mesh          | Medical Subject Headings                                                         | CC0-1.0                                                                                                  | 2025       |   3178 | subset   |
| ncit          | NCI Thesaurus                                                                    | CC-BY-4.0                                                                                                | 25.05d     |  20522 | subset   |
| orphanet      | Orphanet                                                                         | CC-BY-4.0                                                                                                |            |  15066 | observed |
| orphanet.ordo | Orphanet Rare Disease Ontology                                                   | CC-BY-4.0                                                                                                | 4.6        |  15590 | full     |
| umls          | Unified Medical Language System Concept Unique Identifier                        | https://www.nlm.nih.gov/research/umls/knowledge_sources/metathesaurus/release/license_agreement.html     | 2025AA     | 189003 | subset   |
| omim          | Online Mendelian Inheritance in Man                                              | https://www.omim.org/help/agreement                                                                      | 2025-05-29 |  15261 | observed |
| omim.ps       | OMIM Phenotypic Series                                                           | https://www.omim.org/help/agreement                                                                      | 2025-05-29 |    590 | full     |
| gard          | Genetic and Rare Diseases Information Center                                     |                                                                                                          |            |   6109 | full     |
| icd10         | International Classification of Diseases, 10th Revision                          | https://cdn.who.int/media/docs/default-source/publishing-policies/copyright/who-faq-licensing-icd-10.pdf | 2019       |   2345 | full     |
| icd10cm       | International Classification of Diseases, 10th Revision, Clinical Modification   |                                                                                                          |            |  21709 | observed |
| icd10pcs      | International Classification of Diseases, 10th Revision, Procedure Coding System |                                                                                                          |            |      0 | observed |
| icd11         | International Classification of Diseases, 11th Revision (Foundation Component)   | CC-BY-ND-3.0-IGO                                                                                         | 2025-01    |  71175 | full     |
| icd11.code    | ICD 11 Codes                                                                     | http://www.who.int/about/licensing/copyright_form/en                                                     |            |      0 | observed |
| icd9          | International Classification of Diseases, 9th Revision                           |                                                                                                          |            |   3963 | observed |
| icd9cm        | International Classification of Diseases, 9th Revision, Clinical Modification    |                                                                                                          |            |   9134 | observed |
| icdo          | International Classification of Diseases for Oncology                            |                                                                                                          |            |    797 | observed |

There are a total of 421,026 terms across the 19 resources.

## Mapping Summary and Usage

### Raw Mappings

The raw mappings are the ones directly read from the 9 sources.

- This table is symmetric, i.e., taking into account mappings from both the
  source and target.
- Diagonals represent the number of entities in the resource (or the number that
  are observed in the mappings, in some cases)
- All predicate types are combined in this table.

| source_prefix |  doid | mondo |  efo | mesh |  ncit | orphanet | orphanet.ordo |   umls |  omim | omim.ps |  gard | icd10 | icd10cm | icd10pcs | icd11 | icd11.code | icd9 | icd9cm | icdo |
| :------------ | ----: | ----: | ---: | ---: | ----: | -------: | ------------: | -----: | ----: | ------: | ----: | ----: | ------: | -------: | ----: | ---------: | ---: | -----: | ---: |
| doid          | 14372 | 11639 | 1243 |  628 |  4636 |     2208 |             0 |   6773 |  5886 |       0 |  2136 |     0 |    3537 |        0 |     2 |          0 |   11 |   2225 |  488 |
| mondo         | 11639 | 30086 | 1448 |  864 |  7149 |    10288 |             0 |  19271 | 10027 |     597 | 10730 |    18 |    1691 |        0 |  4138 |          0 | 4417 |      2 |  725 |
| efo           |  1243 |  1448 | 2126 |  434 |  1104 |      361 |             0 |   1335 |   317 |      23 |   289 |   525 |     293 |        0 |   410 |          0 | 1194 |      5 |   62 |
| mesh          |   628 |   864 |  434 | 3178 |    27 |      171 |             0 |   2124 |     0 |       0 |     0 |     0 |       0 |        0 |     0 |          0 |    0 |      0 |    0 |
| ncit          |  4636 |  7149 | 1104 |   27 | 20522 |       37 |             0 |  19442 |     0 |       0 |     0 |     0 |       0 |        0 |     0 |          0 |    0 |      0 |    0 |
| orphanet      |  2208 | 10288 |  361 |  171 |    37 |    15066 |             0 |   8834 | 11425 |       5 |    38 |  7850 |       0 |        0 |     1 |          0 |    5 |      0 |    1 |
| orphanet.ordo |     0 |     0 |    0 |    0 |     0 |        0 |         15590 |      0 |     0 |       0 |     0 |     0 |       0 |        0 |     0 |          0 |    0 |      0 |    0 |
| umls          |  6773 | 19271 | 1335 | 2124 | 19442 |     8834 |             0 | 189003 | 13406 |       0 |     0 |  5662 |   25135 |        0 |     0 |          0 |    0 |   9005 |    0 |
| omim          |  5886 | 10027 |  317 |    0 |     0 |    11425 |             0 |  13406 | 15261 |       0 |     0 |     0 |       0 |        0 |     0 |          0 |    0 |      0 |    0 |
| omim.ps       |     0 |   597 |   23 |    0 |     0 |        5 |             0 |      0 |     0 |     590 |     0 |     0 |       0 |        0 |     0 |          0 |    0 |      0 |    0 |
| gard          |  2136 | 10730 |  289 |    0 |     0 |       38 |             0 |      0 |     0 |       0 |  6109 |     0 |       0 |        0 |     0 |          0 |    0 |      0 |    0 |
| icd10         |     0 |    18 |  525 |    0 |     0 |     7850 |             0 |   5662 |     0 |       0 |     0 |  2345 |       0 |        0 |     0 |          0 |    0 |      0 |    0 |
| icd10cm       |  3537 |  1691 |  293 |    0 |     0 |        0 |             0 |  25135 |     0 |       0 |     0 |     0 |   21709 |        0 |     0 |          0 |    0 |      0 |    0 |
| icd10pcs      |     0 |     0 |    0 |    0 |     0 |        0 |             0 |      0 |     0 |       0 |     0 |     0 |       0 |        0 |     0 |          0 |    0 |      0 |    0 |
| icd11         |     2 |  4138 |  410 |    0 |     0 |        1 |             0 |      0 |     0 |       0 |     0 |     0 |       0 |        0 | 71175 |          0 |    0 |      0 |    0 |
| icd11.code    |     0 |     0 |    0 |    0 |     0 |        0 |             0 |      0 |     0 |       0 |     0 |     0 |       0 |        0 |     0 |          0 |    0 |      0 |    0 |
| icd9          |    11 |  4417 | 1194 |    0 |     0 |        5 |             0 |      0 |     0 |       0 |     0 |     0 |       0 |        0 |     0 |          0 | 3963 |      0 |    0 |
| icd9cm        |  2225 |     2 |    5 |    0 |     0 |        0 |             0 |   9005 |     0 |       0 |     0 |     0 |       0 |        0 |     0 |          0 |    0 |   9134 |    0 |
| icdo          |   488 |   725 |   62 |    0 |     0 |        1 |             0 |      0 |     0 |       0 |     0 |     0 |       0 |        0 |     0 |          0 |    0 |      0 |  797 |

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
<li>doid</li>
<li>mondo</li>
<li>efo</li>
<li>mesh</li>
<li>ncit</li>
<li>orphanet</li>
<li>orphanet.ordo</li>
<li>umls</li>
<li>omim</li>
<li>omim.ps</li>
<li>gard</li>
<li>icd10</li>
<li>icd10cm</li>
<li>icd10pcs</li>
<li>icd11</li>
<li>icd11.code</li>
<li>icd9</li>
<li>icd9cm</li>
<li>icdo</li>
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
<td>doid</td>
<td>(all)</td>
<td>oboinowl:hasDbXref</td>
<td>skos:exactMatch</td>
<td align="right">0.95</td>
</tr>
<tr>
<td>mondo</td>
<td>(all)</td>
<td>oboinowl:hasDbXref</td>
<td>skos:exactMatch</td>
<td align="right">0.95</td>
</tr>
<tr>
<td>efo</td>
<td>(all)</td>
<td>oboinowl:hasDbXref</td>
<td>skos:exactMatch</td>
<td align="right">0.9</td>
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
<tr>
<td>orphanet.ordo</td>
<td>(all)</td>
<td>oboinowl:hasDbXref</td>
<td>skos:exactMatch</td>
<td align="right">0.7</td>
</tr>
<tr>
<td>orphanet</td>
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

| source_prefix |  doid | mondo |  efo | mesh |  ncit | orphanet | orphanet.ordo |   umls |  omim | omim.ps |  gard | icd10 | icd10cm | icd10pcs | icd11 | icd11.code | icd9 | icd9cm | icdo |
| :------------ | ----: | ----: | ---: | ---: | ----: | -------: | ------------: | -----: | ----: | ------: | ----: | ----: | ------: | -------: | ----: | ---------: | ---: | -----: | ---: |
| doid          | 14372 | 11773 | 1296 |  714 |  5185 |     2696 |             0 |   8162 |  5910 |      62 |  2136 |    11 |    3617 |        0 |     2 |          0 |   11 |   2225 |  488 |
| mondo         | 11773 | 30086 | 1681 |  909 |  7422 |    10301 |             0 |  20841 | 10027 |     597 | 10732 |    18 |    1713 |        0 |  4138 |          0 | 4417 |      5 |  725 |
| efo           |  1296 |  1681 | 2126 |  440 |  1221 |      408 |             0 |   1719 |   323 |      25 |   290 |   525 |     319 |        0 |   410 |          0 | 1194 |      6 |   62 |
| mesh          |   714 |   909 |  440 | 3178 |   407 |      207 |             0 |   2225 |    16 |       2 |     0 |     2 |     197 |        0 |     0 |          0 |    0 |      0 |    0 |
| ncit          |  5185 |  7422 | 1221 |  407 | 20522 |      759 |             0 |  19779 |   218 |      31 |     7 |     9 |     517 |        0 |     0 |          0 |    0 |      2 |    0 |
| orphanet      |  2696 | 10301 |  408 |  207 |   759 |    15066 |             0 |   9204 | 11468 |      55 |    48 |  7850 |     206 |        0 |     1 |          0 |    5 |      3 |    1 |
| orphanet.ordo |     0 |     0 |    0 |    0 |     0 |        0 |         15590 |      0 |     0 |       0 |     0 |     0 |       0 |        0 |     0 |          0 |    0 |      0 |    0 |
| umls          |  8162 | 20841 | 1719 | 2225 | 19779 |     9204 |             0 | 189003 | 13419 |      68 |     9 |  5668 |   25266 |        0 |     0 |          0 |    0 |   9005 |    0 |
| omim          |  5910 | 10027 |  323 |   16 |   218 |    11468 |             0 |  13419 | 15261 |       0 |     5 |     0 |      47 |        0 |     0 |          0 |    0 |      0 |    0 |
| omim.ps       |    62 |   597 |   25 |    2 |    31 |       55 |             0 |     68 |     0 |     590 |     2 |     0 |       8 |        0 |     0 |          0 |    0 |      1 |    0 |
| gard          |  2136 | 10732 |  290 |    0 |     7 |       48 |             0 |      9 |     5 |       2 |  6109 |     0 |       2 |        0 |     0 |          0 |    0 |      2 |    0 |
| icd10         |    11 |    18 |  525 |    2 |     9 |     7850 |             0 |   5668 |     0 |       0 |     0 |  2345 |      10 |        0 |     0 |          0 |    0 |      0 |    0 |
| icd10cm       |  3617 |  1713 |  319 |  197 |   517 |      206 |             0 |  25266 |    47 |       8 |     2 |    10 |   21709 |        0 |     0 |          0 |    0 |      2 |    0 |
| icd10pcs      |     0 |     0 |    0 |    0 |     0 |        0 |             0 |      0 |     0 |       0 |     0 |     0 |       0 |        0 |     0 |          0 |    0 |      0 |    0 |
| icd11         |     2 |  4138 |  410 |    0 |     0 |        1 |             0 |      0 |     0 |       0 |     0 |     0 |       0 |        0 | 71175 |          0 |    0 |      0 |    0 |
| icd11.code    |     0 |     0 |    0 |    0 |     0 |        0 |             0 |      0 |     0 |       0 |     0 |     0 |       0 |        0 |     0 |          0 |    0 |      0 |    0 |
| icd9          |    11 |  4417 | 1194 |    0 |     0 |        5 |             0 |      0 |     0 |       0 |     0 |     0 |       0 |        0 |     0 |          0 | 3963 |      0 |    0 |
| icd9cm        |  2225 |     5 |    6 |    0 |     2 |        3 |             0 |   9005 |     0 |       1 |     2 |     0 |       2 |        0 |     0 |          0 |    0 |   9134 |    0 |
| icdo          |   488 |   725 |   62 |    0 |     0 |        1 |             0 |      0 |     0 |       0 |     0 |     0 |       0 |        0 |     0 |          0 |    0 |      0 |  797 |

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
<li><a href="https://bioregistry.io/doid">Human Disease Ontology (<code>doid</code>)</a></li>
<li><a href="https://bioregistry.io/mondo">Mondo Disease Ontology (<code>mondo</code>)</a></li>
<li><a href="https://bioregistry.io/efo">Experimental Factor Ontology (<code>efo</code>)</a></li>
<li><a href="https://bioregistry.io/mesh">Medical Subject Headings (<code>mesh</code>)</a></li>
<li><a href="https://bioregistry.io/ncit">NCI Thesaurus (<code>ncit</code>)</a></li>
<li><a href="https://bioregistry.io/orphanet">Orphanet (<code>orphanet</code>)</a></li>
<li><a href="https://bioregistry.io/orphanet.ordo">Orphanet Rare Disease Ontology (<code>orphanet.ordo</code>)</a></li>
<li><a href="https://bioregistry.io/umls">Unified Medical Language System Concept Unique Identifier (<code>umls</code>)</a></li>
<li><a href="https://bioregistry.io/omim">Online Mendelian Inheritance in Man (<code>omim</code>)</a></li>
<li><a href="https://bioregistry.io/omim.ps">OMIM Phenotypic Series (<code>omim.ps</code>)</a></li>
<li><a href="https://bioregistry.io/gard">Genetic and Rare Diseases Information Center (<code>gard</code>)</a></li>
<li><a href="https://bioregistry.io/icd10">International Classification of Diseases, 10th Revision (<code>icd10</code>)</a></li>
<li><a href="https://bioregistry.io/icd10cm">International Classification of Diseases, 10th Revision, Clinical Modification (<code>icd10cm</code>)</a></li>
<li><a href="https://bioregistry.io/icd10pcs">International Classification of Diseases, 10th Revision, Procedure Coding System (<code>icd10pcs</code>)</a></li>
<li><a href="https://bioregistry.io/icd11">International Classification of Diseases, 11th Revision (Foundation Component) (<code>icd11</code>)</a></li>
<li><a href="https://bioregistry.io/icd11.code">ICD 11 Codes (<code>icd11.code</code>)</a></li>
<li><a href="https://bioregistry.io/icd9">International Classification of Diseases, 9th Revision (<code>icd9</code>)</a></li>
<li><a href="https://bioregistry.io/icd9cm">International Classification of Diseases, 9th Revision, Clinical Modification (<code>icd9cm</code>)</a></li>
<li><a href="https://bioregistry.io/icdo">International Classification of Diseases for Oncology (<code>icdo</code>)</a></li>
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

| source_prefix | doid | mondo | efo | mesh | ncit | orphanet | orphanet.ordo | umls | omim | omim.ps | gard | icd10 | icd10cm | icd10pcs | icd11 | icd11.code | icd9 | icd9cm | icdo |
| :------------ | ---: | ----: | --: | ---: | ---: | -------: | ------------: | ---: | ---: | ------: | ---: | ----: | ------: | -------: | ----: | ---------: | ---: | -----: | ---: |
| doid          |    0 |   134 |  53 |   86 |  549 |      488 |             0 | 1389 |   24 |      62 |    0 |    11 |      80 |        0 |     0 |          0 |    0 |      0 |    0 |
| mondo         |  134 |     0 | 233 |   45 |  273 |       13 |             0 | 1570 |    0 |       0 |    2 |     0 |      22 |        0 |     0 |          0 |    0 |      3 |    0 |
| efo           |   53 |   233 |   0 |    6 |  117 |       47 |             0 |  384 |    6 |       2 |    1 |     0 |      26 |        0 |     0 |          0 |    0 |      1 |    0 |
| mesh          |   86 |    45 |   6 |    0 |  380 |       36 |             0 |  101 |   16 |       2 |    0 |     2 |     197 |        0 |     0 |          0 |    0 |      0 |    0 |
| ncit          |  549 |   273 | 117 |  380 |    0 |      722 |             0 |  337 |  218 |      31 |    7 |     9 |     517 |        0 |     0 |          0 |    0 |      2 |    0 |
| orphanet      |  488 |    13 |  47 |   36 |  722 |        0 |             0 |  370 |   43 |      50 |   10 |     0 |     206 |        0 |     0 |          0 |    0 |      3 |    0 |
| orphanet.ordo |    0 |     0 |   0 |    0 |    0 |        0 |             0 |    0 |    0 |       0 |    0 |     0 |       0 |        0 |     0 |          0 |    0 |      0 |    0 |
| umls          | 1389 |  1570 | 384 |  101 |  337 |      370 |             0 |    0 |   13 |      68 |    9 |     6 |     131 |        0 |     0 |          0 |    0 |      0 |    0 |
| omim          |   24 |     0 |   6 |   16 |  218 |       43 |             0 |   13 |    0 |       0 |    5 |     0 |      47 |        0 |     0 |          0 |    0 |      0 |    0 |
| omim.ps       |   62 |     0 |   2 |    2 |   31 |       50 |             0 |   68 |    0 |       0 |    2 |     0 |       8 |        0 |     0 |          0 |    0 |      1 |    0 |
| gard          |    0 |     2 |   1 |    0 |    7 |       10 |             0 |    9 |    5 |       2 |    0 |     0 |       2 |        0 |     0 |          0 |    0 |      2 |    0 |
| icd10         |   11 |     0 |   0 |    2 |    9 |        0 |             0 |    6 |    0 |       0 |    0 |     0 |      10 |        0 |     0 |          0 |    0 |      0 |    0 |
| icd10cm       |   80 |    22 |  26 |  197 |  517 |      206 |             0 |  131 |   47 |       8 |    2 |    10 |       0 |        0 |     0 |          0 |    0 |      2 |    0 |
| icd10pcs      |    0 |     0 |   0 |    0 |    0 |        0 |             0 |    0 |    0 |       0 |    0 |     0 |       0 |        0 |     0 |          0 |    0 |      0 |    0 |
| icd11         |    0 |     0 |   0 |    0 |    0 |        0 |             0 |    0 |    0 |       0 |    0 |     0 |       0 |        0 |     0 |          0 |    0 |      0 |    0 |
| icd11.code    |    0 |     0 |   0 |    0 |    0 |        0 |             0 |    0 |    0 |       0 |    0 |     0 |       0 |        0 |     0 |          0 |    0 |      0 |    0 |
| icd9          |    0 |     0 |   0 |    0 |    0 |        0 |             0 |    0 |    0 |       0 |    0 |     0 |       0 |        0 |     0 |          0 |    0 |      0 |    0 |
| icd9cm        |    0 |     3 |   1 |    0 |    2 |        3 |             0 |    0 |    0 |       1 |    2 |     0 |       2 |        0 |     0 |          0 |    0 |      0 |    0 |
| icdo          |    0 |     0 |   0 |    0 |    0 |        0 |             0 |    0 |    0 |       0 |    0 |     0 |       0 |        0 |     0 |          0 |    0 |      0 |    0 |

Here's an alternative view on the number of mappings normalized to show
percentage gain. Note that:

- `inf` means that there were no mappings before and now there are a non-zero
  number of mappings
- `NaN` means there were no mappings before inference and continue to be no
  mappings after inference

| source_prefix | doid | mondo |  efo |   mesh |   ncit | orphanet | orphanet.ordo | umls | omim | omim.ps | gard | icd10 | icd10cm | icd10pcs | icd11 | icd11.code | icd9 | icd9cm | icdo |
| :------------ | ---: | ----: | ---: | -----: | -----: | -------: | ------------: | ---: | ---: | ------: | ---: | ----: | ------: | -------: | ----: | ---------: | ---: | -----: | ---: |
| doid          |    0 |   1.2 |  4.3 |   13.7 |   11.8 |     22.1 |           nan | 20.5 |  0.4 |     inf |    0 |   inf |     2.3 |      nan |     0 |        nan |    0 |      0 |    0 |
| mondo         |  1.2 |     0 | 16.1 |    5.2 |    3.8 |      0.1 |           nan |  8.1 |    0 |       0 |    0 |     0 |     1.3 |      nan |     0 |        nan |    0 |    150 |    0 |
| efo           |  4.3 |  16.1 |    0 |    1.4 |   10.6 |       13 |           nan | 28.8 |  1.9 |     8.7 |  0.3 |     0 |     8.9 |      nan |     0 |        nan |    0 |     20 |    0 |
| mesh          | 13.7 |   5.2 |  1.4 |      0 | 1407.4 |     21.1 |           nan |  4.8 |  inf |     inf |  nan |   inf |     inf |      nan |   nan |        nan |  nan |    nan |  nan |
| ncit          | 11.8 |   3.8 | 10.6 | 1407.4 |      0 |   1951.4 |           nan |  1.7 |  inf |     inf |  inf |   inf |     inf |      nan |   nan |        nan |  nan |    inf |  nan |
| orphanet      | 22.1 |   0.1 |   13 |   21.1 | 1951.4 |        0 |           nan |  4.2 |  0.4 |    1000 | 26.3 |     0 |     inf |      nan |     0 |        nan |    0 |    inf |    0 |
| orphanet.ordo |  nan |   nan |  nan |    nan |    nan |      nan |             0 |  nan |  nan |     nan |  nan |   nan |     nan |      nan |   nan |        nan |  nan |    nan |  nan |
| umls          | 20.5 |   8.1 | 28.8 |    4.8 |    1.7 |      4.2 |           nan |    0 |  0.1 |     inf |  inf |   0.1 |     0.5 |      nan |   nan |        nan |  nan |      0 |  nan |
| omim          |  0.4 |     0 |  1.9 |    inf |    inf |      0.4 |           nan |  0.1 |    0 |     nan |  inf |   nan |     inf |      nan |   nan |        nan |  nan |    nan |  nan |
| omim.ps       |  inf |     0 |  8.7 |    inf |    inf |     1000 |           nan |  inf |  nan |       0 |  inf |   nan |     inf |      nan |   nan |        nan |  nan |    inf |  nan |
| gard          |    0 |     0 |  0.3 |    nan |    inf |     26.3 |           nan |  inf |  inf |     inf |    0 |   nan |     inf |      nan |   nan |        nan |  nan |    inf |  nan |
| icd10         |  inf |     0 |    0 |    inf |    inf |        0 |           nan |  0.1 |  nan |     nan |  nan |     0 |     inf |      nan |   nan |        nan |  nan |    nan |  nan |
| icd10cm       |  2.3 |   1.3 |  8.9 |    inf |    inf |      inf |           nan |  0.5 |  inf |     inf |  inf |   inf |       0 |      nan |   nan |        nan |  nan |    inf |  nan |
| icd10pcs      |  nan |   nan |  nan |    nan |    nan |      nan |           nan |  nan |  nan |     nan |  nan |   nan |     nan |      nan |   nan |        nan |  nan |    nan |  nan |
| icd11         |    0 |     0 |    0 |    nan |    nan |        0 |           nan |  nan |  nan |     nan |  nan |   nan |     nan |      nan |     0 |        nan |  nan |    nan |  nan |
| icd11.code    |  nan |   nan |  nan |    nan |    nan |      nan |           nan |  nan |  nan |     nan |  nan |   nan |     nan |      nan |   nan |        nan |  nan |    nan |  nan |
| icd9          |    0 |     0 |    0 |    nan |    nan |        0 |           nan |  nan |  nan |     nan |  nan |   nan |     nan |      nan |   nan |        nan |    0 |    nan |  nan |
| icd9cm        |    0 |   150 |   20 |    nan |    inf |      inf |           nan |    0 |  nan |     inf |  inf |   nan |     inf |      nan |   nan |        nan |  nan |      0 |  nan |
| icdo          |    0 |     0 |    0 |    nan |    nan |        0 |           nan |  nan |  nan |     nan |  nan |   nan |     nan |      nan |   nan |        nan |  nan |    nan |    0 |

### Landscape Analysis

Above, the comparison looked at the overlaps between each resource. Now, that
information is used to jointly estimate the number of terms in the landscape
itself, and estimate how much of the landscape each resource covers.

This estimates a total of 194,344 unique entities.

- 43,696 (22.5%) have at least one mapping.
- 150,648 (77.5%) are unique to a single resource.
- 0 (0.0%) appear in all 19 resources.

This estimate is susceptible to several caveats:

- Missing mappings inflates this measurement
- Generic resources like MeSH contain irrelevant entities that can't be mapped

Because there are 19 prefixes, there are 524,287 possible overlaps to consider.
Therefore, a Venn diagram is not possible, so an
[UpSet plot](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4720993) (Lex _et
al._, 2014) is used as a high-dimensional Venn diagram.

![](processed_landscape_upset.svg)

Next, the mappings are aggregated to estimate the number of unique entities and
number that appear in each group of resources.

![](processed_landscape_histogram.svg)

The landscape of 19 resources has 421,026 total terms. After merging redundant
nodes based on mappings, inference, and reasoning, there are 194,344 unique
concepts. Using the reduction formula
$\frac{{\text{{total terms}} - \text{{reduced terms}}}}{{\text{{total terms}}}}$,
this is a 53.84% reduction.

This is only an estimate and is susceptible to a few things:

1. It can be artificially high because there are entities that _should_ be
   mapped, but are not
1. It can be artificially low because there are entities that are incorrectly
   mapped, e.g., as a result of inference. The frontend curation interface can
   help identify and remove these
1. It can be artificially low because for some vocabularies like SNOMED-CT, it's
   not possible to load a terms list, and therefore it's not possible to account
   for terms that aren't mapped. Therefore, a lower bound estimate is made based
   on the terms that appear in mappings.
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
