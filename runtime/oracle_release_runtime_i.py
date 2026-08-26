#!/usr/bin/env python3
"""Runtime I — capability cycle 4: multi-step instructions (additive over H).
Splits a turn on chain connectives, dispatches each part through the FULL
existing route stack in order, labels parts, carries per-part provenance, and
lets one part withhold without killing the other."""

from __future__ import annotations

import re
import time

from oracle_release_runtime_h import OracleReleaseRuntimeH

# lookbehind keeps part 1's terminal punctuation (a "?" must survive so the
# definitional route still sees a question); comma/bare forms handled separately
CHAIN = re.compile(r"(?<=[.?!])\s*(?:and\s+)?then\s+|,\s*then\s+|\s+and\s+then\s+|;\s*then\s+", re.I)


class OracleReleaseRuntimeI(OracleReleaseRuntimeH):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._in_chain = False

    def _chain_turn(self, text: str, session_id: str) -> dict | None:
        if self._in_chain:
            return None
        parts = CHAIN.split(text.strip())
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            return None
        results = []
        self._in_chain = True
        try:
            for part in parts:
                part = part.strip().rstrip(",;")
                if not part.endswith((".", "?", "!")):
                    part += "."
                part = part[0].upper() + part[1:]
                results.append(self.chat(part, session_id=session_id))
        finally:
            self._in_chain = False
        labeled = []
        for index, result in enumerate(results):
            labeled.append(f"Part {index+1}: {result.get('response', '')}")
        answered = sum(1 for r in results if r.get("status") == "answered")
        status = "answered" if answered >= 1 else "withheld"
        return {"status": status, "path": "capability:multi_step",
                "response" : "\n".join(labeled),
                "provenance": {"kind": "instruction_chain",
                               "parts": [{"path": r.get("path"), "status": r.get("status"),
                                          "provenance": r.get("provenance")} for r in results]}}

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        normalized = " ".join(text.strip().split())
        result = None
        if not self._in_chain:
            try:
                result = self._chain_turn(normalized, session_id)
            except Exception:  # noqa: BLE001
                result = None
        if result is not None:
            result["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
            result["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
            return result
        return super().chat(text, session_id)
