#!/usr/bin/env python3
"""M17b3 — release arbiter v3 (additive successor to v2; v1/v2 untouched).

Four repairs from the sealed M17b2 one-shot (see
stage5m17b2_oneshot_adjudication_v1.md):

1. SEED-EXCLUSIVITY — a token that is itself a seed of one marker class never
   projects into another class ("define" is a definitional seed; its
   ConceptNet neighborhood may not vote for summarize). The K161
   wrong-domain-monopoly bound, applied to projection.
2. DEFINITIONAL CUE — "define"/"definition" token + question fires the
   definitional lead independent of "what".
3. TIMELINE SEEDS widened: beginning/beginnings/origins/start/unfold.
4. PROJECTION HYGIENE — hyper-common polysemous tokens are never projected
   (like/now/get/...), and projection edges require weight >= 2.0.

Bid law, floor, tau unchanged. No LM, no transformer, no gradient."""

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
    features as features_v1,
    path_family,
)
from stage5m17_release_arbiter_v2 import (
    CONCEPTNET_DB,
    PROJECTION_RELS,
    PROTOTYPES,
    MARKER_CLASSES as MARKER_CLASSES_V2,
    STOPWORDS,
)

MARKER_CLASSES: dict[str, set[str]] = {name: set(seeds)
                                       for name, seeds in MARKER_CLASSES_V2.items()}
MARKER_CLASSES["timeline"] |= {"beginning", "beginnings", "origins", "start",
                               "started", "unfold", "unfolded"}
ALL_SEEDS: set[str] = set().union(*MARKER_CLASSES.values())

PROJECTION_STOP = {
    "like", "now", "get", "got", "put", "keep", "kept", "make", "made",
    "take", "took", "way", "ways", "kind", "kinds", "thing", "things",
    "going", "come", "came", "look", "want", "need", "see", "sure", "well",
    "right", "life", "back", "off", "over", "trace", "just", "really",
}

_connection: sqlite3.Connection | None = None
_projection_cache: dict[str, frozenset[str]] = {}


def _db() -> sqlite3.Connection | None:
    global _connection
    if _connection is None and CONCEPTNET_DB.exists():
        _connection = sqlite3.connect(f"file:{CONCEPTNET_DB}?mode=ro", uri=True)
    return _connection


def project_token(token: str) -> frozenset[str]:
    """Marker classes reachable via 1 admitted ConceptNet hop (weight>=2.0).
    Seed tokens and hyper-common tokens never project (rules 1 and 4)."""
    if token in ALL_SEEDS or token in PROJECTION_STOP:
        return frozenset()
    cached = _projection_cache.get(token)
    if cached is not None:
        return cached
    classes: set[str] = set()
    connection = _db()
    if connection is not None:
        placeholders = ",".join("?" for _ in PROJECTION_RELS)
        rows = connection.execute(
            f"SELECT start, end FROM edge WHERE (start=? OR end=?) "
            f"AND rel IN ({placeholders}) AND weight >= 2.0 "
            f"ORDER BY weight DESC LIMIT 24",
            (token, token, *PROJECTION_RELS)).fetchall()
        neighbors: set[str] = set()
        for start, end in rows:
            other = end if start == token else start
            neighbors.update(other.split())
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
        base["definition_lead"] = 1.0
    if "definitional" in hits and lower.endswith("?") and "what" in token_set:
        base["definition_lead"] = 1.0
    # repair 2: define/definition + question is definitional regardless of "what"
    if ({"define", "definition", "defined"} & token_set) and lower.endswith("?"):
        base["definition_lead"] = 1.0
        base["summary_token"] = 0.0
    return base


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
