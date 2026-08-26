#!/usr/bin/env python3
"""Runtime AE - answer kind questions from the WordNet evidence corpus (additive over AD).

The live chain cannot answer compound-head kind questions:

    Is a gray whale a whale?               -> act:clarify
    Is a thymus gland a gland?             -> act:clarify
    Is a superior mesenteric artery an artery? -> act:clarify

M30 measured that the corroboration gate cannot fix this - AUC 0.8067 held out on
WordNet compounds, and only 3.0% coverage at a 1% false-answer budget. A curated
lexical hierarchy answers it directly instead.

Why this is admissible where a graph gap is not: WordNet hypernym chains are
complete, terminating at entity.n.01. So for a lemma the corpus HAS, a head noun
absent from its closure is POSITIVELY EXCLUDED, not merely unattested. That is
the one condition under which a negative answer is honest, and it is exactly what
the open-world law otherwise forbids concluding. For a lemma the corpus lacks,
this route says nothing and falls through.

Strictly additive: runs only where the existing chain declined to answer, so no
sealed panel can regress. No neural network; no LM call.
"""

from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path

from oracle_release_runtime_ad import OracleReleaseRuntimeAD

WORDNET_CORPUS = ("/opt/oracle-clm/fable-content/oracle-m-series-2026-08-15"
                  "/m31_wordnet_corpus_v1.sqlite3")

_DP = r"(?:an?\s+|the\s+|some\s+)?"
KIND_Q = re.compile(
    r"^(?:is|are)\s+" + _DP + r"(?P<x>[a-z][a-z '\-]*?)\s+" + _DP +
    r"(?:kind|type|sort)?\s*(?:of\s+)?" + _DP + r"(?P<y>[a-z][a-z '\-]*?)\s*[.?!]*$", re.I)
_FILLER = re.compile(r"\b(?:do you think|would you say|is it true that|really|actually|"
                     r"even|also|just|by any chance|technically|basically)\b", re.I)
_LEAD = re.compile(r"^(?:so|well|hey|um|please|tell me|i wonder|question:)[\s,]+", re.I)


def _forms(word: str) -> list:
    w = word.strip().lower()
    out = [w]
    if w.endswith("ies") and len(w) > 4:
        out.append(w[:-3] + "y")
    if w.endswith("es") and len(w) > 3:
        out.append(w[:-2])
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        out.append(w[:-1])
    return list(dict.fromkeys(out))


class OracleReleaseRuntimeAE(OracleReleaseRuntimeAD):
    def __init__(self, *args, wordnet_corpus: str = WORDNET_CORPUS, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._wn = None
        path = Path(wordnet_corpus)
        if path.exists():
            try:
                self._wn = sqlite3.connect(
                    f"file:{path}?mode=ro&immutable=1", uri=True, check_same_thread=False)
            except sqlite3.Error:
                self._wn = None

    def _present(self, lemma: str) -> str | None:
        if self._wn is None:
            return None
        for form in _forms(lemma):
            row = self._wn.execute(
                "SELECT lemma FROM lemma_present WHERE lemma=?", (form,)).fetchone()
            if row:
                return row[0]
        return None

    def _closure_hit(self, lemma: str, target: str):
        for form in _forms(target):
            row = self._wn.execute(
                "SELECT hypernym,depth,sense FROM lemma_closure WHERE lemma=? AND hypernym=?",
                (lemma, form)).fetchone()
            if row:
                return row
        return None

    def _chain_for(self, lemma: str, limit: int = 6) -> list:
        rows = self._wn.execute(
            "SELECT hypernym FROM lemma_closure WHERE lemma=? ORDER BY depth DESC LIMIT ?",
            (lemma, limit)).fetchall()
        return [r[0] for r in rows]

    def _wordnet_turn(self, text: str) -> dict | None:
        if self._wn is None:
            return None
        t = " ".join(text.strip().split())
        t = " ".join(_FILLER.sub("", _LEAD.sub("", t)).split())
        match = KIND_Q.match(t)
        if not match:
            return None
        x = match.group("x").strip().lower()
        y = match.group("y").strip().lower()
        if not x or not y or x == y or len(x) < 2 or len(y) < 2:
            return None
        lemma = self._present(x)
        if lemma is None:
            return None  # corpus has no entry: say nothing rather than infer from absence
        hit = self._closure_hit(lemma, y)
        article_x = "an" if x[:1] in "aeiou" else "a"
        article_y = "an" if y[:1] in "aeiou" else "a"
        if hit is not None:
            hypernym, _depth, sense = hit
            chain = self._chain_for(lemma)
            shown = " -> ".join(list(reversed(chain))[:5] + [lemma]) if chain else lemma
            return {
                "status": "answered",
                "path": "wordnet_kind_direct",
                "response": (f"Yes. The lexical record places {lemma} under {hypernym}: "
                             f"{shown}. On that record {article_x} {x} is {article_y} {y}. "
                             f"[cited:wordnet:{sense}]"),
                "provenance": {"kind": "lexical_corpus", "corpus": "wordnet",
                               "relation": "hypernym", "lemma": lemma,
                               "hypernym": hypernym, "sense": sense},
            }
        chain = self._chain_for(lemma)
        shown = " -> ".join(list(reversed(chain))[:5] + [lemma]) if chain else lemma
        return {
            "status": "answered",
            "path": "wordnet_kind_excluded",
            "response": (f"No. The lexical record places {lemma} on a different line: "
                         f"{shown}. {y.capitalize()} does not appear anywhere in that chain, "
                         f"and the chain is complete, so this is an exclusion rather than a "
                         f"gap in the record. [cited:wordnet:{lemma}]"),
            "provenance": {"kind": "lexical_corpus", "corpus": "wordnet",
                           "relation": "hypernym_excluded", "lemma": lemma,
                           "chain": chain},
        }

    def chat(self, text: str, session_id: str = "default") -> dict:
        result = super().chat(text, session_id)
        if str(result.get("status", "")) == "answered":
            return result
        started = time.perf_counter()
        try:
            answer = self._wordnet_turn(text)
        except Exception:  # noqa: BLE001
            answer = None
        if answer is None:
            return result
        answer["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
        answer["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
        return answer
