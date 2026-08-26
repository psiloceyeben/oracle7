#!/usr/bin/env python3
"""Runtime AA — evidence-mined tiered cues for the explanatory routes (additive over Z).

M24's cue inventories were authored by guessing and the route stress test showed
the cost: how 10%, what_causes 28%, when 65% answer-rate. Iteration 4 mined
400,000 admitted sentences to find the forms the corpus ACTUALLY uses, and the
guesses had missed the most frequent ones outright:

  cause   : "led to" 1,117 · "so that" 1,012 · "as a result" 372 · "result of" 340
  process : "uses" 3,647 · "when the" 3,580 · "is called" 3,108 · "is/are formed" 263
  date    : "was released" 1,038 · "was built" 560 · "took place" 323
            ("built" was in the question regex but NOT in the inception cues at all)

Widening naively would trade precision for recall, so the cues are TIERED: a
specific form is preferred, and a broad one is consulted only when no specific
form matches. Frequency alone does not promote a cue — "makes" is frequent but
weakly causal, so it sits in the last tier.

Also fixes a sentence-quality defect the harness surfaced: sentence extraction
sometimes yields a fragment starting mid-parenthetical ("1938) is a psychologist
..."), which is cited and correct but reads as broken. Such fragments are
skipped in favour of the next admitted sentence."""

from __future__ import annotations

import re
import time

from oracle_release_runtime_z import OracleReleaseRuntimeZ

# tier 1 = explicitly the relation; tier 2 = strongly indicative; tier 3 = weak fallback
CAUSE_TIERS = [
    re.compile(r"\b(caused by|is caused|are caused|due to|results? from|triggered by|produced by)\b", re.I),
    re.compile(r"\b(because|led to|leads to|as a result|result of|gives rise to)\b", re.I),
    re.compile(r"\b(causes|makes|so that|therefore|happens when|occurs when)\b", re.I),
]
PROCESS_TIERS = [
    re.compile(r"\b(happens when|occurs when|forms? when|is formed|are formed|works? by|by which|through which)\b", re.I),
    re.compile(r"\b(process|is made|are made|begins when|starts when|when there is)\b", re.I),
    re.compile(r"\b(uses|when the|is called|moves|produces)\b", re.I),
]
# Date cues are conditioned on the VERB ACTUALLY ASKED, not a fixed tier order.
# A flat specific-first ordering regressed "When did WWII start?" to "The Tanggu
# Truce ... was signed in 1933" because `was signed` outranked `began`. The asked
# verb is the correct selector: it says which event the questioner means.
VERB_CUES = {
    "start": [r"\b(began|begun|started|broke out|was launched)\b", r"\b(was founded|was established|was created)\b"],
    "begin": [r"\b(began|begun|started|broke out|was launched)\b", r"\b(was founded|was established|was created)\b"],
    "end": [r"\b(ended|finished|collapsed|surrendered|was dissolved)\b"],
    "found": [r"\b(was founded|was established|was created|founded)\b"],
    "built": [r"\b(was built|was constructed|built between|was completed)\b"],
    "build": [r"\b(was built|was constructed|built between|was completed)\b"],
    "discover": [r"\b(was discovered|discovered)\b"],
    "invent": [r"\b(was invented|invented)\b"],
    "born": [r"\b(was born|born)\b"],
    "die": [r"\b(died|was killed)\b"],
    "happen": [r"\b(took place|happened|occurred|was held)\b"],
    "occur": [r"\b(took place|happened|occurred|was held)\b"],
}
INCEPT_GENERAL = [
    re.compile(r"\b(began|begun|started|was founded|was built|was established|was created|took place|broke out)\b", re.I),
    re.compile(r"\b(opened|ended|was released|was signed|was discovered|was invented|born|died)\b", re.I),
]
YEAR = re.compile(r"\b(1[0-9]{3}|20[0-2][0-9])\b")
FRAGMENT = re.compile(r"^\s*(?:[a-z]|\d{1,4}\s*[)\]])")   # "1938) is ..." / lowercase start


class OracleReleaseRuntimeAA(OracleReleaseRuntimeZ):
    def _pick_tiered(self, topic: str, tiers: list, *, require_year: bool = False) -> list[dict]:
        bundle = self._bundle(topic, n=60)
        if not bundle:
            singular = topic[:-1] if topic.endswith("s") and not topic.endswith("ss") else None
            if singular and len(singular) > 2:
                bundle = self._bundle(singular, n=60)
            if not bundle:
                return []
        usable = [c for c in bundle if not FRAGMENT.match(str(c.get("sentence") or ""))]
        if not usable:
            usable = bundle
        for tier in tiers:                       # specific first, broad only as fallback
            hits = []
            for claim in usable:
                sentence = str(claim.get("sentence") or "")
                if require_year and not YEAR.search(sentence):
                    continue
                if tier.search(sentence):
                    hits.append(claim)
            if hits:
                return hits
        return []

    def _explanatory_turn(self, text: str) -> dict | None:   # override Y
        from oracle_release_runtime_y import CAUSE_Q, HOW_Q, WHEN_Q
        stripped = " ".join(text.strip().split())

        match = CAUSE_Q.match(stripped)
        if match:
            topic = match.group("t").strip()
            return self._render(topic, self._pick_tiered(topic, CAUSE_TIERS),
                                "cause", "capability:what_causes", f"what causes {topic}")

        match = HOW_Q.match(stripped)
        if match:
            topic = match.group("t").strip()
            return self._render(topic, self._pick_tiered(topic, PROCESS_TIERS),
                                "process", "capability:how_does", f"how {topic} works")

        match = WHEN_Q.match(stripped)
        if match:
            topic = match.group("t").strip()
            verb = (match.group("v") or "").lower()
            tiers = []
            for stem, patterns in VERB_CUES.items():
                if verb.startswith(stem):
                    tiers = [re.compile(pat, re.I) for pat in patterns]
                    break
            tiers = tiers + INCEPT_GENERAL
            hits = self._pick_tiered(topic, tiers, require_year=True) \
                or self._pick_tiered(topic, [YEAR], require_year=True)
            return self._render(topic, hits, "inception", "capability:when_did",
                                f"when {topic} {match.group('v')}")
        return None

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
