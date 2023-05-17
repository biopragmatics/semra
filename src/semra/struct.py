"""Data structures for mappings."""

from __future__ import annotations

import math
import pickle
from collections.abc import Iterable
from hashlib import md5
from itertools import islice
from typing import Annotated, Literal

import pydantic
from curies import Reference
from more_itertools import triplewise
from pydantic import Field

__all__ = [
    "Reference",
    "Triple",
    "triple_key",
    "Evidence",
    "SimpleEvidence",
    "MutatedEvidence",
    "ReasonedEvidence",
    "Mapping",
    "line",
]

#: A type annotation for a subject-predicate-object triple
Triple = tuple[Reference, Reference, Reference]


def triple_key(triple: Triple) -> tuple[str, str, str]:
    """Get a sortable key for a triple."""
    return triple[0].curie, triple[2].curie, triple[1].curie


EvidenceType = Literal["simple", "mutated", "reasoned"]
JUSTIFICATION_FIELD = Field(description="A SSSOM-compliant justification")


def _md5_hexdigest(picklable) -> str:
    hasher = md5()  # noqa:S324
    hasher.update(pickle.dumps(picklable))
    return hasher.hexdigest()


class EvidenceMixin:
    def key(self):
        raise NotImplementedError

    def hexdigest(self) -> str:
        return _md5_hexdigest(self.key())

    def get_reference(self):
        return Reference(prefix="semra.evidence", identifier=self.hexdigest())


class SimpleEvidence(pydantic.BaseModel, EvidenceMixin):
    """Evidence for a mapping.

    Ideally, this matches the SSSOM data model.
    """

    class Config:
        """Pydantic configuration for evidence."""

        frozen = True

    evidence_type: Literal["simple"] = Field(default="simple")
    justification: Reference | None = Field(description="A SSSOM-compliant justification")
    mapping_set: str | None = None
    mapping_set_version: str | None = None
    author: Reference | None = None
    confidence: float | None = Field(description="Confidence in the transformation of the evidence")

    def key(self):
        """Get a key suitable for hashing the evidence.

        :return: A key for deduplication based on the mapping set.

        Note: this should be extended to include basically _all_ fields
        """
        return self.evidence_type, self.justification, self.mapping_set

    @property
    def explanation(self) -> str:
        return ""


class MutatedEvidence(pydantic.BaseModel, EvidenceMixin):
    """An evidence for a mapping based on a different evidence."""

    class Config:
        """Pydantic configuration for evidence."""

        frozen = True

    evidence_type: Literal["mutated"] = Field(default="mutated")
    justification: Reference = Field(..., description="A SSSOM-compliant justification")
    evidence: Evidence = Field(..., description="A wrapped evidence")
    confidence_factor: float = Field(1.0, description="Confidence in the transformation of the evidence")

    @property
    def mapping_set(self) -> str | None:
        return self.evidence.mapping_set

    @property
    def mapping_set_version(self) -> str | None:
        return self.evidence.mapping_set_version

    @property
    def author(self) -> Reference | None:
        return self.evidence.author

    @property
    def confidence(self) -> float | None:
        if self.evidence.confidence is None:
            return None
        return self.confidence_factor * self.evidence.confidence

    def key(self):
        return self.evidence_type, self.justification, self.evidence.key()

    @property
    def explanation(self) -> str:
        return ""


class ReasonedEvidence(pydantic.BaseModel, EvidenceMixin):
    """A complex evidence based on multiple mappings."""

    class Config:
        """Pydantic configuration for evidence."""

        frozen = True

    evidence_type: Literal["reasoned"] = Field(default="reasoned")
    justification: Reference | None = Field(description="A SSSOM-compliant justification")
    mappings: list[Mapping] = Field(
        ..., description="A list of mappings and their evidences consumed to create this evidence"
    )
    author: Reference | None = None

    def key(self):
        return (
            self.evidence_type,
            self.justification,
            *((*m.triple, *(e.key() for e in m.evidence)) for m in self.mappings),
        )

    @property
    def confidence(self) -> float:
        return _joint_probability(mapping.confidence for mapping in self.mappings)

    @property
    def mapping_set(self) -> str | None:
        mapping_sets = {
            evidence.mapping_set
            for mapping in self.mappings
            for evidence in mapping.evidence
            if evidence.mapping_set is not None
        }
        if not mapping_sets:
            return None
        return ",".join(sorted(mapping_sets))

    @property
    def mapping_set_version(self):
        return None

    @property
    def explanation(self) -> str:
        return " ".join(mapping.s.curie for mapping in self.mappings) + " " + self.mappings[-1].o.curie


Evidence = Annotated[
    ReasonedEvidence | MutatedEvidence | SimpleEvidence,
    Field(discriminator="evidence_type"),
]


class Mapping(pydantic.BaseModel):
    """A semantic mapping."""

    class Config:
        """Pydantic configuration for evidence."""

        frozen = True

    s: Reference = Field(..., title="subject")
    p: Reference = Field(..., title="predicate")
    o: Reference = Field(..., title="object")
    evidence: list[Evidence] = Field(default_factory=list)

    @property
    def triple(self) -> Triple:
        """Get the mapping's core triple as a tuple."""
        return self.s, self.p, self.o

    @classmethod
    def from_triple(cls, triple: Triple, evidence: list[Evidence] | None = None) -> Mapping:
        """Instantiate a mapping from a triple."""
        s, p, o = triple
        return cls(s=s, p=p, o=o, evidence=evidence or [])

    @property
    def confidence(self) -> float:
        if not self.evidence:
            return 0.0
        return _joint_probability(
            1.0 if evidence.confidence is None else evidence.confidence for evidence in self.evidence
        )

    def hexdigest(self) -> str:
        return _md5_hexdigest(self.triple)

    def get_reference(self):
        return Reference(prefix="semra.mapping", identifier=self.hexdigest())


def line(*references: Reference) -> list[Mapping]:
    """Create a list of mappings from a simple mappings path."""
    if not (3 <= len(references) and len(references) % 2):  # noqa:PLR2004
        raise ValueError
    return [Mapping(s=s, p=p, o=o) for s, p, o in islice(triplewise(references), None, None, 2)]


ReasonedEvidence.update_forward_refs()
MutatedEvidence.update_forward_refs()


def _joint_probability(probabilities: Iterable[float]) -> float:
    """Calculate the probability that a list of probabilities are jointly true."""
    return 1.0 - math.prod(1.0 - probability for probability in probabilities)
