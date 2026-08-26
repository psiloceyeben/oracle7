#!/usr/bin/env python3
"""Runtime G — capability cycle 2: compare-two-things (additive over F).

Two gated bundles (public topics or user documents), a definitional lead for
each side with addresses, and a DERIVED contrast analysis carrying rule and
premises drawn from both sides. Typed withhold names the missing side."""

from __future__ import annotations

import re
import time

from oracle_release_runtime_f import OracleReleaseRuntimeF
from stage5m13e8_relevance_gate_v1 import gate_bundle
from stage5m13e8_paragraph_compiler_v1 import _definitional_score

COMPARE = re.compile(
    r"^(?:please |can you )?compare (?:the |a |an )?(?P<x>.+?) (?:and|with|to) (?:the |a |an |my document )?(?P<y>.+?)[.?!]?$"
    r"|^what is the difference between (?:the |a |an )?(?P<x2>.+?) and (?:the |a |an |my document )?(?P<y2>.+?)[.?!]?$"
    r"|^how do (?:the )?(?P<x3>.+?) and (?:the )?(?P<y3>.+?) differ[.?!]?$"
    r"|^(?P<x4>[\w '-]+?) versus (?P<y4>[\w '-]+?)[.?!]?$",
    re.I)


class OracleReleaseRuntimeG(OracleReleaseRuntimeF):
    def _side(self, topic: str, session_id: str) -> tuple[list[dict], str]:
        user = self.user_corpus.bundle(session_id, topic)
        if user:
            return user, topic
        admitted, _ = gate_bundle(topic, self._bundle(topic, n=5))
        return admitted, topic

    def _compare_turn(self, text: str, session_id: str) -> dict | None:
        match = COMPARE.match(text.strip())
        if not match:
            return None
        groups = match.groupdict()
        x = next((groups[k] for k in ("x", "x2", "x3", "x4") if groups.get(k)), "").strip()
        y = next((groups[k] for k in ("y", "y2", "y3", "y4") if groups.get(k)), "").strip()
        if not x or not y:
            return None
        side_x, _ = self._side(x, session_id)
        side_y, _ = self._side(y, session_id)
        missing = [t for t, s in ((x, side_x), (y, side_y)) if not s]
        if missing:
            return {"status": "withheld", "path": "capability:compare",
                    "response": f"I cannot compare these: no provenance-admitted material exists for "
                                f"{' or '.join(missing)}.",
                    "provenance": {"kind": "gated_comparison", "missing": missing}}
        lead_x = max(side_x, key=lambda c: _definitional_score(x, c["sentence"]))
        lead_y = max(side_y, key=lambda c: _definitional_score(y, c["sentence"]))
        # DERIVED contrast: distinctive content terms of each side's lead
        stop = {"the", "a", "an", "is", "are", "was", "in", "of", "and", "to", "that", "it", "on", "with", "as", "by", "or", "for"}
        words_x = {w.lower() for w in re.findall(r"[A-Za-z][\w'-]*", lead_x["sentence"])} - stop
        words_y = {w.lower() for w in re.findall(r"[A-Za-z][\w'-]*", lead_y["sentence"])} - stop
        only_x = sorted(words_x - words_y)[:4]
        only_y = sorted(words_y - words_x)[:4]
        shared = sorted((words_x & words_y) - {x.lower(), y.lower()})[:3]
        analysis = (f"Derived contrast: the {x} record is characterized by "
                    f"{', '.join(only_x) if only_x else 'no distinct terms'}; the {y} record by "
                    f"{', '.join(only_y) if only_y else 'no distinct terms'}"
                    + (f"; both records share {', '.join(shared)}" if shared else "") + ".")
        response = (f"According to {lead_x['page']}, {lead_x['sentence']} [{lead_x['claim_id']}] "
                    f"According to {lead_y['page']}, {lead_y['sentence']} [{lead_y['claim_id']}] "
                    f"{analysis} [derived:lead_term_contrast<-{lead_x['claim_id'][:12]},{lead_y['claim_id'][:12]}]")
        return {"status": "answered", "path": "capability:compare", "response": response,
                "provenance": {"kind": "gated_comparison", "x": x, "y": y,
                               "derived": {"rule": "lead_term_contrast",
                                           "premises": [lead_x["claim_id"], lead_y["claim_id"]]}}}

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        normalized = " ".join(text.strip().split())
        result = None
        try:
            result = self._compare_turn(normalized, session_id)
        except Exception:  # noqa: BLE001
            result = None
        if result is not None:
            result["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
            result["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
            state = self.dialogue.setdefault(session_id, {})
            state["last_result"] = {k: result.get(k) for k in ("path", "provenance", "status")}
            return result
        return super().chat(text, session_id)
