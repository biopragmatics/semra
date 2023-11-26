"""Data structures for mappings."""

from __future__ import annotations

import math
import pickle
import uuid
from collections.abc import Iterable
from hashlib import md5
from itertools import islice
from typing import Annotated, Literal, Optional, Union

import pydantic
from curies import Reference
from more_itertools import triplewise
from pydantic import Field
from pydantic.types import UUID4

__all__ = [
    "Reference",
    "Triple",
    "triple_key",
    "Evidence",
    "SimpleEvidence",
    "ReasonedEvidence",
    "MappingSet",
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
        key = self.key()
        return _md5_hexdigest(key)

    def get_reference(self) -> Reference:
        return Reference(prefix="semra.evidence", identifier=self.hexdigest())

    @property
    def curie(self) -> str:
        return self.get_reference().curie


class MappingSet(pydantic.BaseModel):
    name: str = Field(..., description="Name of the mapping set")
    version: Optional[str] = Field(default=None, description="The version of the dataset from which the mapping comes")
    license: Optional[str] = Field(default=None, description="License name or URL for mapping set")
    confidence: Optional[float] = Field(default=None, description="Mapping set level confidence")

    def key(self):
        return self.name, self.version or "", self.license or "", 1.0 if self.confidence is None else self.confidence

    def hexdigest(self) -> str:
        return _md5_hexdigest(self.key())

    def get_reference(self) -> Reference:
        return Reference(prefix="semra.mappingset", identifier=self.hexdigest())

    @property
    def curie(self) -> str:
        return self.get_reference().curie


class SimpleEvidence(pydantic.BaseModel, EvidenceMixin):
    """Evidence for a mapping.

    Ideally, this matches the SSSOM data model.
    """

    class Config:
        """Pydantic configuration for evidence."""

        frozen = True

    evidence_type: Literal["simple"] = Field(default="simple")
    justification: Reference = Field(
        default=Reference(prefix="semapv", identifier="UnspecifiedMapping"),
        description="A SSSOM-compliant justification",
    )
    mapping_set: MappingSet = Field(..., description="The name of the dataset from which the mapping comes")
    author: Optional[Reference] = Field(
        default=None,
        description="A reference to the author of the mapping (e.g. with ORCID)",
        example=Reference(prefix="orcid", identifier="0000-0003-4423-4370"),
    )
    uuid: UUID4 = Field(default_factory=uuid.uuid4)

    def key(self):
        """Get a key suitable for hashing the evidence.

        :return: A key for deduplication based on the mapping set.

        Note: this should be extended to include basically _all_ fields
        """
        return (self.evidence_type, self.justification, self.author, self.mapping_set.key(), self.uuid)

    @property
    def mapping_set_names(self) -> set[str]:
        return {self.mapping_set.name}

    @property
    def confidence(self) -> Optional[float]:
        return self.mapping_set.confidence

    @property
    def explanation(self) -> str:
        return ""


class ReasonedEvidence(pydantic.BaseModel, EvidenceMixin):
    """A complex evidence based on multiple mappings."""

    class Config:
        """Pydantic configuration for evidence."""

        frozen = True

    evidence_type: Literal["reasoned"] = Field(default="reasoned")
    justification: Reference = Field(..., description="A SSSOM-compliant justification")
    mappings: list[Mapping] = Field(
        ..., description="A list of mappings and their evidences consumed to create this evidence"
    )
    author: Optional[Reference] = None
    confidence_factor: float = 1.0

    def key(self):
        return (
            self.evidence_type,
            self.justification,
            *((*m.triple, *(e.key() for e in m.evidence)) for m in self.mappings),
        )

    @property
    def confidence(self) -> Optional[float]:
        confidences = [mapping.confidence for mapping in self.mappings]
        nn_confidences = [c for c in confidences if c is not None]
        if not nn_confidences:
            return None
        return self.confidence_factor * _joint_probability(nn_confidences)

    @property
    def mapping_set(self) -> None:
        return None

    @property
    def mapping_set_names(self) -> set[str]:
        return {
            name for mapping in self.mappings for evidence in mapping.evidence for name in evidence.mapping_set_names
        }

    @property
    def explanation(self) -> str:
        return " ".join(mapping.s.curie for mapping in self.mappings) + " " + self.mappings[-1].o.curie


Evidence = Annotated[
    Union[ReasonedEvidence, SimpleEvidence],
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
    def from_triple(cls, triple: Triple, evidence: Union[list[Evidence], None] = None) -> Mapping:
        """Instantiate a mapping from a triple."""
        s, p, o = triple
        return cls(s=s, p=p, o=o, evidence=evidence or [])

    @property
    def confidence(self) -> Optional[float]:
        if not self.evidence:
            return None
        confidences = [e.confidence for e in self.evidence]
        nn_confidences = [c for c in confidences if c is not None]
        if not nn_confidences:
            return None
        return _joint_probability(nn_confidences)

    def hexdigest(self) -> str:
        return _md5_hexdigest(self.triple)

    def get_reference(self) -> Reference:
        return Reference(prefix="semra.mapping", identifier=self.hexdigest())

    @property
    def curie(self) -> str:
        return self.get_reference().curie

    @property
    def has_primary(self) -> bool:
        """Get if there is a primary evidence associated with this mapping."""
        return any(
            isinstance(evidence, SimpleEvidence) and evidence.mapping_set.name == self.s.prefix
            for evidence in self.evidence
        )

    @property
    def has_secondary(self) -> bool:
        """Get if there is a secondary evidence associated with this mapping."""
        return any(
            isinstance(evidence, SimpleEvidence) and evidence.mapping_set.name != self.s.prefix
            for evidence in self.evidence
        )

    @property
    def has_tertiary(self) -> bool:
        """Get if there are any tertiary (i.e., reasoned) evidences for this mapping."""
        return any(not isinstance(evidence, SimpleEvidence) for evidence in self.evidence)


def line(*references: Reference) -> list[Mapping]:
    """Create a list of mappings from a simple mappings path."""
    if not (3 <= len(references) and len(references) % 2):  # noqa:PLR2004
        raise ValueError
    return [Mapping(s=s, p=p, o=o) for s, p, o in islice(triplewise(references), None, None, 2)]


ReasonedEvidence.update_forward_refs()


def _joint_probability(probabilities: Iterable[float]) -> float:
    """Calculate the probability that a list of probabilities are jointly true."""
    return 1.0 - math.prod(1.0 - probability for probability in probabilities)
