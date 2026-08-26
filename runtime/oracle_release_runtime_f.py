#!/usr/bin/env python3
"""Runtime F — capability cycle 1: summarization (additive over E).

Route forms per stage5m15_capability1_summarization_precommit_v1.md. The
composition organ already exists (gated paragraph compiler); this cycle adds
the construction routes and the summary-specific shape: definitional lead,
distinct evidence, length bound, provenance everywhere, typed abstention."""

from __future__ import annotations

import re
import time

from oracle_release_runtime_e import OracleReleaseRuntimeE
from stage5m13e8_relevance_gate_v1 import gate_bundle
from stage5m13e8_paragraph_compiler_v2 import compile_paragraph_v2, recover_program_v2

SUMMARIZE = re.compile(
    r"^(?:please |can you )?(?:summarize|sum up)(?: (?:the|my document|my))? (?P<t>.+?)(?: for me)?[.?!]?$"
    r"|^(?:please |can you )?give me a(?: brief| short| quick)? summary of(?: the| my document| my)? (?P<t2>.+?)[.?!]?$",
    re.I)


class OracleReleaseRuntimeF(OracleReleaseRuntimeE):
    def _summarize_turn(self, text: str, session_id: str) -> dict | None:
        match = SUMMARIZE.match(text.strip())
        if not match:
            return None
        topic = (match.group("t") or match.group("t2") or "").strip()
        if not topic:
            return None
        user_claims = self.user_corpus.bundle(session_id, topic)
        admitted_public, excluded = gate_bundle(topic, self._bundle(topic, n=8))
        claims = user_claims + admitted_public
        if not claims:
            return {"status": "withheld", "path": "capability:summarize",
                    "response": f"No provenance-admitted material on {topic} is available to summarize.",
                    "provenance": {"kind": "gated_summary", "topic": topic,
                                   "excluded": [{"page": e["page"], "relevance": e["relevance"]}
                                                for e in excluded]}}
        paragraph, program = compile_paragraph_v2(topic, claims[:8], evidence=5,
                                                  aggregation_term=None)
        if paragraph is None or not recover_program_v2(paragraph, program):
            return {"status": "withheld", "path": "capability:summarize",
                    "response": "Summary failed derivation verification and is withheld.",
                    "provenance": {"kind": "gated_summary", "topic": topic}}
        sentences = paragraph.count("]")  # each claim address closes a sentence
        return {"status": "answered", "path": "capability:summarize",
                "response": paragraph,
                "provenance": {"kind": "gated_summary", "topic": topic,
                               "sentences": sentences,
                               "user_claims": len(user_claims),
                               "public_claims": len(admitted_public)}}

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        normalized = " ".join(text.strip().split())
        result = None
        try:
            result = self._summarize_turn(normalized, session_id)
        except Exception:  # noqa: BLE001
            result = None
        if result is not None:
            result["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
            result["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
            state = self.dialogue.setdefault(session_id, {})
            state["last_result"] = {k: result.get(k) for k in ("path", "provenance", "status")}
            state["last_topic"] = result["provenance"].get("topic")
            state["last_offset"] = 0
            return result
        return super().chat(text, session_id)
