#!/usr/bin/env python3
"""M22 — implied-knowledge, slice 2: transitive CONTAINMENT (part-of).

Generalizes the sealed M21b transitive-kind machinery to a second admitted
relation. The mechanism is identical — target-anchored breadth-first search for
a shortest chain X -> ... -> Y, sense-dominance pruning (only follow edges >=
0.25 x the node's strongest edge of that relation, which is what blocks
sense-crossing chains), a hub floor so a derivation never runs toward a tiny
leaf, and the full premise chain returned so the answer is the shown derivation.

Relation chosen empirically: PartOf is genuinely transitive and clean in the
admitted corpus (piston -> engine -> car; finger -> hand -> body). AtLocation
was measured and REJECTED — too sparse and noisy (Tokyo/California empty; "heart
at location artichoke") to chain honestly. It is not built rather than built
badly. No neural network."""

from __future__ import annotations

from collections import deque
from typing import Any

MAX_DEPTH = 3
FRONTIER_CAP = 400
EDGE_CAP = 10
MIN_WEIGHT = 1.0
DOMINANCE_FRAC = 0.25


def norm(concept: str) -> str:
    c = concept.strip().lower()
    if c.endswith("s") and not c.endswith("ss") and len(c) > 3:
        return c[:-1]
    return c


def hub_indegree(adapter: Any, y: str, relation: str) -> int:
    best = 0
    for form in dict.fromkeys([y.strip().lower(), norm(y)]):
        row = adapter.connection.execute(
            "SELECT COUNT(*) FROM edge WHERE end=? AND rel=?", (form, relation)).fetchone()
        best = max(best, int(row[0]) if row else 0)
    return best


def direct(adapter: Any, x: str, y: str, relation: str) -> dict | None:
    yn = norm(y)
    for concept in dict.fromkeys([x.strip().lower(), norm(x)]):
        for edge in adapter.edges(concept, relation, limit=24):
            end = edge["end"].strip().lower()
            if end == y.strip().lower() or norm(end) == yn:
                return edge
    return None


def _dominant_edges(adapter: Any, node: str, relation: str) -> list[dict]:
    edges = adapter.edges(node, relation, limit=EDGE_CAP)
    if not edges:
        return []
    top = max(e["weight"] for e in edges)
    threshold = max(MIN_WEIGHT, DOMINANCE_FRAC * top)
    return [e for e in edges if e["weight"] >= threshold]


def chain(adapter: Any, x: str, y: str, relation: str, *, floor: int,
          max_depth: int = MAX_DEPTH) -> list[dict] | None:
    """Shortest dominant-sense chain of admitted `relation` edges, x -> y."""
    if hub_indegree(adapter, y, relation) < floor:
        return None
    targets = {y.strip().lower(), norm(y)}
    starts = [x.strip().lower(), norm(x)]
    visited: set[str] = set(starts)
    queue: deque[tuple[str, list[dict]]] = deque((s, []) for s in dict.fromkeys(starts))
    expanded = 0
    while queue and expanded < FRONTIER_CAP:
        node, path = queue.popleft()
        if len(path) >= max_depth:
            continue
        expanded += 1
        for edge in _dominant_edges(adapter, node, relation):
            end = edge["end"].strip().lower()
            new_path = path + [edge]
            if (end in targets or norm(end) in targets) and len(new_path) >= 2:
                return new_path
            if end not in visited:
                visited.add(end)
                queue.append((end, new_path))
    return None


def render_chain(adapter: Any, path: list[dict]) -> str:
    steps = []
    for edge in path:
        rendered = adapter.render_edge(edge).rstrip(".")
        steps.append(rendered[0].lower() + rendered[1:])
    return "; ".join(steps)
