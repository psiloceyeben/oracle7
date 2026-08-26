#!/usr/bin/env python3
"""K7b — recursive composition successor to K7 (frozen; not edited).

The K7 withheld one-shot failed 1/10 (stage5m13e6_k7_withheld_products_report_v1.json,
preserved): builders were first-match-wins and sub-clauses went only to the
plain K6 clause parser, so families never composed. K7b makes decomposition
RECURSIVE: every sub-clause request routes back through compile_text (with a
depth guard), so a connective can hold a relative, an appositive can hold an
attitude report, a measure can hold a possessive chain. Also: connective moved
ahead of existential (the F6 bypass that broke ablation attribution), a
broadened cleft (non-capitalized focus NPs), and the parenthetical attitude
construction ("X, Ferra said, Y")."""

from __future__ import annotations

import re

from stage5m13e2_construction_kernel import ClauseProgram
from stage5m13e2_construction_kernel_k7 import (
    ConstructionKernelK7, LinkedProgram, PRE_ADVERBS,
)

PARENTHETICAL_ATTITUDE = re.compile(
    r"^(.+?), ([A-Z]\w+) (said|says|believed|believes|claimed|claims), (.+?)\.?$")
CLEFT_ANY = re.compile(r"^It (was|is) (.+?) (who|that) (.+?)\.?$")
_MAX_DEPTH = 6


class ConstructionKernelK7b(ConstructionKernelK7):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._depth = 0

    # ── recursion: sub-clause requests re-enter the full builder stack ───
    def _clause(self, text: str):  # may now return LinkedProgram
        if self._depth >= _MAX_DEPTH:
            return super()._clause(text)
        self._depth += 1
        try:
            return self._compile_inner(text)
        finally:
            self._depth -= 1

    NUMERALS = {"one", "two", "three", "four", "five", "six", "seven",
                "eight", "nine", "ten"}

    def _plain_clause(self, text: str) -> ClauseProgram | None:
        program = super()._clause(text)
        if program is not None:
            return program
        # elliptical numeral object ("the plans demanded four" = four [units],
        # anaphoric to a measure in the host clause): parse without the numeral
        # and stash it, symmetric with the adverbial lift.
        words = text.strip().rstrip(".").split()
        if len(words) >= 3 and words[-1].lower() in self.NUMERALS:
            program = super()._clause(" ".join(words[:-1]))
            if program is not None:
                program.predicate = {**program.predicate,
                                     "k7_numeral_object": words[-1].lower()}
        return program

    # ── new/overridden builders ──────────────────────────────────────────
    def _parenthetical_attitude(self, text: str) -> LinkedProgram | None:
        match = PARENTHETICAL_ATTITUDE.match(text.strip())
        if not match:
            return None
        first, holder, verb, rest = match.groups()
        content = self._clause(f"{first} {rest}")
        if content is None:
            return None
        lemma = {"said": "say", "says": "say", "believed": "believe", "believes": "believe",
                 "claimed": "claim", "claims": "claim"}[verb]
        tense = "past" if verb in ("said", "believed", "claimed") else "present"
        return LinkedProgram("attitude", content, None,
                             meta={"holder": holder, "verb_lemma": lemma, "tense": tense,
                                   "world": "reported", "parenthetical": True,
                                   "split_at": first})

    def _cleft(self, text: str) -> LinkedProgram | None:
        match = CLEFT_ANY.match(text.strip())
        if not match:
            return None
        copula, focus, relativizer, rest = match.groups()
        if "," in focus or len(focus.split()) > 5:
            return None
        base = self._clause(f"{focus} {rest}")
        if base is None:
            return None
        return LinkedProgram("cleft_focus", base, None,
                             meta={"focus": focus, "copula": copula, "relativizer": relativizer})

    # measure/phrasal tense assignment must tolerate a linked base
    def _measure(self, text: str):
        program = super()._measure(text)
        return program

    # ── entry with recursive order (connective BEFORE existential) ───────
    def _compile_inner(self, text: str):
        stripped = text.strip()
        if not stripped:
            return None
        stripped = stripped[0].upper() + stripped[1:]
        pre_adverb = None
        words = stripped.rstrip(".").split()
        for adverb in PRE_ADVERBS:
            if adverb in words[1:-1]:
                index = words.index(adverb)
                stripped = " ".join(words[:index] + words[index + 1:]) + "."
                pre_adverb = adverb
                break
        disabled = getattr(self, "disabled_families", frozenset())
        family_builders = (
            ("F9", self._parenthetical_attitude), ("F8", self._cleft),
            ("F9", self._attitude), ("F10", self._neg_scope),
            ("F3", self._appositive), ("F13", self._verbal_subject),
            ("F1", self._connective), ("F4", self._fronted_adverbial),
            ("F5", self._coordination_ellipsis), ("F7", self._measure),
            ("F12", self._phrasal), ("F14", self._passive_agent),
            ("F11", self._possessive_chain), ("F2", self._relative),
            ("F6", self._existential))
        for family, builder in family_builders:
            if family in disabled:
                continue
            program = builder(stripped)
            if program is not None:
                if pre_adverb:
                    target = program.main if isinstance(program, LinkedProgram) else program
                    if isinstance(target, ClauseProgram):
                        target.predicate = {**target.predicate, "k7_pre_adverb": pre_adverb}
                return program
        clause = self._plain_clause(stripped)
        if clause is not None and pre_adverb:
            clause.predicate = {**clause.predicate, "k7_pre_adverb": pre_adverb}
        return clause

    def compile_text(self, text: str):
        self._depth = 1
        try:
            return self._compile_inner(text)
        finally:
            self._depth = 0
