#!/usr/bin/env python3
"""Runtime J — capability cycle 5: timeline-of-topic (additive over I)."""

from __future__ import annotations

import re
import time

from oracle_release_runtime_i import OracleReleaseRuntimeI
from stage5m13e8_relevance_gate_v1 import gate_bundle

TIMELINE = re.compile(
    r"^(?:please |can you )?(?:give me |show(?: me)? |what is )?(?:a |the )?timeline of"
    r"(?: the| my document| my)? (?P<t>.+?)[.?!]?$", re.I)
YEAR = re.compile(r"\b(1[0-9]{3}|20[0-2][0-9])\b")


class OracleReleaseRuntimeJ(OracleReleaseRuntimeI):
    def _timeline_turn(self, text: str, session_id: str) -> dict | None:
        match = TIMELINE.match(text.strip())
        if not match:
            return None
        topic = match.group("t").strip()
        user_claims = self.user_corpus.bundle(session_id, topic)
        # timelines scan DEEP into the page: dated sentences cluster in history
        # sections, not the definitional lead
        page = self.anchors.resolve(topic)
        deep = []
        if page:
            title = self.anchors.page_to_title.get(page, topic)
            deep = [{"claim_id": c, "page": title, "sentence": s}
                    for c, s in self.bench_query.page_sentences(page)[:40]]
        admitted, _ = gate_bundle(topic, deep)
        dated = []
        for claim in user_claims + admitted:
            years = YEAR.findall(claim["sentence"])
            if years:
                dated.append((min(int(y) for y in years), claim))
        if len(dated) < 2:
            return {"status": "withheld", "path": "capability:timeline",
                    "response": f"A timeline needs at least two dated statements; the admitted "
                                f"material on {topic} contains {len(dated)}.",
                    "provenance": {"kind": "gated_timeline", "topic": topic,
                                   "dated_claims": len(dated)}}
        dated.sort(key=lambda pair: pair[0])
        lines = [f"{year}: {c['sentence']} [{c['claim_id']}]" for year, c in dated[:8]]
        first_year, first_claim = dated[0]
        last_year, last_claim = dated[-1]
        span = (f"Derived span: the dated record on {topic} runs {last_year - first_year} years, "
                f"from {first_year} to {last_year}. "
                f"[derived:year_span<-{first_claim['claim_id'][:12]},{last_claim['claim_id'][:12]}]")
        return {"status": "answered", "path": "capability:timeline",
                "response": " ".join(lines) + " " + span,
                "provenance": {"kind": "gated_timeline", "topic": topic,
                               "entries": len(dated[:8]),
                               "derived": {"rule": "year_span",
                                           "premises": [first_claim["claim_id"], last_claim["claim_id"]]}}}

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        normalized = " ".join(text.strip().split())
        result = None
        if not self._in_chain or True:  # timeline is chain-safe
            try:
                result = self._timeline_turn(normalized, session_id)
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
