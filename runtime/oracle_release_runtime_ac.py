#!/usr/bin/env python3
"""Runtime AC — explain-simply picks the identifying sentence (additive over AB).

Iteration 6 diagnosis. `_definitional_score` returns 0 for every sentence on a
biographical page (it keys on copular definition patterns that proper-noun prose
does not use), so selection fell through to the tiebreak `-len(words)` — the
SHORTEST sentence wins. That systematically chose trivia and fragments over the
sentence that identifies the subject:

    "Explain Paco Gento simply."        -> "He played for Spain national team."
    "Explain Arthur C. Clarke simply."  -> "He also wrote many short stories."
    "Explain Bernard Montgomery simply."-> "Later, in World War II."   (a fragment)

In encyclopedic prose the FIRST sentence of a page is by convention the one that
says what the subject is. So on a score tie the tiebreak now prefers EARLIER
position rather than fewer words, and sentences that cannot stand alone (no
finite verb, or opening mid-parenthetical) are skipped. Brevity is still
preferred among sentences that actually define.

Note on the metric that found this: `explain_simply` on-topic looked like the
same false-drift artifact that `list` produced, but it was not. For an
"explain X" question, mentioning X is not a proxy for relevance — it IS the
requirement, because an explanation that never identifies its subject has not
explained it."""

from __future__ import annotations

import re
import time

from oracle_release_runtime_ab import OracleReleaseRuntimeAB
from oracle_release_runtime_m import SIMPLY, _definitional_score
from stage5m13e8_relevance_gate_v1 import gate_bundle

_WORD = chr(92) + "b"          # backslash-b built at runtime; heredocs eat the literal
FINITE_VERB = re.compile(_WORD + r"(is|are|was|were|has|have|had|does|did|can|"
                         r"could|will|would|became|becomes|plays|played|wrote|"
                         r"made|makes|lives|lived|died|won|led|serves|served)" + _WORD, re.I)
OPENS_MID = re.compile(r"^\s*(?:[a-z]|\d{1,4}\s*[)\]]|later,|however,|also,|then,)", re.I)


def _standalone(sentence: str) -> bool:
    """Can this sentence stand alone as an identification?"""
    text = str(sentence or "").strip()
    if len(text.split()) < 4 or OPENS_MID.match(text):
        return False
    return bool(FINITE_VERB.search(text))


class OracleReleaseRuntimeAC(OracleReleaseRuntimeAB):
    def _simply_turn(self, text: str, session_id: str) -> dict | None:   # override M
        match = SIMPLY.match(text.strip())
        if not match:
            return None
        topic = (match.group("t") or match.group("t2") or "").strip()
        if not topic:
            return None
        bundle = self._bundle(topic, n=8)
        admitted, _ = gate_bundle(topic, bundle)
        gloss = self._gloss(topic)
        if not admitted and not gloss:
            return {"status": "withheld", "path": "capability:explain_simply",
                    "response": f"No provenance-admitted material on {topic} is available to explain.",
                    "provenance": {"kind": "simple_register", "topic": topic}}
        parts: list[str] = []
        premises: list[str] = []
        if admitted:
            order = {c["claim_id"]: i for i, c in enumerate(bundle)}
            standalone = [c for c in admitted if _standalone(c.get("sentence"))]
            pool = standalone or admitted
            short_defs = [c for c in pool
                          if len(c["sentence"].split()) <= 30
                          and _definitional_score(topic, c["sentence"]) >= 6]
            if short_defs:
                lead = max(short_defs, key=lambda c: (_definitional_score(topic, c["sentence"]),
                                                      -len(c["sentence"].split())))
            else:
                # No scored definition (typical of proper-noun pages): take the
                # page's own opening sentence, which is the identifying one.
                lead = min(pool, key=lambda c: order.get(c["claim_id"], 10_000))
            parts.append(f"{lead['sentence']} [{lead['claim_id']}]")
            premises.append(lead["claim_id"])
        if gloss:
            parts.append(f"The dictionary sense: {gloss}. [wiktionary:{topic.lower()}:sense1]")
            premises.append(f"wiktionary:{topic.lower()}")
        return {"status": "answered", "path": "capability:explain_simply",
                "response": "In simple terms: " + " ".join(parts),
                "provenance": {"kind": "simple_register", "topic": topic, "premises": premises}}

    def _timeline_turn(self, text: str, session_id: str) -> dict | None:   # override J
        result = super()._timeline_turn(text, session_id)
        if not result or result.get("status") != "answered":
            return result
        body = str(result.get("response", ""))
        distinct = {y for y in year_tokens(body)}
        if len(distinct) >= 2:
            return result
        topic_note = "the admitted material yields fewer than two distinct dates"
        return {"status": "withheld", "path": "capability:timeline",
                "response": f"A timeline needs at least two distinct dated statements; "
                            f"{topic_note}. I will not present a measurement as a date.",
                "provenance": {"kind": "temporal_projection",
                               "result": "insufficient_distinct_dates"}}

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        result = None
        try:
            result = self._simply_turn(" ".join(text.strip().split()), session_id)
        except Exception:  # noqa: BLE001
            result = None
        if result is not None:
            result["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
            result["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
            return result
        return super().chat(text, session_id)


# ── timeline: a year token is not the same thing as a number ────────────────
# The route treated any 4-digit token as a date, so "One megasecond contains
# 1000 kiloseconds" was rendered as the year 1000, and a page with one date
# repeated produced a single-point "timeline". A date must not be a measurement,
# and a timeline needs at least two DISTINCT years.
UNIT_AFTER = re.compile(
    r"^(?:kilo|mega|giga|milli|micro|nano)?"
    r"(?:second|meter|metre|gram|litre|liter|byte|watt|hertz|mile|foot|feet|inch|"
    r"year|month|week|day|hour|minute|people|person|km|kg|cm|mm|ft|lb)s?$", re.I)


def year_tokens(sentence: str) -> list[int]:
    """4-digit years in a sentence, excluding numbers that are measurements."""
    text = str(sentence or "")
    out: list[int] = []
    for match in re.finditer(r"(1[0-9]{3}|20[0-2][0-9])", text):
        tail = text[match.end():].lstrip()
        next_word = tail.split()[0].strip(".,;:)") if tail.split() else ""
        if next_word and UNIT_AFTER.match(next_word):
            continue          # "1000 kiloseconds" is a quantity, not a date
        out.append(int(match.group(1)))
    return out
