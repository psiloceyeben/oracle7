#!/usr/bin/env python3
"""M13e2 K3: fold-donated construction rules (first fold pass, M13e4 fold protocol).

Rule families donated by the residue of the 2026-08-16 essay fold, each promoted
because it compresses multiple independent (surface, program) pairs:
  1. intransitive verb phrases        (Alexandria burned. / The substrate existed.)
  2. bare-noun arguments              (Writing externalized memory.)
  3. adjective stacking in nominals   (the first compiled artifact)
  4. adverb-modified adjectives       (architecturally absent)
  5. of-PP nominal complements        (the grammar of Sanskrit)
  6. modal verbs can/could + aux intransitives (A machine can speak.)
Banked residue (registered, NOT patched): free relatives, reduced relatives,
object complements ("made the mind affordable").
"""

from __future__ import annotations

import stage5m13e2_construction_kernel_k2 as k2
from stage5m13e2_construction_kernel import CLOSED_CLASS, Item, _get, _sem
from stage5m13e2_construction_kernel_k2 import ConstructionKernelK2

SCHEMA = "oracle-stage5m13e2-construction-kernel-k3-v1"

# modal verbs join the modal inventory (K2's inversion and lexicon read this dict)
k2.MODALS.update({"can": "can", "could": "could"})
CLOSED_CLASS |= {"of", "can", "could"}


class ConstructionKernelK3(ConstructionKernelK2):
    def _lexical(self, token: str, position: int):
        low = token.casefold()
        span = (position, position + 1)
        items = super()._lexical(token, position)
        # closed-class and wh tokens must not carry open-class readings: 'not' is not
        # a verb, 'What' is not a bare noun, 'Three' is not a name (fold pass-1/3 laws)
        if low in k2.WH_WORDS:
            items = [item for item in items if item.category not in {"N", "ADJ", "VBASE", "VF"}]
        elif low in CLOSED_CLASS:
            items = [item for item in items if item.category not in {"N", "ADJ", "VBASE", "VF", "NAME"}]
        if low == "of":
            items.append(Item("OF", _sem(), span))
        if low.endswith("ly") and low.isalpha() and len(low) > 4:
            items.append(Item("ADVLY", _sem(lemma=low), span))
        # Greek/Latin singulars in -is/-us are not plurals (diagnosis, basis, bus)
        if low.endswith(("is", "us")) and low.isalpha():
            items = [Item("N", _sem(lemma=low), item.span) if item.category == "N" else item for item in items]
        return items

    def _parse_tokens(self, tokens, question: bool):
        # copular inversion with an of-PP subject: "Is the king of Norwind a sailor?"
        from stage5m13e2_construction_kernel import ARTICLES, COPULAS, QUANTIFIERS
        if (question and tokens and tokens[0].casefold() in COPULAS and len(tokens) >= 6
                and tokens[1].casefold() in (ARTICLES | set(QUANTIFIERS)) and tokens[3].casefold() == "of"):
            aux, rest = tokens[0], tokens[1:]
            # subject NP spans 4 tokens (of + name) or 5 (of + article + noun)
            np_length = 5 if len(rest) >= 5 and rest[3].casefold() in ARTICLES else 4
            tokens = [*rest[:np_length], aux, *rest[np_length:]]
            return ConstructionKernelK2._parse_tokens(self, tokens, False)
        return super()._parse_tokens(tokens, question)

    def _combine(self, left: Item, right: Item):
        out = super()._combine(left, right)
        span = (left.span[0], right.span[1])
        # 3. adjective stacking: ADJ N -> N with joined lemma (recursive, feeds DET/Q rules)
        if left.category == "ADJ" and right.category == "N":
            out.append(Item("N", _sem(lemma=f"{_get(left.semantics, 'lemma')} {_get(right.semantics, 'lemma')}"), span))
        # 4. adverb-modified adjective: ADVLY ADJ -> ADJ with joined lemma
        if left.category == "ADVLY" and right.category == "ADJ":
            out.append(Item("ADJ", _sem(lemma=f"{_get(left.semantics, 'lemma')} {_get(right.semantics, 'lemma')}"), span))
        # 5. of-PP nominal complement: (OF, NAME|N) -> PPOF ; (N, PPOF) -> N joined
        if left.category == "OF" and right.category in {"NAME", "N"}:
            tail = _get(right.semantics, "name") or _get(right.semantics, "lemma")
            out.append(Item("PPOF", _sem(tail=str(tail).casefold()), span))
        if left.category == "N" and right.category == "PPOF":
            out.append(Item("N", _sem(lemma=f"{_get(left.semantics, 'lemma')} of {_get(right.semantics, 'tail')}"), span))
        # 2. bare-noun object: VF N -> VP (mass/abstract nouns as arguments)
        if left.category == "VF" and right.category == "N":
            out.append(Item("VP", _sem(kind="verb", lemma=_get(left.semantics, "lemma"),
                                       obj=("definite", _get(right.semantics, "lemma")),
                                       polarity="+", tense=_get(left.semantics, "tense")), span))
        if left.category == "VBASE" and right.category == "N":
            out.append(Item("VPBASE", _sem(lemma=_get(left.semantics, "lemma"),
                                           obj=("definite", _get(right.semantics, "lemma"))), span))
        # 1. intransitive clause: (NAME|DNP|QNP) VF -> CL with no object
        if left.category in {"NAME", "DNP", "QNP"} and right.category == "VF":
            from stage5m13e2_construction_kernel import _subject_of
            out.append(Item("CL", _sem(subject=_subject_of(left),
                                       vp=_sem(kind="verb", lemma=_get(right.semantics, "lemma"),
                                               obj=None, polarity="+", tense=_get(right.semantics, "tense"))), span))
        # 6a. modal + bare verb: MODAL VBASE -> VP (intransitive, modality carried)
        if left.category == "MODAL" and right.category == "VBASE":
            out.append(Item("VP", _sem(kind="verb", lemma=_get(right.semantics, "lemma"), obj=None,
                                       polarity="+", tense="present",
                                       modality=_get(left.semantics, "modality")), span))
        # 6b. modal + transitive base: MODAL VPBASE -> VP
        if left.category == "MODAL" and right.category == "VPBASE":
            out.append(Item("VP", _sem(kind="verb", lemma=_get(right.semantics, "lemma"),
                                       obj=_get(right.semantics, "obj"), polarity="+", tense="present",
                                       modality=_get(left.semantics, "modality")), span))
        # 6c. aux intransitives: AUX VBASE -> VP ; AUXNEG VBASE -> VP (negated)
        if left.category == "AUX" and right.category == "VBASE":
            out.append(Item("VP", _sem(kind="verb", lemma=_get(right.semantics, "lemma"), obj=None,
                                       polarity="+", tense=_get(left.semantics, "tense")), span))
        if left.category == "AUXNEG" and right.category == "VBASE":
            out.append(Item("VP", _sem(kind="verb", lemma=_get(right.semantics, "lemma"), obj=None,
                                       polarity="-", tense=_get(left.semantics, "tense")), span))
        return out


__all__ = ["ConstructionKernelK3", "SCHEMA"]
