#!/usr/bin/env python3
"""Runtime AK - decline rather than guess an unsupported split (additive over AJ).

M39 failed on 12 Latin binomials:

    "Is cinnamomum loureirii loureirii?"
        AJ -> x='cinnamomum', y='loureirii loureirii'
        -> emits an EXCLUSION about "cinnamomum"

A species epithet is not an independent lemma, so no split point has lexical support.
AJ then fell back to the loose pattern and took the shortest split, producing a confident
answer about the wrong subject. Guessing a split without lexical support is how a
malformed question becomes a wrong answer instead of a refusal.

AK declines instead. For a determiner-free multi-word body, if no split has BOTH sides
present in the admitted record, the route returns None and the question falls through to
the rest of the chain. Silence is the correct output where the record cannot even
identify the terms.

This is a scope declaration enforced by the runtime rather than by the test sample: the
route serves head-containment questions whose head is a term the corpus carries, and it
now says nothing outside that, rather than being sampled only inside it. No neural network.
"""

from __future__ import annotations

import re

from oracle_release_runtime_aj import OracleReleaseRuntimeAJ, _BODY, MAX_WORDS
from oracle_release_runtime_af import KIND_Q_STRICT, _FILLER, _LEAD


class OracleReleaseRuntimeAK(OracleReleaseRuntimeAJ):
    def _parse_kind(self, text: str):
        t = " ".join(text.strip().split())
        t = " ".join(_FILLER.sub("", _LEAD.sub("", t)).split())
        match = KIND_Q_STRICT.match(t)
        if match:
            return self._valid_pair(match.group("x").strip().lower(),
                                    match.group("y").strip().lower())
        body_match = _BODY.match(t)
        if not body_match:
            return super(OracleReleaseRuntimeAJ, self)._parse_kind(text)
        words = body_match.group("body").strip().lower().split()
        if len(words) < 2 or len(words) > MAX_WORDS:
            return super(OracleReleaseRuntimeAJ, self)._parse_kind(text)
        if len(words) == 2:
            # single-word subject and target: no split ambiguity to resolve
            return self._valid_pair(words[0], words[1])
        chosen = None
        for cut in range(1, len(words)):
            pair = self._valid_pair(" ".join(words[:cut]), " ".join(words[cut:]))
            if pair is None:
                continue
            if self._present(pair[0]) and self._present(pair[1]):
                chosen = pair                      # prefer the LONGEST supported subject
        return chosen                              # None => decline, never guess
