#!/usr/bin/env python3
"""Runtime K — capability cycle 6: explain-why-different (additive over J)."""

from __future__ import annotations

import re
import time

from oracle_release_runtime_j import OracleReleaseRuntimeJ
from stage5m13e8_paragraph_compiler_v1 import _definitional_score

WHYDIFF = re.compile(
    r"^(?:please )?(?:explain )?why are (?:the |a |an )?(?P<x>.+?) and (?:the |a |an |my document )?(?P<y>.+?) different[.?!]?$"
    r"|^(?:please )?(?:explain )?why is (?:the |a |an )?(?P<x2>.+?) different from (?:the |a |an |my document )?(?P<y2>.+?)[.?!]?$"
    r"|^(?:please )?(?:explain )?why (?:the |a |an )?(?P<x3>.+?) and (?:the |a |an |my document )?(?P<y3>.+?) are different[.?!]?$"
    r"|^what makes (?:the |a |an )?(?P<x4>.+?) different from (?:the |a |an |my document )?(?P<y4>.+?)[.?!]?$",
    re.I)
KIND = re.compile(r"\bis (?:a|an|the) ([\w -]{3,40}?)(?:[,.]| that| which| in| of| with)")


class OracleReleaseRuntimeK(OracleReleaseRuntimeJ):
    def _whydiff_turn(self, text: str, session_id: str) -> dict | None:
        match = WHYDIFF.match(text.strip())
        if not match:
            return None
        groups = match.groupdict()
        x = next((groups[k] for k in ("x", "x2", "x3", "x4") if groups.get(k)), "").strip()
        y = next((groups[k] for k in ("y", "y2", "y3", "y4") if groups.get(k)), "").strip()
        if not x or not y:
            return None
        side_x, _ = self._side(x, session_id)
        side_y, _ = self._side(y, session_id)
        missing = [t for t, s in ((x, side_x), (y, side_y)) if not s]
        if missing:
            return {"status": "withheld", "path": "capability:why_different",
                    "response": f"I cannot explain the difference: no provenance-admitted material "
                                f"exists for {' or '.join(missing)}.",
                    "provenance": {"kind": "gated_whydiff", "missing": missing}}
        lead_x = max(side_x, key=lambda c: _definitional_score(x, c["sentence"]))
        lead_y = max(side_y, key=lambda c: _definitional_score(y, c["sentence"]))
        kind_x_match = KIND.search(lead_x["sentence"])
        kind_y_match = KIND.search(lead_y["sentence"])
        kind_x = kind_x_match.group(1).strip() if kind_x_match else None
        kind_y = kind_y_match.group(1).strip() if kind_y_match else None
        if kind_x and kind_y and kind_x.lower() != kind_y.lower():
            reason = (f"Derived reason: they belong to different categories — {x} is attested as "
                      f"a {kind_x}, whereas {y} is attested as a {kind_y}.")
        else:
            reason = (f"Derived reason: the admitted records place them in "
                      f"{'the same attested category (' + kind_x + '); their difference lies in the particulars below' if kind_x else 'categories the leads do not name explicitly; the difference rests on the particulars below'}.")
        response = (f"According to {lead_x['page']}, {lead_x['sentence']} [{lead_x['claim_id']}] "
                    f"According to {lead_y['page']}, {lead_y['sentence']} [{lead_y['claim_id']}] "
                    f"{reason} [derived:category_contrast<-{lead_x['claim_id'][:12]},{lead_y['claim_id'][:12]}]")
        return {"status": "answered", "path": "capability:why_different", "response": response,
                "provenance": {"kind": "gated_whydiff", "x": x, "y": y,
                               "derived": {"rule": "category_contrast",
                                           "premises": [lead_x["claim_id"], lead_y["claim_id"]]}}}

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        normalized = " ".join(text.strip().split())
        result = None
        try:
            result = self._whydiff_turn(normalized, session_id)
        except Exception:  # noqa: BLE001
            result = None
        if result is not None:
            result["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
            result["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
            state = self.dialogue.setdefault(session_id, {})
            state["last_result"] = {k: result.get(k) for k in ("path", "provenance", "status")}
            return result
        return super().chat(text, session_id)
