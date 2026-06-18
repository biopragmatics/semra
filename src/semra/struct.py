"""SeMRA implements a data structure as an extension to a simple :class:`curies.Triple` that contains a list of :class:`EvidenceMixin` objects, that are come as of the the following two flavors:

1. :class:`semra.struct.SimpleEvidence` - simple evidence objects correspond to rows in
   a SSSOM file. These contain a mapping justification, optional confidence, and
   optional provenance for the mapping tool and/or curator that produced the mapping
2. :class:`semra.struct.ReasonedEvidence` - complex evidence objects that are based on
   other mappings. These contain a mapping justification (typically
   :data:`semra.vocabulary.INVERSION_MAPPING` for inversions or
   :data:`semra.vocabulary.CHAIN_MAPPING` for graph-based inference) and a list of full
   mapping objects.

Here's an example of how a mapping might look:

.. image:: img/datastruct.svg

.. note::

    This data structure is based on SSSOM, but is implemented such that each mapping has
    a full reference to the mapping set that it's part of (while SSSOM's data model
    makes the mapping set the primary object, which contains a list of mappings).

A simple evidence can be used to justify a mapping:

.. code-block:: python

    from semra import (
        Reference,
        Mapping,
        EXACT_MATCH,
        SimpleEvidence,
        MappingSet,
        MANUAL_MAPPING,
    )

    r1 = Reference(prefix="chebi", identifier="107635", name="2,3-diacetyloxybenzoic")
    r2 = Reference(prefix="mesh", identifier="C011748", name="tosiben")

    mapping = Mapping(
        subject=r1,
        predicate=EXACT_MATCH,
        object=r2,
        evidence=[
            SimpleEvidence(
                justification=MANUAL_MAPPING,
                confidence=0.99,
                author=Reference(
                    prefix="orcid",
                    identifier="0000-0003-4423-4370",
                    name="Charles Tapley Hoyt",
                ),
                mapping_set=MappingSet(
                    name="biomappings",
                    license="CC0",
                    confidence=0.90,
                ),
            )
        ],
    )

A mapping that relies on another mapping can use a reasoned evidence. In the following
example, we justify the inverse mapping from the first one:

.. code-block:: python

    from semra import ReasonedEvidence, INVERSION_MAPPING

    mapping_inv = Mapping(
        subject=r2,
        predicate=EXACT_MATCH,
        object=r1,
        evidence=[
            ReasonedEvidence(
                justification=INVERSION_MAPPING,
                mappings=[mapping],
            )
        ],
    )

.. note::

    These mappings can be produced with :func:`semra.api.flip` for a single mapping or
    with :func:`semra.inference.infer_reversible` for a mapping set.
"""  # noqa: D400

from __future__ import annotations

import math
import pickle
from abc import ABC, abstractmethod
from collections.abc import Iterable
from hashlib import md5
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Generic,
    Literal,
    ParamSpec,
    Self,
    TypeVar,
)

import bioregistry
import curies
import pydantic
import sssom_pydantic
from bioregistry.constants import FailureReturnType
from curies.triples import Triple
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator
from pyobo import Reference
from sssom_pydantic import MappingSet, SemanticMapping

from semra.constants import CC0_URL, SEMRA_EVIDENCE_PREFIX, SEMRA_MAPPING_PREFIX, SEMRA_SOURCE

if TYPE_CHECKING:
    import sssom_pydantic

__all__ = [
    "ConfidenceMixin",
    "Evidence",
    "EvidenceMixin",
    "Mapping",
    "MappingSet",
    "ReasonedEvidence",
    "Reference",
    "SimpleEvidence",
    "Statistics",
    "Triple",
]

P = ParamSpec("P")
X = TypeVar("X")


def _md5_hexdigest(picklable: object) -> str:
    hasher = md5()  # noqa: S324
    hasher.update(pickle.dumps(picklable))
    return hasher.hexdigest()


def _upgrade(x: curies.Reference | Reference | None) -> Reference | None:
    if x is None:
        return None
    if isinstance(x, Reference):
        return x
    elif isinstance(x, curies.Reference):
        return Reference.from_reference(x)
    return x


ReferenceValidator = BeforeValidator(_upgrade)


