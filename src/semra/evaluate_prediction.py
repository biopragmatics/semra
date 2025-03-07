"""A workflow for evaluating predicted mappings."""

import itertools as itt
import logging
from collections import defaultdict
from collections.abc import Iterable

import click
from ssslm import GildaGrounder, Grounder, LiteralMapping
from tqdm import tqdm

from semra.api import assemble_evidences, get_index
from semra.io import from_pyobo
from semra.rules import EXACT_MATCH, LEXICAL_MAPPING
from semra.struct import Evidence, Mapping, MappingSet, Reference, SimpleEvidence

logger = logging.getLogger(__name__)


def _get_v1(positive_set, negative_set, predicted_set):
    tp = len(positive_set.intersection(predicted_set))  # true positives
    fp = len(negative_set.intersection(predicted_set))  # false positives
    fn = len(positive_set - predicted_set)  # false negatives
    tn = len(negative_set - predicted_set)  # true negatives
    return tp, fp, fn, tn


def evaluate_predictions(
    *,
    positive: Iterable[Mapping],
    negative: Iterable[Mapping],
    predicted: Iterable[Mapping],
    tag: str | None = None,
):
    """Evaluate predicted mappings using ground truth positive and negative mappings."""
    positive_index = get_index(positive, progress=False)
    negative_index = get_index(negative, progress=False)
    predicted_index = get_index(predicted, progress=False)

    positive_set = set(positive_index)
    negative_set = set(negative_index)
    predicted_set = set(predicted_index)

    tp, fp, fn, tn = _get_v1(positive_set, negative_set, predicted_set)

    predicted_only = len(predicted_set - positive_set - negative_set)
    union_len = len(positive_set.union(predicted_set).union(negative_set))

    msg = f"union={union_len:,}, intersection={tp:,}, curated={fn:,}, predicted={predicted_only:,}"
    if tag is not None:
        msg = f"[{tag}] {msg}"
    logger.info(msg)

    accuracy = (tp + tn) / (tp + tn + fp + fn)
    recall = tp / (tp + fn)
    precision = tp / (tp + fp)
    f1 = 2 * tp / (2 * tp + fp + fn)
    completion = 1 - predicted_only / len(predicted_set)

    # what is the percentage of curated examples that are positive?
    # positive_percentage = len(positive_set) / (len(positive_set) + len(negative_set))
    return completion, accuracy, precision, recall, f1


def _get_text_to_literal_mappings(grounder: Grounder) -> dict[str, list[LiteralMapping]]:
    if not isinstance(grounder, GildaGrounder):
        raise NotImplementedError
    dd = defaultdict(list)
    for terms in grounder._grounder.entries.values():
        for term in terms:
            dd[term.text].append(LiteralMapping.from_gilda(term))
    return dict(dd)


def _grounder_to_mappings(
    grounders: dict[str, Grounder],
) -> Iterable[tuple[Reference, Reference, float]]:
    terms: dict[str, dict[str, list[LiteralMapping]]] = {
        prefix: _get_text_to_literal_mappings(grounder)
        for prefix, grounder in tqdm(grounders.items(), desc="Indexing texts")
    }
    for (p1, g1), (p2, _g2) in tqdm(
        itt.combinations(grounders.items(), 2), unit_scale=True, desc="Generating mappings"
    ):
        text_to_terms = terms[p2]
        for text, literal_mappings in tqdm(
            text_to_terms.items(), unit_scale=True, desc=f"{p1}-{p2} lexical"
        ):
            scored_matches = g1.get_matches(text)
            # there are lots of ways to do this, now we do all-by-all
            for literal_mapping, scored_match in itt.product(literal_mappings, scored_matches):
                yield literal_mapping.reference, scored_match.reference, scored_match.score


#: A default confidence for predicated lexical mappings
LEXICAL_MAPPING_CONFIDENCE = 0.9


def grounder_to_mappings(grounders: dict[str, Grounder]) -> list[Mapping]:
    """Get semantic mappings between a set of grounders."""
    prefix_list_str = ", ".join(sorted(grounders))
    mapping_set = MappingSet(
        name=f"Predicted lexical mappings for {prefix_list_str}",
        confidence=LEXICAL_MAPPING_CONFIDENCE,
    )

    def _evidence(confidence: float) -> list[Evidence]:
        return [
            SimpleEvidence(
                justification=LEXICAL_MAPPING,
                mapping_set=mapping_set,
                confidence=confidence,
            )
        ]

    mappings = [
        Mapping(s=s, p=EXACT_MATCH, o=o, evidence=_evidence(confidence))
        for s, o, confidence in _grounder_to_mappings(grounders)
    ]
    mappings = assemble_evidences(mappings, progress=False)
    return mappings


@click.command()
def main() -> None:
    """Run the workflow for evaluating predicted mappings."""
    import pyobo
    import pystow
    from tabulate import tabulate

    from semra.api import infer_reversible, keep_prefixes
    from semra.io import from_sssom, write_sssom
    from semra.sources import (
        from_biomappings_negative,
        get_biomappings_positive_mappings,
        get_clo_mappings,
    )

    positive_mappings = get_biomappings_positive_mappings()
    positive_mappings = infer_reversible(positive_mappings, progress=False)
    click.echo(f"Got {len(positive_mappings):,} positive mappings")

    negative_mappings = from_biomappings_negative()
    negative_mappings = infer_reversible(negative_mappings, progress=False)
    click.echo(f"Got {len(negative_mappings):,} negative mappings")

    rows = []
    mesh_grounder = pyobo.get_grounder("mesh")
    for prefix in sorted(["chebi", "maxo", "cl", "doid", "go", "uberon", "vo", "clo"]):
        path = pystow.join(
            "semra", "evaluation_prediction", name=f"evaluation_prediction_sample_{prefix}.tsv"
        )

        if path.is_file():
            predicted_mappings = from_sssom(path, mapping_set_name=" predictions")
        else:
            grounders = {"mesh": mesh_grounder, prefix: pyobo.get_grounder(prefix)}
            predicted_mappings = grounder_to_mappings(grounders)
            click.echo(f"Got {len(predicted_mappings):,} predicted mappings")
            predicted_mappings = infer_reversible(predicted_mappings, progress=False)
            write_sssom(predicted_mappings, path)

        if prefix == "clo":
            ontology_mappings = get_clo_mappings()
            ontology_mappings = keep_prefixes(ontology_mappings, [prefix, "mesh"], progress=False)
        else:
            ontology_mappings = from_pyobo(prefix, "mesh")
        ontology_mappings = infer_reversible(ontology_mappings, progress=False)
        click.echo(f"[{prefix}] got {len(ontology_mappings):,} mappings from the ontology")

        positive_mappings_subset = keep_prefixes(
            positive_mappings, [prefix, "mesh"], progress=False
        )
        negative_mappings_subset = keep_prefixes(
            negative_mappings, [prefix, "mesh"], progress=False
        )
        evaluation_row = evaluate_predictions(
            positive=itt.chain(positive_mappings_subset, ontology_mappings),
            negative=negative_mappings_subset,
            predicted=predicted_mappings,
            tag=prefix,
        )
        rows.append((f"[{prefix}](https://bioregistry.io/{prefix})", *evaluation_row))

    click.echo(
        tabulate(
            rows,
            headers=["prefix", "completion", "accuracy", "precision", "recall", "f1"],
            floatfmt=".1%",
            tablefmt="github",
        )
    )


if __name__ == "__main__":
    main()
