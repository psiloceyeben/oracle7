#!/usr/bin/env python3
"""Realizer2 — natural-register realization for K7 LinkedPrograms.

Composes the sealed M13e4 Realizer for clause-level surfaces and adds the
linked/setting constructions. Round-trip law: realize2 output must re-parse
via K7 to a structurally identical program (checked by the external gate
battery in the K7 development evaluator, not assumed here).
"""

from __future__ import annotations

import sys

sys.path.insert(0, r"C:\Users\BenHo\Desktop\ClaudeCode\_m13e0v4\control-install")

from stage5m13e4_migration2 import Realizer, soften
from stage5m13e2_construction_kernel_k7 import LinkedProgram, CONNECTIVES

RELATION_SURFACE = {value[0]: key for key, value in CONNECTIVES.items()}


def _decap(sentence: str) -> str:
    words = sentence.split()
    if words and words[0][0].isupper() and not words[0].isupper() and words[0] not in ("I",):
        head = words[0]
        # keep proper names capitalized: single capitalized token followed by
        # lowercase verb is ambiguous; the sealed Realizer capitalizes clause
        # starts, so decap only kernel-known lowercase-start surfaces.
        if head.lower() in ("the", "a", "an", "every", "no", "some", "there",
                            "in", "on", "at", "after", "before", "during", "not"):
            words[0] = head[0].lower() + head[1:]
    return " ".join(words)


class Realizer2(Realizer):
    def _cs(self, clause) -> str:
        """Clause surface via the sealed realizer, with K7 adverbials re-applied."""
        surface = self.realize(clause).rstrip(".")
        adverbial = (clause.predicate or {}).get("k7_adverbial")
        if adverbial:
            surface = f"{surface} {adverbial}"
        pre_adverb = (clause.predicate or {}).get("k7_pre_adverb")
        if pre_adverb:
            words = surface.split()
            # placement before the final verb word (intransitive clauses);
            # registered limitation: transitive placement is approximate until
            # Realizer2 exposes verb position.
            words.insert(len(words) - 1, pre_adverb)
            surface = " ".join(words)
        return surface

    def realize_linked(self, program: LinkedProgram) -> str:
        if program.relation == "apposition":
            meta = program.meta
            main_surface = self._cs(program.main)
            name = meta.get("name", "")
            if name and main_surface.lower().startswith(name.lower()):
                rest = main_surface[len(name):].lstrip()
                return f"{name}, {meta['article']} {meta['description']}, {rest}."
            isa_surface = self._cs(program.subordinate)
            return f"{main_surface}, and {_decap(isa_surface)}."
        if program.relation == "setting":
            setting = program.setting or {}
            main_surface = self._cs(program.main)
            return f"{setting.get('prep', 'in').capitalize()} {setting.get('np', '')}, {_decap(main_surface)}."
        if program.relation == "located":
            meta = program.meta
            setting = program.setting or {}
            entity_np = (meta.get("article", "") + " " + meta.get("entity_np", "")).strip()
            copula = "was" if program.main.tense == "past" else "is"
            if entity_np.split()[:1] and entity_np.split()[0] in ("three", "two", "four"):
                copula = "were" if program.main.tense == "past" else "are"
            surface = f"There {copula} {entity_np} {setting.get('prep', 'in')} {setting.get('np', '')}."
            return surface[0].upper() + surface[1:]
        if program.relation == "cleft_focus":
            meta = program.meta
            base = self._cs(program.main)
            focus = meta["focus"]
            if base.lower().startswith(focus.lower()):
                rest = base[len(focus):].lstrip()
                return f"It {meta['copula']} {focus} {meta['relativizer']} {rest}."
            return f"{base}."
        if program.relation == "attitude":
            meta = program.meta
            verb = {"say": "said", "believe": "believed", "think": "thought",
                    "claim": "claimed", "report": "reported"}[meta["verb_lemma"]] \
                if meta["tense"] == "past" else meta["verb_lemma"] + "s"
            content = _decap(self._cs(program.main))
            return f"{meta['holder']} {verb} that {content}."
        if program.relation == "neg_universal":
            base = self._cs(program.main)
            for head in ("Every ", "every "):
                if base.startswith(head):
                    return f"Not every {base[len(head):]}."
            return f"Not {base[0].lower()}{base[1:]}."
        if program.relation == "possessive":
            meta = program.meta
            base = self._cs(program.main)
            for head in (f"The {meta['head']}", f"the {meta['head']}"):
                if base.startswith(head):
                    return f"{meta['chain']} {meta['head']}{base[len(head):]}."
            return f"{base}."
        if program.relation == "verbal_subject":
            meta = program.meta
            base = self._cs(program.main)
            for head in ("The activity ", "the activity "):
                if base.startswith(head):
                    return f"{meta['subject_np']} {base[len(head):]}."
            return f"{base}."
        if program.relation == "relative":
            meta = program.meta
            main_surface = self._cs(program.main)
            head = meta["head"]
            if main_surface.lower().startswith(head.lower()):
                rest = main_surface[len(head):].lstrip()
                return f"{head} {meta['relativizer']} {meta['rel_surface']} {rest}."
            return f"{main_surface}."
        if program.relation == "conjunction_ellipsis":
            meta = program.meta
            return f"{self._cs(program.main)} and {meta['right_surface']}."
        if program.relation == "measure":
            meta = program.meta
            return (f"{meta['np']} {meta['copula']} {meta['value']} "
                    f"{meta['unit']} {meta['dimension']}.")
        if program.relation == "phrasal":
            meta = program.meta
            return f"{meta['np']} {meta['surface_verb']}."
        if program.relation == "passive_agent":
            meta = program.meta
            return (f"{meta['patient_np']} {meta['copula']} {meta['participle']} "
                    f"by {meta['agent_np']}.")
        connective = RELATION_SURFACE.get(program.relation)
        if connective is None:
            return self.realize(program.main)
        main_surface = self._cs(program.main)
        sub_surface = self._cs(program.subordinate)
        if program.surface_order == "fronted" and CONNECTIVES[connective][1]:
            return f"{connective.capitalize()} {_decap(sub_surface)}, {_decap(main_surface)}."
        joiner = ", so " if connective == "so" else f" {connective} "
        return f"{main_surface}{joiner}{_decap(sub_surface)}."

    def realize2(self, program) -> str:
        if isinstance(program, LinkedProgram):
            surface = soften(self.realize_linked(program))
            return surface[0].upper() + surface[1:] if surface else surface
        surface = self._cs(program).rstrip(".") + "."
        return surface[0].upper() + surface[1:]