class KeyedMixin(ABC, Generic[P]):
    """A mixin for a class that can be hashed and CURIE-encoded."""

    #: The prefix for CURIEs for instances of this class
    _prefix: ClassVar[str]

    def __init_subclass__(cls, *, prefix: str, **kwargs: Any) -> None:
        cls._prefix = prefix

    def get_identifier(self, *args: P.args, **kwargs: P.kwargs) -> str:
        """Get a local unique identifier."""
        raise NotImplementedError

    def get_reference(self, *args: P.args, **kwargs: P.kwargs) -> Reference:
        """Get a CURIE reference using this class's prefix and its hexadecimal representation."""
        return Reference(prefix=self._prefix, identifier=self.get_identifier(*args, **kwargs))

    @property
    def curie(self, *args: P.args, **kwargs: P.kwargs) -> str:
        """Get a string representing the CURIE."""
        return self.get_reference(*args, **kwargs).curie


class ConfidenceMixin:
    """A mixin for classes that have confidence information."""

    def get_confidence(self) -> float | None:
        """Get the confidence.

        :returns: The confidence, which can either be a direct annotation or computed
            based on other related objects. For example, a :class:`MappingSet` has an
            explicitly annotated confidence, whereas a :class:`ReasonedEvidence`
            calculates its confidence based on all of its prior probability *and* the
            confidences of the mappings on which it depends.
        """
        raise NotImplementedError


class EvidenceMixin(KeyedMixin[[Triple]], prefix=SEMRA_EVIDENCE_PREFIX):
    """A class that represents evidences."""

    @property
    def explanation(self) -> str | None:
        """Get a textual explanation for this evidence."""
        return None

    @property
    def mapping_set_names(self) -> set[str]:
        """Get set of mapping set names that contribute to this evidence."""
        raise NotImplementedError

    def get_identifier(self, triple: Triple) -> str:
        """Get a hex string for the MD5 hash of the pickled key() for this class."""
        return sssom_pydantic.hash_mapping(self._to_sssom_pydantic(triple), CONVERTER)

    @abstractmethod
    def _to_sssom_pydantic(
        self,
        mapping: Triple,
        subject: Reference | None = None,
        object: Reference | None = None,
    ) -> sssom_pydantic.SemanticMapping:
        raise NotImplementedError


class SimpleEvidence(
    pydantic.BaseModel, EvidenceMixin, ConfidenceMixin, prefix=SEMRA_EVIDENCE_PREFIX
):
    """Evidence for a mapping."""

    model_config = ConfigDict(frozen=True)

    evidence_type: Literal["simple"] = Field(default="simple", exclude=False)
    mapping: SemanticMapping
    mapping_set: Annotated[
        MappingSet, Field(description="The name of the dataset from which the mapping comes")
    ]

    @property
    def author(self) -> Reference | None:
        """Get the author."""
        if self.mapping.authors:
            return Reference.from_reference(self.mapping.authors[0])
        return None

    @property
    def justification(self) -> Reference:
        """Get the justification."""
        return Reference.from_reference(self.mapping.justification)

    @property
    def mapping_set_names(self) -> set[str]:
        """Get a set containing 1 element - this evidence's mapping set's name."""
        if self.mapping_set.title is None:
            return set()
        return {self.mapping_set.title}

    def get_confidence(self) -> float | None:
        """Get the confidence from the mapping set."""
        if self.mapping.confidence is not None:
            return self.mapping.confidence
        if self.mapping_set.confidence is not None:
            return self.mapping_set.confidence
        return None

    def _to_sssom_pydantic(
        self,
        mapping: Triple | Mapping,
        subject: Reference | None = None,
        object: Reference | None = None,
    ) -> sssom_pydantic.SemanticMapping:
        return self.mapping


