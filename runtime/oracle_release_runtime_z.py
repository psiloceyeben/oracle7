#!/usr/bin/env python3
"""Runtime Z — definitional substitution guard (additive over Y).

Found by the M29 route stress test (1,200 turns; five-case panels never hit it
because they used clean single-word topics): the definitional path silently
answers about a DIFFERENT term than the one asked about, in confident,
cited-looking prose.

    "What is James VI and I?"          -> "Vi is a locality ... in Sweden"
    "What is Batman: Rise of Sin Tzu?" -> "A sin is a bad act."
    "What is John Russell, 1st Earl Russell?" -> defines the peerage rank "Earl"
    "What is Epistasis?"               -> defines "Hypostasis"

The answers are true — about something else. That is worse than an uncited
assertion, because the user asked about X and is handed a fact about Y with no
signal that a substitution occurred. 18 of 81 definitional answers (22%) drifted
off-topic at scale.

This guard compares the term actually defined against the term asked about and,
when they differ, DISCLOSES the substitution instead of hiding it — the answer
stays useful (the component term is often what a reader wants) but it can no
longer be mistaken for an answer about the original subject. Nothing in the
sealed document chain is modified."""

from __future__ import annotations

import re
import time

from oracle_release_runtime_y import OracleReleaseRuntimeY

ASK_WHAT_IS = re.compile(r"^what\s+is\s+(?:an?\s+|the\s+)?(?P<t>.+?)\s*\??$", re.I)
# "<Term> is defined as ...", "A <term> is ...", "<Term> refers to ..."
DEFINED_TERM = re.compile(
    r"^(?:an?\s+|the\s+)?(?P<term>[\w' .\-]{2,60}?)\s+(?:is\s+defined\s+as|refers\s+to|is\s+a\b|is\s+an\b|is\s+the\b)",
    re.I)
DEFINITIONAL_PATHS = ("definitional_encyclopedic", "document_runtime",
                      "arb:definitional->", "corpus_query:property_of")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", str(text).lower()).strip()


class OracleReleaseRuntimeZ(OracleReleaseRuntimeY):
    def _definitional_substitution_guard(self, question: str, result: dict) -> dict:
        if result.get("status") != "answered":
            return result
        path = str(result.get("path", ""))
        if not any(path.startswith(p) or p in path for p in DEFINITIONAL_PATHS):
            return result
        asked = ASK_WHAT_IS.match(" ".join(question.strip().split()))
        if not asked:
            return result
        topic = asked.group("t").strip()
        body = str(result.get("response", ""))
        found = DEFINED_TERM.match(body.strip())
        if not found:
            return result
        defined = found.group("term").strip()
        if not defined or _norm(defined) == _norm(topic):
            return result                      # answered about the right thing
        # A substitution happened. Disclose it rather than let it pass as the answer.
        result = dict(result)
        result["response"] = (
            f"I have no admitted entry for \u201c{topic}\u201d. "
            f"The related term \u201c{defined}\u201d is what the record defines \u2014 "
            f"{body[0].lower() + body[1:] if body else ''}"
        )
        result["path"] = path + "|substitution_disclosed"
        provenance = dict(result.get("provenance") or {})
        provenance["substitution"] = {"asked": topic, "defined": defined}
        result["provenance"] = provenance
        return result

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        result = super().chat(text, session_id)
        try:
            result = self._definitional_substitution_guard(text, result)
        except Exception:  # noqa: BLE001 — a guard must never break a turn
            pass
        return result
