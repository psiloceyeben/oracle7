#!/usr/bin/env python3
"""Runtime U — graceful-clarify terminal (additive over T).

The last routing step for conversational smoothness: when a turn falls all the
way through the chain into the fallback tier WITHOUT being answered (the
document tier's "partial" evidence roundups and Wikipedia-address asks were
the wrong register for conversation — Ben-reported class, 2026-08-19), the
turn terminates in a typed clarify act instead: a short capability statement
in the machine's own voice. Answered / recorded / withheld results pass
through untouched; the arbitration record is preserved on the clarify so the
residue scoreboard keeps its labels. Per the K147 law, no user text rides in
the clarify."""

from __future__ import annotations

import time

from oracle_release_runtime_t import OracleReleaseRuntimeT

CLARIFY_RESPONSE = (
    "I didn't fully parse that, so I won't guess. I can summarize a topic, "
    "compare two things, list facts, give a timeline, explain something "
    "simply, define a term, reason about why and what-if, and discuss any "
    "document you teach me. A shorter, more direct phrasing usually lands."
)

PASS_THROUGH = {"answered", "recorded", "withheld"}
FALLBACK_TIER = {"document_runtime", "session_relational"}


class OracleReleaseRuntimeU(OracleReleaseRuntimeT):
    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        result = super().chat(text, session_id)
        if (result.get("path") in FALLBACK_TIER
                and result.get("status") not in PASS_THROUGH):
            return {"status": "clarification", "path": "act:clarify",
                    "response": CLARIFY_RESPONSE,
                    "provenance": {"kind": "dialogue_state",
                                   "note": "graceful clarify terminal"},
                    "arbitration": result.get("arbitration"),
                    "latency_ms": round(1000.0 * (time.perf_counter() - started), 1),
                    "zero_model_gate": {"lm_calls": 0, "transformer_calls": 0}}
        return result
