#!/usr/bin/env python3
"""M21 slice 1b — robust transitive-kind reasoner (additive successor to v1).

Two robustness upgrades over v1, both root-caused from the v1 one-shot's
false abstentions and preserved trap:

1. SENSE-DOMINANCE PRUNING replaces the blunt in-degree gate as the primary
   guard. A sense-crossing chain (robin[bird] -> thrush -> candidiasis[disease])
   always enters through a MINORITY-sense edge: robin's dominant kind is "bird"
   (weight 6.3); "thrush" is a weak 1.0 edge. So we only follow IsA edges whose
   weight is >= max(1.0, DOMINANCE_FRAC x the node's strongest IsA weight). This
   targets the actual trap mechanism instead of guessing at the terminus, and it
   RECOVERS true chains the in-degree gate wrongly blocked (sparrow -> bird ->
   vertebrate: vertebrate's in-degree 27 fell just under v1's threshold 30).

2. A low category FLOOR (in-degree >= 12) remains as belt-and-suspenders so a
   derivation never runs toward a tiny leaf concept, but it no longer does the
   sense work — the dominance prune does.

Same target-anchored BFS (shortest chain first), depth<=3, provenance chain
returned so the answer stays the shown derivation. No neural network."""

from __future__ import annotations

from collections import deque
from typing import Any

MAX_DEPTH = 3
FRONTIER_CAP = 400
EDGE_CAP = 10
MIN_WEIGHT = 1.0
DOMINANCE_FRAC = 0.25          # prune edges weaker than this x the node's top IsA edge
CATEGORY_MIN_INDEGREE = 12     # terminus must be a real (if small) category


def _norm(concept: str) -> str:
    c = concept.strip().lower()
    if c.endswith("s") and not c.endswith("ss") and len(c) > 3:
        return c[:-1]
    return c


def category_indegree(adapter: Any, y: str) -> int:
    best = 0
    for form in dict.fromkeys([y.strip().lower(), _norm(y)]):
        row = adapter.connection.execute(
            "SELECT COUNT(*) FROM edge WHERE end=? AND rel='IsA'", (form,)).fetchone()
        best = max(best, int(row[0]) if row else 0)
    return best


def direct_isa(adapter: Any, x: str, y: str) -> dict | None:
    xn, yn = _norm(x), _norm(y)
    for concept in dict.fromkeys([x.strip().lower(), xn]):
        for edge in adapter.edges(concept, "IsA", limit=24):
            end = edge["end"].strip().lower()
            if end == y.strip().lower() or _norm(end) == yn:
                return edge
    return None


def _dominant_edges(adapter: Any, node: str) -> list[dict]:
    """IsA edges of node, minority-sense edges pruned by relative weight."""
    edges = adapter.edges(node, "IsA", limit=EDGE_CAP)
    if not edges:
        return []
    top = max(e["weight"] for e in edges)
    threshold = max(MIN_WEIGHT, DOMINANCE_FRAC * top)
    return [e for e in edges if e["weight"] >= threshold]


def chain_isa(adapter: Any, x: str, y: str, *, max_depth: int = MAX_DEPTH) -> list[dict] | None:
    """Shortest dominant-sense chain of admitted IsA edges from x to y, or None."""
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
        for edge in _dominant_edges(adapter, node):
            end = edge["end"].strip().lower()
            new_path = path + [edge]
            if (end in targets or _norm(end) in targets) and len(new_path) >= 2:
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
