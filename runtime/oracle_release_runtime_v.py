#!/usr/bin/env python3
"""Runtime V — implied-knowledge turn (additive over U): transitive kind.

"Is a robin an animal?" / "Is an oak a plant?" — when no single admitted claim
answers, chain admitted IsA edges and answer with the shown premise chain
(the derivation mode the architecture already supports). Direct edges are
cited; chains are derived; anything else abstains honestly. Fires before the
rest of the chain so it can claim these question forms; everything it does not
match falls through untouched."""

from __future__ import annotations

import re
import time

from oracle_release_runtime_u import OracleReleaseRuntimeU
from stage5m21_transitive_reasoner_v1 import chain_isa, direct_isa, render_chain

# "Is a X a Y?" / "Is X a kind of Y?" / "Are robins animals?"
ISA_Q = re.compile(
    r"^(?:is|are)\s+(?:an?\s+)?(?P<x>[a-z][a-z '\-]*?)\s+"
    r"(?:an?\s+|a\s+kind\s+of\s+|a\s+type\s+of\s+)?(?P<y>[a-z][a-z '\-]*?)\s*\??$",
    re.I)


class OracleReleaseRuntimeV(OracleReleaseRuntimeU):
    def _implied_isa_turn(self, text: str) -> dict | None:
        match = ISA_Q.match(text.strip())
        if not match:
            return None
        x = match.group("x").strip().lower()
        y = match.group("y").strip().lower()
        if not x or not y or x == y or len(x) < 2 or len(y) < 2:
            return None
        cs = self.commonsense

        direct = direct_isa(cs, x, y)
        if direct is not None:
            rendered = cs.render_edge(direct)
            return {"status": "answered", "path": "conceptnet_isa_direct",
                    "response": f"Yes — the admitted record states it directly: {rendered} "
                                f"[{direct['provenance']}]",
                    "provenance": {"kind": "commonsense_edge", "relation": "IsA",
                                   "premises": [direct["provenance"]]}}

        path = chain_isa(cs, x, y)
        if path is not None:
            steps = render_chain(cs, path)
            premises = [edge["provenance"] for edge in path]
            tag = "[derived:transitive_isa<-" + ",".join(p[:24] for p in premises) + "]"
            article_x = "an" if x[:1] in "aeiou" else "a"
            article_y = "an" if y[:1] in "aeiou" else "a"
            return {"status": "answered", "path": "conceptnet_isa_derived",
                    "response": f"By the admitted record, in steps: {steps}. Therefore, if "
                                f"kind is transitive, {article_x} {x} is {article_y} {y}. {tag}",
                    "provenance": {"kind": "derived", "rule": "transitive_isa",
                                   "hops": len(path), "premises": premises}}

        article_x = "an" if x[:1] in "aeiou" else "a"
        article_y = "an" if y[:1] in "aeiou" else "a"
        return {"status": "withheld", "path": "conceptnet_isa_derived",
                "response": f"The admitted record does not establish that {article_x} {x} is "
                            f"{article_y} {y}, directly or by a chain of kind within "
                            f"{3} steps.",
                "provenance": {"kind": "derived", "rule": "transitive_isa", "result": "no_chain"}}

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        result = None
        try:
            result = self._implied_isa_turn(" ".join(text.strip().split()))
        except Exception:  # noqa: BLE001 — reasoning must never break a turn
            result = None
        if result is not None:
            result["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
            result["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
            return result
        return super().chat(text, session_id)
