"""Data structures for mappings."""

from __future__ import annotations

import math
import pickle
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterable
from hashlib import md5
from itertools import islice
from typing import Annotated, Any, ClassVar, Literal

import pydantic
from more_itertools import triplewise
from pydantic import ConfigDict, Field
from pydantic.types import UUID4
from pyobo import Reference

from semra.rules import SEMRA_EVIDENCE_PREFIX, SEMRA_MAPPING_PREFIX, SEMRA_MAPPING_SET_PREFIX

__all__ = [
    "Evidence",
    "Mapping",
    "MappingSet",
    "ReasonedEvidence",
    "Reference",
    "SimpleEvidence",
    "Triple",
    "line",
    "triple_key",
]

#: A type annotation for a subject-predicate-object triple
Triple = tuple[Reference, Reference, Reference]


def triple_key(triple: Triple) -> tuple[str, str, str]:
    """Get a sortable key for a triple."""
    return triple[0].curie, triple[2].curie, triple[1].curie


def _md5_hexdigest(picklable: object) -> str:
    hasher = md5()  # noqa: S324
    hasher.update(pickle.dumps(picklable))
    return hasher.hexdigest()


class KeyedMixin(ABC):
    """A mixin for a class that can be hashed and CURIE-encoded."""

    #: The prefix for CURIEs for instances of this class
    _prefix: ClassVar[str]

    def __init_subclass__(cls, *, prefix: str, **kwargs: Any) -> None:
        cls._prefix = prefix

    @abstractmethod
    def key(self) -> object:
        """Return a picklable key."""
        raise NotImplementedError

    def hexdigest(self) -> str:
        """Get a hex string for the MD5 hash of the pickled key() for this class."""
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
    """A mixin for classes that have confidence information."""

    def get_confidence(self) -> float:
        """Get the confidence.

        :returns: The confidence, which can either be a direct annotation or computed
            based on other related objects. For example, a :class:`MappingSet` has an
            explicitly annotated confidence, whereas a :class:`ReasonedEvidence`
            calculates its confidence based on all of its prior probability *and* the
            confidences of the mappings on which it depends.
        """
        raise NotImplementedError


class EvidenceMixin:
    """A mixin for evidence classes."""

    @property
    def explanation(self) -> str:
        """Get a textual explanation for this evidence."""
        return ""

    @property
    def mapping_set_names(self) -> set[str]:
        """Get set of mapping set names that contribute to this evidence."""
        raise NotImplementedError


class MappingSet(pydantic.BaseModel, ConfidenceMixin, KeyedMixin, prefix=SEMRA_MAPPING_SET_PREFIX):
    """Represents a set of semantic mappings.

    For example, this might correspond to:

    1. All the mappings extracted from an ontology
    2. All the mappings published with a database
    3. All the mappings inferred by SeMRA based on a given configuration
    """

    name: str = Field(..., description="Name of the mapping set")
    version: str | None = Field(
        default=None, description="The version of the dataset from which the mapping comes"
    )
    license: str | None = Field(default=None, description="License name or URL for mapping set")
    confidence: float = Field(..., description="Mapping set level confidence")

    def key(self) -> object:
        """Get a picklable key representing the mapping set."""
        return self.name, self.version or "", self.license or "", self.confidence

    def get_confidence(self) -> float:
        """Get the explicit confidence for the mapping set."""
        return self.confidence


class SimpleEvidence(
    pydantic.BaseModel, KeyedMixin, EvidenceMixin, ConfidenceMixin, prefix=SEMRA_EVIDENCE_PREFIX
):
    """Evidence for a mapping.

    Ideally, this matches the SSSOM data model.
    """

    model_config = ConfigDict(frozen=True)

    evidence_type: Literal["simple"] = Field(default="simple")
    justification: Reference = Field(
        default=Reference(prefix="semapv", identifier="UnspecifiedMapping"),
        description="A SSSOM-compliant justification",
    )
    mapping_set: MappingSet = Field(
        ..., description="The name of the dataset from which the mapping comes"
    )
    author: Reference | None = Field(
        default=None,
        description="A reference to the author of the mapping (e.g. with ORCID)",
        examples=[
            Reference(prefix="orcid", identifier="0000-0003-4423-4370"),
        ],
    )
    uuid: UUID4 = Field(default_factory=uuid.uuid4)
    confidence: float | None = Field(None, description="The confidence")

    def key(self) -> object:
        """Get a key suitable for hashing the evidence.

        :returns: A key for deduplication based on the mapping set.

        Note: this should be extended to include basically _all_ fields
        """
        return (
            self.evidence_type,
            self.justification,
            self.author,
            self.mapping_set.key(),
            self.uuid,
        )

    @property
    def mapping_set_names(self) -> set[str]:
        """Get a set containing 1 element - this evidence's mapping set's name."""
        return {self.mapping_set.name}

    def get_confidence(self) -> float:
        """Get the confidence from the mapping set."""
        return self.confidence if self.confidence is not None else self.mapping_set.confidence


