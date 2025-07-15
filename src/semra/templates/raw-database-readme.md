# SeMRA Raw Semantic Mappings Database

The SeMRA Raw Semantic Mappings Database is an automatically assembled dataset
of raw semantic mappings incorporating mappings from:

- Ontologies indexed in
  [the Bioregistry](https://github.com/biopragmatics/bioregistry) (primary)
- Databases integrated in [PyOBO](https://github.com/biopragmatics/pyobo)
  (primary)
- [Biomappings](https://github.com/biopragmatics/biomappings) (secondary)
- Wikidata (primary/secondary)
- Custom resources integrated in SeMRA (primary)

This is a database of raw mapping without further processing. For processed
mapping datasets, we suggest smaller domain-specific processing rules. See
https://github.com/biopragmatics/semra/tree/main/landscape#readme for examples.

## Reproduction

The SeMRA Raw Semantic Mappings Database can be rebuilt with the following
commands:

```console
$ uv pip install semra
$ semra build
```

Note that downloading raw data resources can take on the order of hours to tens
of hours depending on your internet connection and the reliability of
the resources' respective servers.

{% if statistics.refresh_source_timedelta %}
A full resource refresh (i.e., re-download of resources)
was run in {{ naturaldelta(statistics.refresh_source_timedelta)}}
{%- elif statistics.refresh_raw_timedelta %}
A refresh of raw mappings (i.e., re-processing of mappings)
was run in {{ naturaldelta(statistics.refresh_raw_timedelta)}}
{%- else %}
Processing without re-downloading nor re-parsing of sources
was run in {{ naturaldelta(statistics.no_refresh_timedelta)}}
{%- endif %}
on commodity hardware (e.g., a 2023 MacBook Pro with 36GB RAM).

## Mapping Summary and Usage

The assembled raw mappings can be downloaded from
[![](https://zenodo.org/badge/DOI/10.5281/zenodo.11082038.svg)](https://doi.org/10.5281/zenodo.11082038).
then can be accessed via the [SeMRA](https://github.com/biopragmatics/semra)
Python Package using the following examples:

```python
import semra

# Load from JSONL
mappings_from_jsonl = semra.from_jsonl("mappings.jsonl.gz")

# Load from SSSOM
mappings_from_sssom = semra.from_sssom("mappings.sssom.tsv.gz")
```

## Web Application

1. Download all artifacts from
   [![](https://zenodo.org/badge/DOI/10.5281/zenodo.11082038.svg)](https://doi.org/10.5281/zenodo.11082038)
   into a folder and `cd` into it
2. Run `sh run_on_docker.sh` from the command line
3. Navigate to http://localhost:8773 to see the SeMRA dashboard or to
   http://localhost:7474 for direct access to the Neo4j graph database

## Licensing

Mappings are licensed according to their primary resources. These are explicitly
annotated in the SSSOM file on each row (when available) and on the mapping set
level in the Neo4j graph database artifacts.

## Statistics

{{ statistics.tabulate_summaries() | safe }}
