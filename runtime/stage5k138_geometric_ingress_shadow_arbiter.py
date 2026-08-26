#!/usr/bin/env python3
"""K138 geometric ingress shadow arbiter.

Scores every typed interpretation family simultaneously for an utterance and
returns an ArbitrationRecord with winner, runner-up, and calibrated margin.
Each family's bid combines (a) HRR resonance between the utterance bundle —
role-bound word states plus bigram bindings over unitary phase vectors — and
the family's prototype state, and (b) typed feature evidence: construction
markers, caller-context availability, and discourse-state compatibility.

Shadow mode only: this module controls no dispatch, mutates no runtime
state, and imports nothing from the agent chain.  Prototype phrase sets are
generic paraphrase templates, not panel surfaces.  No language model,
transformer, pretrained encoder, autoregressive carrier, remote call, or
gradient update is involved; every vector is a deterministic seeded phasor.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

import numpy as np

from stage5k138_typed_interpretation_candidate import (
    FAMILIES,
    ArbitrationRecord,
    DiscourseSummary,
    InterpretationCandidate,
)


D = 1024
CLARIFICATION_FLOOR = 0.55
MARGIN_TAU = 0.08

MODALS = {"may", "might", "must", "should", "can", "could", "would", "will"}
STOP = {
    "a", "an", "the", "of", "to", "for", "in", "on", "and", "or", "its",
    "it", "is", "are", "was", "be", "this", "that", "these", "those",
}
ARTIFACT_NOUNS = {"essay", "article", "paragraph", "paragraphs", "report", "summary"}
ARTIFACT_VERBS = {"write", "compose", "draft", "develop", "produce", "prepare", "author"}
DATASET_NOUNS = {"database", "catalog", "dataset", "observations", "records", "table", "data"}
REGISTERED_DOMAINS = {"earthquake", "population", "seismic"}
EXTREMA = {
    "smallest", "largest", "minimum", "maximum", "lowest", "highest",
    "greatest", "least", "weakest", "strongest", "biggest",
}
SELECTION_VERBS = {
    "use", "using", "consult", "search", "select", "choose", "find",
    "locate", "identify", "determine", "within", "from", "query",
}
PROJECTION_MARKERS = {"chosen", "selected", "record", "event"}
COMPARISON = {"which", "greater", "smaller", "difference", "belongs", "supplied"}
SOCIAL_MARKERS = {"hello", "hi", "hey", "thanks", "thank", "greetings", "goodbye"}
OPINION_MARKERS = {"take", "opinion", "think", "feel", "view", "thoughts"}
DEFINITION_LEADS = ("what is ", "what are ", "define ")

PROTOTYPES: dict[str, tuple[str, ...]] = {
    "registered_source_action": (
        "use the registered catalog to find the smallest entry then report the chosen record",
        "search the registered source for the highest value and give the selected record",
        "from the registered records determine the greatest measurement then state that entry",
        "consult the catalog to locate the lowest reading and return its record",
    ),
    "corpus_compile": (
        "which supplied item has the greater measurement and by what difference",
        "compare the supplied entries and report which one is larger",
        "which of the provided units has the smaller rating and which part belongs to it",
    ),
    "essay_artifact": (
        "write a short essay examining a topic",
        "compose an article explaining why something happens",
        "draft a structured essay about a subject",
        "develop a multi paragraph essay on a relation between two ideas",
        "produce an essay about the relationship between two concepts",
    ),
    "typed_modal": (
        "could a thing perform an action",
        "might the entity change its state",
        "must the subject complete the task",
        "the entity could perform the action",
        "the subject might reach the outcome",
    ),
    "causal_discourse": (
        "the outcome happened because the cause occurred",
        "why did the subject do that",
        "the machine stopped because a part broke",
    ),
    "lexical_definition": (
        "what is a concept",
        "what is the meaning of a term",
        "define the following word",
    ),
    "discourse_assertion": (
        "the entity is a kind of thing",
        "the object has a property",
        "the item sits inside the container",
    ),
    "social": (
        "hello there how are you",
        "hey what can you actually do",
        "thanks for the help",
    ),
    "open_retrieval": (
        "tell me about a broad topic",
        "explain what is known about the subject",
        "share background knowledge on this matter",
    ),
}

FEATURE_WEIGHTS: dict[str, dict[str, float]] = {
    "registered_source_action": {
        "dataset_noun": 0.35, "registered_word": 0.30, "registered_domain": 0.25,
        "extremum": 0.30, "selection_verb": 0.15, "projection": 0.15,
        "artifact_request": -0.60, "corpus_context": -0.30,
    },
    "corpus_compile": {
        "corpus_context": 0.90, "comparison": 0.30, "question": 0.10,
        "artifact_request": -0.60,
    },
    "essay_artifact": {
        "artifact_request": 1.10, "dataset_noun": -0.15, "corpus_context": 0.0,
    },
    "typed_modal": {
        "modal_initial": 0.95, "modal_medial_declarative": 0.85,
        "artifact_request": -0.90, "why_lead": -0.50,
    },
    "causal_discourse": {
        "because_link": 0.95, "why_lead": 0.55, "discourse_causal_match": 0.45,
        "why_without_discourse_match": -0.50, "opinion": -0.80,
        "modal_initial": -0.60, "artifact_request": -0.80,
    },
    "lexical_definition": {
        "definition_lead": 1.00, "artifact_request": -0.80,
    },
    "discourse_assertion": {
        "copular_declarative": 0.35, "question": -0.40, "modal_medial_declarative": -0.70,
        "because_link": -0.60, "artifact_request": -0.80,
    },
    "social": {
        "social_marker": 0.95, "capability_question": 0.55, "artifact_request": -0.80,
    },
    "open_retrieval": {
        "question": 0.15, "opinion": 0.35, "artifact_request": -0.80,
        "modal_initial": -0.55, "dataset_noun": -0.25, "definition_lead": -0.50,
    },
}


def _terms(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9'-]*", text.casefold())


def _vector(token: str) -> np.ndarray:
    seed = int.from_bytes(hashlib.sha256(f"k138:{token}".encode()).digest()[:8], "big")
    phases = np.random.default_rng(seed).uniform(0.0, 2.0 * np.pi, D)
    return np.exp(1j * phases)


def _bind(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    return np.fft.ifft(np.fft.fft(left) * np.fft.fft(right))


def _bucket(index: int) -> str:
    if index == 0:
        return "pos:first"
    if index <= 3:
        return "pos:early"
    if index <= 8:
        return "pos:middle"
    return "pos:late"


def encode(text: str) -> np.ndarray:
    tokens = [value for value in _terms(text) if value not in STOP]
    if not tokens:
        tokens = _terms(text) or ["empty"]
    bundle = np.zeros(D, dtype=np.complex128)
    for index, token in enumerate(tokens):
        bundle += _bind(_vector(token), _vector(_bucket(index)))
    for left, right in zip(tokens, tokens[1:]):
        bundle += _bind(_bind(_vector(left), _vector(right)), _vector("role:bigram"))
    norm = np.linalg.norm(bundle)
    return bundle / norm if norm else bundle


_PROTOTYPE_STATES: dict[str, np.ndarray] = {}


def prototype(family: str) -> np.ndarray:
    state = _PROTOTYPE_STATES.get(family)
    if state is None:
        phrases = PROTOTYPES.get(family, ())
        if phrases:
            stacked = np.sum([encode(phrase) for phrase in phrases], axis=0)
            norm = np.linalg.norm(stacked)
            state = stacked / norm if norm else stacked
        else:
            state = np.zeros(D, dtype=np.complex128)
        _PROTOTYPE_STATES[family] = state
    return state


def resonance(bundle: np.ndarray, family: str) -> float:
    state = prototype(family)
    if not np.any(state):
        return 0.0
    return float(np.real(np.vdot(state, bundle)))


def features(
    text: str, *, has_training_corpus: bool, summary: DiscourseSummary,
) -> dict[str, float]:
    lower = text.casefold().strip()
    tokens = _terms(lower)
    token_set = set(tokens)
    first = tokens[0] if tokens else ""
    modal_initial = first in MODALS
    modal_medial = bool(
        not modal_initial
        and any(value in MODALS for value in tokens[1:4])
        and not lower.endswith("?")
    )
    why_lead = first == "why"
    discourse_match = bool(
        {value for value in tokens} & summary.causal_subjects
    )
    return {
        "question": float(lower.endswith("?")),
        "artifact_request": float(
            bool(token_set & ARTIFACT_NOUNS) and bool(token_set & ARTIFACT_VERBS)
        ),
        "dataset_noun": float(bool(token_set & DATASET_NOUNS)),
        "registered_word": float("registered" in token_set),
        "registered_domain": float(bool(token_set & REGISTERED_DOMAINS)),
        "extremum": float(bool(token_set & EXTREMA)),
        "selection_verb": float(bool(token_set & SELECTION_VERBS)),
        "projection": float(bool(token_set & PROJECTION_MARKERS)),
        "corpus_context": float(has_training_corpus),
        "comparison": float(bool(token_set & COMPARISON)),
        "modal_initial": float(modal_initial),
        "modal_medial_declarative": float(modal_medial),
        "because_link": float("because" in token_set),
        "why_lead": float(why_lead),
        "discourse_causal_match": float(why_lead and discourse_match),
        "why_without_discourse_match": float(why_lead and not discourse_match),
        "opinion": float(
            bool(token_set & OPINION_MARKERS) and bool({"your", "you"} & token_set)
        ),
        "definition_lead": float(lower.startswith(DEFINITION_LEADS)),
        "social_marker": float(bool(token_set & SOCIAL_MARKERS)),
        "capability_question": float(
            "you" in token_set and bool({"can", "could"} & token_set) and lower.endswith("?")
        ),
        "copular_declarative": float(
            not lower.endswith("?")
            and bool({"is", "has", "sits", "contains"} & set(_terms(lower)))
        ),
    }


def declarative_subject(text: str) -> str | None:
    tokens = _terms(text)
    for token in tokens:
        if token not in STOP and token not in MODALS:
            return token
    return None


def arbitrate(
    text: str,
    *,
    has_training_corpus: bool = False,
    summary: DiscourseSummary | None = None,
) -> ArbitrationRecord:
    summary = summary if summary is not None else DiscourseSummary()
    bundle = encode(text)
    evidence = features(text, has_training_corpus=has_training_corpus, summary=summary)
    candidates: list[InterpretationCandidate] = []
    for family in FAMILIES:
        if family == "clarification":
            continue
        weights = FEATURE_WEIGHTS.get(family, {})
        typed = {
            name: weights[name] * evidence[name]
            for name in weights
            if evidence.get(name)
        }
        geometric = resonance(bundle, family)
        bid = 1.4 * geometric + sum(typed.values())
        candidates.append(InterpretationCandidate(family, geometric, typed, bid))
    candidates.sort(key=lambda value: (-value.bid, value.family))
    top, second = candidates[0], candidates[1]
    margin = top.bid - second.bid
    floor_applied = top.bid < CLARIFICATION_FLOOR or margin < MARGIN_TAU
    winner = "clarification" if floor_applied else top.family
    runner_up = top.family if floor_applied else second.family
    record = ArbitrationRecord(
        utterance_sha256=hashlib.sha256(text.encode()).hexdigest(),
        candidates=tuple(candidates),
        winner=winner,
        runner_up=runner_up,
        margin=margin,
        clarification_floor_applied=floor_applied,
    )
    return record


__all__ = [
    "CLARIFICATION_FLOOR", "MARGIN_TAU",
    "arbitrate", "declarative_subject", "encode", "features", "resonance",
]
