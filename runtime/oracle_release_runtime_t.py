#!/usr/bin/env python3
"""Runtime T — act batch 4: self-description (additive over S).

"Who are you?" / "What is this?" / "Explain who you are and what this is."
had NO route: the regex chain fell to the document tier, which answered in its
own idiom (asking for a Wikipedia page address) — a routing gap, not a
capability failure (live specimen 2026-08-19, Ben-reported). The about act is
a typed pre-dispatch route like the other conversation acts: deictic
self-reference only ("who YOU are", "what THIS is"), so "Who is Napoleon?"
and "What is a volcano?" never match. The response is a curated, honest
self-description; no user text is echoed into it."""

from __future__ import annotations

import re
import time

from oracle_release_runtime_s import OracleReleaseRuntimeS

ABOUT_LEAD = re.compile(r"^(?:explain |tell me |describe )?", re.I)
ABOUT_CUES = (
    "who you are", "who are you", "what you are", "what are you",
    "what this is", "what is this", "what am i looking at",
    "who am i talking to", "what am i talking to", "how do you work",
    "how you work",
)

ABOUT_RESPONSE = (
    "I am the Oracle, a compiler-learning model: a conversational system with "
    "no neural network anywhere in it. My grammar is a compiled inventory of "
    "constructions — authored families plus rules I induced myself from "
    "sentences I failed to parse — and my knowledge is an admitted corpus of "
    "sourced claims; every answer carries a source address, a rule with its "
    "premises, or an honest refusal. Dispatch is arbitrated over letter-level "
    "geometry, so paraphrases reach the same typed operation. I learn from "
    "this conversation too: anything I cannot parse becomes a rule candidate. "
    "Ask me to summarize, compare, list, explain simply, give timelines — or "
    "teach me a document and ask about it."
)


class OracleReleaseRuntimeT(OracleReleaseRuntimeS):
    def _about_turn(self, text: str) -> dict | None:
        normalized = " ".join(text.strip().lower().split()).rstrip(".?!")
        if len(normalized.split()) > 12:
            return None
        remainder = ABOUT_LEAD.sub("", normalized, count=1)
        if not any(cue in remainder for cue in ABOUT_CUES):
            return None
        return {"status": "answered", "path": "act:about",
                "response": ABOUT_RESPONSE,
                "provenance": {"kind": "self_description",
                               "note": "curated architecture statement"}}

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        result = None
        try:
            result = self._about_turn(text)
        except Exception:  # noqa: BLE001
            result = None
        if result is not None:
            result["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
            result["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
            return result
        return super().chat(text, session_id)
