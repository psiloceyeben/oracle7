#!/usr/bin/env python3
"""Runtime X — transitive part-of turn (additive over W).

"Is a piston part of a car?" — no single admitted edge says so, but
piston is part of an engine and an engine is part of a car. Same shown-chain
derivation as the kind reasoner, over the PartOf relation. The "part of"
marker is specific, so hijack risk is low; still gated to real question forms.
Runs before W's kind turn in the chain."""

from __future__ import annotations

import re
import time

from oracle_release_runtime_w import OracleReleaseRuntimeW
from stage5m22_relational_reasoner_v1 import chain, direct, norm, render_chain

PARTOF_FLOOR = 8

_FILLER = re.compile(r"\b(?:do you think|would you say|is it true that|really|actually|"
                     r"even|also|just|by any chance|technically|basically)\b", re.I)
_LEAD = re.compile(r"^(?:so|well|hey|um|please|tell me|i wonder|question:)[\s,]+", re.I)
# "Is (a) X part of (a) Y?", "Are Xs part of Ys?", "Is X a part of Y?"
_DP = r"(?:an?\s+|the\s+|some\s+)?"
PARTOF_Q = re.compile(
    rf"^(?:is|are)\s+{_DP}(?P<x>[a-z][a-z '\-]*?)\s+{_DP}parts?\s+of\s+{_DP}(?P<y>[a-z][a-z '\-]*?)\s*[.?!]*$", re.I)
# declarative, embedded-question only ("do you think X is part of Y")
PARTOF_DECL = re.compile(
    rf"^{_DP}(?P<x>[a-z][a-z '\-]*?)\s+(?:is|are)\s+{_DP}parts?\s+of\s+{_DP}(?P<y>[a-z][a-z '\-]*?)\s*[.?!]*$", re.I)
_EMBEDDED = re.compile(r"\b(?:do you think|would you say|is it true that)\b", re.I)


class OracleReleaseRuntimeX(OracleReleaseRuntimeW):
    def _partof_turn(self, text: str) -> dict | None:
        t = " ".join(text.strip().split())
        t = _FILLER.sub("", _LEAD.sub("", t))
        t = " ".join(t.split())
        match = PARTOF_Q.match(t)
        if match is None and _EMBEDDED.search(text):
            match = PARTOF_DECL.match(t)
        if not match:
            return None
        x = match.group("x").strip().lower()
        y = match.group("y").strip().lower()
        if not x or not y or x == y or len(x) < 2 or len(y) < 2 or norm(x) == norm(y):
            return None
        cs = self.commonsense

        d = direct(cs, x, y, "PartOf")
        if d is not None:
            return {"status": "answered", "path": "conceptnet_partof_direct",
                    "response": f"Yes — the admitted record states it directly: "
                                f"{cs.render_edge(d)} [{d['provenance']}]",
                    "provenance": {"kind": "commonsense_edge", "relation": "PartOf",
                                   "premises": [d["provenance"]]}}

        path = chain(cs, x, y, "PartOf", floor=PARTOF_FLOOR)
        if path is not None:
            steps = render_chain(cs, path)
            premises = [edge["provenance"] for edge in path]
            tag = "[derived:transitive_partof<-" + ",".join(p[:24] for p in premises) + "]"
            ax = "an" if x[:1] in "aeiou" else "a"
            ay = "an" if y[:1] in "aeiou" else "a"
            return {"status": "answered", "path": "conceptnet_partof_derived",
                    "response": f"By the admitted record, in steps: {steps}. Therefore, if "
                                f"part-of is transitive, {ax} {x} is part of {ay} {y}. {tag}",
                    "provenance": {"kind": "derived", "rule": "transitive_partof",
                                   "hops": len(path), "premises": premises}}

        ax = "an" if x[:1] in "aeiou" else "a"
        ay = "an" if y[:1] in "aeiou" else "a"
        return {"status": "withheld", "path": "conceptnet_partof_derived",
                "response": f"The admitted record does not establish that {ax} {x} is part of "
                            f"{ay} {y}, directly or by a chain of part-of within 3 steps.",
                "provenance": {"kind": "derived", "rule": "transitive_partof", "result": "no_chain"}}

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        result = None
        try:
            result = self._partof_turn(text)
        except Exception:  # noqa: BLE001
            result = None
        if result is not None:
            result["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
            result["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
            return result
        return super().chat(text, session_id)
