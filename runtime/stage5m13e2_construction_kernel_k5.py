#!/usr/bin/env python3
"""M13e2 K5: fold pass 3 — everyday conversational constructions.

 13. there-existentials         (There is a hammer on the bench.)
 14. possessives                (Kip's hammer)
 15. prepositional locatives    (in/on/at + "Where is X?")
 16. comparatives               (taller than Sef)
 17. because-clauses            (conjoined cause; causal link = registered debt)
 18. want/try + infinitive      (attitude verbs with to-infinitive objects)
 19. plural copular agreement   (are/were — verification pairs, no new rule)
 20. tag confirmations          (", right?" stripped in question context)
 21. temporal when-clauses      (conjoined; temporal link = registered debt)
 22. numeric determiners        (two guards -> some+restrictor; exact count = registered debt)
"""

from __future__ import annotations

from stage5m13e2_construction_kernel import CLOSED_CLASS, COPULAS, ClauseProgram, Item, _get, _sem
from stage5m13e2_construction_kernel_k4 import ConstructionKernelK4

SCHEMA = "oracle-stage5m13e2-construction-kernel-k5-v1"

PREPOSITIONS = {"in", "on", "at"}
NUMBER_DETERMINERS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
CLOSED_CLASS |= PREPOSITIONS | set(NUMBER_DETERMINERS) | {"there", "than", "because", "to", "when", "locwh"}


def _comparative_base(word: str) -> str:
    stem = word[:-2]
    # de-double gemination (bigger -> big) but keep legitimate doubles (taller, lesser)
    if len(stem) >= 2 and stem[-1] == stem[-2] and stem[-1] not in "lse":
        stem = stem[:-1]
    return stem


