# SeMRA Gene Mappings Database

Analyze the landscape of gene nomenclature resources, species-agnostic. Created
by:

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

1 resources were not available through
[PyOBO](https://github.com/biopragmatics/pyobo). Therefore, the number of terms
in that resource are estimated based on the ones that are observed in mappings
assembled by SeMRA. Note that these are typically an underestimate.

| prefix    | name                                                      | license                                                                                              | version    |    terms | status   |
| :-------- | :-------------------------------------------------------- | :--------------------------------------------------------------------------------------------------- | :--------- | -------: | :------- |
| ncbigene  | NCBI Gene                                                 |                                                                                                      | daily      | 56689711 | full     |
| hgnc      | HUGO Gene Nomenclature Committee                          | CC0-1.0                                                                                              | 2025-06-03 |    44117 | full     |
| mgi       | Mouse Genome Informatics                                  | CC-BY-4.0                                                                                            | 6.24       |   661778 | full     |
| rgd       | Rat Genome Database                                       | CC-BY-4.0                                                                                            | 2025-06-21 |    61462 | full     |
| cgnc      | Chicken Gene Nomenclature Consortium                      | CC-BY-4.0                                                                                            |            |    26085 | full     |
| wormbase  | WormBase                                                  | CC0-1.0                                                                                              |            |        0 | observed |
| flybase   | FlyBase Gene                                              | CC-BY-4.0                                                                                            | 2025_02    |    17871 | full     |
| sgd       | Saccharomyces Genome Database                             | CC-BY-4.0                                                                                            | R64-5-1    |     6600 | full     |
| omim      | Online Mendelian Inheritance in Man                       | https://www.omim.org/help/agreement                                                                  | 2025-06-27 |    27277 | observed |
| civic.gid | CIViC gene                                                | CC0-1.0                                                                                              | 2025-06-01 |      901 | full     |
| umls      | Unified Medical Language System Concept Unique Identifier | https://www.nlm.nih.gov/research/umls/knowledge_sources/metathesaurus/release/license_agreement.html | 2025AA     |        1 | subset   |
| ncit      | NCI Thesaurus                                             | CC-BY-4.0                                                                                            | 25.06d     |    12711 | subset   |
| wikidata  | Wikidata                                                  | CC0-1.0                                                                                              |            |   797957 | observed |

There are a total of 58,346,471 terms across the 13 resources.

## Mapping Summary and Usage

### Raw Mappings

The raw mappings are the ones directly read from the 15 sources.

- This table is symmetric, i.e., taking into account mappings from both the
  source and target.
- Diagonals represent the number of entities in the resource (or the number that
  are observed in the mappings, in some cases)
- All predicate types are combined in this table.

| source_prefix |    ncbigene |  hgnc |    mgi |   rgd |  cgnc | wormbase | flybase |  sgd |  omim | civic.gid | umls |  ncit | wikidata |
| :------------ | ----------: | ----: | -----: | ----: | ----: | -------: | ------: | ---: | ----: | --------: | ---: | ----: | -------: |
| ncbigene      | 5.66897e+07 | 43865 | 111826 | 48330 | 26070 |        0 |       0 |    0 | 18568 |       594 |    0 |     0 |   788061 |
| hgnc          |       43865 | 44117 |      0 |     0 |     0 |        0 |       0 |    0 | 17496 |         0 |    0 |  5978 |    43557 |
| mgi           |      111826 |     0 | 661778 |     0 |     0 |        0 |       0 |    0 |     0 |         0 |    0 |     0 |        0 |
| rgd           |       48330 |     0 |      0 | 61462 |     0 |        0 |       0 |    0 |     0 |         0 |    0 |     0 |        0 |
| cgnc          |       26070 |     0 |      0 |     0 | 26085 |        0 |       0 |    0 |     0 |         0 |    0 |     0 |        0 |
| wormbase      |           0 |     0 |      0 |     0 |     0 |        0 |       0 |    0 |     0 |         0 |    0 |     0 |        0 |
| flybase       |           0 |     0 |      0 |     0 |     0 |        0 |   17871 |    0 |     0 |         0 |    0 |     0 |        0 |
| sgd           |           0 |     0 |      0 |     0 |     0 |        0 |       0 | 6600 |     0 |         0 |    0 |     0 |        0 |
| omim          |       18568 | 17496 |      0 |     0 |     0 |        0 |       0 |    0 | 27277 |         0 |    0 |     0 |    25898 |
| civic.gid     |         594 |     0 |      0 |     0 |     0 |        0 |       0 |    0 |     0 |       901 |    0 |     1 |      491 |
| umls          |           0 |     0 |      0 |     0 |     0 |        0 |       0 |    0 |     0 |         0 |    1 |     0 |        0 |
| ncit          |           0 |  5978 |      0 |     0 |     0 |        0 |       0 |    0 |     0 |         1 |    0 | 12711 |        0 |
| wikidata      |      788061 | 43557 |      0 |     0 |     0 |        0 |       0 |    0 | 25898 |       491 |    0 |     0 |   797957 |

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
<td>umls</td>
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
<td align="right">0.8</td>
</tr>
</tbody>
</table>

The processed mappings table has the following qualities:

- This table is symmetric, i.e., taking into account mappings from the source,
  target, and inference
- Diagonals represent the number of entities in the resource (or the number that
  are observed in the mappings, in some cases)
- Only exact matches are retained

| source_prefix |    ncbigene |  hgnc |    mgi |   rgd |  cgnc | wormbase | flybase |  sgd |  omim | civic.gid | umls |  ncit | wikidata |
| :------------ | ----------: | ----: | -----: | ----: | ----: | -------: | ------: | ---: | ----: | --------: | ---: | ----: | -------: |
| ncbigene      | 5.66897e+07 | 44352 | 111826 | 48330 | 26070 |        0 |       0 |    0 | 18589 |       623 |    0 |  5957 |   788878 |
| hgnc          |       44352 | 44117 |      0 |     0 |     0 |        0 |       0 |    0 | 17871 |       624 |    0 |  5978 |    44622 |
| mgi           |      111826 |     0 | 661778 |     0 |     0 |        0 |       0 |    0 |     0 |         0 |    0 |     0 |    71593 |
| rgd           |       48330 |     0 |      0 | 61462 |     0 |        0 |       0 |    0 |     0 |         0 |    0 |     0 |        0 |
| cgnc          |       26070 |     0 |      0 |     0 | 26085 |        0 |       0 |    0 |     0 |         0 |    0 |     0 |        1 |
| wormbase      |           0 |     0 |      0 |     0 |     0 |        0 |       0 |    0 |     0 |         0 |    0 |     0 |        0 |
| flybase       |           0 |     0 |      0 |     0 |     0 |        0 |   17871 |    0 |     0 |         0 |    0 |     0 |        0 |
| sgd           |           0 |     0 |      0 |     0 |     0 |        0 |       0 | 6600 |     0 |         0 |    0 |     0 |        0 |
| omim          |       18589 | 17871 |      0 |     0 |     0 |        0 |       0 |    0 | 27277 |       624 |    0 |  5850 |    28470 |
| civic.gid     |         623 |   624 |      0 |     0 |     0 |        0 |       0 |    0 |   624 |       901 |    0 |   580 |      632 |
| umls          |           0 |     0 |      0 |     0 |     0 |        0 |       0 |    0 |     0 |         0 |    1 |     0 |        0 |
| ncit          |        5957 |  5978 |      0 |     0 |     0 |        0 |       0 |    0 |  5850 |       580 |    0 | 12711 |     6007 |
| wikidata      |      788878 | 44622 |  71593 |     0 |     1 |        0 |       0 |    0 | 28470 |       632 |    0 |  6007 |   797957 |

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
<li><a href="https://bioregistry.io/ncbigene">NCBI Gene (<code>ncbigene</code>)</a></li>
<li><a href="https://bioregistry.io/hgnc">HUGO Gene Nomenclature Committee (<code>hgnc</code>)</a></li>
<li><a href="https://bioregistry.io/mgi">Mouse Genome Informatics (<code>mgi</code>)</a></li>
<li><a href="https://bioregistry.io/rgd">Rat Genome Database (<code>rgd</code>)</a></li>
<li><a href="https://bioregistry.io/cgnc">Chicken Gene Nomenclature Consortium (<code>cgnc</code>)</a></li>
<li><a href="https://bioregistry.io/wormbase">WormBase (<code>wormbase</code>)</a></li>
<li><a href="https://bioregistry.io/flybase">FlyBase Gene (<code>flybase</code>)</a></li>
<li><a href="https://bioregistry.io/sgd">Saccharomyces Genome Database (<code>sgd</code>)</a></li>
<li><a href="https://bioregistry.io/omim">Online Mendelian Inheritance in Man (<code>omim</code>)</a></li>
<li><a href="https://bioregistry.io/civic.gid">CIViC gene (<code>civic.gid</code>)</a></li>
<li><a href="https://bioregistry.io/umls">Unified Medical Language System Concept Unique Identifier (<code>umls</code>)</a></li>
<li><a href="https://bioregistry.io/ncit">NCI Thesaurus (<code>ncit</code>)</a></li>
<li><a href="https://bioregistry.io/wikidata">Wikidata (<code>wikidata</code>)</a></li>
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

| source_prefix | ncbigene | hgnc |   mgi | rgd | cgnc | wormbase | flybase | sgd | omim | civic.gid | umls | ncit | wikidata |
| :------------ | -------: | ---: | ----: | --: | ---: | -------: | ------: | --: | ---: | --------: | ---: | ---: | -------: |
| ncbigene      |        0 |  487 |     0 |   0 |    0 |        0 |       0 |   0 |   21 |        29 |    0 | 5957 |      817 |
| hgnc          |      487 |    0 |     0 |   0 |    0 |        0 |       0 |   0 |  375 |       624 |    0 |    0 |     1065 |
| mgi           |        0 |    0 |     0 |   0 |    0 |        0 |       0 |   0 |    0 |         0 |    0 |    0 |    71593 |
| rgd           |        0 |    0 |     0 |   0 |    0 |        0 |       0 |   0 |    0 |         0 |    0 |    0 |        0 |
| cgnc          |        0 |    0 |     0 |   0 |    0 |        0 |       0 |   0 |    0 |         0 |    0 |    0 |        1 |
| wormbase      |        0 |    0 |     0 |   0 |    0 |        0 |       0 |   0 |    0 |         0 |    0 |    0 |        0 |
| flybase       |        0 |    0 |     0 |   0 |    0 |        0 |       0 |   0 |    0 |         0 |    0 |    0 |        0 |
| sgd           |        0 |    0 |     0 |   0 |    0 |        0 |       0 |   0 |    0 |         0 |    0 |    0 |        0 |
| omim          |       21 |  375 |     0 |   0 |    0 |        0 |       0 |   0 |    0 |       624 |    0 | 5850 |     2572 |
| civic.gid     |       29 |  624 |     0 |   0 |    0 |        0 |       0 |   0 |  624 |         0 |    0 |  579 |      141 |
| umls          |        0 |    0 |     0 |   0 |    0 |        0 |       0 |   0 |    0 |         0 |    0 |    0 |        0 |
| ncit          |     5957 |    0 |     0 |   0 |    0 |        0 |       0 |   0 | 5850 |       579 |    0 |    0 |     6007 |
| wikidata      |      817 | 1065 | 71593 |   0 |    1 |        0 |       0 |   0 | 2572 |       141 |    0 | 6007 |        0 |

Here's an alternative view on the number of mappings normalized to show
percentage gain. Note that:

- `inf` means that there were no mappings before and now there are a non-zero
  number of mappings
- `NaN` means there were no mappings before inference and continue to be no
  mappings after inference

| source_prefix | ncbigene | hgnc | mgi | rgd | cgnc | wormbase | flybase | sgd | omim | civic.gid | umls |  ncit | wikidata |
| :------------ | -------: | ---: | --: | --: | ---: | -------: | ------: | --: | ---: | --------: | ---: | ----: | -------: |
| ncbigene      |        0 |  1.1 |   0 |   0 |    0 |      nan |     nan | nan |  0.1 |       4.9 |  nan |   inf |      0.1 |
| hgnc          |      1.1 |    0 | nan | nan |  nan |      nan |     nan | nan |  2.1 |       inf |  nan |     0 |      2.4 |
| mgi           |        0 |  nan |   0 | nan |  nan |      nan |     nan | nan |  nan |       nan |  nan |   nan |      inf |
| rgd           |        0 |  nan | nan |   0 |  nan |      nan |     nan | nan |  nan |       nan |  nan |   nan |      nan |
| cgnc          |        0 |  nan | nan | nan |    0 |      nan |     nan | nan |  nan |       nan |  nan |   nan |      inf |
| wormbase      |      nan |  nan | nan | nan |  nan |      nan |     nan | nan |  nan |       nan |  nan |   nan |      nan |
| flybase       |      nan |  nan | nan | nan |  nan |      nan |       0 | nan |  nan |       nan |  nan |   nan |      nan |
| sgd           |      nan |  nan | nan | nan |  nan |      nan |     nan |   0 |  nan |       nan |  nan |   nan |      nan |
| omim          |      0.1 |  2.1 | nan | nan |  nan |      nan |     nan | nan |    0 |       inf |  nan |   inf |      9.9 |
| civic.gid     |      4.9 |  inf | nan | nan |  nan |      nan |     nan | nan |  inf |         0 |  nan | 57900 |     28.7 |
| umls          |      nan |  nan | nan | nan |  nan |      nan |     nan | nan |  nan |       nan |    0 |   nan |      nan |
| ncit          |      inf |    0 | nan | nan |  nan |      nan |     nan | nan |  inf |     57900 |  nan |     0 |      inf |
| wikidata      |      0.1 |  2.4 | inf | nan |  inf |      nan |     nan | nan |  9.9 |      28.7 |  nan |   inf |        0 |

### Landscape Analysis

Above, the comparison looked at the overlaps between each resource. Now, that
information is used to jointly estimate the number of terms in the landscape
itself, and estimate how much of the landscape each resource covers.

This estimates a total of 57,624,180 unique entities.

- 912,192 (1.6%) have at least one mapping.
- 56,711,988 (98.4%) are unique to a single resource.
- 0 (0.0%) appear in all 13 resources.

This estimate is susceptible to several caveats:

- Missing mappings inflates this measurement
- Generic resources like MeSH contain irrelevant entities that can't be mapped

Because there are 13 prefixes, there are 8,191 possible overlaps to consider.
Therefore, a Venn diagram is not possible, so an
[UpSet plot](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4720993) (Lex _et
al._, 2014) is used as a high-dimensional Venn diagram.

![](processed_landscape_upset.svg)

Next, the mappings are aggregated to estimate the number of unique entities and
number that appear in each group of resources.

![](processed_landscape_histogram.svg)

The landscape of 13 resources has 58,346,471 total terms. After merging
redundant nodes based on mappings, inference, and reasoning, there are
57,624,180 unique concepts. Using the reduction formula
$\frac{{\text{{total terms}} - \text{{reduced terms}}}}{{\text{{total terms}}}}$,
this is a 1.24% reduction.

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
