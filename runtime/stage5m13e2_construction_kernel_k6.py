#!/usr/bin/env python3
"""M13e2 K6: fold pass 4 — the residue menu the corpus identified for itself.

 23. of-PP with definite tails      (the keeper of the tower)
 24. ditransitives                  (gave Sef the map -> relation + recipient fact)
 25. prepositional datives          (gave the map to Sef)
 26. passives                       (was given to Sef; agentless; active-passive bridge via shared recipient facts)
 27. coordinated subjects           (Kip and Mira arrived -> two facts)
 28. disjunctive subjects           (the lamp or the candle glows -> disjunction store)
 29. clefts / the-one-who           (opaque definite description)
 30. that-clause subjects           (proposition-as-entity, registered partial)
Registered debts: conjunct questions verify only their final conjunct; full
active/passive agent unification awaits the lambda IR.
"""

from __future__ import annotations

import stage5m13e2_construction_kernel as k1
from stage5m13e2_construction_kernel import CLOSED_CLASS, ClauseProgram, Item, _get, _sem, _subject_of
from stage5m13e2_construction_kernel_k5 import ConstructionKernelK5

SCHEMA = "oracle-stage5m13e2-construction-kernel-k6-v1"

k1.IRREGULAR_PAST.update({
    "left": "leave", "fell": "fall", "rang": "ring", "told": "tell", "came": "come", "ran": "run",
    "saw": "see", "said": "say", "got": "get", "found": "find", "felt": "feel", "met": "meet",
    "sat": "sit", "stood": "stand", "won": "win", "lost": "lose", "sent": "send", "spent": "spend",
    "paid": "pay", "heard": "hear",
})
IRREGULAR_PARTICIPLES = {"given": "give", "taken": "take", "shown": "show", "told": "tell",
                         "sent": "send", "won": "win", "found": "find", "held": "hold",
                         "brought": "bring", "written": "write", "worn": "wear"}
CLOSED_CLASS |= {"that"}


