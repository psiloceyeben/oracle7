#!/usr/bin/env python3
"""H2 slice 1 — paragraph-program compiler (development evidence).

Compiles a claim bundle (provenance-addressed sentences from one page/topic)
through a typed paragraph frame into a natural-register paragraph, and keeps
the program: every emitted sentence is a MOVE with its claim address, so
Program(paragraph) is recoverable from the output by construction.

Moves implemented this slice: TOPIC (most definitional claim, attributed),
EVIDENCE (further claims, rotating natural attribution), BRIDGE (registered
connective to a named next topic). ANALYSIS moves are deliberately absent
until they can be engine-derived with premises — a templated analysis
sentence would violate the derived-provenance law.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from stage5m13e5_frame_transform_v1 import classify_clause_initial_it

NATURAL_FORMS = [
    "According to {page}, {claim}",
    "The page for {page} records: {claim}",
    "{page} notes that {claim}",
    "As {page} has it, {claim}",
    "From {page}: {claim}",
]


@dataclass
class ParagraphProgram:
    topic: str
    moves: list[dict] = field(default_factory=list)   # {move, claim_id, page, text}

    def public(self) -> dict:
        return {"topic": self.topic, "moves": self.moves}


def _definitional_score(topic: str, sentence: str) -> int:
    low = sentence.lower()
    t = topic.lower()
    score = 0
    # a genuine definition: "(A|An|The)? TOPIC is a/an ..." near the start
    if re.match(rf"^(?:a|an|the)?\s*{re.escape(t)}\b[^.]{{0,40}}?\bis (?:a|an)\b", low):
        score += 6
    if low.startswith(t):
        score += 2
    if re.search(r"\bis (?:a|an|the)\b", low):
        score += 1
    if t in low:
        score += 1
    return score


def compile_paragraph(topic: str, claims: list[dict], *, evidence: int = 3,
                      next_topic: str | None = None) -> tuple[str, ParagraphProgram]:
    """claims: [{claim_id, page, sentence}] — provenance-addressed inputs only."""
    if not claims:
        raise ValueError("empty claim bundle")
    program = ParagraphProgram(topic=topic)
    ranked = sorted(claims, key=lambda c: -_definitional_score(topic, c["sentence"]))
    lead, rest = ranked[0], ranked[1:1 + evidence]
    sentences = []
    # TOPIC move: attributed definitional lead (grounded referential `it` only —
    # the P068 classifier guards substitution here exactly as in the transformer).
    lead_text = lead["sentence"]
    if classify_clause_initial_it(lead_text) == "referential":
        lead_text = lead["page"] + lead_text[2:]
    sentences.append(f"According to {lead['page']}, {lead_text} [{lead['claim_id']}]")
    program.moves.append({"move": "TOPIC", "claim_id": lead["claim_id"],
                          "page": lead["page"], "text": lead_text})
    # EVIDENCE moves: rotating natural attribution
    for index, claim in enumerate(rest):
        form = NATURAL_FORMS[(index + 1) % len(NATURAL_FORMS)]
        rendered = form.format(page=claim["page"], claim=claim["sentence"])
        sentences.append(f"{rendered} [{claim['claim_id']}]")
        program.moves.append({"move": "EVIDENCE", "claim_id": claim["claim_id"],
                              "page": claim["page"], "text": claim["sentence"]})
    # BRIDGE move: registered connective, no factual content, so no address
    if next_topic:
        sentences.append(f"The record turns next to {next_topic}.")
        program.moves.append({"move": "BRIDGE", "claim_id": None,
                              "page": None, "text": next_topic})
    return " ".join(sentences), program


def recover_program(paragraph: str, program: ParagraphProgram) -> bool:
    """Round-trip law at paragraph scale: every addressed move's claim text and
    address must be recoverable from the emitted surface, in move order."""
    cursor = 0
    for move in program.moves:
        if move["claim_id"] is None:
            continue
        address = f"[{move['claim_id']}]"
        position = paragraph.find(address, cursor)
        if position < 0 or move["text"] not in paragraph[cursor:position]:
            return False
        cursor = position
    return True
