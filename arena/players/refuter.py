"""Adversarial Refuter that stores minimized, reproducible counterexamples."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from arena.assurance.failures import Failure, FailureStore
from arena.assurance.fuzz import run_parser_fuzz
from arena.assurance.mutations import Subject, semantic_mutations
from arena.assurance.reducers import minimize_subject, minimize_text
from arena.canonical.schema import CanonicalState
from arena.verifier.base import Verifier


@dataclass(frozen=True, slots=True)
class RefuterReport:
    candidate_id: str
    semantic_attacks: int
    grammar_attacks: int
    false_accepts: tuple[Failure, ...]
    false_rejects: tuple[Failure, ...]
    novel_failure_classes: tuple[str, ...]

    @property
    def critical_count(self) -> int:
        return sum(item.severity == "CRITICAL" for item in self.false_accepts)


class Refuter:
    def __init__(self, verifier: Verifier, failure_path: str | Path) -> None:
        self.verifier = verifier
        self.store = FailureStore(failure_path)

    def attack_semantics(self, candidate_id: str, state: CanonicalState) -> tuple[Failure, ...]:
        failures: list[Failure] = []
        for case in semantic_mutations(state):
            if not case.witness():
                continue
            if isinstance(case.subject, CanonicalState):
                accepted = self.verifier.verify_state(case.subject).accepted
            else:
                accepted = self.verifier.verify_transition(case.subject).accepted
            if accepted == case.expected_accepted:
                continue

            def reproduces(subject: Subject, expected: bool = case.expected_accepted) -> bool:
                if isinstance(subject, CanonicalState):
                    observed = self.verifier.verify_state(subject).accepted
                else:
                    observed = self.verifier.verify_transition(subject).accepted
                return observed != expected

            try:
                minimized = minimize_subject(case.subject, reproduces)
            except (TypeError, ValueError):
                minimized = case.subject
            false_accept = accepted and not case.expected_accepted
            failure = Failure.create(
                candidate=candidate_id,
                source=case.subject,
                minimized_source=minimized,
                expected={"accepted": case.expected_accepted},
                observed={"accepted": accepted},
                failure_class=case.attack_class.value,
                severity="CRITICAL" if false_accept else "ERROR",
                root_cause="verifier/candidate disagrees with independent mutation witness",
            )
            self.store.append(failure)
            failures.append(failure)
        return tuple(failures)

    def attack_parser(
        self,
        candidate_id: str,
        valid_source: str,
        parser: Callable[[str], object],
        *,
        seed: int = 0,
        random_cases: int = 64,
    ) -> tuple[Failure, ...]:
        report = run_parser_fuzz(valid_source, parser, seed=seed, random_cases=random_cases)
        failures: list[Failure] = []
        for case in report.unexpected_accepts:
            try:
                minimized = minimize_text(case.source, lambda source: self._parses(parser, source))
            except ValueError:
                minimized = case.source
            failure = Failure.create(
                candidate=candidate_id,
                source=case.source,
                minimized_source=minimized,
                expected={"parse": False},
                observed={"parse": True},
                failure_class=f"grammar:{case.operation}",
                severity="CRITICAL",
                root_cause="parser accepted a declared malformed surface",
            )
            self.store.append(failure)
            failures.append(failure)
        return tuple(failures)

    @staticmethod
    def _parses(parser: Callable[[str], object], source: str) -> bool:
        try:
            parser(source)
        except Exception:
            return False
        return True

    def run(
        self,
        candidate_id: str,
        state: CanonicalState,
        *,
        rendered_source: str | None = None,
        parser: Callable[[str], object] | None = None,
        seed: int = 0,
        random_cases: int = 64,
    ) -> RefuterReport:
        before_classes = {item.failure_class for item in self.store.all()}
        semantic = self.attack_semantics(candidate_id, state)
        grammar = (
            self.attack_parser(
                candidate_id,
                rendered_source,
                parser,
                seed=seed,
                random_cases=random_cases,
            )
            if rendered_source is not None and parser is not None
            else ()
        )
        failures = (*semantic, *grammar)
        return RefuterReport(
            candidate_id,
            len(semantic_mutations(state)),
            len(grammar),
            tuple(item for item in failures if item.severity == "CRITICAL"),
            tuple(item for item in failures if item.severity != "CRITICAL"),
            tuple(sorted({item.failure_class for item in failures} - before_classes)),
        )
