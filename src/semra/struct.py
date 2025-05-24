"""Data structures for mappings."""

from __future__ import annotations

import math
import pickle
from abc import ABC, abstractmethod
from collections.abc import Iterable
from hashlib import md5
from itertools import islice
from typing import Annotated, Any, ClassVar, Generic, Literal, NamedTuple, ParamSpec, TypeVar, Union

import pydantic
from curies.triples import StrTriple, Triple
from more_itertools import triplewise
from pydantic import ConfigDict, Field
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
]

P = ParamSpec("P")
X = TypeVar("X")


def _md5_hexdigest(picklable: object) -> str:
    hasher = md5()  # noqa: S324
    hasher.update(pickle.dumps(picklable))
    return hasher.hexdigest()


class KeyedMixin(ABC, Generic[P, X]):
    """A mixin for a class that can be hashed and CURIE-encoded."""

    #: The prefix for CURIEs for instances of this class
    _prefix: ClassVar[str]

    def __init_subclass__(cls, *, prefix: str, **kwargs: Any) -> None:
        cls._prefix = prefix

    @abstractmethod
    def key(self, *args: P.args, **kwargs: P.kwargs) -> X:
        """Return a picklable key."""
        raise NotImplementedError

    def hexdigest(self, *args: P.args, **kwargs: P.kwargs) -> str:
        """Get a hex string for the MD5 hash of the pickled key() for this class."""
        key = self.key(*args, **kwargs)
        return _md5_hexdigest(key)

    def get_reference(self, *args: P.args, **kwargs: P.kwargs) -> Reference:
        """Get a CURIE reference using this class's prefix and its hexadecimal representation."""
        return Reference(prefix=self._prefix, identifier=self.hexdigest(*args, **kwargs))

    @property
    def curie(self, *args: P.args, **kwargs: P.kwargs) -> str:
        """Get a string representing the CURIE."""
        return self.get_reference(*args, **kwargs).curie


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


class MappingSetKey(NamedTuple):
    """The key used for a mapping set."""

    purl: str
    name: str
    version: str
    license: str


class MappingSet(
    pydantic.BaseModel,
    ConfidenceMixin,
    KeyedMixin[[], MappingSetKey],
    prefix=SEMRA_MAPPING_SET_PREFIX,
):
    """Represents a set of semantic mappings.

    For example, this might correspond to:

    1. All the mappings extracted from an ontology
    2. All the mappings published with a database
    3. All the mappings inferred by SeMRA based on a given configuration

    Mostly corresponds to the concept of a SSSOM mapping set, documented in
    https://mapping-commons.github.io/sssom/MappingSet.
    """

    model_config = ConfigDict(frozen=True)

    purl: str | None = Field(
        None,
        description="The persistent URL (PURL) for the mapping set. While it's optional in SeMRA, this is a required SSSOM field: https://mapping-commons.github.io/sssom/mapping_set_id/",
    )
    name: str = Field(
        ...,
        description="Name of the mapping set. Corresponds to optional SSSOM field: https://mapping-commons.github.io/sssom/mapping_set_title/",
    )
    version: str | None = Field(
        default=None,
        description="The version of the dataset from which the mapping comes. Corresponds to optional SSSOM field https://mapping-commons.github.io/sssom/mapping_set_version/",
    )
    license: str | None = Field(
        default=None,
        description="License name or URL that applies to the whole mapping set. Corresponds to optional SSSOM field https://mapping-commons.github.io/sssom/license/",
    )
    confidence: float = Field(
        default=1.0,
        description="Mapping set level confidence. This is _not_ a SSSOM field, since SeMRA makes a difference confidence assessment at the mapping set level and at the individual mapping level. This was requeted to be added to SSSOM in https://github.com/mapping-commons/sssom/issues/438.",
    )

    def key(self) -> MappingSetKey:
        """Get a picklable key representing the mapping set."""
        return MappingSetKey(self.purl or "", self.name, self.version or "", self.license or "")

    def get_confidence(self) -> float:
        """Get the explicit confidence for the mapping set."""
        return self.confidence


class SimpleEvidenceKey(NamedTuple):
    """The key used for a simple evidence."""

    evidence_type: str
    justification: str
    author: str
    mapping_set: MappingSetKey


