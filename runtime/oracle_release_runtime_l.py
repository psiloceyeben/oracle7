#!/usr/bin/env python3
"""Runtime L — capability cycle 7: what-if hypothetical worlds (additive over K).
The response lives in an explicitly-marked HYPOTHESIS scope: attested facts
carry provenance; the hypothetical consequence carries premises and is never
rendered as an actual-world assertion (M13e4 world-scope discipline surfaced
into conversation)."""

from __future__ import annotations

import re
import time

from oracle_release_runtime_k import OracleReleaseRuntimeK

WHATIF = re.compile(
    r"^(?:please tell me )?what (?:if|would happen if) (?:a |an |the )?(?P<x>[\w '-]+?) had no (?P<y>[\w '-]+?)[.?!]?$",
    re.I)


class OracleReleaseRuntimeL(OracleReleaseRuntimeK):
    def _whatif_turn(self, text: str, session_id: str) -> dict | None:
        match = WHATIF.match(text.strip())
        if not match:
            return None
        x = match.group("x").strip().lower()
        y = match.group("y").strip().lower()
        y_singular = y[:-1] if y.endswith("s") and not y.endswith("ss") else y
        has_edges = [e for e in self.commonsense.edges(x, "HasA", limit=6)
                     if y in e["end"].lower() or y_singular in e["end"].lower()]
        if not has_edges:
            return {"status": "withheld", "path": "capability:what_if",
                    "response": f"I cannot ground that hypothetical: no admitted evidence attests "
                                f"that a {x} has {y}.",
                    "provenance": {"kind": "hypothetical_world", "unattested": f"{x} HasA {y}"}}
        base = has_edges[0]
        uses = self.commonsense.edges(y_singular, "UsedFor", limit=3) or \
               self.commonsense.edges(x, "UsedFor", limit=3)
        attested = (f"Attested: {self.commonsense.render_edge(base)} [{base['provenance']}]")
        use_part = ""
        premises = [base["provenance"]]
        if uses:
            use = uses[0]
            use_part = f" Attested: {self.commonsense.render_edge(use)} [{use['provenance']}]"
            premises.append(use["provenance"])
        hypo = (f" HYPOTHESIS (hypothetical world, not asserted of the actual world): "
                f"a {x} without {y} would lack what the admitted record attributes to it"
                + (f" — in particular the attested use of {uses[0]['start']}" if uses else "")
                + f". [derived:hypothetical_severance<-{','.join(p[:24] for p in premises)}]")
        return {"status": "answered", "path": "capability:what_if",
                "response": attested + use_part + hypo,
                "provenance": {"kind": "hypothetical_world", "x": x, "y": y,
                               "derived": {"rule": "hypothetical_severance", "premises": premises},
                               "world": "hypothetical"}}

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        normalized = " ".join(text.strip().split())
        result = None
        try:
            result = self._whatif_turn(normalized, session_id)
        except Exception:  # noqa: BLE001
            result = None
        if result is not None:
            result["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
            result["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
            state = self.dialogue.setdefault(session_id, {})
            state["last_result"] = {k: result.get(k) for k in ("path", "provenance", "status")}
            return result
        return super().chat(text, session_id)
