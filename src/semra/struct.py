"""Data structures for mappings."""

from __future__ import annotations

from itertools import islice

import bioregistry
import pydantic
from more_itertools import triplewise
from pydantic import Field

__all__ = [
    "Reference",
    "Triple",
    "triple_key",
    "Evidence",
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


class Evidence(pydantic.BaseModel):
    """Evidence for a mapping.

    Ideally, this matches the SSSOM data model.
    """

    class Config:
        """Pydantic configuration for evidence."""

        frozen = True

    justification: Reference | None = Field(description="A SSSOM-compliant justification")
    mapping_set: str | None = None


class Mapping(pydantic.BaseModel):
    """A semantic mapping."""

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


def line(*references: Reference) -> list[Mapping]:
    """Create a list of mappings from a simple mappings path."""
    if not (3 <= len(references) and len(references) % 2):  # noqa:PLR2004
        raise ValueError
    return [Mapping(s=s, p=p, o=o) for s, p, o in islice(triplewise(references), None, None, 2)]
