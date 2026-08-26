#!/usr/bin/env python3
"""Realizer2b — recursive realization for K7b composed programs.

Additive successor to Realizer2 (frozen; not edited). _cs now dispatches:
a linked sub-program realizes through realize_linked recursively, a plain
clause through the sealed realizer. Adds the parenthetical attitude surface."""

from __future__ import annotations

from stage5m13e2_construction_kernel_k7 import LinkedProgram
from stage5m13e6_realizer2 import Realizer2, _decap


class Realizer2b(Realizer2):
    def _cs(self, clause) -> str:
        if isinstance(clause, LinkedProgram):
            return self.realize_linked(clause).rstrip(".")
        surface = super()._cs(clause)
        numeral = (clause.predicate or {}).get("k7_numeral_object")
        if numeral:
            surface = f"{surface} {numeral}"
        return surface

    def realize_linked(self, program: LinkedProgram) -> str:
        meta = program.meta or {}
        if program.relation == "attitude" and meta.get("parenthetical"):
            content = self._cs(program.main)
            split_at = meta.get("split_at", "")
            verb = {"say": "said", "believe": "believed", "claim": "claimed"}[meta["verb_lemma"]] \
                if meta["tense"] == "past" else meta["verb_lemma"] + "s"
            if split_at and content.lower().startswith(split_at.lower()):
                rest = content[len(split_at):].strip()
                return f"{split_at}, {meta['holder']} {verb}, {rest}."
            return f"{meta['holder']} {verb} that {_decap(content)}."
        if program.relation == "located":
            # tolerate a linked main (no .tense attribute)
            tense = getattr(program.main, "tense", "present")
            setting = program.setting or {}
            entity_np = (meta.get("article", "") + " " + meta.get("entity_np", "")).strip()
            copula = "was" if tense == "past" else "is"
            if entity_np.split()[:1] and entity_np.split()[0] in ("three", "two", "four"):
                copula = "were" if tense == "past" else "are"
            surface = f"There {copula} {entity_np} {setting.get('prep', 'in')} {setting.get('np', '')}."
            return surface[0].upper() + surface[1:]
        return super().realize_linked(program)
