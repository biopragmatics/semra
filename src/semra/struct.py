"""Data structures for mappings."""

from __future__ import annotations

import math
import pickle
import typing as t
import uuid
from collections.abc import Iterable
from hashlib import md5
from itertools import islice
from typing import ClassVar, Literal, Optional, Union

import pydantic
from curies import Reference
from more_itertools import triplewise
from pydantic import Field
from pydantic.types import UUID4
from typing_extensions import Annotated

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
Triple = t.Tuple[Reference, Reference, Reference]


def triple_key(triple: Triple) -> t.Tuple[str, str, str]:
    """Get a sortable key for a triple."""
    return triple[0].curie, triple[2].curie, triple[1].curie


EPSILON = 1e-6
EvidenceType = Literal["simple", "mutated", "reasoned"]
JUSTIFICATION_FIELD = Field(description="A SSSOM-compliant justification")


def _md5_hexdigest(picklable) -> str:
    hasher = md5()  # noqa:S324
    hasher.update(pickle.dumps(picklable))
    return hasher.hexdigest()


class KeyedMixin:
    """A mixin for a class that can be hashed and CURIE-encoded."""

    #: The prefix for CURIEs for instances of this class
    _prefix: ClassVar[str]

    def __init_subclass__(cls, *, prefix: str, **kwargs):
        cls._prefix = prefix

    def key(self):
        """Return a picklable key."""
        raise NotImplementedError

    def hexdigest(self) -> str:
        """Generate a hexadecimal representation of the MD5 hash of the pickled key() for this class."""
        key = self.key()
        return _md5_hexdigest(key)

    def get_reference(self) -> Reference:
        """Get a CURIE reference using this class's prefix and its hexadecimal representation."""
        return Reference(prefix=self._prefix, identifier=self.hexdigest())

    @property
    def curie(self) -> str:
        """Get a string representing the CURIE."""
        return self.get_reference().curie


class ConfidenceMixin:
    def get_confidence(self) -> float:
        raise NotImplementedError


class EvidenceMixin:
    @property
    def explanation(self) -> str:
        return ""


class MappingSet(pydantic.BaseModel, ConfidenceMixin, KeyedMixin, prefix="semra.mappingset"):
    """Represents a set of semantic mappings.

    For example, this might correspond to:

    1. All the mappings extracted from an ontology
    2. All the mappings published with a database
    3. All the mappings inferred by SeMRA based on a given configuration
    """

    name: str = Field(..., description="Name of the mapping set")
    version: Optional[str] = Field(default=None, description="The version of the dataset from which the mapping comes")
    license: Optional[str] = Field(default=None, description="License name or URL for mapping set")
    confidence: float = Field(..., description="Mapping set level confidence")

    def key(self):
        """Get a picklable key representing the mapping set."""
        return self.name, self.version or "", self.license or "", self.confidence

    def get_confidence(self) -> float:
        """Get the confidence for the mapping set."""
        return self.confidence


class SimpleEvidence(pydantic.BaseModel, KeyedMixin, EvidenceMixin, ConfidenceMixin, prefix="semra.evidence"):
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
        examples=[
            Reference(prefix="orcid", identifier="0000-0003-4423-4370"),
        ],
    )
    uuid: UUID4 = Field(default_factory=uuid.uuid4)
    confidence: Optional[float] = Field(None, description="The confidence")

    def key(self):
        """Get a key suitable for hashing the evidence.

        :return: A key for deduplication based on the mapping set.

        Note: this should be extended to include basically _all_ fields
        """
        return self.evidence_type, self.justification, self.author, self.mapping_set.key(), self.uuid

    @property
    def mapping_set_names(self) -> t.Set[str]:
        return {self.mapping_set.name}

    def get_confidence(self) -> float:
        return self.confidence if self.confidence is not None else self.mapping_set.confidence


class ReasonedEvidence(pydantic.BaseModel, KeyedMixin, EvidenceMixin, ConfidenceMixin, prefix="semra.evidence"):
    """A complex evidence based on multiple mappings."""

    class Config:
        """Pydantic configuration for evidence."""

        frozen = True

    evidence_type: Literal["reasoned"] = Field(default="reasoned")
    justification: Reference = Field(..., description="A SSSOM-compliant justification")
    mappings: t.List[Mapping] = Field(
        ..., description="A list of mappings and their evidences consumed to create this evidence"
    )
    author: Optional[Reference] = None
    confidence_factor: float = Field(1.0, description="The probability that the reasoning method is correct")

    def key(self):
        return (
            self.evidence_type,
            self.justification,
            *((*m.triple, *(e.key() for e in m.evidence)) for m in self.mappings),
        )

    def get_confidence(self) -> float:
        confidences = [mapping.get_confidence() for mapping in self.mappings]
        return _joint_probability([self.confidence_factor, *confidences])

    @property
    def mapping_set(self) -> None:
        return None

    @property
    def mapping_set_names(self) -> t.Set[str]:
        return {
            name
            for mapping in self.mappings
            for evidence in mapping.evidence
            for name in evidence.mapping_set_names  # type:ignore
        }

    @property
    def explanation(self) -> str:
        return " ".join(mapping.s.curie for mapping in self.mappings) + " " + self.mappings[-1].o.curie


Evidence = Annotated[
    Union[ReasonedEvidence, SimpleEvidence],
    Field(discriminator="evidence_type"),
]


class Mapping(pydantic.BaseModel, ConfidenceMixin, KeyedMixin, prefix="semra.mapping"):
    """A semantic mapping."""

    class Config:
        """Pydantic configuration for evidence."""

        frozen = True

    s: Reference = Field(..., title="subject")
    p: Reference = Field(..., title="predicate")
    o: Reference = Field(..., title="object")
    evidence: t.List[Evidence] = Field(default_factory=list)

    @property
    def triple(self) -> Triple:
        """Get the mapping's core triple as a tuple."""
        return self.s, self.p, self.o

    def key(self):
        return self.triple

    @classmethod
    def from_triple(cls, triple: Triple, evidence: Optional[t.List[Evidence]] = None) -> Mapping:
        """Instantiate a mapping from a triple."""
        s, p, o = triple
        return cls(s=s, p=p, o=o, evidence=evidence or [])

    def get_confidence(self) -> float:
        """Get the mapping's confidence by aggregating its evidences' confidences in a binomial model."""
        if not self.evidence:
            raise ValueError("can not calculate confidence since no evidence")
        return _joint_probability(e.get_confidence() for e in self.evidence)

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


def line(*references: Reference) -> t.List[Mapping]:
    """Create a list of mappings from a simple mappings path."""
    if not (3 <= len(references) and len(references) % 2):  # noqa:PLR2004
        raise ValueError
    return [Mapping(s=s, p=p, o=o) for s, p, o in islice(triplewise(references), None, None, 2)]


ReasonedEvidence.update_forward_refs()


def _joint_probability(probabilities: Iterable[float]) -> float:
    """Calculate the probability that a list of probabilities are jointly true."""
    return 1.0 - math.prod(1.0 - probability for probability in probabilities)
