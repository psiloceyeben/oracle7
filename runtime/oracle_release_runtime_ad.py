#!/usr/bin/env python3
"""Runtime AD - serve the corroborated subset of the deductive closure (additive over AC).

The closure engine derived 32,724 facts. Only 6,768 of them carry independent
corroboration through a distinct middle; the rest were derived by valid steps
from attested premises but nothing outside the derivation vouches for them.
Serving all of them would break citation-or-derivation-or-refusal, so M30 gates
the store and this runtime serves the admitted subset only.

Two design commitments:

1. STRICTLY ADDITIVE. This runtime calls the existing chain FIRST and engages
   only where that chain declined to answer. It can widen coverage; it cannot
   change an answer any sealed panel already depends on.

2. WITHHELD IS NOT FALSE. A fact absent from the admitted store is not reported
   as false. In an incomplete record, absence of corroboration is absence of
   evidence, and the honest answer stays refusal. The response says which of the
   two it is.

Evidence channels are named in the response so the derivation is shown rather
than asserted. No neural network; no LM call.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path

from oracle_release_runtime_ac import OracleReleaseRuntimeAC

ADMITTED_STORE = ("/opt/oracle-clm/fable-content/oracle-m-series-2026-08-15"
                  "/m30_admitted_closure_v1.sqlite3")

_DP = r"(?:an?\s+|the\s+|some\s+)?"
ISA_Q = re.compile(
    r"^(?:is|are)\s+" + _DP + r"(?P<x>[a-z][a-z '\-]*?)\s+" + _DP +
    r"(?:kind|type|sort)?\s*(?:of\s+)?" + _DP + r"(?P<y>[a-z][a-z '\-]*?)\s*[.?!]*$", re.I)
_FILLER = re.compile(r"\b(?:do you think|would you say|is it true that|really|actually|"
                     r"even|also|just|by any chance|technically|basically)\b", re.I)
_LEAD = re.compile(r"^(?:so|well|hey|um|please|tell me|i wonder|question:)[\s,]+", re.I)

CHANNEL_NAMES = {
    "sib": "shared classification with concepts already in that category",
    "assoc1": "association through related and equivalent terms",
    "assoc2": "association through context, derivation and use",
    "wiki": "an independent encyclopedic corpus",
}


def _singular(concept: str) -> str:
    c = concept.strip().lower()
    if c.endswith("s") and not c.endswith("ss") and len(c) > 3:
        return c[:-1]
    return c


class OracleReleaseRuntimeAD(OracleReleaseRuntimeAC):
    def __init__(self, *args, admitted_store: str = ADMITTED_STORE, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._admitted = None
        path = Path(admitted_store)
        if path.exists():
            try:
                self._admitted = sqlite3.connect(
                    f"file:{path}?mode=ro&immutable=1", uri=True, check_same_thread=False)
            except sqlite3.Error:
                self._admitted = None

    def _lookup(self, x: str, y: str) -> dict | None:
        if self._admitted is None:
            return None
        for subject in dict.fromkeys([x, _singular(x)]):
            for obj in dict.fromkeys([y, _singular(y)]):
                row = self._admitted.execute(
                    "SELECT score,channels,premises FROM admitted_fact "
                    "WHERE subject=? AND object=? AND relation='IsA'", (subject, obj)).fetchone()
                if row:
                    return {"subject": subject, "object": obj, "score": row[0],
                            "channels": row[1], "premises": row[2]}
        return None

    def _admitted_turn(self, text: str) -> dict | None:
        t = " ".join(text.strip().split())
        t = " ".join(_FILLER.sub("", _LEAD.sub("", t)).split())
        match = ISA_Q.match(t)
        if not match:
            return None
        x = match.group("x").strip().lower()
        y = match.group("y").strip().lower()
        if not x or not y or x == y or len(x) < 2 or len(y) < 2:
            return None
        if _singular(x) == _singular(y):
            return None
        hit = self._lookup(x, y)
        if hit is None:
            return None
        try:
            channels = json.loads(hit["channels"])
        except (ValueError, TypeError):
            channels = {}
        named = [CHANNEL_NAMES[k] for k in ("sib", "assoc1", "assoc2", "wiki") if k in channels]
        support = "; ".join(named) if named else "corroboration through a distinct middle"
        premises = [p for p in str(hit["premises"]).split(",") if p][:4]
        tag = "[derived:closure_admitted<-" + ",".join(p[:24] for p in premises) + "]"
        article_x = "an" if x[:1] in "aeiou" else "a"
        article_y = "an" if y[:1] in "aeiou" else "a"
        return {
            "status": "answered",
            "path": "closure_admitted_isa",
            "response": (f"Yes. This is not stated directly in the admitted record, but it "
                         f"follows from it, and the conclusion is independently corroborated "
                         f"by {support}. On that basis {article_x} {x} is {article_y} {y}. {tag}"),
            "provenance": {"kind": "derived", "rule": "closure_admitted",
                           "relation": "IsA", "corroboration_score": hit["score"],
                           "channels": sorted(channels), "premises": premises},
        }

    def chat(self, text: str, session_id: str = "default") -> dict:
        result = super().chat(text, session_id)
        if str(result.get("status", "")) == "answered":
            return result
        started = time.perf_counter()
        try:
            admitted = self._admitted_turn(text)
        except Exception:  # noqa: BLE001
            admitted = None
        if admitted is None:
            return result
        admitted["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
        admitted["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
        return admitted
