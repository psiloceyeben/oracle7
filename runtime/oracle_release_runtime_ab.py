#!/usr/bin/env python3
"""Runtime AB — the `when` route declines ill-posed questions (additive over AA).

Iteration 5 added an automatic RELEVANCE column to the stress harness and it
immediately found the largest defect the campaign has surfaced: of 96 answered
`when` turns, only 6 actually carried the relation asked for. 90 were confident,
cited, on-topic — and did not answer the question.

Cause: AA's date selection ended with a bare-year fallback. If no inception cue
matched, it returned ANY admitted sentence containing a date. So an ill-posed
question ("When did Paco Gento start?", "When did Cape York Peninsula start?" —
people and peninsulas do not "start") was answered with a date-bearing sentence
rather than declined.

That fallback is exactly the "say something rather than nothing" reflex this
architecture exists to refuse. It is removed: if no sentence carries an
inception cue appropriate to the verb asked, the route WITHHOLDS. This will cut
the `when` answer-rate substantially, and that is the correct trade — a system
whose contract is citation-or-derivation-or-refusal must prefer a refusal to a
plausible irrelevance."""

from __future__ import annotations

import re
import time

from oracle_release_runtime_aa import (
    INCEPT_GENERAL, VERB_CUES, OracleReleaseRuntimeAA,
)

YEAR = re.compile(r"\b(1[0-9]{3}|20[0-2][0-9])\b")

# Wider topic charset than runtime Y's WHEN_Q: titles legitimately contain
# periods, colons, commas and ampersands ("Arthur C. Clarke", "Batman: Rise of
# Sin Tzu"). Without them a when-question never matched this route at all and
# fell through to the timeline route, which answered with a chronology.
WHEN_Q_WIDE = re.compile(
    r"^when\s+(?:did|was|does|do|were)\s+(?:the\s+)?(?P<t>[\w' .:,&\-]+?)\s+"
    r"(?P<v>start|begin|end|happen|occur|found|built|discover|invent|born|die)\w*\s*\??$",
    re.I)


class OracleReleaseRuntimeAB(OracleReleaseRuntimeAA):
    def _explanatory_turn(self, text: str) -> dict | None:   # override AA
        from oracle_release_runtime_y import CAUSE_Q, HOW_Q, WHEN_Q
        stripped = " ".join(text.strip().split())

        match = WHEN_Q_WIDE.match(stripped) or WHEN_Q.match(stripped)
        if match:
            topic = match.group("t").strip()
            verb = (match.group("v") or "").lower()
            tiers = []
            for stem, patterns in VERB_CUES.items():
                if verb.startswith(stem):
                    tiers = [re.compile(pat, re.I) for pat in patterns]
                    break
            # A matched verb uses ONLY its own cues. INCEPT_GENERAL carries other
            # verbs' markers (born|died|was released...), which is how "when did
            # <a person> start?" was being answered with a birth-date sentence.
            if not tiers:
                tiers = list(INCEPT_GENERAL)
            # NO bare-year fallback: an inception cue is required, or we decline.
            hits = self._pick_tiered(topic, tiers, require_year=True)
            if not hits:
                article = "an" if topic[:1].lower() in "aeiou" else "a"
                return {"status": "withheld", "path": "capability:when_did",
                        "response": f"The admitted record for {topic} contains no dated statement "
                                    f"about when it {verb or 'began'}. It may also be that "
                                    f"\u201cwhen did {topic} {verb}\u201d is not a well-posed "
                                    f"question for {article} subject of this kind. I will not "
                                    f"offer an unrelated date.",
                        "provenance": {"kind": "selected_evidence", "selector": "inception",
                                       "topic": topic, "result": "no_inception_statement"}}
            return self._render(topic, hits, "inception", "capability:when_did",
                                f"when {topic} {verb}")

        # cause and process paths unchanged from AA
        return super()._explanatory_turn(text)

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        result = None
        try:
            result = self._explanatory_turn(text)
        except Exception:  # noqa: BLE001
            result = None
        if result is not None:
            result["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
            result["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
            return result
        return super(OracleReleaseRuntimeAA, self).chat(text, session_id)