class ReasonedEvidence(
    pydantic.BaseModel, EvidenceMixin, ConfidenceMixin, prefix=SEMRA_EVIDENCE_PREFIX
):
    """A complex evidence based on multiple mappings."""

    model_config = ConfigDict(frozen=True)

    evidence_type: Literal["reasoned"] = Field(default="reasoned", exclude=False)
    justification: Annotated[
        Reference, Field(description="A SSSOM-compliant justification"), ReferenceValidator
    ]
    mappings: Annotated[
        list[Mapping],
        Field(
            description="A list of mappings and their evidences consumed to create this evidence"
        ),
    ]
    author: Annotated[Reference | None, ReferenceValidator] = None
    confidence_factor: Annotated[
        float, Field(description="The probability that the reasoning method is correct")
    ] = 1.0

    def _to_sssom_pydantic(
        self, triple: Triple, subject: Reference | None = None, object: Reference | None = None
    ) -> sssom_pydantic.SemanticMapping:
        return sssom_pydantic.SemanticMapping(
            subject=subject or triple.subject,
            predicate=triple.predicate,
            object=object or triple.object,
            justification=self.justification,
            confidence=self.get_confidence(),
            license=CC0_URL,
            authors=[self.author] if self.author else None,
            comment=self.explanation,
            source=SEMRA_SOURCE,
            derived_from=[mapping.get_reference() for mapping in self.mappings],
        )

    def get_confidence(self) -> float | None:
        r"""Calculate confidence for the reasoned evidence.

        :returns: The joint binomial probability that all reasoned evidences are
            correct. This is calculated with the following:

            $\alpha \times (1 - \sum_{e \in E} 1 - \text{confidence}_e)$

            where $E$ is the set of all evidences in this object and $\alpha$ is the
            confidence factor for the reasoning approach.
        """
        confidences = [
            confidence for mapping in self.mappings if (confidence := mapping.get_confidence())
        ]
        if confidences:
            return _joint_probability([self.confidence_factor, *confidences])
        return None

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
    def explanation(self) -> str | None:
        """Get a textual explanation for this reasoned evidence.

        :returns: Assuming this reasoned evidence represents a pathway where each
            mapping in the chain's subject shares the object from the previous mapping,
            returns a space-delmited list of the CURIEs for these entities.
        """
        if len(self.mappings) == 1:
            return None
        return (
            " ".join(mapping.subject.curie for mapping in self.mappings)
            + " "
            + self.mappings[-1].object.curie
        )


Evidence = Annotated[
    ReasonedEvidence | SimpleEvidence,
    Field(discriminator="evidence_type"),
]

CONVERTER = bioregistry.get_default_converter(stubs=True)