class SimpleEvidence(
    pydantic.BaseModel,
    KeyedMixin[[Union[Triple, "Mapping"]], tuple[StrTriple, SimpleEvidenceKey]],
    EvidenceMixin,
    ConfidenceMixin,
    prefix=SEMRA_EVIDENCE_PREFIX,
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
    confidence: float | None = Field(None, description="The confidence")

    def _simple_key(self) -> SimpleEvidenceKey:
        return SimpleEvidenceKey(
            self.evidence_type,
            self.justification.curie,
            self.author.curie if self.author else "",
            self.mapping_set.key(),
        )

    def key(self, triple: Triple | Mapping) -> tuple[StrTriple, SimpleEvidenceKey]:
        """Get a key suitable for hashing the evidence.

        :returns: A key for deduplication based on the mapping set.

        Note: this should be extended to include basically _all_ fields
        """
        return (
            triple.as_str_triple(),
            self._simple_key(),
        )

    @property
    def mapping_set_names(self) -> set[str]:
        """Get a set containing 1 element - this evidence's mapping set's name."""
        return {self.mapping_set.name}

    def get_confidence(self) -> float:
        """Get the confidence from the mapping set."""
        return self.confidence if self.confidence is not None else self.mapping_set.confidence


def _sort_evidence_key(ev: Evidence) -> tuple[Any, ...]:
    # the first element of the simple key is the type of evidence,
    # so they can be compared
    return ev._simple_key()


class ReasonedEvidenceKey(NamedTuple):
    """The key used for a reasoned evidence."""

    evidence_type: str
    justification: str
    rest: tuple[
        tuple[tuple[StrTriple, ReasonedEvidenceKey] | tuple[StrTriple, SimpleEvidenceKey], ...], ...
    ]


class ReasonedEvidence(
    pydantic.BaseModel,
    KeyedMixin[[Union[Triple, "Mapping"]], tuple[StrTriple, ReasonedEvidenceKey]],
    EvidenceMixin,
    ConfidenceMixin,
    prefix=SEMRA_EVIDENCE_PREFIX,
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

    def _simple_key(self) -> ReasonedEvidenceKey:
        return ReasonedEvidenceKey(
            self.evidence_type,
            self.justification.curie,
            tuple(
                tuple(
                    evidence.key(mapping)
                    for evidence in sorted(mapping.evidence, key=_sort_evidence_key)
                )
                for mapping in sorted(self.mappings)
            ),
        )

    def key(self, triple: Triple | Mapping) -> tuple[StrTriple, ReasonedEvidenceKey]:
        """Get a key suitable for hashing the evidence.

        :returns: A key for deduplication based on the mapping set.

        Note: this should be extended to include basically _all_ fields
        """
        return (
            triple.as_str_triple(),
            self._simple_key(),
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
            " ".join(mapping.subject.curie for mapping in self.mappings)
            + " "
            + self.mappings[-1].object.curie
        )


Evidence = Annotated[
    ReasonedEvidence | SimpleEvidence,
    Field(discriminator="evidence_type"),
]


class Mapping(
    Triple,
    ConfidenceMixin,
    KeyedMixin[[], StrTriple],
    prefix=SEMRA_MAPPING_PREFIX,
):
    """A semantic mapping.

    This builds on the basic concept of a subject-predicate-object triple, where the
    predicate is a semantic predicate, such as those listed in the `SSSOM specification
    <https://mapping-commons.github.io/sssom/spec-model/>`_.
    """

    model_config = ConfigDict(frozen=True)

    subject: Reference = Field(..., title="subject")
    predicate: Reference = Field(..., title="predicate")
    object: Reference = Field(..., title="object")
    evidence: list[Evidence] = Field(default_factory=list)

    @property
    def triple(self) -> Triple:
        """Get the mapping's core triple as a tuple."""
        return Triple(subject=self.subject, predicate=self.predicate, object=self.object)

    def key(self) -> StrTriple:
        """Get a hashable key for the mapping, based on the subject, predicate, and object."""
        return self.as_str_triple()

    @classmethod
    def from_triple(
        cls,
        triple: Triple | tuple[Reference, Reference, Reference],
        evidence: list[Evidence] | None = None,
    ) -> Mapping:
        """Instantiate a mapping from a triple."""
        if isinstance(triple, Triple):
            return cls(
                subject=triple.subject,
                predicate=triple.predicate,
                object=triple.object,
                evidence=evidence or [],
            )
        else:
            subject, predicate, obj = triple
            return cls(subject=subject, predicate=predicate, object=obj, evidence=evidence or [])

    def get_confidence(self) -> float:
        """Aggregate the mapping's evidences' confidences in a binomial model."""
        if not self.evidence:
            raise ValueError("can not calculate confidence since no evidence")
        return _joint_probability(e.get_confidence() for e in self.evidence)

    @property
    def has_primary(self) -> bool:
        """Get if there is a primary evidence associated with this mapping."""
        return any(
            isinstance(evidence, SimpleEvidence)
            and evidence.mapping_set.name == self.subject.prefix
            for evidence in self.evidence
        )

    @property
    def has_secondary(self) -> bool:
        """Get if there is a secondary evidence associated with this mapping."""
        return any(
            isinstance(evidence, SimpleEvidence)
            and evidence.mapping_set.name != self.subject.prefix
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
    return [
        Mapping(subject=subject, predicate=predicate, object=obj)
        for subject, predicate, obj in islice(triplewise(references), None, None, 2)
    ]


ReasonedEvidence.model_rebuild()


def _joint_probability(probabilities: Iterable[float]) -> float:
    """Calculate the probability that a list of probabilities are jointly true."""
    return 1.0 - math.prod(1.0 - probability for probability in probabilities)
