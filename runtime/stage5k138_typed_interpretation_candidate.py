#!/usr/bin/env python3
"""K138 typed interpretation schema for geometric ingress arbitration.

An InterpretationCandidate is one hypothesis about what an utterance is
doing: a typed family, the geometric resonance of the utterance against the
family's prototype state, the typed feature evidence that supports or
opposes it, and the resulting bid.  An ArbitrationRecord is the simultaneous
scoring of every family with an explicit winner, runner-up, and calibrated
margin — the object that replaces first-match handler precedence.

The schema is deliberately runtime-independent: it imports nothing from the
agent chain so that the shadow arbiter can be evaluated against frozen panel
transcripts without constructing a runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


FAMILIES = (
    "registered_source_action",
    "corpus_compile",
    "essay_artifact",
    "typed_modal",
    "causal_discourse",
    "lexical_definition",
    "discourse_assertion",
    "social",
    "open_retrieval",
    "clarification",
)

# Terminal operator -> interpretation family.  Derived from the operator
# vocabulary of the frozen K132-K145 panels.
OPERATION_FAMILY = {
    "bounded_tool": "registered_source_action",
    "bounded_agentic_tool": "registered_source_action",
    "compile_corpus_expert": "corpus_compile",
    "native_relational_essay": "essay_artifact",
    "clarify_essay_topic": "essay_artifact",
    "clarify_essay_evidence": "essay_artifact",
    "assert_modal_relation": "typed_modal",
    "query_modal_relation": "typed_modal",
    "compose_causal_graph": "causal_discourse",
    "compose_causal_clause": "causal_discourse",
    "query_causal_clause": "causal_discourse",
    "query_persistent_causal_discourse": "causal_discourse",
    "lexical_concept_definition": "lexical_definition",
    "assert_graph_fact": "discourse_assertion",
    "social_acknowledgement": "social",
    "knowledge_explanation": "open_retrieval",
}

# Panel expected-kind -> family, for gold turns that constrain the operator
# only negatively (operation_not) or structurally.
KIND_FAMILY = {
    "public_essay": "essay_artifact",
    "caller_essay": "essay_artifact",
    "missing_topic": "essay_artifact",
    "unknown_topic": "essay_artifact",
    "modal_control": "typed_modal",
    "modal_abstain": "typed_modal",
    "modal_assert": "typed_modal",
    "modal_query": "typed_modal",
    "registered_tool": "registered_source_action",
    "rapid_expert": "corpus_compile",
}


@dataclass(frozen=True)
class InterpretationCandidate:
    family: str
    resonance: float
    feature_evidence: dict[str, float]
    bid: float

    def public(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "resonance": round(self.resonance, 6),
            "feature_evidence": {
                name: round(value, 4) for name, value in self.feature_evidence.items()
            },
            "bid": round(self.bid, 6),
        }


@dataclass(frozen=True)
class ArbitrationRecord:
    utterance_sha256: str
    candidates: tuple[InterpretationCandidate, ...]
    winner: str
    runner_up: str
    margin: float
    clarification_floor_applied: bool
    geometric_prototype_states: bool = True

    def public(self) -> dict[str, Any]:
        return {
            "utterance_sha256": self.utterance_sha256,
            "candidates": [value.public() for value in self.candidates],
            "winner": self.winner,
            "runner_up": self.runner_up,
            "margin": round(self.margin, 6),
            "clarification_floor_applied": self.clarification_floor_applied,
            "geometric_prototype_states": self.geometric_prototype_states,
            "simultaneous_candidate_scoring": True,
        }


@dataclass
class DiscourseSummary:
    """Light typed discourse state the arbiter conditions bids on."""

    causal_subjects: set[str] = field(default_factory=set)
    modal_subjects: set[str] = field(default_factory=set)
    graph_subjects: set[str] = field(default_factory=set)
    registered_addresses: set[str] = field(default_factory=set)

    def observe(self, family: str, subject: str | None) -> None:
        if not subject:
            return
        value = subject.casefold()
        if family == "causal_discourse":
            self.causal_subjects.add(value)
        elif family == "typed_modal":
            self.modal_subjects.add(value)
        elif family == "discourse_assertion":
            self.graph_subjects.add(value)
        elif family == "registered_source_action":
            self.registered_addresses.add(value)


def gold_family(expected: dict[str, Any]) -> str | None:
    operation = str(expected.get("operation") or "")
    if operation in OPERATION_FAMILY:
        return OPERATION_FAMILY[operation]
    kind = str(expected.get("kind") or "")
    if kind in KIND_FAMILY:
        return KIND_FAMILY[kind]
    return None


__all__ = [
    "FAMILIES", "OPERATION_FAMILY", "KIND_FAMILY",
    "InterpretationCandidate", "ArbitrationRecord", "DiscourseSummary",
    "gold_family",
]
