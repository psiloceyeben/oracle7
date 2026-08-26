#!/usr/bin/env python3
"""M21 — implied-knowledge engine, slice 1: transitive kind (IsA) chaining.

The Oracle answers only when a single admitted claim matches, which is why
open-domain coverage is ~1%. But admitted claims IMPLY others: if the record
holds "a robin is a bird" and "a bird is an animal", it implicitly holds "a
robin is an animal" — it just never computes it. This module computes exactly
that closure, over the transitive IsA relation of the admitted ConceptNet
corpus, and returns the FULL premise chain so a derived answer stays auditable:
the answer is the shown chain, not a bare assertion.

Target-anchored: given (X, Y) it searches for a shortest chain X -> ... -> Y,
breadth-first (shortest path first), each hop a real admitted edge. It never
enumerates a closure and asserts from it; it only confirms the specific link
the user asked about, and shows the steps. Bounded: depth<=MAX_DEPTH, a frontier
cap, a per-node edge cap; deterministic (edges are weight-then-lexical ordered).

Known limitation, recorded for the next slice: chains can cross a word-sense
boundary (robin->thrush[bird]->candidiasis[disease]) because ConceptNet
conflates senses. This slice shows the chain rather than hiding it; sense-
consistent chaining is the successor (it reuses the M17c evidence-conditioned
sense machinery). No neural network, no gradient; pure graph search."""

from __future__ import annotations

from collections import deque
from typing import Any

MAX_DEPTH = 3
FRONTIER_CAP = 400
EDGE_CAP = 8
MIN_WEIGHT = 1.0
# A transitive derivation "X is a Y" only fires when Y is an ESTABLISHED
# category — many admitted claims call something a Y. This is the reasoning-
# level guard against sense-crossing chains (robin->thrush[bird]->candidiasis
# [disease]): the disease terminus has almost no incoming IsA edges, a real
# category has hundreds. Direct single edges are unaffected (they are citations,
# not derivations). Calibrated against the measured gap: traps <=13, the
# lowest kept real category 68.
CATEGORY_MIN_INDEGREE = 30


def _norm(concept: str) -> str:
    c = concept.strip().lower()
    # a bare trailing plural is the common surface form ("are robins animals")
    if c.endswith("s") and not c.endswith("ss") and len(c) > 3:
        return c[:-1]
    return c


def direct_isa(adapter: Any, x: str, y: str) -> dict | None:
    """A single admitted IsA(x, y) edge, if present — a citation, not a chain."""
    xn, yn = _norm(x), _norm(y)
    for concept in (x.strip().lower(), xn):
        for edge in adapter.edges(concept, "IsA", limit=24):
            end = edge["end"].strip().lower()
            if end == y.strip().lower() or _norm(end) == yn:
                return edge
    return None


def category_indegree(adapter: Any, y: str) -> int:
    """How many admitted IsA edges point AT y — how established a category it is.
    Read-only against the same corpus; max over the surface and normalized form."""
    best = 0
    for form in dict.fromkeys([y.strip().lower(), _norm(y)]):
        row = adapter.connection.execute(
            "SELECT COUNT(*) FROM edge WHERE end=? AND rel='IsA'", (form,)).fetchone()
        best = max(best, int(row[0]) if row else 0)
    return best


def chain_isa(adapter: Any, x: str, y: str, *, max_depth: int = MAX_DEPTH) -> list[dict] | None:
    """Shortest chain of admitted IsA edges from x to y, or None.

    BFS so the returned path is the fewest hops; the per-node edges are already
    weight-descending, so among equal-length paths the strongest dominant-sense
    links are explored first. Never returns a zero-hop (direct) path — that is
    a citation, handled by direct_isa(). A chain is only returned when y is an
    established category (guard against sense-crossing termini)."""
    if category_indegree(adapter, y) < CATEGORY_MIN_INDEGREE:
        return None
    targets = {y.strip().lower(), _norm(y)}
    starts = [x.strip().lower(), _norm(x)]
    visited: set[str] = set(starts)
    queue: deque[tuple[str, list[dict]]] = deque((s, []) for s in dict.fromkeys(starts))
    expanded = 0
    while queue and expanded < FRONTIER_CAP:
        node, path = queue.popleft()
        if len(path) >= max_depth:
            continue
        expanded += 1
        for edge in adapter.edges(node, "IsA", limit=EDGE_CAP):
            if edge["weight"] < MIN_WEIGHT:
                continue
            end = edge["end"].strip().lower()
            new_path = path + [edge]
            if end in targets or _norm(end) in targets:
                if len(new_path) >= 2:  # >=2 hops = a genuine derivation
                    return new_path
                # 1-hop match here would be a direct edge; let direct_isa own it
                continue
            if end not in visited:
                visited.add(end)
                queue.append((end, new_path))
    return None


def render_chain(adapter: Any, path: list[dict]) -> str:
    """Human-readable step list: 'a robin is a bird; a bird is an animal'."""
    steps = []
    for edge in path:
        rendered = adapter.render_edge(edge).rstrip(".")
        steps.append(rendered[0].lower() + rendered[1:])
    return "; ".join(steps)
