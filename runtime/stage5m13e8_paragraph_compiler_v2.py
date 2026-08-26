#!/usr/bin/env python3
"""H2 slice 2 — paragraph compiler with ENGINE-DERIVED ANALYSIS moves.

Additive successor to stage5m13e8_paragraph_compiler_v1 (unedited). Adds the
second provenance type: a DERIVED sentence carries {rule, premises} instead of
a page address, and the recover law now also checks that every premise of a
derived move was cited EARLIER in the same paragraph — analysis may only
comment on evidence the reader has already been shown.

Rules this slice (deterministic, zero-model):
  year_precedence   -- two premise claims with extractable years ->
                       "the A record (YYYY) precedes the B record (YYYY) by N years"
  count_aggregation -- k of the n cited statements mention TERM
"""

from __future__ import annotations

import re

from stage5m13e8_paragraph_compiler_v1 import (
    ParagraphProgram, compile_paragraph, recover_program,
)

YEAR = re.compile(r"\b(1[0-9]{3}|20[0-2][0-9])\b")


def extract_year(sentence: str) -> int | None:
    match = YEAR.search(sentence)
    return int(match.group(1)) if match else None


def compile_paragraph_v2(topic: str, claims: list[dict], *, evidence: int = 3,
                         next_topic: str | None = None,
                         aggregation_term: str | None = None) -> tuple[str, ParagraphProgram]:
    paragraph, program = compile_paragraph(topic, claims, evidence=evidence, next_topic=None)
    sentences = [paragraph]
    cited = [m for m in program.moves if m["claim_id"]]

    # ANALYSIS: year precedence over cited claims only
    dated = [(m, extract_year(m["text"])) for m in cited]
    dated = [(m, y) for m, y in dated if y is not None]
    if len(dated) >= 2:
        (first_move, first_year), (second_move, second_year) = \
            sorted(dated, key=lambda pair: pair[1])[0], sorted(dated, key=lambda pair: pair[1])[-1]
        if first_year != second_year:
            span = second_year - first_year
            text = (f"Between the cited records, the earliest dated statement ({first_year}) "
                    f"precedes the latest ({second_year}) by {span} years.")
            premises = [first_move["claim_id"], second_move["claim_id"]]
            sentences.append(f"{text} [derived:year_precedence<-{','.join(p[:20] for p in premises)}]")
            program.moves.append({"move": "ANALYSIS", "claim_id": None,
                                  "rule": "year_precedence", "premises": premises,
                                  "text": text})

    # ANALYSIS: count aggregation over cited claims only
    if aggregation_term:
        term = aggregation_term.lower()
        hits = [m for m in cited if term in m["text"].lower()]
        if hits:
            verb = "mentions" if len(hits) == 1 else "mention"
            text = (f"Of the {len(cited)} statements cited here, {len(hits)} "
                    f"{verb} {aggregation_term}.")
            premises = [m["claim_id"] for m in cited]
            sentences.append(f"{text} [derived:count_aggregation<-{len(premises)}premises]")
            program.moves.append({"move": "ANALYSIS", "claim_id": None,
                                  "rule": "count_aggregation", "premises": premises,
                                  "text": text})

    if next_topic:
        sentences.append(f"The record turns next to {next_topic}.")
        program.moves.append({"move": "BRIDGE", "claim_id": None, "page": None,
                              "text": next_topic})
    return " ".join(sentences), program


def recover_program_v2(paragraph: str, program: ParagraphProgram) -> bool:
    if not recover_program(paragraph, program):
        return False
    for move in program.moves:
        if move.get("move") != "ANALYSIS":
            continue
        marker = f"[derived:{move['rule']}"
        position = paragraph.find(marker)
        if position < 0 or move["text"] not in paragraph:
            return False
        before = paragraph[:position]
        # every premise must have been cited earlier in the paragraph
        for premise in move["premises"]:
            if premise[:20] not in before:
                return False
    return True
