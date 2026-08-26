#!/usr/bin/env python3
"""M13e2 K4: fold pass 2 — the banked residue gets homes.

Donated by the registered debts of fold pass 1:
  7. object complements   (made the mind affordable)  — also resolves the recorded misparse hazard
  8. free relatives       (what guts had labored over) — opaque definite description, semantics registered partial
  9. reduced relatives    (the institution the species would build) — complex restrictor, semantics registered partial
 10. verb particles       (labored over, kept back)
 11. past perfect         (had labored)
 12. bare-plural subjects (guts labored)
Preference law: when a full-span object-complement reading exists, it outranks the
stacked-nominal reading (the pass-1 hazard becomes the dispreferred parse).
"""

from __future__ import annotations

import stage5m13e2_construction_kernel as k1
from stage5m13e2_construction_kernel import CLOSED_CLASS, ClauseProgram, Item, _get, _sem, _subject_of
from stage5m13e2_construction_kernel_k2 import ConstructionKernelK2
from stage5m13e2_construction_kernel_k3 import ConstructionKernelK3

SCHEMA = "oracle-stage5m13e2-construction-kernel-k4-v1"

PARTICLES = {"over", "up", "back", "out", "off"}
k1.AUXILIARIES.setdefault("would", "past")
CLOSED_CLASS |= PARTICLES | {"would", "had"}
DROPPED_ADVERBS = {"ever"}


