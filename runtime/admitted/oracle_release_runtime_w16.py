#!/usr/bin/env python3
"""oracle_release_runtime_w16 - REFLECTION + TURN CONTINUATION fold: the witness as mirror, every turn forward-edged.

Two capabilities in one letter (Ben's directive 2026-08-25):
SELF-REFLECTION: "reflect" / "how is this conversation going" / "what have you failed
at here" answered FROM THE SESSION'S OWN WITNESS PATH - answered/declined counts,
conversions used, standing residuals, doors opened. Reflection with warrant: the
witness is the substrate, nothing is self-flattery. Loop-level reflection composes
from the self-improvement fold already in this chain.
TURN CONTINUATION: every answered turn carries result["continuation"] =
{"doors": [...], "offer": "..."} - introduced terms filtered to corpus anchors,
a structural forward edge on every step. The response text is NEVER mutated
(witness fidelity); surfaces opt in to render or speak the offer.
Authored 2026-08-25 07:55 UTC by oracle_fold_worker_v6, chained on oracle_release_runtime_w15."""

from __future__ import annotations

import re

from oracle_release_runtime_w15 import OracleReleaseRuntimeW15

REFL_RX = re.compile(
    r"(^reflect |^reflect$|how is this conversation going|what have you failed at"
    r"|reflect on (?:this|the) conversation|how are we doing)", re.I)
_MONTHS2 = {"january", "february", "march", "april", "may", "june", "july",
             "august", "september", "october", "november", "december"}


class OracleReleaseRuntimeW16(OracleReleaseRuntimeW15):
    """Base + witness reflection + structural turn continuation."""

    def _doors_from(self, session_id):
        doors = []
        try:
            anchors = self.anchors.title_to_page
            for rec in reversed(list(self.path(session_id))):
                if rec.get("out_status") != "answered":
                    continue
                for t in (rec.get("relation", {}).get("introduced") or []):
                    tl = str(t).lower()
                    if (4 <= len(tl) < 30 and tl in anchors
                            and tl not in _MONTHS2 and tl not in doors):
                        doors.append(tl)
                if len(doors) >= 3:
                    break
        except Exception:
            pass
        return doors[:3]

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        if REFL_RX.search(s):
            try:
                p = list(self.path(session_id))
            except Exception:
                p = []
            answered = sum(1 for r in p if r.get("out_status") == "answered")
            declined = sum(1 for r in p
                           if r.get("out_status") in ("withheld", "clarification"))
            convs = sum(1 for r in p if r.get("conversion"))
            residuals = [r.get("residual", {}).get("class") for r in p
                         if r.get("residual")][-2:]
            doors = self._doors_from(session_id)
            bits = (f"this session holds {len(p)} witnessed turns: {answered} "
                    f"answered, {declined} honestly declined, {convs} conversions")
            if residuals:
                bits += f"; standing residuals: {', '.join(str(x) for x in residuals)}"
            if doors:
                bits += f"; open doors: {', '.join(doors)}"
            return {"status": "answered", "path": "worker:reflect",
                     "response": f"By my own witness, {bits}. [witness_reflection]",
                     "provenance": {"kind": "witness_reflection", "turns": len(p)},
                     "latency_ms": 1}
        result = super().chat(s, session_id)
        if result.get("status") == "answered" and "continuation" not in result:
            doors = self._doors_from(session_id)
            if doors:
                offer = " or ".join(doors[:2])
                result["continuation"] = {"doors": doors,
                                           "offer": f"from here, {offer} stand open"}
        return result
