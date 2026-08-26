#!/usr/bin/env python3
"""oracle_release_runtime_w4 - REGENERATIVE fold: withhold-recovery via bounded typed transforms.

When the chain withholds or clarifies, attempt at most two typed surface transforms
(strip leading article; singularize the final content word) and retry once each.
A recovery answers with the conversion RECORDED (construction REGEN) - the plural
gap discovered 2026-08-24 ("Summarize bees." failing beside the bee page),
generalized into an organ. Never fires on answered turns; never invents content -
the unchanged chain supplies every recovered answer with its warrant.
Authored 2026-08-25 05:31 UTC by oracle_fold_worker_v3, chained on oracle_release_runtime_w1."""

from __future__ import annotations

import re

from oracle_release_runtime_w1 import OracleReleaseRuntimeW1

_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def _transforms(s: str):
    out = []
    low = s.lower()
    if low.startswith("the "):
        out.append(s[4:])
    words = s.rstrip(".?! ").split()
    if words:
        last = words[-1]
        if len(last) > 4 and last.lower().endswith("es"):
            out.append(" ".join(words[:-1] + [last[:-2]]) + s[len(s.rstrip(".?! ")):])
        elif len(last) > 3 and last.lower().endswith("s"):
            out.append(" ".join(words[:-1] + [last[:-1]]) + s[len(s.rstrip(".?! ")):])
    seen = set()
    for t in out:
        t = " ".join(t.split())
        if t and t.lower() != low and t not in seen:
            seen.add(t)
            yield t


class OracleReleaseRuntimeW4(OracleReleaseRuntimeW1):
    """Base + withhold-recovery. Two bounded retries, conversions recorded."""

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        result = super().chat(s, session_id)
        if result.get("status") not in ("withheld", "clarification"):
            return result
        for probe in list(_transforms(s))[:2]:
            pending = getattr(self, "_pending_conversion", None)
            if pending is None:
                pending = self._pending_conversion = {}
            pending[session_id] = {
                "construction": "REGEN", "from": s[:80], "to": probe[:80],
                "produced_by": "oracle_fold_worker_v3"}
            retry = super().chat(probe, session_id)
            if retry.get("status") == "answered":
                return retry
        return result