class ReasonedEvidence(
    pydantic.BaseModel, KeyedMixin, EvidenceMixin, ConfidenceMixin, prefix=SEMRA_EVIDENCE_PREFIX
):
    """A complex evidence based on multiple mappings."""

    model_config = ConfigDict(frozen=True)

    evidence_type: Literal["reasoned"] = Field(default="reasoned")
    justification: Reference = Field(..., description="A SSSOM-compliant justification")
    mappings: list[Mapping] = Field(
        ..., description="A list of mappings and their evidences consumed to create this evidence"
    )
    author: Reference | None = None
    confidence_factor: float = Field(
        1.0, description="The probability that the reasoning method is correct"
    )

    def key(self) -> object:
        """Get a key for reasoned evidence."""
        return (
            self.evidence_type,
            self.justification,
            *((*m.triple, *(e.key() for e in m.evidence)) for m in self.mappings),
        )

    def get_confidence(self) -> float:
        r"""Calculate confidence for the reasoned evidence.

        :returns: The joint binomial probability that all reasoned evidences are
            correct. This is calculated with the following:

            $\alpha \times (1 - \sum_{e \in E} 1 - \text{confidence}_e)$

            where $E$ is the set of all evidences in this object and $\alpha$ is the
            confidence factor for the reasoning approach.
        """
        confidences = [mapping.get_confidence() for mapping in self.mappings]
        return _joint_probability([self.confidence_factor, *confidences])

    @property
    def mapping_set(self) -> None:
        """Return an empty mapping set, since this is a reasoned evidence."""
        return None

    @property
    def mapping_set_names(self) -> set[str]:
        """Get a set containing the union of all the mappings' evidences' mapping set names."""
        return {
            name
            for mapping in self.mappings
            for evidence in mapping.evidence
            for name in evidence.mapping_set_names
        }

    @property
    def explanation(self) -> str:
        """Get a textual explanation for this reasoned evidence.

        :returns: Assuming this reasoned evidence represents a pathway where each
            mapping in the chain's subject shares the object from the previous mapping,
            returns a space-delmited list of the CURIEs for these entities.
        """
        return (
            " ".join(mapping.s.curie for mapping in self.mappings) + " " + self.mappings[-1].o.curie
        )


Evidence = Annotated[
    ReasonedEvidence | SimpleEvidence,
    Field(discriminator="evidence_type"),
]


class Mapping(pydantic.BaseModel, ConfidenceMixin, KeyedMixin, prefix=SEMRA_MAPPING_PREFIX):
    """A semantic mapping."""

    model_config = ConfigDict(frozen=True)

    s: Reference = Field(..., title="subject")
    p: Reference = Field(..., title="predicate")
    o: Reference = Field(..., title="object")
    evidence: list[Evidence] = Field(default_factory=list)

    @property
    def triple(self) -> Triple:
        """Get the mapping's core triple as a tuple."""
        return self.s, self.p, self.o

    def key(self) -> object:
        """Get a hashable key for the mapping, based on the subject, predicate, and object."""
        return self.triple

    @classmethod
    def from_triple(cls, triple: Triple, evidence: list[Evidence] | None = None) -> Mapping:
        """Instantiate a mapping from a triple."""
        s, p, o = triple
        return cls(s=s, p=p, o=o, evidence=evidence or [])

    def get_confidence(self) -> float:
        """Aggregate the mapping's evidences' confidences in a binomial model."""
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


def line(*references: Reference) -> list[Mapping]:
    """Create a list of mappings from a simple mappings path."""
    if not (3 <= len(references) and len(references) % 2):
        raise ValueError
    return [Mapping(s=s, p=p, o=o) for s, p, o in islice(triplewise(references), None, None, 2)]


ReasonedEvidence.model_rebuild()


def _joint_probability(probabilities: Iterable[float]) -> float:
    """Calculate the probability that a list of probabilities are jointly true."""
    return 1.0 - math.prod(1.0 - probability for probability in probabilities)
