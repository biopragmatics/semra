# {{ configuration.name }}

{{ configuration.description }}

## Configuration

The `configuration.json` stores the sources and workflows applied to assemble mappings.

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

### Prioritization

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

## Usage

This is a database of raw mapping without further processing. For processed mapping datasets, we suggest smaller
domain-specific processing rules (see https://github.com/biopragmatics/semra/tree/main/notebooks/landscape for
examples). It can be accessed directly via:

```python
import semra.io

# Load from JSONL
mappings = semra.io.from_jsonl("processed.jsonl.gz")

# Load from SSSOM
mappings = semra.io.from_sssom("processed.sssom.tsv.gz")
```

### Run the SeMRA Web Application

1. Download all artifacts into a folder and `cd` into it
2. Run `sh run_on_docker.sh` from the command line
3. Navigate to http://localhost:8773 to see the SeMRA dashboard or to http://localhost:7474 for direct access to the
   Neo4j graph database

## Licensing

Mappings are licensed according to their primary resources. These are explicitly annotated in the SSSOM file on each
row (when available) and on the mapping set level in the Neo4j graph database artifacts.

## Extras

An automatically assembled dataset of raw semantic mappings produced by python -m semra.database. This incorporates
mappings from the following places:

    Ontologies indexed in the Bioregistry (primary)
    Databases integrated in PyOBO (primary)
    Biomappings (secondary)
    Wikidata (primary/secondary)
    Custom resources integrated in SeMRA (primary)

