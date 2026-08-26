#!/usr/bin/env python3
"""Evidential plant V3 - verdicts read from the RECORD's structure, never from text.

M60b demonstrated V2's remaining defect on h035:3: "Is a teddy bear a bear?" was
dispatched to summarize (a Teddy bear page exists), the summary carries no polarity
shape, and the text-regex polarity check rendered "supported" beside content that
refutes the claim. The repair is this plant's own founding principle applied strictly:
the answer's evidential comes from what the record LICENSES, and the record's kind
verdict is TYPED -

  SUPPORTED   provenance.kind == "derived" with rule transitive_isa, or
              kind == "commonsense_edge" with relation IsA, or
              kind == "lexical_corpus" with relation hypernym / hypernym_of
  REFUTED     kind == "lexical_corpus" with relation hypernym_excluded
  NO VERDICT  any other route (gated_summary, document_runtime, ...) - the record
              produced no kind verdict, so the plant says so: "The record does not
              settle what you heard." A summary does not license a kind verdict.

Probe conversion (declarative->kind question) inherited from V2. No text regex remains
in the verdict path. No neural network; no LM call.
"""

from __future__ import annotations

import re

from oracle_sibling_evidential_v2 import SiblingEvidentialV2, DECL_KIND, _art
from oracle_siblings_bed2_v1 import SiblingEvidential, HEARSAY, DIRECT, INFER


def kind_verdict(result: dict) -> str:
    prov = result.get("provenance") or {}
    kind = str(prov.get("kind", ""))
    rel = str(prov.get("relation", ""))
    rule = str(prov.get("rule", ""))
    if kind == "derived" and rule == "transitive_isa":
        return "supported"
    if kind == "commonsense_edge" and rel == "IsA":
        return "supported"
    if kind == "lexical_corpus" and rel in ("hypernym", "hypernym_of"):
        return "supported"
    if kind == "lexical_corpus" and rel == "hypernym_excluded":
        return "refuted"
    return "no_verdict"


class SiblingEvidentialV3(SiblingEvidentialV2):
    """V2's probe conversion + structural verdicts."""

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
                if dk:
                    x, y = dk.group("x").strip(), dk.group("y").strip()
                    probe = f"Is {_art(x)} {x} {_art(y)} {y}?"
                else:
                    probe = f"Summarize {proposition}."
            self._pending_conversion[session_id] = {
                "construction": f"EVIDENTIAL:{marked}", "from": s[:80], "to": probe[:80],
                "produced_by": "sibling:evidential_v3"}
            result = super(SiblingEvidential, self).chat(probe, session_id)
        else:
            result = super(SiblingEvidential, self).chat(s, session_id)
        ev = self._evidential_of(result)
        result["evidential"] = {"input_marked": marked, "answer_licensed": ev}
        if result.get("status") == "answered":
            tag = {"direct": "[ev:direct]", "inferred": "[ev:inferred]",
                   "reported": "[ev:reported]", "unknown": "[ev:unknown]"}[ev]
            answer = str(result.get("response", ""))
            if marked == "hearsay":
                verdict = kind_verdict(result)
                lead = {"supported": "What you heard is supported. ",
                        "refuted": "What you heard is not supported by the record. ",
                        "no_verdict": "The record does not settle what you heard. "}[verdict]
                result["evidential"]["verdict"] = verdict
                result["response"] = f"{tag} {lead}" + answer
            else:
                result["response"] = f"{tag} " + answer
        hist = getattr(self, "_paths", {}).get(session_id)
        if hist:
            hist[-1]["evidential"] = result["evidential"]
        return result
