import itertools as itt
from collections import defaultdict
from typing import TYPE_CHECKING, Iterable, Tuple

from tqdm import tqdm

from .api import assemble_evidences, get_index
from .rules import EXACT_MATCH, LEXICAL_MAPPING, MANUAL_MAPPING
from .struct import Mapping, MappingSet, Reference, SimpleEvidence

if TYPE_CHECKING:
    import gilda


def evaluate_predictions(*, positive: list[Mapping], negative: list[Mapping], predicted: list[Mapping], tag: str):
    positive_index = get_index(positive, progress=False)
    negative_index = get_index(negative, progress=False)
    predicted_index = get_index(predicted, progress=False)

    positive_set = set(positive_index)
    negative_set = set(negative_index)
    predicted_set = set(predicted_index)

    union_len = len(positive_set.union(predicted_set).union(negative_set))
    tp = len(positive_set.intersection(predicted_set))  # true positives
    fp = len(negative_set.intersection(predicted_set))  # false positives
    fn = len(positive_set - predicted_set)  # false negatives
    tn = len(negative_set - predicted_set)  # true negatives
    predicted_only = len(predicted_set - positive_set - negative_set)
    print(f"[{tag}] union={union_len:,}, intersection={tp:,}, curated={fn:,}, predicted={predicted_only:,}")

    accuracy = (tp + tn) / (tp + tn + fp + fn)
    recall = tp / (tp + fn)
    precision = tp / (tp + fp)
    f1 = 2 * tp / (2 * tp + fp + fn)
    completion = 1 - predicted_only / union_len

    # print(f"[{tag}] {completion=:.1%}")
    # print(f"[{tag}] {accuracy=:.1%}, {precision=:.1%} {recall=:.1%}, {f1=:.1%}")
    return (completion, accuracy, precision, recall, f1)


def _index_text(grounder: "gilda.Grounder"):
    dd = defaultdict(list)
    for terms in grounder.entries.values():
        for term in terms:
            dd[term.text].append(term)
    return dict(dd)


def _grounder_to_mappings(grounders: dict[str, "gilda.Grounder"]) -> Iterable[Tuple["gilda.Term", "gilda.Term"]]:
    terms = {prefix: _index_text(grounder) for prefix, grounder in tqdm(grounders.items(), desc="Indexing texts")}
    for (p1, g1), (p2, _g2) in tqdm(
        itt.combinations(grounders.items(), 2), unit_scale=True, desc="Generating mappings"
    ):
        text_to_terms = terms[p2]
        for text, terms in tqdm(text_to_terms.items(), unit_scale=True, desc=f"{p1}-{p2} lexical"):
            scored_matches = g1.ground(text)
            # there are lots of ways to do this, now we do all-by-all
            match_terms = [sm.term for sm in scored_matches]
            yield from itt.product(terms, match_terms)


def grounder_to_mappings(grounders: dict[str, "gilda.Grounder"]) -> list[Mapping]:
    xx = ", ".join(sorted(grounders))
    mapping_set = MappingSet(name=f"Gilda predicted mappings for {xx}")
    mappings = []
    for subject_term, object_term in _grounder_to_mappings(grounders):
        mapping = Mapping(
            s=Reference(prefix=subject_term.db, identifier=subject_term.id),
            p=EXACT_MATCH,
            o=Reference(prefix=object_term.db, identifier=object_term.id),
            evidence=[
                # TODO annotate confidence
                SimpleEvidence(justification=LEXICAL_MAPPING, mapping_set=mapping_set)
            ],
        )
        mappings.append(mapping)
    mappings = assemble_evidences(mappings, progress=False)
    return mappings


def main():
    import click
    import pyobo.gilda_utils
    import pystow
    from tabulate import tabulate

    from semra.api import infer_reversible, keep_prefixes
    from semra.io import from_sssom, write_sssom
    from semra.sources import from_biomappings_negative, get_biomappings_positive_mappings

    positive_mappings = get_biomappings_positive_mappings()
    positive_mappings = infer_reversible(positive_mappings, progress=False)
    click.echo(f"Got {len(positive_mappings):,} positive mappings")

    negative_mappings = from_biomappings_negative()
    negative_mappings = infer_reversible(negative_mappings, progress=False)
    click.echo(f"Got {len(negative_mappings):,} negative mappings")

    rows = []
    for p in ["chebi", "maxo", "cl", "doid", "go", "uberon", "vo", "clo"]:
        path = pystow.join("semra", "evaluation_prediction", name=f"evaluation_prediction_sample_{p}.tsv")
        prefixes = ["mesh", p]
        versions = ["2023", None]

        if path.is_file():
            predicted_mappings = from_sssom(path, mapping_set_name="gilda predictions")
        else:
            grounders = {
                prefix: pyobo.gilda_utils.get_grounder(prefix, versions=version)
                for prefix, version in zip(prefixes, versions)
            }
            predicted_mappings = grounder_to_mappings(grounders)
            click.echo(f"Got {len(predicted_mappings):,} predicted mappings")
            predicted_mappings = infer_reversible(predicted_mappings, progress=False)
            write_sssom(predicted_mappings, path)

        positive_mappings_subset = keep_prefixes(positive_mappings, prefixes, progress=False)
        negative_mappings_subset = keep_prefixes(negative_mappings, prefixes, progress=False)
        t = evaluate_predictions(
            positive=positive_mappings_subset,
            negative=negative_mappings_subset,
            predicted=predicted_mappings,
            tag=p,
        )
        rows.append((p, *t))

    print(
        tabulate(
            rows,
            headers=["prefix", "completion", "accuracy", "precision", "recall", "f1"],
            floatfmt=".1%",
        )
    )


if __name__ == "__main__":
    main()
