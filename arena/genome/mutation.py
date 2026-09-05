"""Auditable mutation proposals, application, and immutable history."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Self

from .genes import GeneFamily, ImpactClass, parse_gene_value
from .schema import LanguageGenome, derive_candidate_id
from .validation import affected_tests, require_valid_genome, required_impact_class


class MutationOperator(StrEnum):
    CHANGE_TOKEN = "change-token"
    CHANGE_DELIMITER = "change-delimiter"
    PREFIX_TO_SEXPR = "prefix-to-sexpr"
    MAKE_ARGUMENT_ROLE_LABELLED = "make-argument-role-labelled"
    REMOVE_REDUNDANT_TYPE_ANNOTATION = "remove-redundant-type-annotation"
    ADD_TYPE_ANNOTATION = "add-type-annotation"
    CANONICALIZE_ARGUMENT_ORDER = "canonicalize-argument-order"
    CHANGE_BINDER_ENCODING = "change-binder-encoding"
    UNIFY_BINDER_POLICY = "unify-binder-policy"
    EXPLICIT_SCOPE_MARKER = "explicit-scope-marker"
    FACTOR_ACTION = "factor-action"
    MERGE_ACTION = "merge-action"
    SPLIT_ACTION = "split-action"
    MOVE_OBLIGATION_INLINE = "move-obligation-inline"
    MOVE_OBLIGATION_EXTERNAL = "move-obligation-external"
    MAKE_PRECONDITION_EXPLICIT = "make-precondition-explicit"
    COMPRESS_STATUS = "compress-status"
    EXPAND_STATUS = "expand-status"
    STRUCTURAL_VARIABLE_ID = "structural-variable-id"
    CHANGE_STATEMENT_ORDER = "change-statement-order"
    GRAPH_TO_LINEAR = "graph-to-linear"
    LINEAR_TO_TREE = "linear-to-tree"
    ADD_ROLE_MORPHOLOGY = "add-role-morphology"
    REMOVE_REDUNDANT_WRAPPER = "remove-redundant-wrapper"


class EvaluationTier(StrEnum):
    SURFACE = "surface"
    STRUCTURAL = "structural"
    CANONICAL_GOVERNANCE = "canonical-governance"


class SoundnessRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MutationDecision(StrEnum):
    PENDING = "pending"
    PROMOTED = "promoted"
    REJECTED = "rejected"


OPERATOR_GENE_SCOPE: dict[MutationOperator, frozenset[GeneFamily]] = {
    MutationOperator.CHANGE_TOKEN: frozenset({GeneFamily.ALPHABET, GeneFamily.TOKEN_POLICY}),
    MutationOperator.CHANGE_DELIMITER: frozenset(
        {GeneFamily.ERROR_LOCALITY, GeneFamily.SERIALIZATION}
    ),
    MutationOperator.PREFIX_TO_SEXPR: frozenset({GeneFamily.GRAMMAR, GeneFamily.SERIALIZATION}),
    MutationOperator.MAKE_ARGUMENT_ROLE_LABELLED: frozenset(
        {GeneFamily.TOKEN_POLICY, GeneFamily.MORPHOLOGY}
    ),
    MutationOperator.REMOVE_REDUNDANT_TYPE_ANNOTATION: frozenset(
        {GeneFamily.TYPES, GeneFamily.REDUNDANCY}
    ),
    MutationOperator.ADD_TYPE_ANNOTATION: frozenset({GeneFamily.TYPES, GeneFamily.REDUNDANCY}),
    MutationOperator.CANONICALIZE_ARGUMENT_ORDER: frozenset(
        {GeneFamily.COMPOSITION, GeneFamily.GRAMMAR}
    ),
    MutationOperator.CHANGE_BINDER_ENCODING: frozenset({GeneFamily.BINDERS}),
    MutationOperator.UNIFY_BINDER_POLICY: frozenset({GeneFamily.BINDERS}),
    MutationOperator.EXPLICIT_SCOPE_MARKER: frozenset(
        {GeneFamily.BINDERS, GeneFamily.ERROR_LOCALITY}
    ),
    MutationOperator.FACTOR_ACTION: frozenset({GeneFamily.ACTIONS}),
    MutationOperator.MERGE_ACTION: frozenset({GeneFamily.ACTIONS}),
    MutationOperator.SPLIT_ACTION: frozenset({GeneFamily.ACTIONS}),
    MutationOperator.MOVE_OBLIGATION_INLINE: frozenset({GeneFamily.OBLIGATIONS}),
    MutationOperator.MOVE_OBLIGATION_EXTERNAL: frozenset({GeneFamily.OBLIGATIONS}),
    MutationOperator.MAKE_PRECONDITION_EXPLICIT: frozenset(
        {GeneFamily.ACTIONS, GeneFamily.REDUNDANCY}
    ),
    MutationOperator.COMPRESS_STATUS: frozenset({GeneFamily.EVIDENCE, GeneFamily.REDUNDANCY}),
    MutationOperator.EXPAND_STATUS: frozenset({GeneFamily.EVIDENCE, GeneFamily.REDUNDANCY}),
    MutationOperator.STRUCTURAL_VARIABLE_ID: frozenset({GeneFamily.BINDERS}),
    MutationOperator.CHANGE_STATEMENT_ORDER: frozenset(
        {GeneFamily.STATE, GeneFamily.SERIALIZATION}
    ),
    MutationOperator.GRAPH_TO_LINEAR: frozenset(
        {GeneFamily.GRAMMAR, GeneFamily.STATE, GeneFamily.SERIALIZATION}
    ),
    MutationOperator.LINEAR_TO_TREE: frozenset(
        {GeneFamily.GRAMMAR, GeneFamily.STATE, GeneFamily.SERIALIZATION}
    ),
    MutationOperator.ADD_ROLE_MORPHOLOGY: frozenset(
        {GeneFamily.MORPHOLOGY, GeneFamily.TOKEN_POLICY}
    ),
    MutationOperator.REMOVE_REDUNDANT_WRAPPER: frozenset(
        {GeneFamily.GRAMMAR, GeneFamily.REDUNDANCY}
    ),
}


def _stable_hash(raw: object) -> str:
    encoded = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class GeneChange:
    gene: GeneFamily
    from_value: str
    to_value: str

    def __post_init__(self) -> None:
        parse_gene_value(self.gene, self.from_value)
        parse_gene_value(self.gene, self.to_value)
        if self.from_value == self.to_value:
            raise ValueError(f"mutation does not change {self.gene.value}")

    def to_dict(self) -> dict[str, str]:
        return {
            "gene": self.gene.value,
            "from_value": self.from_value,
            "to_value": self.to_value,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, str]) -> Self:
        if set(raw) != {"gene", "from_value", "to_value"}:
            raise ValueError("gene change has missing or unknown fields")
        return cls(GeneFamily(raw["gene"]), raw["from_value"], raw["to_value"])


@dataclass(frozen=True, slots=True)
class MutationProposal:
    proposal_id: str
    parent_id: str
    operator: MutationOperator
    changes: tuple[GeneChange, ...]
    hypothesis: str
    expected_benefit: str
    soundness_risk: SoundnessRisk
    required_evaluation_tier: EvaluationTier
    impact_class: ImpactClass
    scope: str

    def __post_init__(self) -> None:
        if not self.changes:
            raise ValueError("a mutation proposal must change at least one gene")
        genes = tuple(change.gene for change in self.changes)
        if len(set(genes)) != len(genes):
            raise ValueError("a proposal cannot change the same gene twice")
        out_of_scope = set(genes) - OPERATOR_GENE_SCOPE[self.operator]
        if out_of_scope:
            names = ", ".join(sorted(gene.value for gene in out_of_scope))
            raise ValueError(f"mutation operator {self.operator.value} cannot change: {names}")
        expected_impact = required_impact_class(genes)
        impact_rank = {
            ImpactClass.SURFACE_ONLY: 0,
            ImpactClass.STRUCTURAL_SEMANTIC: 1,
            ImpactClass.CANONICAL_SEMANTIC_EXTENSION: 2,
        }
        if impact_rank[self.impact_class] < impact_rank[expected_impact]:
            raise ValueError(
                f"impact class {self.impact_class.value} understates required "
                f"{expected_impact.value} evaluation"
            )
        if not self.scope.strip():
            raise ValueError("mutation scope must be explicit")
        if not self.hypothesis.strip() or not self.expected_benefit.strip():
            raise ValueError("hypothesis and expected_benefit must be explicit")
        expected_id = f"mutation:{self.proposal_hash[:20]}"
        if self.proposal_id != expected_id:
            raise ValueError(
                f"proposal_id does not match proposal content; expected {expected_id!r}"
            )

    @property
    def changed_genes(self) -> tuple[GeneFamily, ...]:
        return tuple(change.gene for change in self.changes)

    @property
    def genes_changed(self) -> tuple[GeneFamily, ...]:
        return self.changed_genes

    @property
    def parent(self) -> str:
        return self.parent_id

    @property
    def expected_gain(self) -> str:
        return self.expected_benefit

    @property
    def risk(self) -> SoundnessRisk:
        return self.soundness_risk

    @property
    def affected_tests(self) -> tuple[str, ...]:
        return affected_tests(self.changed_genes)

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "parent_id": self.parent_id,
            "operator": self.operator.value,
            "changes": [change.to_dict() for change in self.changes],
            "hypothesis": self.hypothesis,
            "expected_benefit": self.expected_benefit,
            "soundness_risk": self.soundness_risk.value,
            "required_evaluation_tier": self.required_evaluation_tier.value,
            "impact_class": self.impact_class.value,
            "scope": self.scope,
        }

    @property
    def proposal_hash(self) -> str:
        return _stable_hash(self._identity_payload())

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            **self._identity_payload(),
            "affected_tests": list(self.affected_tests),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        expected = {
            "proposal_id",
            "parent_id",
            "operator",
            "changes",
            "hypothesis",
            "expected_benefit",
            "soundness_risk",
            "required_evaluation_tier",
            "impact_class",
            "scope",
            "affected_tests",
        }
        if set(raw) != expected:
            raise ValueError("mutation proposal has missing or unknown fields")
        changes = raw["changes"]
        if not isinstance(changes, list) or not all(isinstance(item, dict) for item in changes):
            raise ValueError("mutation changes must be a list of records")
        proposal = cls(
            proposal_id=str(raw["proposal_id"]),
            parent_id=str(raw["parent_id"]),
            operator=MutationOperator(raw["operator"]),
            changes=tuple(GeneChange.from_dict(item) for item in changes),
            hypothesis=str(raw["hypothesis"]),
            expected_benefit=str(raw["expected_benefit"]),
            soundness_risk=SoundnessRisk(raw["soundness_risk"]),
            required_evaluation_tier=EvaluationTier(raw["required_evaluation_tier"]),
            impact_class=ImpactClass(raw["impact_class"]),
            scope=str(raw["scope"]),
        )
        if raw["affected_tests"] != list(proposal.affected_tests):
            raise ValueError("mutation proposal affected_tests do not match changed genes")
        return proposal

    @classmethod
    def build(
        cls,
        *,
        parent: LanguageGenome,
        operator: MutationOperator | str,
        changes: Mapping[GeneFamily | str, str],
        hypothesis: str,
        expected_benefit: str,
        soundness_risk: SoundnessRisk | str,
        required_evaluation_tier: EvaluationTier | str,
        impact_class: ImpactClass | str | None = None,
        scope: str = "candidate-language",
    ) -> Self:
        parsed_changes = tuple(
            GeneChange(
                gene=GeneFamily(gene),
                from_value=parent.gene(GeneFamily(gene)),
                to_value=str(value),
            )
            for gene, value in sorted(changes.items(), key=lambda item: GeneFamily(item[0]).value)
        )
        computed_impact = required_impact_class(change.gene for change in parsed_changes)
        identity = {
            "parent_id": parent.candidate_id,
            "operator": MutationOperator(operator).value,
            "changes": [change.to_dict() for change in parsed_changes],
            "hypothesis": hypothesis,
            "expected_benefit": expected_benefit,
            "soundness_risk": SoundnessRisk(soundness_risk).value,
            "required_evaluation_tier": EvaluationTier(required_evaluation_tier).value,
            "impact_class": (
                ImpactClass(impact_class).value if impact_class else computed_impact.value
            ),
            "scope": scope,
        }
        return cls(
            proposal_id=f"mutation:{_stable_hash(identity)[:20]}",
            parent_id=parent.candidate_id,
            operator=MutationOperator(operator),
            changes=parsed_changes,
            hypothesis=hypothesis,
            expected_benefit=expected_benefit,
            soundness_risk=SoundnessRisk(soundness_risk),
            required_evaluation_tier=EvaluationTier(required_evaluation_tier),
            impact_class=ImpactClass(impact_class) if impact_class else computed_impact,
            scope=scope,
        )


@dataclass(frozen=True, slots=True)
class MutationRecord:
    proposal: MutationProposal
    result_candidate_id: str
    result_candidate_hash: str
    evaluation: str = ""
    regressions: tuple[str, ...] = ()
    decision: MutationDecision = MutationDecision.PENDING

    def __post_init__(self) -> None:
        if self.decision is not MutationDecision.PENDING and not self.evaluation.strip():
            raise ValueError("a completed mutation decision requires an evaluation")

    @property
    def record_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal": self.proposal.to_dict(),
            "result_candidate_id": self.result_candidate_id,
            "result_candidate_hash": self.result_candidate_hash,
            "evaluation": self.evaluation,
            "regressions": list(self.regressions),
            "decision": self.decision.value,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        expected = {
            "proposal",
            "result_candidate_id",
            "result_candidate_hash",
            "evaluation",
            "regressions",
            "decision",
        }
        if set(raw) != expected or not isinstance(raw["proposal"], dict):
            raise ValueError("mutation record has missing or unknown fields")
        regressions = raw["regressions"]
        if not isinstance(regressions, list) or not all(
            isinstance(item, str) for item in regressions
        ):
            raise ValueError("mutation regressions must be a list of strings")
        return cls(
            proposal=MutationProposal.from_dict(raw["proposal"]),
            result_candidate_id=str(raw["result_candidate_id"]),
            result_candidate_hash=str(raw["result_candidate_hash"]),
            evaluation=str(raw["evaluation"]),
            regressions=tuple(regressions),
            decision=MutationDecision(raw["decision"]),
        )


@dataclass(frozen=True, slots=True)
class MutationHistory:
    records: tuple[MutationRecord, ...] = ()

    def append(self, record: MutationRecord) -> MutationHistory:
        known_results = {item.result_candidate_id for item in self.records}
        if record.result_candidate_id in known_results:
            raise ValueError(f"duplicate mutation result: {record.result_candidate_id}")
        return MutationHistory((*self.records, record))

    def for_candidate(self, candidate_id: str) -> tuple[MutationRecord, ...]:
        return tuple(
            record
            for record in self.records
            if candidate_id in {record.proposal.parent_id, record.result_candidate_id}
        )

    def to_dict(self) -> dict[str, object]:
        return {"records": [record.to_dict() for record in self.records]}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> MutationHistory:
        if set(raw) != {"records"} or not isinstance(raw["records"], list):
            raise ValueError("mutation history must contain one records list")
        history = cls()
        for item in raw["records"]:
            if not isinstance(item, dict):
                raise ValueError("mutation history entries must be records")
            history = history.append(MutationRecord.from_dict(item))
        return history


def apply_mutation(
    parent: LanguageGenome,
    proposal: MutationProposal,
) -> tuple[LanguageGenome, MutationRecord]:
    if proposal.parent_id != parent.candidate_id:
        raise ValueError(
            f"proposal parent {proposal.parent_id!r} does not match {parent.candidate_id!r}"
        )
    updates: dict[GeneFamily | str, str] = {}
    for change in proposal.changes:
        actual = parent.gene(change.gene)
        if actual != change.from_value:
            raise ValueError(
                f"stale proposal for {change.gene.value}: expected {change.from_value!r}, "
                f"found {actual!r}"
            )
        updates[change.gene] = change.to_value
    new_gene_values = parent.genes_dict()
    new_gene_values.update({GeneFamily(family).value: value for family, value in updates.items()})
    candidate_id = derive_candidate_id(
        parent_ids=(parent.candidate_id,), genes=new_gene_values, prefix="M"
    )
    child = parent.with_gene_values(
        updates,
        candidate_id=candidate_id,
        parent_ids=(parent.candidate_id,),
    )
    require_valid_genome(child)
    return child, MutationRecord(
        proposal=proposal,
        result_candidate_id=child.candidate_id,
        result_candidate_hash=child.candidate_hash,
    )
