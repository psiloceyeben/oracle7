#!/usr/bin/env python3
"""Runtime W — robust implied-knowledge turn (additive over V).

Same capability as V (transitive kind), two robustness upgrades:
  * reasoner v2 (sense-dominance pruning; recovers true chains v1 blocked);
  * a widened, normalized parser that accepts many more natural phrasings
    ("Are dogs animals?", "Is the robin really a bird?", "Do you think a
    beagle is an animal?", "a kind/type/sort of").
Still: cite direct edge, derive a shown chain, or abstain honestly."""

from __future__ import annotations

import re
import time

from oracle_release_runtime_v import OracleReleaseRuntimeV
from stage5m21_transitive_reasoner_v2 import _norm, chain_isa, direct_isa, render_chain

# strip conversational filler before matching
_FILLER = re.compile(
    r"\b(?:do you think|would you say|is it true that|is it the case that|"
    r"really|actually|even|still|also|just|by any chance|technically|"
    r"essentially|basically)\b", re.I)
_LEAD = re.compile(r"^(?:so|well|hey|um|please|tell me|i wonder|question:)[\s,]+", re.I)
# an embedded-question frame ("do you think X is Y") — only these license the
# declarative pattern, so plain statements ("The Moon is a planet.") are NOT
# hijacked from the summarize/definitional routes.
_EMBEDDED = re.compile(r"\b(?:do you think|would you say|is it true that|is it the case that)\b", re.I)

# A genuine kind-question needs a determiner before the predicate nominal
# ("is a beagle AN animal") or bare-plural agreement ("are dogs animals"); this
# keeps predicate-adjective / comparison questions ("is the Moon bigger than
# Mars?") from being read as IsA queries.
_DETP = r"(?:an?|the|some|(?:an?\s+)?(?:kind|type|sort)\s+of)"
# singular: "is <det>? X <det> Y ?"
ISA_Q_SING = re.compile(
    rf"^is\s+(?:{_DETP}\s+)?(?P<x>[a-z][a-z '\-]*?)\s+{_DETP}\s+(?P<y>[a-z][a-z '\-]*?)\s*[.?!]*$", re.I)
# plural: "are Xs Ys ?"  (both bare plurals)
ISA_Q_PLUR = re.compile(
    r"^are\s+(?P<x>[a-z][a-z'\-]*?s)\s+(?P<y>[a-z][a-z'\-]*?s)\s*[.?!]*$", re.I)
# declarative, embedded-question only: "<det>? X is <det> Y"
ISA_DECL = re.compile(
    rf"^(?:{_DETP}\s+)?(?P<x>[a-z][a-z '\-]*?)\s+(?:is|are)\s+{_DETP}\s+(?P<y>[a-z][a-z '\-]*?)\s*[.?!]*$", re.I)
_DET = re.compile(r"^(?:an?|the|some)\s+(?:(?:kind|type|sort)\s+of\s+)?|^(?:kind|type|sort)\s+of\s+", re.I)

_STOP_Y = {"thing", "one", "example", "sort", "kind", "type", "it", "that", "this"}
_REL_WORDS = re.compile(r"\b(?:than|more|less|bigger|smaller|larger|faster|slower|"
                        r"better|worse|taller|shorter|older|younger|same)\b", re.I)


def _peel(span: str) -> str:
    prev = None
    s = span.strip().lower()
    while s != prev:  # repeatedly strip stacked determiners ("a kind of a ...")
        prev = s
        s = _DET.sub("", s).strip()
    return s


class OracleReleaseRuntimeW(OracleReleaseRuntimeV):
    def _normalize_isa(self, text: str) -> str:
        t = " ".join(text.strip().split())
        t = _LEAD.sub("", t)
        t = _FILLER.sub("", t)
        return " ".join(t.split())

    def _implied_isa_turn(self, text: str) -> dict | None:  # override V
        normalized = self._normalize_isa(text)
        if _REL_WORDS.search(normalized):  # comparison, not a kind-question
            return None
        match = ISA_Q_SING.match(normalized) or ISA_Q_PLUR.match(normalized)
        if match is None and _EMBEDDED.search(text):
            match = ISA_DECL.match(normalized)
        if not match:
            return None
        x = _peel(match.group("x"))
        y = _peel(match.group("y"))
        if (not x or not y or x == y or len(x) < 2 or len(y) < 2
                or y in _STOP_Y or x in _STOP_Y or x.split()[-1] == _norm(y)):
            return None
        cs = self.commonsense

        direct = direct_isa(cs, x, y)
        if direct is not None:
            return {"status": "answered", "path": "conceptnet_isa_direct",
                    "response": f"Yes — the admitted record states it directly: "
                                f"{cs.render_edge(direct)} [{direct['provenance']}]",
                    "provenance": {"kind": "commonsense_edge", "relation": "IsA",
                                   "premises": [direct["provenance"]]}}

        path = chain_isa(cs, x, y)
        if path is not None:
            steps = render_chain(cs, path)
            premises = [edge["provenance"] for edge in path]
            tag = "[derived:transitive_isa<-" + ",".join(p[:24] for p in premises) + "]"
            ax = "an" if x[:1] in "aeiou" else "a"
            ay = "an" if y[:1] in "aeiou" else "a"
            return {"status": "answered", "path": "conceptnet_isa_derived",
                    "response": f"By the admitted record, in steps: {steps}. Therefore, if "
                                f"kind is transitive, {ax} {x} is {ay} {y}. {tag}",
                    "provenance": {"kind": "derived", "rule": "transitive_isa",
                                   "hops": len(path), "premises": premises}}

        ax = "an" if x[:1] in "aeiou" else "a"
        ay = "an" if y[:1] in "aeiou" else "a"
        return {"status": "withheld", "path": "conceptnet_isa_derived",
                "response": f"The admitted record does not establish that {ax} {x} is "
                            f"{ay} {y}, directly or by a chain of kind within 3 steps.",
                "provenance": {"kind": "derived", "rule": "transitive_isa", "result": "no_chain"}}

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        result = None
        try:
            result = self._implied_isa_turn(text)
        except Exception:  # noqa: BLE001
            result = None
        if result is not None:
            result["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
            result["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
            return result
        # skip V's _implied_isa_turn (we overrode it); go straight to U's chain
        return super(OracleReleaseRuntimeV, self).chat(text, session_id)