class ConstructionKernelK5(ConstructionKernelK4):
    @staticmethod
    def _sentences(text: str):
        out = []
        for tokens, question in ConstructionKernelK4._sentences(text):
            if question and tokens and tokens[-1].casefold() == "right":
                tokens = tokens[:-1]  # tag confirmation: ", right?"
            if tokens:
                out.append((tokens, question))
        return out

    def _lexical(self, token: str, position: int):
        low = token.casefold()
        span = (position, position + 1)
        items = super()._lexical(token, position)
        if low in PREPOSITIONS:
            items.append(Item("PREP", _sem(prep=low), span))
        if low == "there":
            items.append(Item("THERE", _sem(), span))
        if low == "than":
            items.append(Item("THAN", _sem(), span))
        if low == "because":
            items.append(Item("BECAUSE", _sem(), span))
        if low == "when":
            items.append(Item("WHEN", _sem(), span))
        if low == "to":
            items.append(Item("TO", _sem(), span))
        if low in NUMBER_DETERMINERS:
            items.append(Item("NUMDET", _sem(count=NUMBER_DETERMINERS[low]), span))
        if low == "locwh":  # injected by the where-question transform
            items.append(Item("PPLOC", _sem(prep="?", place="?x"), span))
        if low.endswith("'s") and len(low) > 2:
            items = [item for item in items if item.category != "NAME"]
            items.append(Item("POSS", _sem(owner=low[:-2]), span))
        return items

    def _parse_tokens(self, tokens, question: bool):
        # where-question transform: Where is NP? -> NP is locwh
        if question and tokens and tokens[0].casefold() == "where" and len(tokens) >= 3 \
                and tokens[1].casefold() in COPULAS:
            tokens = [*tokens[2:], tokens[1], "locwh"]
            return super()._parse_tokens(tokens, False)
        return super()._parse_tokens(tokens, question)

    def _combine(self, left: Item, right: Item):
        out = super()._combine(left, right)
        span = (left.span[0], right.span[1])
        # 15. locative PP: PREP + (DNP|NAME|N) -> PPLOC
        if left.category == "PREP" and right.category in {"DNP", "NAME", "N"}:
            place = _get(right.semantics, "name") or _get(right.semantics, "lemma")
            out.append(Item("PPLOC", _sem(prep=_get(left.semantics, "prep"), place=str(place).casefold()), span))
        if left.category == "COP" and right.category == "PPLOC":
            place = _get(right.semantics, "place")
            out.append(Item("VP", _sem(kind="location", lemma=_get(right.semantics, "prep"),
                                       obj=("proper", "?x") if place == "?x" else ("definite", place),
                                       polarity="+", tense=_get(left.semantics, "tense")), span))
        # 13. existentials: (DNP|N) + PPLOC -> NPLOC ; COP + NPLOC -> VPEX ; THERE + VPEX -> CL
        if left.category in {"DNP", "N"} and right.category == "PPLOC":
            out.append(Item("NPLOC", _sem(entity=_get(left.semantics, "lemma"),
                                          prep=_get(right.semantics, "prep"),
                                          place=_get(right.semantics, "place")), span))
        if left.category == "COP" and right.category == "NPLOC":
            out.append(Item("VPEX", _sem(kind="location", lemma=_get(right.semantics, "prep"),
                                         obj=("definite", _get(right.semantics, "place")),
                                         entity=_get(right.semantics, "entity"),
                                         polarity="+", tense=_get(left.semantics, "tense")), span))
        if left.category == "THERE" and right.category == "VPEX":
            vp = _sem(kind="location", lemma=_get(right.semantics, "lemma"), obj=_get(right.semantics, "obj"),
                      polarity="+", tense=_get(right.semantics, "tense"))
            out.append(Item("CL", _sem(subject=("quant", ("some", _get(right.semantics, "entity"))), vp=vp), span))
        # 14. possessives: POSS + N -> DNP (possessives are definite descriptions)
        if left.category == "POSS" and right.category == "N":
            out.append(Item("DNP", _sem(article="poss",
                                        lemma=f"{_get(left.semantics, 'owner')}'s {_get(right.semantics, 'lemma')}"), span))
        # 16. comparatives: THAN + (NAME|DNP) -> THANP ; ADJ + THANP -> ADJCOMP ; COP (+NEG) + ADJCOMP -> VP
        if left.category == "THAN" and right.category in {"NAME", "DNP"}:
            std = _get(right.semantics, "name") or _get(right.semantics, "lemma")
            out.append(Item("THANP", _sem(standard=str(std)), span))
        if left.category == "ADJ" and right.category == "THANP" and str(_get(left.semantics, "lemma")).endswith("er"):
            out.append(Item("ADJCOMP", _sem(dimension=_comparative_base(_get(left.semantics, "lemma")),
                                            standard=_get(right.semantics, "standard")), span))
        if left.category == "NEG" and right.category == "ADJCOMP":
            out.append(Item("NEGADJCOMP", right.semantics, span))
        if left.category == "COP" and right.category == "ADJCOMP":
            out.append(Item("VP", _sem(kind="comparative", lemma=_get(right.semantics, "dimension"),
                                       obj=("proper", _get(right.semantics, "standard")),
                                       polarity="+", tense=_get(left.semantics, "tense")), span))
        if left.category == "COP" and right.category == "NEGADJCOMP":
            out.append(Item("VP", _sem(kind="comparative", lemma=_get(right.semantics, "dimension"),
                                       obj=("proper", _get(right.semantics, "standard")),
                                       polarity="-", tense=_get(left.semantics, "tense")), span))
        # 17/21. because/when clause pairs
        if left.category == "BECAUSE" and right.category == "CL":
            out.append(Item("BECCL", right.semantics, span))
        if left.category == "CL" and right.category == "BECCL":
            out.append(Item("CLCAUSE", _sem(main=left.semantics, cause=right.semantics), span))
        if left.category == "WHEN" and right.category == "CL":
            out.append(Item("WHENCL", right.semantics, span))
        if left.category == "WHENCL" and right.category == "CL":
            out.append(Item("CLTEMP", _sem(when=left.semantics, main=right.semantics), span))
        # 18. infinitives: TO + VBASE -> INF ; VF/VBASE + INF -> attitude VP
        if left.category == "TO" and right.category == "VBASE":
            out.append(Item("INF", _sem(verb=_get(right.semantics, "lemma")), span))
        if left.category == "VF" and right.category == "INF":
            out.append(Item("VP", _sem(kind="attitude", lemma=_get(left.semantics, "lemma"),
                                       obj=("inf", f"to {_get(right.semantics, 'verb')}"),
                                       polarity="+", tense=_get(left.semantics, "tense")), span))
        if left.category == "VBASE" and right.category == "INF":
            out.append(Item("VPBASE", _sem(lemma=_get(left.semantics, "lemma"),
                                           obj=("inf", f"to {_get(right.semantics, 'verb')}")), span))
        # 22. numeric determiners: NUMDET + N -> QNP (count = registered debt)
        if left.category == "NUMDET" and right.category == "N":
            out.append(Item("QNP", _sem(quant="some", restrictor=_get(right.semantics, "lemma"),
                                        count=_get(left.semantics, "count")), span))
        return out

    def compile_sentence(self, tokens, question: bool):
        items, shape = self._parse_tokens(tokens, question)
        if not self.compositional:
            if shape not in self.memorized_signatures:
                return None
        else:
            self.memorized_signatures.add(shape)
        for item in items:
            if item.category in {"CLCAUSE", "CLTEMP"}:
                if item.category == "CLCAUSE":
                    first = self._clause_from(_get(item.semantics, "main"), False)
                    second = self._clause_from(_get(item.semantics, "cause"), False)
                else:
                    first = self._clause_from(_get(item.semantics, "when"), False)
                    second = self._clause_from(_get(item.semantics, "main"), False)
                return ClauseProgram(kind="question" if question else "statement", conjuncts=[first, second])
        return super().compile_sentence(tokens, question)

    def _wh_matches(self, question: ClauseProgram, derived):
        matches = super()._wh_matches(question, derived)
        if matches or question.predicate.get("kind") != "location" or question.predicate.get("lemma") != "?":
            return matches
        # where-question: match any locative lemma for the same subject
        for (subject, kind, lemma, obj, tense, _modality), (polarity, _p, _r) in derived.items():
            if kind == "location" and polarity == "+" and subject == question.subject and obj not in (None, "?x"):
                matches.append(f"{lemma} the {obj}")
        return matches


__all__ = ["ConstructionKernelK5", "SCHEMA"]
