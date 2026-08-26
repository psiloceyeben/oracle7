#!/usr/bin/env python3
"""Runtime M — capability cycle 8: explain-simply (additive over L).
Simplest admitted definitional statement + Wiktionary first gloss where the
entry exists; register marked; everything addressed."""

from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path

from oracle_release_runtime_l import OracleReleaseRuntimeL
from oracle_release_runtime import PHASE
from stage5m13e8_relevance_gate_v1 import gate_bundle
from stage5m13e8_paragraph_compiler_v1 import _definitional_score

SIMPLY = re.compile(
    r"^(?:please )?explain (?:the |a |an )?(?P<t>.+?)(?: simply| in simple (?:terms|words)| like i(?:'m| am) new to it)[.?!]?$"
    r"|^what is (?:the |a |an )?(?P<t2>.+?), in simple (?:terms|words)\??$",
    re.I)
WIKT = PHASE / "m13e5_wiktionary_build_a_v1" / "wiktionary_specialist.sqlite3"


class OracleReleaseRuntimeM(OracleReleaseRuntimeL):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._wikt = None
        if WIKT.exists():
            self._wikt = sqlite3.connect(WIKT.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)

    def _gloss(self, term: str) -> str | None:
        if self._wikt is None:
            return None
        row = self._wikt.execute("SELECT glosses_json FROM entry WHERE word=? AND pos='noun' LIMIT 1",
                                 (term.lower(),)).fetchone() or \
              self._wikt.execute("SELECT glosses_json FROM entry WHERE word=? LIMIT 1",
                                 (term.lower(),)).fetchone()
        if not row:
            return None
        glosses = json.loads(row[0])
        return glosses[0] if glosses else None

    def _simply_turn(self, text: str, session_id: str) -> dict | None:
        match = SIMPLY.match(text.strip())
        if not match:
            return None
        topic = (match.group("t") or match.group("t2") or "").strip()
        if not topic:
            return None
        admitted, _ = gate_bundle(topic, self._bundle(topic, n=8))
        gloss = self._gloss(topic)
        if not admitted and not gloss:
            return {"status": "withheld", "path": "capability:explain_simply",
                    "response": f"No provenance-admitted material on {topic} is available to explain.",
                    "provenance": {"kind": "simple_register", "topic": topic}}
        parts = []
        premises = []
        if admitted:
            # true definitions that are also short; else the best true definition
            short_defs = [c for c in admitted if len(c["sentence"].split()) <= 30
                          and _definitional_score(topic, c["sentence"]) >= 6]
            pool = short_defs or admitted
            lead = max(pool, key=lambda c: (_definitional_score(topic, c["sentence"]),
                                            -len(c["sentence"].split())))
            parts.append(f"{lead['sentence']} [{lead['claim_id']}]")
            premises.append(lead["claim_id"])
        if gloss:
            parts.append(f"The dictionary sense: {gloss}. [wiktionary:{topic.lower()}:sense1]")
            premises.append(f"wiktionary:{topic.lower()}")
        return {"status": "answered", "path": "capability:explain_simply",
                "response": "In simple terms: " + " ".join(parts),
                "provenance": {"kind": "simple_register", "topic": topic, "premises": premises}}

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        normalized = " ".join(text.strip().split())
        result = None
        try:
            result = self._simply_turn(normalized, session_id)
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
