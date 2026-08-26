#!/usr/bin/env python3
"""Runtime Y — M24 explanatory routes (additive over X): how / what-causes / when.

Live probing (2026-08-20) found three of the most common question forms in
English had no working route, while the admitted corpus plainly contained the
answers:

  "How does a volcano erupt?"  -> clarify   (corpus: "When there is enough
                                             pressure, the volcano erupts.")
  "What causes earthquakes?"   -> withheld  (corpus: "Earthquakes are caused by
                                             tectonic movements in the Earth's crust.")
  "When did World War 2 start?"-> withheld  (corpus: "The war in Europe began when
                                             Nazi Germany invaded Poland on 1 September 1939.")

So this is a ROUTING gap, not a knowledge gap. Each route resolves the topic
through the existing anchor store, pulls the page's admitted sentences via the
existing bundle primitive, and selects the sentence whose form actually answers
the question (causal cue / process cue / date+inception cue). Selection is
cue-based and deterministic — it never composes a claim, it only chooses which
admitted sentence to cite, and abstains when none matches. Citations ride the
normal claim-id path."""

from __future__ import annotations

import re
import time

from oracle_release_runtime_x import OracleReleaseRuntimeX

HOW_Q = re.compile(r"^how\s+(?:does|do|did|is|are|can)\s+(?:an?\s+|the\s+)?"
                   r"(?P<t>[\w' \-]+?)\s+(?:work|works|erupt|erupts|happen|happens|form|forms|"
                   r"occur|occurs|made|grow|grows|move|moves|function|functions)\b[^?]*\??$", re.I)
CAUSE_Q = re.compile(r"^(?:what\s+causes?|what\s+makes?|why\s+(?:do|does|are|is))\s+"
                     r"(?:an?\s+|the\s+)?(?P<t>[\w' \-]+?)\s*(?:happen|occur|erupt|form|work)?\s*\??$", re.I)
WHEN_Q = re.compile(r"^when\s+(?:did|was|does|do|were)\s+(?:the\s+)?(?P<t>[\w' \-]+?)\s+"
                    r"(?P<v>start|begin|end|happen|occur|founded|built|discovered|invented|born|die)\w*\s*\??$", re.I)

CUE_CAUSE = re.compile(r"\b(caused by|causes|because|due to|results? from|produced by|"
                       r"triggered by|happens when|occurs when|when .{3,40} (?:meet|collide|move))\b", re.I)
CUE_PROCESS = re.compile(r"\b(happens when|occurs when|forms? when|when there is|process|"
                         r"works? by|is made|are made|by which|through which)\b", re.I)
YEAR = re.compile(r"\b(1[0-9]{3}|20[0-2][0-9])\b")
CUE_INCEPT = re.compile(r"\b(began|begun|started|founded|opened|created|established|"
                        r"broke out|ended|discovered|invented|born|died)\b", re.I)

BUNDLE_N = 60


class OracleReleaseRuntimeY(OracleReleaseRuntimeX):
    def _pick(self, topic: str, cue, *, require_year: bool = False,
              second_cue=None) -> list[dict]:
        """Admitted sentences from the topic's page whose FORM answers the question."""
        bundle = self._bundle(topic, n=BUNDLE_N)
        if not bundle:
            # plural surface ("what causes earthquakes") vs singular page title
            singular = topic[:-1] if topic.endswith("s") and not topic.endswith("ss") else None
            if singular and len(singular) > 2:
                bundle = self._bundle(singular, n=BUNDLE_N)
            if not bundle:
                return []
        hits = []
        for claim in bundle:
            sentence = claim.get("sentence") or ""
            if require_year and not YEAR.search(sentence):
                continue
            if second_cue is not None and not second_cue.search(sentence):
                continue
            if cue.search(sentence):
                hits.append(claim)
        return hits

    def _explanatory_turn(self, text: str) -> dict | None:
        stripped = " ".join(text.strip().split())

        match = CAUSE_Q.match(stripped)
        if match:
            topic = match.group("t").strip()
            hits = self._pick(topic, CUE_CAUSE)
            return self._render(topic, hits, "cause", "capability:what_causes",
                                f"what causes {topic}")

        match = HOW_Q.match(stripped)
        if match:
            topic = match.group("t").strip()
            hits = self._pick(topic, CUE_PROCESS)
            return self._render(topic, hits, "process", "capability:how_does",
                                f"how {topic} works")

        match = WHEN_Q.match(stripped)
        if match:
            topic = match.group("t").strip()
            hits = self._pick(topic, CUE_INCEPT, require_year=True) \
                or self._pick(topic, YEAR)
            return self._render(topic, hits, "inception", "capability:when_did",
                                f"when {topic} {match.group('v')}")

        return None

    def _render(self, topic: str, hits: list[dict], kind: str, path: str,
                asked: str) -> dict:
        if not hits:
            return {"status": "withheld", "path": path,
                    "response": f"The admitted record for {topic} contains no statement that "
                                f"answers {asked}. I will not infer one.",
                    "provenance": {"kind": "selected_evidence", "selector": kind,
                                   "topic": topic, "result": "no_matching_statement"}}
        lead = hits[0]
        parts = [f"According to {lead['page']}, {lead['sentence']} [{lead['claim_id']}]"]
        for extra in hits[1:2]:
            parts.append(f"{extra['page']} also records: {extra['sentence']} [{extra['claim_id']}]")
        return {"status": "answered", "path": path, "response": " ".join(parts),
                "provenance": {"kind": "selected_evidence", "selector": kind, "topic": topic,
                               "premises": [h["claim_id"] for h in hits[:2]]}}

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        result = None
        try:
            result = self._explanatory_turn(text)
        except Exception:  # noqa: BLE001
            result = None
        if result is not None:
            result["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
            result["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
            return result
        return super().chat(text, session_id)
