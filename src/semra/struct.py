"""Data structures for mappings."""

from __future__ import annotations

import math
from itertools import islice
from typing import Annotated, Iterable, Literal, Union

import bioregistry
import pydantic
from more_itertools import triplewise
from pydantic import Field

__all__ = [
    "Reference",
    "Triple",
    "triple_key",
    "SimpleEvidence",
    "Mapping",
    "line",
]


class Reference(pydantic.BaseModel):
    """A reference to an entity in a given identifier space."""

    prefix: str = Field(
        ...,
        description="The prefix used in a compact URI (CURIE). Should be pre-standardized with the Bioregistry.",
    )
    identifier: str = Field(
        ...,
        description="The local unique identifier used in a compact URI (CURIE). "
        "Should be pre-standardized with the Bioregistry.",
    )

    class Config:
        """Pydantic configuration for references."""

        frozen = True

    @property
    def curie(self) -> str:
        """Get the reference as a CURIE string.

        :return:
            A string representation of a compact URI (CURIE).
            This assumes that prefixes and identifiers have been
            pre-standardized.

        >>> Reference(prefix="chebi", identifier="1234").curie
        'chebi:1234'
        """
        return f"{self.prefix}:{self.identifier}"

    @property
    def pair(self) -> tuple[str, str]:
        """Get the reference as a 2-tuple of prefix and identifier."""
        return self.prefix, self.identifier

    @classmethod
    def from_curie(cls, curie: str, manager: bioregistry.Manager | None = None) -> Reference:
        """Parse a CURIE string and populate a reference.

        :param curie: A string representation of a compact URI (CURIE)
        :param manager: A bioregistry manager to mediate standardization
        :return: A reference object

        >>> Reference.from_curie("chebi:1234")
        Reference(prefix='chebi', identifier='1234')
        """
        if manager:
            prefix, identifier = manager.parse_curie(curie)
        else:
            prefix, identifier = curie.split(":", 1)
        return cls(prefix=prefix, identifier=identifier)


#: A type annotation for a subject-predicate-object triple
Triple = tuple[Reference, Reference, Reference]


def triple_key(triple: Triple) -> tuple[str, str, str]:
    """Get a sortable key for a triple."""
    return triple[0].curie, triple[2].curie, triple[1].curie


EvidenceType = Literal["simple", "mutated", "reasoned"]
JUSTIFICATION_FIELD = Field(description="A SSSOM-compliant justification")


class SimpleEvidence(pydantic.BaseModel):
    """Evidence for a mapping.

    Ideally, this matches the SSSOM data model.
    """

    class Config:
        """Pydantic configuration for evidence."""

        frozen = True

    type: Literal["simple"] = Field(default="simple")
    justification: Reference | None = Field(description="A SSSOM-compliant justification")
    mapping_set: str | None = None
    author: Reference | None = None
    confidence: float | None = Field(description="Confidence in the transformation of the evidence")

    def key(self):
        """Get a key suitable for hashing the evidence.

        :return: A key for deduplication based on the mapping set.

        Note: this should be extended to include basically _all_ fields
        """
        return self.type, self.justification, self.mapping_set

    @property
    def explanation(self) -> str:
        return ""


class MutatedEvidence(pydantic.BaseModel):
    """An evidence for a mapping based on a different evidence."""

    class Config:
        """Pydantic configuration for evidence."""

        frozen = True

    type: Literal["mutated"] = Field(default="mutated")
    justification: Reference = Field(..., description="A SSSOM-compliant justification")
    evidence: Evidence = Field(..., description="A wrapped evidence")
    confidence_factor: float = Field(1.0, description="Confidence in the transformation of the evidence")

    @property
    def mapping_set(self) -> str | None:
        return self.evidence.mapping_set

    @property
    def author(self) -> Reference | None:
        return self.evidence.author

    @property
    def confidence(self) -> float | None:
        if self.evidence.confidence is None:
            return None
        return self.confidence_factor * self.evidence.confidence

    def key(self):
        return self.type, self.justification, self.evidence.key()

    @property
    def explanation(self) -> str:
        return ""


class ReasonedEvidence(pydantic.BaseModel):
    """A complex evidence based on multiple mappings."""

    class Config:
        """Pydantic configuration for evidence."""

        frozen = True

    type: Literal["reasoned"] = Field(default="reasoned")
    justification: Reference | None = Field(description="A SSSOM-compliant justification")
    mappings: list[Mapping] = Field(
        ..., description="A list of mappings and their evidences consumed to create this evidence"
    )
    author: Reference | None = None

    def key(self):
        return self.type, self.justification, *((*m.triple, *(e.key() for e in m.evidence)) for m in self.mappings)

    @property
    def confidence(self) -> float:
        return _bin(mapping.confidence for mapping in self.mappings)

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
    def explanation(self) -> str:
        return " ".join(mapping.s.curie for mapping in self.mappings) + " " + self.mappings[-1].o.curie


Evidence = Annotated[
    Union[ReasonedEvidence, MutatedEvidence, SimpleEvidence],
    Field(discriminator="type"),
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
        return _bin(1 - (evidence.confidence if evidence.confidence is not None else 0.0) for evidence in self.evidence)


def line(*references: Reference) -> list[Mapping]:
    """Create a list of mappings from a simple mappings path."""
    if not (3 <= len(references) and len(references) % 2):  # noqa:PLR2004
        raise ValueError
    return [Mapping(s=s, p=p, o=o) for s, p, o in islice(triplewise(references), None, None, 2)]


ReasonedEvidence.update_forward_refs()
MutatedEvidence.update_forward_refs()


def _bin(probs: Iterable[float]) -> float:
    return 1 - math.prod(1 - p for p in probs)