class ConstructionKernelK6(ConstructionKernelK5):
    def _lexical(self, token: str, position: int):
        low = token.casefold()
        span = (position, position + 1)
        items = super()._lexical(token, position)
        if low == "that":
            items.append(Item("THAT", _sem(), span))
        if low in IRREGULAR_PARTICIPLES:
            items.append(Item("VPART", _sem(lemma=IRREGULAR_PARTICIPLES[low]), span))
        elif low.endswith("ed") and low.isalpha() and len(low) > 3:
            base = k1._lemma_from_past(low)
            if base:
                items.append(Item("VPART", _sem(lemma=base), span))
        return items

    def _combine(self, left: Item, right: Item):
        out = super()._combine(left, right)
        span = (left.span[0], right.span[1])
        # 23. of-PP with definite tail: OF + DNP -> PPOF
        if left.category == "OF" and right.category == "DNP":
            out.append(Item("PPOF", _sem(tail=str(_get(right.semantics, "lemma")).casefold()), span))
        # 26. passives: COP + (NEG)VPART -> VP(kind=passive)
        if left.category == "COP" and right.category == "VPART":
            out.append(Item("VP", _sem(kind="passive", lemma=_get(right.semantics, "lemma"), obj=None,
                                       polarity="+", tense=_get(left.semantics, "tense")), span))
        if left.category == "NEG" and right.category == "VPART":
            out.append(Item("NEGVPART", right.semantics, span))
        if left.category == "COP" and right.category == "NEGVPART":
            out.append(Item("VP", _sem(kind="passive", lemma=_get(right.semantics, "lemma"), obj=None,
                                       polarity="-", tense=_get(left.semantics, "tense")), span))
        # 24/25. recipients: TO + (NAME|DNP) -> PPTO ; VP + PPTO ; double-object reanalysis
        if left.category == "TO" and right.category in {"NAME", "DNP"}:
            recipient = _get(right.semantics, "name") or _get(right.semantics, "lemma")
            out.append(Item("PPTO", _sem(recipient=str(recipient)), span))
        if left.category == "VP" and _get(left.semantics, "kind") in {"verb", "passive"} and right.category == "PPTO":
            fields = dict(left.semantics)
            fields["recipient"] = _get(right.semantics, "recipient")
            out.append(Item("VP", tuple(sorted(fields.items())), span))
        if (left.category == "VP" and _get(left.semantics, "kind") == "verb"
                and isinstance(_get(left.semantics, "obj"), tuple) and _get(left.semantics, "obj")[0] == "proper"
                and right.category == "DNP"):
            fields = dict(left.semantics)
            fields["recipient"] = _get(left.semantics, "obj")[1]
            fields["obj"] = ("definite", _get(right.semantics, "lemma"))
            out.append(Item("VP", tuple(sorted(fields.items())), span))
        # 27. coordinated subjects
        if left.category == "AND" and right.category in {"NAME", "DNP"}:
            out.append(Item("NPAND", _sem(second=_subject_of(right)), span))
        if left.category in {"NAME", "DNP"} and right.category == "NPAND":
            out.append(Item("NPCOORD", _sem(first=_subject_of(left), second=_get(right.semantics, "second")), span))
        if left.category == "NPCOORD" and right.category == "VP":
            out.append(Item("CL", _sem(coord=(_get(left.semantics, "first"), _get(left.semantics, "second")),
                                       vp=right.semantics), span))
        if left.category == "NPCOORD" and right.category == "VF":
            vp = _sem(kind="verb", lemma=_get(right.semantics, "lemma"), obj=None,
                      polarity="+", tense=_get(right.semantics, "tense"))
            out.append(Item("CL", _sem(coord=(_get(left.semantics, "first"), _get(left.semantics, "second")), vp=vp), span))
        # 28. disjunctive subjects -> CLDISJ (reuses the disjunction store)
        if left.category == "OR" and right.category in {"NAME", "DNP"}:
            out.append(Item("NPOR", _sem(second=_subject_of(right)), span))
        if left.category in {"NAME", "DNP"} and right.category == "NPOR":
            out.append(Item("NPDISJ", _sem(first=_subject_of(left), second=_get(right.semantics, "second")), span))
        if left.category == "NPDISJ" and right.category == "VP":
            out.append(Item("CLDISJ", _sem(first=_sem(subject=_get(left.semantics, "first"), vp=right.semantics),
                                           second=_sem(subject=_get(left.semantics, "second"), vp=right.semantics)), span))
        if left.category == "NPDISJ" and right.category == "VF":
            vp = _sem(kind="verb", lemma=_get(right.semantics, "lemma"), obj=None,
                      polarity="+", tense=_get(right.semantics, "tense"))
            out.append(Item("CLDISJ", _sem(first=_sem(subject=_get(left.semantics, "first"), vp=vp),
                                           second=_sem(subject=_get(left.semantics, "second"), vp=vp)), span))
        # infinitives with objects: TO + VPBASE -> INF (opaque verb-object description)
        if left.category == "TO" and right.category == "VPBASE":
            obj = _get(right.semantics, "obj")
            out.append(Item("INF", _sem(verb=f"{_get(right.semantics, 'lemma')} {obj[1]}"), span))
        # 29. clefts: (DNP|N) + CL(subject ?x) -> opaque definite "one who <verb>"
        if left.category in {"DNP", "N"} and right.category == "CL":
            subject = _get(right.semantics, "subject")
            vp = _get(right.semantics, "vp")
            if isinstance(subject, tuple) and subject == ("proper", "?x") and _get(vp, "kind") == "verb":
                out.append(Item("DNP", _sem(article="cleft",
                                            lemma=f"{_get(left.semantics, 'lemma')} who {_get(vp, 'lemma')}"), span))
        # 30. that-clause subjects: THAT + CL -> THATCL ; THATCL + VP -> CL
        if left.category == "THAT" and right.category == "CL":
            subject = _get(right.semantics, "subject")
            vp = _get(right.semantics, "vp")
            if isinstance(subject, tuple):
                out.append(Item("THATCL", _sem(lemma=f"that {subject[1]} {_get(vp, 'lemma')}".casefold()), span))
        if left.category == "THATCL" and right.category == "VP":
            out.append(Item("CL", _sem(subject=("definite", _get(left.semantics, "lemma")), vp=right.semantics), span))
        return out

    @staticmethod
    def _clause_from(semantics: tuple, question: bool) -> ClauseProgram:
        coord = _get(semantics, "coord")
        if coord is not None:
            vp = _get(semantics, "vp")
            first = ConstructionKernelK6._clause_from(_sem(subject=coord[0], vp=vp), False)
            second = ConstructionKernelK6._clause_from(_sem(subject=coord[1], vp=vp), False)
            return ClauseProgram(kind="question" if question else "statement", conjuncts=[first, second])
        vp = _get(semantics, "vp")
        recipient = _get(vp, "recipient") if vp else None
        if recipient:
            base_fields = {name: value for name, value in vp if name != "recipient"}
            main = ConstructionKernelK6._clause_from(
                _sem(subject=_get(semantics, "subject"), vp=tuple(sorted(base_fields.items()))), False)
            thing = main.obj if (main.predicate.get("kind") == "verb" and main.obj) else main.subject
            recipient_fact = ClauseProgram(kind="statement", quantifier="definite", subject=thing,
                                           predicate={"kind": "recipient", "lemma": "to"},
                                           obj=recipient, tense=main.tense)
            return ClauseProgram(kind="question" if question else "statement", conjuncts=[main, recipient_fact])
        return ConstructionKernelK5._clause_from(semantics, question)


__all__ = ["ConstructionKernelK6", "SCHEMA"]
