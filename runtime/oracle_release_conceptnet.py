#!/usr/bin/env python3
"""R1 — ConceptNet commonsense adapter for the release runtime.

Typed edge retrieval over the sealed M13e5 ConceptNet specialist
(m13e5_conceptnet_build_a_v1, index sha 5e28406c...), rendered with provenance.
Zero-model: SQL + deterministic rendering only. Speech uses ConceptNet's own
crowd-authored surface_text where present (attributed), otherwise a typed
relation template. Every released line carries its edge provenance; empty
retrieval is an explicit abstention, never a guess.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

PHASE = Path(__file__).resolve().parents[1] / "fable-content" / "oracle-m-series-2026-08-15"
DEFAULT_BUILD = PHASE / "m13e5_conceptnet_build_a_v1" / "conceptnet_specialist.sqlite3"

# Relation -> (question forms it answers, deterministic template)
RELATION_TEMPLATES: dict[str, str] = {
    "IsA": "{start} is a kind of {end}",
    "PartOf": "{start} is part of {end}",
    "HasA": "{start} has {end}",
    "UsedFor": "{start} is used for {end}",
    "CapableOf": "{start} can {end}",
    "AtLocation": "{start} is typically found at {end}",
    "Causes": "{start} causes {end}",
    "HasSubevent": "{start} involves {end}",
    "HasPrerequisite": "{start} requires {end}",
    "MotivatedByGoal": "{start} is motivated by {end}",
    "Desires": "{start} desires {end}",
    "MadeOf": "{start} is made of {end}",
    "ReceivesAction": "{start} can be {end}",
    "HasProperty": "{start} is {end}",
    "Synonym": "{start} is a synonym of {end}",
    "Antonym": "{start} is an antonym of {end}",
    "DistinctFrom": "{start} is distinct from {end}",
    "SimilarTo": "{start} is similar to {end}",
    "RelatedTo": "{start} is related to {end}",
}

QUESTION_ROUTES: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"^what is (?:a |an |the )?(.+?) used for\??$", re.I), ["UsedFor"]),
    (re.compile(r"^what can (?:a |an |the )?(.+?) do\??$", re.I), ["CapableOf"]),
    (re.compile(r"^where (?:would you |do you |can you )?find (?:a |an |the )?(.+?)\??$", re.I), ["AtLocation"]),
    (re.compile(r"^where is (?:a |an |the )?(.+?) (?:usually |typically )?found\??$", re.I), ["AtLocation"]),
    (re.compile(r"^what (?:does|do) (?:a |an |the )?(.+?) have\??$", re.I), ["HasA"]),
    (re.compile(r"^what is (?:a |an |the )?(.+?) made of\??$", re.I), ["MadeOf"]),
    (re.compile(r"^what causes (?:a |an |the )?(.+?)\??$", re.I), ["Causes:end"]),
    (re.compile(r"^what (?:does|do) (?:a |an |the )?(.+?) cause\??$", re.I), ["Causes"]),
    (re.compile(r"^what kind of thing is (?:a |an |the )?(.+?)\??$", re.I), ["IsA"]),
    (re.compile(r"^what (?:is|are) (?:a |an |the )?(.+?) (?:a )?(?:kind|type|sort) of\??$", re.I), ["IsA"]),
    (re.compile(r"^what is (?:a |an |the )?(.+?) part of\??$", re.I), ["PartOf"]),
    (re.compile(r"^what (?:is|are) (?:the )?parts? of (?:a |an |the )?(.+?)\??$", re.I), ["PartOf:end", "HasA"]),
    (re.compile(r"^what do(?:es)? (?:a |an |the )?(.+?) require\??$", re.I), ["HasPrerequisite"]),
    (re.compile(r"^what is (?:a |an |the )?(.+?) similar to\??$", re.I), ["SimilarTo", "Synonym"]),
    (re.compile(r"^what is (?:the )?opposite of (?:a |an |the )?(.+?)\??$", re.I), ["Antonym"]),
]

_SURFACE_BRACKETS = re.compile(r"\[\[|\]\]")


class ConceptNetAdapter:
    def __init__(self, build_path: Path | str = DEFAULT_BUILD):
        build_path = Path(build_path)
        if not build_path.is_file():
            raise FileNotFoundError(str(build_path))
        uri = build_path.resolve().as_uri() + "?mode=ro&immutable=1"
        self.connection = sqlite3.connect(uri, uri=True)

    # ── retrieval ────────────────────────────────────────────────────────
    def edges(self, concept: str, relation: str, *, reverse: bool = False,
              limit: int = 6) -> list[dict[str, Any]]:
        concept = concept.strip().lower()
        column, other = ("end", "start") if reverse else ("start", "end")
        rows = self.connection.execute(
            f"SELECT rel, start, end, weight, surface_text, dataset FROM edge "
            f"WHERE {column}=? AND rel=? ORDER BY weight DESC, start, end LIMIT ?",
            (concept, relation, limit)).fetchall()
        return [{"rel": r[0], "start": r[1], "end": r[2], "weight": r[3],
                 "surface_text": r[4], "dataset": r[5],
                 "provenance": f"conceptnet57:{r[0]}:{r[1]}->{r[2]}"} for r in rows]

    def neighborhood(self, concept: str, *, limit_per_relation: int = 4) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for relation in RELATION_TEMPLATES:
            if relation == "RelatedTo":
                continue  # too diffuse for a summary; available via edges()
            found = self.edges(concept, relation, limit=limit_per_relation)
            if found:
                out[relation] = found
        return out

    # ── rendering ────────────────────────────────────────────────────────
    @staticmethod
    def render_edge(edge: dict[str, Any]) -> str:
        surface = (edge.get("surface_text") or "").strip()
        if surface:
            text = _SURFACE_BRACKETS.sub("", surface).lstrip("*").strip()
            if text:
                return text[0].upper() + text[1:].rstrip(".") + "."
        template = RELATION_TEMPLATES.get(edge["rel"], "{start} relates to {end}")
        text = template.format(start=edge["start"], end=edge["end"])
        return text[0].upper() + text[1:] + "."

    def answer(self, question: str) -> dict[str, Any]:
        """Route a commonsense question form; abstain explicitly otherwise."""
        text = " ".join(question.strip().split())
        for pattern, relations in QUESTION_ROUTES:
            match = pattern.match(text)
            if not match:
                continue
            concept = match.group(1).strip().lower()
            collected: list[dict[str, Any]] = []
            for spec in relations:
                relation, _, direction = spec.partition(":")
                collected.extend(self.edges(concept, relation, reverse=(direction == "end")))
            if not collected:
                return {"status": "withheld", "operation": "conceptnet_no_admitted_edges",
                        "concept": concept,
                        "response": f"The commonsense index has no admitted edges answering that about {concept}.",
                        "claims": []}
            seen: set[str] = set()
            lines = []
            claims = []
            for edge in collected:
                rendered = self.render_edge(edge)
                if rendered in seen:
                    continue
                seen.add(rendered)
                lines.append(rendered)
                claims.append({"provenance": edge["provenance"], "weight": edge["weight"],
                               "dataset": edge["dataset"]})
                if len(lines) >= 5:
                    break
            return {"status": "answered", "operation": "conceptnet_commonsense",
                    "concept": concept, "response": " ".join(lines), "claims": claims}
        return {"status": "unrouted", "operation": "conceptnet_form_not_registered",
                "response": "", "claims": []}
