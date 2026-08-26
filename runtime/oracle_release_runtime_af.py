#!/usr/bin/env python3
"""Runtime AF - corrected kind-question parser over the WordNet corpus (additive over AE).

M31 FAILED and the failure is preserved. Its parser used two non-greedy
quantifiers, so the shortest possible subject matched:

    "Is a gray whale a whale?"  ->  x='gray', y='whale a whale'
    "Is a sea horse a horse?"   ->  x='sea',  y='horse a horse'

Coverage was therefore 0/284. Worse, 258 questions were answered with a confident
EXCLUSION computed over mis-parsed terms - a wrong answer is a more serious defect
than no answer, and the panel's soundness column was vacuous rather than clean.

Fix: require a determiner before the target. That forces the subject to backtrack
to the full compound, because "whale" cannot satisfy an obligatory article slot.
A determiner-free form ("Are petals flowers?") has no second article to mis-split,
so it falls back to the permissive pattern safely.

    strict: Is a [gray whale] a [whale]?      determiner before y is REQUIRED
    loose:  Are [petals] [flowers]?           only when strict does not match

Everything else - corpus, closure lookup, exclusion semantics, additive dispatch -
is inherited from AE unchanged. No neural network; no LM call.
"""

from __future__ import annotations

import re

from oracle_release_runtime_ae import OracleReleaseRuntimeAE, _forms

_DET = r"(?:an?|the|some)\s+"
KIND_Q_STRICT = re.compile(
    r"^(?:is|are)\s+(?:" + _DET + r")?(?P<x>[a-z][a-z '\-]*?)\s+" + _DET +
    r"(?:(?:kind|type|sort)\s+of\s+)?(?P<y>[a-z][a-z '\-]+?)\s*[.?!]*$", re.I)
KIND_Q_LOOSE = re.compile(
    r"^(?:is|are)\s+(?:" + _DET + r")?(?P<x>[a-z][a-z '\-]*?)\s+"
    r"(?:(?:kind|type|sort)\s+of\s+)?(?P<y>[a-z][a-z '\-]+?)\s*[.?!]*$", re.I)
_FILLER = re.compile(r"\b(?:do you think|would you say|is it true that|really|actually|"
                     r"even|also|just|by any chance|technically|basically)\b", re.I)
_LEAD = re.compile(r"^(?:so|well|hey|um|please|tell me|i wonder|question:)[\s,]+", re.I)


class OracleReleaseRuntimeAF(OracleReleaseRuntimeAE):
    def _parse_kind(self, text: str):
        t = " ".join(text.strip().split())
        t = " ".join(_FILLER.sub("", _LEAD.sub("", t)).split())
        match = KIND_Q_STRICT.match(t) or KIND_Q_LOOSE.match(t)
        if not match:
            return None
        x = match.group("x").strip().lower()
        y = match.group("y").strip().lower()
        if not x or not y or x == y or len(x) < 2 or len(y) < 2:
            return None
        if set(_forms(x)) & set(_forms(y)):
            return None
        return x, y

    def _wordnet_turn(self, text: str) -> dict | None:
        if self._wn is None:
            return None
        parsed = self._parse_kind(text)
        if parsed is None:
            return None
        x, y = parsed
        lemma = self._present(x)
        if lemma is None:
            return None  # corpus has no entry: say nothing rather than infer from absence
        hit = self._closure_hit(lemma, y)
        article_x = "an" if x[:1] in "aeiou" else "a"
        article_y = "an" if y[:1] in "aeiou" else "a"
        chain = self._chain_for(lemma)
        shown = " -> ".join(list(reversed(chain))[:5] + [lemma]) if chain else lemma
        if hit is not None:
            hypernym, _depth, sense = hit
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
        return {
            "status": "answered",
            "path": "wordnet_kind_excluded",
            "response": (f"No. The lexical record places {lemma} on a different line: "
                         f"{shown}. {y.capitalize()} does not appear anywhere in that chain, "
                         f"and the chain is complete, so this is an exclusion rather than a "
                         f"gap in the record. [cited:wordnet:{lemma}]"),
            "provenance": {"kind": "lexical_corpus", "corpus": "wordnet",
                           "relation": "hypernym_excluded", "lemma": lemma, "chain": chain},
        }