class Mapping(
    Triple,
    ConfidenceMixin,
    KeyedMixin[[]],
    prefix=SEMRA_MAPPING_PREFIX,
):
    """A semantic mapping.

    This builds on the basic concept of a subject-predicate-object triple, where the
    predicate is a semantic predicate, such as those listed in the `SSSOM specification
    <https://mapping-commons.github.io/sssom/spec-model/>`_.
    """

    model_config = ConfigDict(frozen=True)

    subject: Annotated[Reference, ReferenceValidator]
    predicate: Annotated[Reference, ReferenceValidator]
    object: Annotated[Reference, ReferenceValidator]
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_simple_evidences_match(self) -> Self:
        """Check triples in simple evidences match."""
        for evidence in self.evidence:
            if not isinstance(evidence, SimpleEvidence):
                continue
            if self.subject != evidence.mapping.subject:
                raise ValueError(
                    f"subjects do not match {self.subject} vs {evidence.mapping.subject}"
                )
            if self.predicate != evidence.mapping.predicate:
                raise ValueError("predicates do not match")
            if self.object != evidence.mapping.object:
                raise ValueError("objects do not match")
        return self

    @property
    def triple(self) -> Triple:
        """Get the mapping's core triple as a tuple."""
        return Triple(subject=self.subject, predicate=self.predicate, object=self.object)

    def get_identifier(self) -> str:
        """Get the mapping's sameness identifier."""
        return CONVERTER.hash_triple(self)

    @classmethod
    def from_triple(
        cls,
        triple: Triple | tuple[Reference, Reference, Reference],
        evidence: list[Evidence] | None = None,
    ) -> Self:
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

    @classmethod
    def from_sssom_pydantic(
        cls,
        mapping: sssom_pydantic.SemanticMapping,
        mapping_set: sssom_pydantic.MappingSet | None = None,
    ) -> Self:
        """Construct a mapping from :mod:`sssom_pydantic` object."""
        # TODO what if derived_from annotations, introduced in
        #  https://github.com/cthoyt/sssom-pydantic/pull/108,
        #  then construct a ReasonedEvidence

        # if there's a source, then we want to expand this to create the mapping
        #  set, just with the ID. otherwise, were reuse the mapping_set given
        if mapping.source is not None:
            c = bioregistry.get_default_converter()
            url = c.expand_reference(mapping.source, strict=True)
            mapping_set = MappingSet(id=url, license=mapping.license)
        elif mapping.provider:
            mapping_set = MappingSet(id=mapping.provider, license=mapping.license)
        elif mapping_set is None:
            raise ValueError("mapping set ID could not be inferred, and mapping set wasn't passed")

        evidence = SimpleEvidence(mapping=mapping, mapping_set=mapping_set)
        return cls(
            subject=Reference.from_reference(mapping.subject),
            predicate=Reference.from_reference(mapping.predicate).without_name(),
            object=Reference.from_reference(mapping.object),
            evidence=[evidence],
        )

    def get_confidence(self) -> float | None:
        """Aggregate the mapping's evidences' confidences in a binomial model."""
        return _aggregate_confidences(self.evidence)

    # FIXME test primary, secondary, tertiary
    @property
    def has_primary(self) -> bool:
        """Get if there is a primary evidence associated with this mapping."""
        return any(
            str(source).removeprefix("https://bioregistry.io/") == self.subject.prefix
            for evidence in self.evidence
            if isinstance(evidence, SimpleEvidence) and evidence.mapping_set is not None
            for source in evidence.mapping_set.source or []
        )

    @property
    def has_secondary(self) -> bool:
        """Get if there is a secondary evidence associated with this mapping."""
        return any(
            str(source).removeprefix("https://bioregistry.io/") != self.subject.prefix
            for evidence in self.evidence
            if isinstance(evidence, SimpleEvidence) and evidence.mapping_set is not None
            for source in evidence.mapping_set.source or []
        )

    @property
    def has_tertiary(self) -> bool:
        """Get if there are any tertiary (i.e., reasoned) evidences for this mapping."""
        return any(not isinstance(evidence, SimpleEvidence) for evidence in self.evidence)


ReasonedEvidence.model_rebuild()


def _aggregate_confidences(elements: Iterable[ConfidenceMixin]) -> float | None:
    confidences = [confidence for element in elements if (confidence := element.get_confidence())]
    if confidences:
        return _joint_probability(confidences)
    return None


def _joint_probability(probabilities: Iterable[float]) -> float:
    """Calculate the probability that a list of probabilities are jointly true."""
    return 1.0 - math.prod(1.0 - probability for probability in probabilities)


class Statistics(BaseModel):
    """Summary statistics."""

    raw_mappings: int | None = Field(None, description="The number of raw mappings.")
    processed_mappings: int | None = Field(None, description="The number of processed mappings.")
    priority_mappings: int | None = Field(None, description="The number of priority mappings.")
    raw_term_count: int
    unique_term_count: int
    reduction: float
    distribution: dict[int, int]
    refresh_raw_timedelta: float | None = None
    refresh_source_timedelta: float | None = None


def _get_source_reference(mapping_set: MappingSet) -> Reference | None:
    if reference := _parse_source_iri(str(mapping_set.id)):
        return reference
    for source_uri in mapping_set.source or []:
        if reference := _parse_source_iri(str(source_uri)):
            return reference
            # note that if there are multiple sources, this could be a problem
    return None


def _parse_source_iri(uri: str) -> Reference | None:
    if uri.startswith("https://bioregistry.io/registry/"):
        return Reference(
            prefix="bioregistry",
            identifier=uri.removeprefix("https://bioregistry.io/registry/"),
        )
    elif uri.startswith("https://bioregistry.io/"):
        return Reference(
            prefix="bioregistry",
            identifier=uri.removeprefix("https://bioregistry.io/"),
        )
    elif source_ref := bioregistry.parse_iri(
        str(uri), strict=False, on_failure_return_type=FailureReturnType.single
    ):
        try:
            rv = Reference(prefix=source_ref.prefix, identifier=source_ref.identifier)
        except ValueError:
            return None
        else:
            return rv
    return None
