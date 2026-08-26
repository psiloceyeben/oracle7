#!/usr/bin/env python3
"""Runtime AJ - lexicon-informed splitting for determiner-free questions (additive over AI).

M38 passed eight columns and still mis-parsed this:

    "Is hand luggage luggage?"  ->  x='hand', y='luggage luggage'
    -> "No. The record classifies HAND under forepaw, paw, animal foot..."

With no determiner the strict pattern cannot anchor, and the loose pattern's non-greedy
subject takes the shortest split. This is the M31 defect resurfacing in the form the M31
fix did not cover, and no panel saw it because every generated question carries
determiners ("Is a X a Y?"). The route's own domain includes determiner-free forms;
the test distribution did not.

Fix: when no determiner is available to anchor the split, use the admitted record as the
lexicon. Enumerate every split point and choose the longest subject for which BOTH sides
are lemmas the corpus carries. Purely structural, no heuristic weighting - the record
already knows which strings are terms.

    "Is hand luggage luggage?"
        split 1: x='hand'         y='luggage luggage'   -> y not a lemma, rejected
        split 2: x='hand luggage' y='luggage'           -> both lemmas, ACCEPTED

Determiner-bearing forms still take the strict path unchanged. No neural network.
"""

from __future__ import annotations

import re

from oracle_release_runtime_ai import OracleReleaseRuntimeAI
from oracle_release_runtime_af import KIND_Q_STRICT, _FILLER, _LEAD
from oracle_release_runtime_ae import _forms

_BODY = re.compile(
    r"^(?:is|are)\s+(?:(?:an?|the|some)\s+)?(?P<body>[a-z][a-z '\-]+?)\s*[.?!]*$", re.I)
MAX_WORDS = 8


class OracleReleaseRuntimeAJ(OracleReleaseRuntimeAI):
    def _valid_pair(self, x: str, y: str):
        if not x or not y or x == y or len(x) < 2 or len(y) < 2:
            return None
        if set(_forms(x)) & set(_forms(y)):
            return None
        return x, y

    def _parse_kind(self, text: str):
        t = " ".join(text.strip().split())
        t = " ".join(_FILLER.sub("", _LEAD.sub("", t)).split())
        match = KIND_Q_STRICT.match(t)
        if match:
            return self._valid_pair(match.group("x").strip().lower(),
                                    match.group("y").strip().lower())
        body_match = _BODY.match(t)
        if not body_match:
            return super()._parse_kind(text)
        words = body_match.group("body").strip().lower().split()
        if len(words) < 2 or len(words) > MAX_WORDS:
            return super()._parse_kind(text)
        chosen = None
        for cut in range(1, len(words)):
            x = " ".join(words[:cut])
            y = " ".join(words[cut:])
            pair = self._valid_pair(x, y)
            if pair is None:
                continue
            if self._present(x) and self._present(y):
                chosen = pair            # keep iterating: prefer the LONGEST subject
        if chosen is not None:
            return chosen
        return super()._parse_kind(text)
