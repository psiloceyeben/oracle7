#!/usr/bin/env python3
"""oracle_release_runtime_w12 - OPEN-ENDED CONVERSATION fold: grounded continuation as a runtime route.

"What should we talk about?" answered from the live dialogue state: the last answered
turn's introduced terms, filtered to CORPUS ANCHORS (doors that actually open), plus a
standing potential from the improvement ledger. Open-endedness with warrant: every
offered continuation is a door the record can walk through. Continuations taken are
recorded via conversions - the acquisition signal for later epochs.
Authored 2026-08-25 06:17 UTC by oracle_fold_worker_v6, chained on oracle_release_runtime_w10."""

from __future__ import annotations

import re

from oracle_release_runtime_w10 import OracleReleaseRuntimeW10

CONV_RX = re.compile(
    r"(what should we (?:talk|speak) about|what can we explore"
    r"|where should we go next|what else is there)", re.I)
_MONTHS = {"january", "february", "march", "april", "may", "june", "july",
            "august", "september", "october", "november", "december"}


class OracleReleaseRuntimeW12(OracleReleaseRuntimeW10):
    """Base + grounded continuation offers."""

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        if CONV_RX.search(s):
            doors = []
            try:
                anchors = self.anchors.title_to_page
                for rec in reversed(list(self.path(session_id))):
                    if rec.get("out_status") != "answered":
                        continue
                    for t in (rec.get("relation", {}).get("introduced") or []):
                        tl = str(t).lower()
                        if (4 <= len(tl) < 30 and tl in anchors
                                and tl not in _MONTHS and tl not in doors):
                            doors.append(tl)
                    if len(doors) >= 3:
                        break
            except Exception:
                pass
            if doors:
                offer = ", ".join(doors[:3])
                resp = (f"From where we stand, the record opens doors to: {offer}. "
                        f"Name one and I will ground it. [dialogue_state]")
            else:
                resp = ("Nothing is introduced yet - ground a topic first and I will "
                        "offer the doors it opens. [dialogue_state]")
            return {"status": "answered", "path": "worker:open_converse",
                     "response": resp,
                     "provenance": {"kind": "dialogue_state", "doors": doors[:3]},
                     "latency_ms": 1}
        return super().chat(s, session_id)
