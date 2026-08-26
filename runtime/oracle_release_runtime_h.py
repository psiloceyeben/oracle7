#!/usr/bin/env python3
"""Runtime H — capability cycle 3: list-N-things (additive over G)."""

from __future__ import annotations

import re
import time

from oracle_release_runtime_g import OracleReleaseRuntimeG
from stage5m13e8_relevance_gate_v1 import gate_bundle

NUMERALS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
            "seven": 7, "eight": 8, "nine": 9, "ten": 10, "a": 3, "an": 3,
            "some": 3, "few": 3, "several": 4, "couple": 2}
LISTN = re.compile(
    r"^(?:please |can you )?(?:list|give me|tell me|name|share)"
    r"(?: (?P<n>\d+|one|two|three|four|five|six|seven|eight|nine|ten|a few|some|several|a couple(?: of)?))?"
    r" (?:facts?|things?|details?)(?: about| on| regarding)"
    r"(?: the| my document| my)? (?P<t>.+?)[.?!]?$"
    r"|^what are (?:some|a few) facts? about(?: the| my document| my)? (?P<t2>.+?)[.?!]?$",
    re.I)


class OracleReleaseRuntimeH(OracleReleaseRuntimeG):
    def _listn_turn(self, text: str, session_id: str) -> dict | None:
        match = LISTN.match(text.strip())
        if not match:
            return None
        groups = match.groupdict()
        topic = (groups.get("t") or groups.get("t2") or "").strip()
        if not topic:
            return None
        raw_n = (groups.get("n") or "some").lower().replace("a couple of", "couple").replace("a couple", "couple").replace("a few", "few")
        n = int(raw_n) if raw_n.isdigit() else NUMERALS.get(raw_n, 3)
        n = max(1, min(n, 10))
        user_claims = self.user_corpus.bundle(session_id, topic)
        admitted, _ = gate_bundle(topic, self._bundle(topic, n=10))
        claims = (user_claims + admitted)[:n]
        if not claims:
            return {"status": "withheld", "path": "capability:list_n",
                    "response": f"No provenance-admitted facts about {topic} are available to list.",
                    "provenance": {"kind": "gated_list", "topic": topic}}
        lines = [f"{i+1}. {c['sentence']} [{c['claim_id']}]" for i, c in enumerate(claims)]
        shortfall = ""
        if len(claims) < n:
            shortfall = (f" Only {len(claims)} admitted fact"
                         f"{'s are' if len(claims) != 1 else ' is'} available for {topic}.")
        return {"status": "answered", "path": "capability:list_n",
                "response": " ".join(lines) + shortfall,
                "provenance": {"kind": "gated_list", "topic": topic,
                               "requested": n, "delivered": len(claims),
                               "user_claims": len([c for c in claims if c["claim_id"].startswith("user:")])}}

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        normalized = " ".join(text.strip().split())
        result = None
        try:
            result = self._listn_turn(normalized, session_id)
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