class ConstructionKernelK4(ConstructionKernelK3):
    @staticmethod
    def _sentences(text: str):
        out = []
        for tokens, question in ConstructionKernelK3._sentences(text):
            tokens = [t for t in tokens if t.casefold() not in DROPPED_ADVERBS]
            if tokens:
                out.append((tokens, question))
        return out

    def _lexical(self, token: str, position: int):
        low = token.casefold()
        span = (position, position + 1)
        items = super()._lexical(token, position)
        if low in PARTICLES:
            items.append(Item("PRT", _sem(prt=low), span))
        if low == "had":
            items.append(Item("AUXPERF", _sem(), span))
        if low in {"species", "series"}:  # invariant nouns: singular form ends in -es
            items = [Item("N", _sem(lemma=low), item.span) if item.category == "N" else item for item in items]
        return items

    def _combine(self, left: Item, right: Item):
        out = super()._combine(left, right)
        span = (left.span[0], right.span[1])
        # 10. verb particles: VF/VBASE + PRT -> joined lemma
        if left.category == "VF" and right.category == "PRT":
            out.append(Item("VF", _sem(lemma=f"{_get(left.semantics, 'lemma')} {_get(right.semantics, 'prt')}",
                                       tense=_get(left.semantics, "tense")), span))
        if left.category == "VBASE" and right.category == "PRT":
            out.append(Item("VBASE", _sem(lemma=f"{_get(left.semantics, 'lemma')} {_get(right.semantics, 'prt')}"), span))
        # 11. past perfect: had + VF -> VF (tense past)
        if left.category == "AUXPERF" and right.category == "VF":
            out.append(Item("VF", _sem(lemma=_get(right.semantics, "lemma"), tense="past"), span))
        # 12. bare-plural subject: N + VF -> CL (intransitive gapped or plain)
        if left.category == "N" and right.category == "VF":
            out.append(Item("CL", _sem(subject=("definite", _get(left.semantics, "lemma")),
                                       vp=_sem(kind="verb", lemma=_get(right.semantics, "lemma"), obj=None,
                                               polarity="+", tense=_get(right.semantics, "tense"))), span))
        # 8. free relative: wh-NAME + gapped CL -> opaque definite description
        if left.category == "NAME" and _get(left.semantics, "name") == "?x" and right.category == "CL":
            vp = _get(right.semantics, "vp")
            if _get(vp, "obj") is None and _get(vp, "kind") == "verb":
                subject = _get(right.semantics, "subject")
                description = f"what {subject[1]} {_get(vp, 'lemma')}".casefold()
                out.append(Item("NAME", _sem(name=description), span))
        # 9. reduced relative: N + gapped definite-subject CL -> complex restrictor
        if left.category == "N" and right.category == "CL":
            vp = _get(right.semantics, "vp")
            subject = _get(right.semantics, "subject")
            if (_get(vp, "obj") is None and _get(vp, "kind") == "verb"
                    and isinstance(subject, tuple) and subject[0] == "definite"):
                out.append(Item("N", _sem(lemma=f"{_get(left.semantics, 'lemma')} {subject[1]} {_get(vp, 'lemma')}"), span))
        # 7. object complement: transitive VP + ADJ -> VP(kind=objcomp)
        if (left.category == "VP" and _get(left.semantics, "kind") == "verb"
                and _get(left.semantics, "obj") is not None and right.category == "ADJ"):
            out.append(Item("VP", _sem(kind="objcomp", lemma=_get(left.semantics, "lemma"),
                                       obj=_get(left.semantics, "obj"), adj=_get(right.semantics, "lemma"),
                                       polarity="+", tense=_get(left.semantics, "tense")), span))
        return out

    @staticmethod
    def _clause_from(semantics: tuple, question: bool) -> ClauseProgram:
        vp = _get(semantics, "vp")
        if _get(vp, "kind") == "objcomp":
            subject = _get(semantics, "subject")
            obj = _get(vp, "obj")
            obj_name = obj[1]
            relation = ClauseProgram(kind="statement")
            if subject[0] == "proper":
                relation.subject = subject[1]
            elif subject[0] == "quant":
                relation.quantifier, relation.restrictor = subject[1]
            else:
                relation.quantifier, relation.subject = "definite", subject[1]
            relation.predicate = {"kind": "verb", "lemma": _get(vp, "lemma")}
            relation.obj = obj_name
            relation.tense = _get(vp, "tense")
            # resultative semantics: the caused property holds as a present result state
            prop = ClauseProgram(kind="statement", quantifier="definite", subject=obj_name,
                                 predicate={"kind": "adjective", "lemma": _get(vp, "adj")},
                                 tense="present")
            return ClauseProgram(kind="question" if question else "statement", conjuncts=[relation, prop])
        return ConstructionKernelK3._clause_from(semantics, question)

    def compile_sentence(self, tokens, question: bool):
        items, shape = self._parse_tokens(tokens, question)
        if not self.compositional:
            if shape not in self.memorized_signatures:
                return None
        else:
            self.memorized_signatures.add(shape)
        for item in items:
            if item.category == "CLDISJ":
                first = self._clause_from(_get(item.semantics, "first"), False)
                second = self._clause_from(_get(item.semantics, "second"), False)
                return ClauseProgram(kind="disjunction", conjuncts=[first, second])
        for category in ("COND", "CLCONJ"):
            for item in items:
                if item.category != category:
                    continue
                if category == "CLCONJ":
                    first = self._clause_from(_get(item.semantics, "first"), question)
                    second = self._clause_from(_get(item.semantics, "second"), question)
                    return ClauseProgram(kind="question" if question else "statement", conjuncts=[first, second])
                condition = _get(item.semantics, "condition")
                consequent = _get(item.semantics, "consequent")
                program = ClauseProgram(kind="conditional")
                program.condition = self._clause_from(condition, False)
                consequent_program = self._clause_from(consequent, False)
                program.predicate = consequent_program.predicate
                program.subject = consequent_program.subject
                program.quantifier = consequent_program.quantifier
                program.restrictor = consequent_program.restrictor
                program.obj = consequent_program.obj
                program.polarity = consequent_program.polarity
                program.tense = consequent_program.tense
                program.modality = consequent_program.modality
                return program
        clauses = [item for item in items if item.category == "CL"]
        # preference law: object-complement readings outrank stacked-nominal readings
        clauses.sort(key=lambda item: 0 if _get(_get(item.semantics, "vp") or (), "kind") == "objcomp" else 1)
        for item in clauses:
            return self._clause_from(item.semantics, question)
        return None


__all__ = ["ConstructionKernelK4", "SCHEMA"]
