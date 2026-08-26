#!/usr/bin/env python3
"""oracle_release_runtime_w24 - THE COMPOSER (D1): two-hop composition of admitted operators, hops cited.

"What is X ultimately made of?"  = made_of(made_of(X)) - both hops extracted LIVE
by the rule operator, both claims cited, honest partial when hop 2 is unattested.
"Is X made of a kind of K?"      = made_of(X)=Y then the CHAIN'S OWN kind operator
judges "Is Y a K?" - composition ACROSS admitted operators, premises from both.
Declines when any hop is unattested: depth without false-answer discipline is not
depth (D1 negative sets must stay 0 false-yes).
Authored 2026-08-25 18:44 UTC by the fold worker, chained on oracle_release_runtime_w23."""

from __future__ import annotations

import re

from oracle_release_runtime_w23 import OracleReleaseRuntimeW23

_ULT_Q = re.compile(
    r"^what (?:is|are) (?:the )?(?P<t>[a-z][\w \-']{1,40}?) ultimately made "
    r"(?:of|from)[?.! ]*$", re.I)
_MKIND_Q = re.compile(
    r"^is (?:the )?(?P<t>[a-z][\w \-']{1,40}?) made of a kind of "
    r"(?P<k>[a-z][\w \-']{1,40}?)[?.! ]*$", re.I)


class OracleReleaseRuntimeW24(OracleReleaseRuntimeW23):
    """Base + two-hop composition. Every hop cited; unattested hops decline."""

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        result = super().chat(s, session_id)
        if result.get("status") == "answered":
            return result          # fallback law: compose only where the chain declines
        m = _ULT_Q.match(s)
        if m and hasattr(self, "made_of_lookup"):
            x = m.group("t").strip().lower()
            h1 = self.made_of_lookup(x)
            if h1:
                mid_head = h1[0].split()[-1] if h1[0] else ""
                h2 = self.made_of_lookup(h1[0]) or (
                    self.made_of_lookup(mid_head) if mid_head else None)
                pending = getattr(self, "_pending_conversion", None)
                if pending is None:
                    pending = self._pending_conversion = {}
                pending[session_id] = {"construction": "COMPOSE_2HOP",
                                        "from": s[:80], "to": "made_of^2",
                                        "produced_by": "fold_worker_depth"}
                if h2:
                    return {"status": "answered", "path": "worker:compose_2hop",
                             "response": f"In steps: {x} is made of {h1[0]} "
                                         f"[{h1[1]}]; {h1[0]} is made of {h2[0]} "
                                         f"[{h2[1]}]. So {x} is ultimately made "
                                         f"of {h2[0]}.",
                             "provenance": {"kind": "derived",
                                             "rule": "transitive_made_of",
                                             "premises": [h1[1], h2[1]]},
                             "latency_ms": 3}
                return {"status": "withheld", "path": "worker:compose_2hop",
                         "response": f"The record attests {x} is made of {h1[0]} "
                                     f"[{h1[1]}], but the composition of {h1[0]} "
                                     f"is not attested - I won't guess the second hop.",
                         "provenance": {"kind": "partial_chain",
                                         "premises": [h1[1]]},
                         "latency_ms": 3}
        km = _MKIND_Q.match(s)
        if km and hasattr(self, "made_of_lookup"):
            x, k = km.group("t").strip().lower(), km.group("k").strip().lower()
            h1 = self.made_of_lookup(x)
            if h1:
                mid = h1[0].split()[-1]
                kind_r = super().chat(f"Is a {mid} a {k}?", session_id)
                resp_l = str(kind_r.get("response", "")).lower()
                if kind_r.get("status") == "answered" and resp_l.startswith(("yes",)):
                    return {"status": "answered", "path": "worker:compose_made_kind",
                             "response": f"In steps: {x} is made of {h1[0]} "
                                         f"[{h1[1]}]; and {mid} is a kind of "
                                         f"{k}. So yes.",
                             "provenance": {"kind": "derived",
                                             "rule": "made_of_then_kind",
                                             "premises": [h1[1], kind_r.get(
                                                 "provenance", {})]},
                             "latency_ms": 3}
                if kind_r.get("status") == "answered" and resp_l.startswith("no"):
                    return kind_r
                return {"status": "withheld", "path": "worker:compose_made_kind",
                         "response": f"The record attests {x} is made of {h1[0]} "
                                     f"[{h1[1]}], but whether {mid} is a kind of "
                                     f"{k} is not attested - I won't guess.",
                         "provenance": {"kind": "partial_chain",
                                         "premises": [h1[1]]},
                         "latency_ms": 2}
        return result
