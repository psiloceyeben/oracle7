#!/usr/bin/env python3
"""M17b2 — release arbiter v2 (additive successor to v1; v1 untouched).

Two repairs from the sealed M17b one-shot failure (see
stage5m17b_oneshot_adjudication_v1.md):

1. WIDENED PROTOTYPES — lexically diverse generic paraphrase templates per
   family (gist/nutshell/story/not-the-same/appreciated classes), so the
   frozen K138 geometry has token support across more of the paraphrase space.
2. CONCEPTNET MARKER PROJECTION — novel content tokens are mapped into family
   marker classes through the admitted ConceptNet English edges (Synonym /
   FormOf / SimilarTo / IsA / DerivedFrom, weight-ordered, 1 hop, read-only).
   Corpus-grounded: "fistful" reaches the count class because the admitted
   corpus says Synonym(fistful, handful), not because an author listed it.

Same bid law as v1: 1.4 * resonance + typed markers; same floor and tau.
No LM, no transformer, no gradient."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path

import numpy as np

from stage5k138_geometric_ingress_shadow_arbiter import encode  # frozen geometry
from stage5k138_typed_interpretation_candidate import (
    ArbitrationRecord,
    InterpretationCandidate,
)
from stage5m17_release_arbiter_v1 import (
    CLARIFICATION_FLOOR,
    MARGIN_TAU,
    M_FAMILIES,
    FEATURE_WEIGHTS,
    PROTOTYPES as PROTOTYPES_V1,
    features as features_v1,
    path_family,
)

CONCEPTNET_DB = (Path(__file__).resolve().parents[1] / "fable-content"
                 / "oracle-m-series-2026-08-15" / "m13e5_conceptnet_build_a_v1"
                 / "conceptnet_specialist.sqlite3")
PROJECTION_RELS = ("Synonym", "FormOf", "SimilarTo", "IsA", "DerivedFrom")

EXTRA_PROTOTYPES: dict[str, tuple[str, ...]] = {
    "summarize": (
        "give me the gist of the topic",
        "the topic in a nutshell please",
        "a brief overview of the subject please",
        "boil the topic down to its essentials",
        "what is the story of the subject in brief",
    ),
    "compare": (
        "how are the first thing and the second thing not the same",
        "what do the two subjects have in common and where do they part",
        "how does one thing stack up against the other",
    ),
    "list_n": (
        "name a handful of facts about the topic",
        "give me a smattering of points about the subject",
        "rattle off some things about the topic",
    ),
    "timeline": (
        "what is the story of the topic over the years",
        "how did the subject unfold through time",
        "trace the subject from its beginning to now",
    ),
    "explain_simply": (
        "explain the topic in plain words",
        "put the subject in terms a beginner would get",
        "make the idea easy to understand",
    ),
    "definitional": (
        "what would you say a concept is",
        "what does the word actually mean",
        "how would you define the term",
    ),
    "act_provenance": (
        "why would you claim that",
        "what makes you say that",
        "on what basis did you answer",
    ),
    "act_acknowledge": (
        "much appreciated",
        "cheers i am grateful",
        "that was really helpful thanks a lot",
    ),
}

# family marker classes: seed words; ConceptNet projects novel tokens into them
MARKER_CLASSES: dict[str, set[str]] = {
    "summary": {"summarize", "summarise", "summary", "overview", "recap",
                "rundown", "gist", "synopsis", "digest", "outline", "essentials"},
    "compare": {"compare", "contrast", "difference", "differences", "differ",
                "versus", "alike", "dissimilar"},
    "count": {"few", "couple", "several", "handful", "some", "quantity",
              "number", "fistful", "smattering"},
    "list": {"facts", "things", "points", "items", "examples", "reasons"},
    "timeline": {"timeline", "chronology", "chronological", "history"},
    "simple": {"simple", "simply", "plain", "easy", "easier", "basic",
               "beginner", "clear"},
    "ack": {"thanks", "thank", "appreciate", "appreciated", "grateful",
            "gratitude", "cheers", "helpful"},
    "provenance": {"claim", "basis", "source", "evidence", "say", "said",
                   "assert", "assertion", "know"},
    "definitional": {"mean", "meaning", "define", "definition"},
}

STOPWORDS = {"a", "an", "the", "of", "to", "for", "in", "on", "and", "or",
             "is", "are", "was", "be", "this", "that", "these", "those", "it",
             "its", "you", "your", "me", "my", "i", "we", "what", "whats",
             "how", "why", "would", "could", "should", "do", "does", "did",
             "give", "get", "please", "about", "with", "from", "so", "not"}

_connection: sqlite3.Connection | None = None
_projection_cache: dict[str, frozenset[str]] = {}


def _db() -> sqlite3.Connection | None:
    global _connection
    if _connection is None and CONCEPTNET_DB.exists():
        _connection = sqlite3.connect(f"file:{CONCEPTNET_DB}?mode=ro", uri=True)
    return _connection


def project_token(token: str) -> frozenset[str]:
    """Marker classes reachable from token via 1 admitted ConceptNet hop."""
    cached = _projection_cache.get(token)
    if cached is not None:
        return cached
    classes: set[str] = set()
    connection = _db()
    if connection is not None:
        placeholders = ",".join("?" for _ in PROJECTION_RELS)
        rows = connection.execute(
            f"SELECT start, end FROM edge WHERE (start=? OR end=?) "
            f"AND rel IN ({placeholders}) ORDER BY weight DESC LIMIT 24",
            (token, token, *PROJECTION_RELS)).fetchall()
        neighbors: set[str] = set()
        for start, end in rows:
            other = end if start == token else start
            neighbors.update(other.split())  # multiword ends contribute words
        for name, seeds in MARKER_CLASSES.items():
            if neighbors & seeds:
                classes.add(name)
    result = frozenset(classes)
    _projection_cache[token] = result
    return result


def _terms(text: str) -> list[str]:
    return [w.strip("'-") for w in re.findall(r"[a-z0-9][a-z0-9'-]*", text.casefold())]


def features(text: str) -> dict[str, float]:
    base = features_v1(text)
    lower = " ".join(text.casefold().strip().split())
    tokens = _terms(lower)
    token_set = set(tokens)
    first = tokens[0] if tokens else ""

    hits: set[str] = set()
    for name, seeds in MARKER_CLASSES.items():
        if token_set & seeds:
            hits.add(name)
    for token in token_set:
        if len(token) >= 3 and token not in STOPWORDS:
            hits.update(project_token(token))

    if "summary" in hits or "in a nutshell" in lower or "boil" in lower:
        base["summary_token"] = 1.0
    if ("compare" in hits or "not the same" in lower or "not alike" in lower
            or "in common" in lower):
        base["compare_token"] = 1.0
    if "count" in hits and "list" in hits:
        base["list_count"] = 1.0
    if ("timeline" in hits or "over the years" in lower
            or "through the years" in lower or "through time" in lower):
        base["timeline_token"] = 1.0
    if "simple" in hits or "plain words" in lower:
        base["simple_token"] = 1.0
    if len(tokens) <= 6 and "ack" in hits and not lower.endswith("?"):
        base["ack_marker"] = 1.0
    if (first in ("why", "how") and "you" in token_set and "provenance" in hits
            and len(tokens) <= 7):
        base["provenance_phrase"] = 1.0
    if lower.endswith("?") and tokens and tokens[-1] == "is":
        base["definition_lead"] = 1.0  # "what would you say a glacier is?"
    if "definitional" in hits and lower.endswith("?") and "what" in token_set:
        base["definition_lead"] = 1.0
    return base


PROTOTYPES: dict[str, tuple[str, ...]] = {
    family: tuple(PROTOTYPES_V1.get(family, ())) + tuple(EXTRA_PROTOTYPES.get(family, ()))
    for family in set(PROTOTYPES_V1) | set(EXTRA_PROTOTYPES)
}

_prototype_states: dict[str, np.ndarray] = {}


def prototype(family: str) -> np.ndarray:
    state = _prototype_states.get(family)
    if state is None:
        phrases = PROTOTYPES.get(family, ())
        stacked = np.sum([encode(phrase) for phrase in phrases], axis=0)
        norm = np.linalg.norm(stacked)
        state = stacked / norm if norm else stacked
        _prototype_states[family] = state
    return state


def resonance(bundle: np.ndarray, family: str) -> float:
    state = prototype(family)
    if not np.any(state):
        return 0.0
    return float(np.real(np.vdot(state, bundle)))


def arbitrate(text: str) -> ArbitrationRecord:
    bundle = encode(text)
    evidence = features(text)
    candidates: list[InterpretationCandidate] = []
    for family in M_FAMILIES:
        if family == "clarification":
            continue
        weights = FEATURE_WEIGHTS.get(family, {})
        typed = {name: weights[name] * evidence[name]
                 for name in weights if evidence.get(name)}
        geometric = resonance(bundle, family)
        bid = 1.4 * geometric + sum(typed.values())
        candidates.append(InterpretationCandidate(family, geometric, typed, bid))
    candidates.sort(key=lambda value: (-value.bid, value.family))
    top, second = candidates[0], candidates[1]
    margin = top.bid - second.bid
    floor_applied = top.bid < CLARIFICATION_FLOOR or margin < MARGIN_TAU
    winner = "clarification" if floor_applied else top.family
    runner_up = top.family if floor_applied else second.family
    return ArbitrationRecord(
        utterance_sha256=hashlib.sha256(text.encode()).hexdigest(),
        candidates=tuple(candidates),
        winner=winner,
        runner_up=runner_up,
        margin=margin,
        clarification_floor_applied=floor_applied,
    )


__all__ = ["arbitrate", "features", "path_family", "project_token",
           "prototype", "resonance", "M_FAMILIES"]
