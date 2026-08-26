#!/usr/bin/env python3
"""Evidential plant V2 - two repairs found by inspection, to be DEMONSTRATED by M60b.

V1 defects (oracle_siblings_bed2_v1.SiblingEvidential):
  1. PROBE conversion: a declarative claim ("a beagle is an animal") does not match the
     question head regex, so it becomes "Summarize a beagle is an animal." - a garbage
     probe. Repair: the declarative->interrogative KIND construction
     "X is a Y" -> "Is X a Y?" (typed, article-preserving).
  2. POLARITY: the rendering says "What you heard is supported" whenever the record
     licenses direct/inferred evidence - without checking whether the warranted answer
     is NO. A refuted claim would render as supported next to a No. Repair: polarity
     check; refuted claims render "not supported by the record".

Everything else inherited unchanged: same evidential typing, same [ev:] tags, same
digest law (the chain answers; the plant only re-reads and re-renders).
No neural network; no LM call.
"""

from __future__ import annotations

import re

from oracle_siblings_bed2_v1 import SiblingEvidential, HEARSAY, DIRECT, INFER

DECL_KIND = re.compile(
    r"^(?:an?\s+)?(?P<x>[a-z][a-z\s\-]{1,40}?)\s+(?:is|are)\s+(?:an?\s+)?(?P<y>[a-z][a-z\s\-]{1,40})$",
    re.I)
NEG_OPEN = re.compile(r"^\s*no\b", re.I)


def _art(w: str) -> str:
    return "an" if w[:1].lower() in "aeiou" else "a"


class SiblingEvidentialV2(SiblingEvidential):
    """V1 + declarative->kind-question construction + polarity-coherent rendering."""

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        marked, proposition = None, s
        for name, pat in (("hearsay", HEARSAY), ("direct", DIRECT), ("inferred", INFER)):
            m = pat.match(s)
            if m:
                marked, proposition = name, m.group("p").strip()
                break
        if marked:
            if re.match(r"^(is|are|what|who|when|how)\b", proposition, re.I):
                probe = proposition
            else:
                dk = DECL_KIND.match(proposition)
                if dk:                                   # repair 1: the KIND construction
                    x, y = dk.group("x").strip(), dk.group("y").strip()
                    probe = f"Is {_art(x)} {x} {_art(y)} {y}?"
                else:
                    probe = f"Summarize {proposition}."
            self._pending_conversion[session_id] = {
                "construction": f"EVIDENTIAL:{marked}", "from": s[:80], "to": probe[:80],
                "produced_by": "sibling:evidential_v2"}
            result = super(SiblingEvidential, self).chat(probe, session_id)
        else:
            result = super(SiblingEvidential, self).chat(s, session_id)
        ev = self._evidential_of(result)
        result["evidential"] = {"input_marked": marked, "answer_licensed": ev}
        if result.get("status") == "answered":
            tag = {"direct": "[ev:direct]", "inferred": "[ev:inferred]",
                   "reported": "[ev:reported]", "unknown": "[ev:unknown]"}[ev]
            answer = str(result.get("response", ""))
            refuted = bool(NEG_OPEN.match(answer))       # repair 2: polarity
            if marked == "hearsay" and ev in ("direct", "inferred"):
                verdict = ("What you heard is not supported by the record. "
                           if refuted else "What you heard is supported. ")
                result["response"] = f"{tag} {verdict}" + answer
            else:
                result["response"] = f"{tag} " + answer
        hist = getattr(self, "_paths", {}).get(session_id)
        if hist:
            hist[-1]["evidential"] = result["evidential"]
        return result
