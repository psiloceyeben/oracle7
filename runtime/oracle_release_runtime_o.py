#!/usr/bin/env python3
"""Runtime O — acts batch 3 (additive over N): refine-request.
"Simpler" / "shorter" / "again, but simpler" re-dispatches the session's last
topic through the explain-simply capability; "in one sentence" returns just
the definitional lead. Pure conversions over dialogue state."""

from __future__ import annotations

import re
import time

from oracle_release_runtime_n import OracleReleaseRuntimeN

REFINE_SIMPLER = re.compile(r"^(?:again,? )?(?:but )?(?:simpler|more simply|make it simpler|explain it more simply)[.!]?$", re.I)
REFINE_SHORTER = re.compile(r"^(?:shorter|make it shorter|in one sentence|briefer)[.!]?$", re.I)


class OracleReleaseRuntimeO(OracleReleaseRuntimeN):
    def _refine_turn(self, text: str, session_id: str) -> dict | None:
        state = self.dialogue.get(session_id, {})
        topic = state.get("last_topic")
        simpler = bool(REFINE_SIMPLER.match(text))
        shorter = bool(REFINE_SHORTER.match(text))
        if not (simpler or shorter):
            return None
        if not topic:
            return {"status": "withheld", "path": "act:refine",
                    "response": "There is no active topic to restate — ask about something first.",
                    "provenance": {"kind": "dialogue_state"}}
        if simpler:
            result = self._simply_turn(f"Explain {topic} simply.", session_id)
            if result is not None:
                result["path"] = "act:refine->explain_simply"
                return result
        # shorter: definitional lead only
        result = self._definitional_turn(f"What is a {topic.lower()}?") or \
                 self._definitional_turn(f"What is {topic}?")
        if result is not None:
            result["path"] = "act:refine->definitional"
            return result
        return {"status": "withheld", "path": "act:refine",
                "response": f"No shorter admitted statement of {topic} is available.",
                "provenance": {"kind": "dialogue_state", "topic": topic}}

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        normalized = " ".join(text.strip().split())
        result = None
        try:
            result = self._refine_turn(normalized, session_id)
        except Exception:  # noqa: BLE001
            result = None
        if result is not None:
            result["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
            result["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
            state = self.dialogue.setdefault(session_id, {})
            state["last_result"] = {k: result.get(k) for k in ("path", "provenance", "status")}
            return result
        return super().chat(text, session_id)
