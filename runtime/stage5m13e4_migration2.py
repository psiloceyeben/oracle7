#!/usr/bin/env python3
"""M13e4 migration gate 2: wh + repair on the IR path; realization with the round-trip law."""

from __future__ import annotations

import re
from typing import Any

import stage5m13e2_construction_kernel as k1
from stage5m13e2_construction_kernel import ClauseProgram
from stage5m13e2_construction_kernel_k2 import PRONOUNS
from stage5m13e2_construction_kernel_k6 import IRREGULAR_PARTICIPLES
from stage5m13e4_combinators import IRProofWorld, core_term, subject_entity, translate
from stage5m13e4_oracle_logical_ir import Const, digest, normalize

SCHEMA = "oracle-stage5m13e4-migration2-v1"

REVERSE_PAST = {base: past for past, base in k1.IRREGULAR_PAST.items()}
REVERSE_PART = {base: part for part, base in IRREGULAR_PARTICIPLES.items()}
SIBILANT = re.compile(r"(?:s|x|z|ch|sh)$")


def past_form(lemma: str) -> str:
    head, _, tail = lemma.partition(" ")
    if head in REVERSE_PAST:
        head = REVERSE_PAST[head]
    elif head.endswith("e"):
        head += "d"
    elif re.search(r"[^aeiou]y$", head):
        head = head[:-1] + "ied"
    else:
        head += "ed"
    return f"{head} {tail}".strip()


def third_form(lemma: str) -> str:
    head, _, tail = lemma.partition(" ")
    if SIBILANT.search(head):
        head += "es"
    elif re.search(r"[^aeiou]y$", head):
        head = head[:-1] + "ies"
    else:
        head += "s"
    return f"{head} {tail}".strip()


def participle_form(lemma: str) -> str:
    head, _, tail = lemma.partition(" ")
    if head in REVERSE_PART:
        head = REVERSE_PART[head]
    else:
        return past_form(lemma)
    return f"{head} {tail}".strip()


def plural_form(noun: str) -> str:
    if SIBILANT.search(noun):
        return noun + "es"
    if re.search(r"[^aeiou]y$", noun):
        return noun[:-1] + "ies"
    return noun + "s"



SOFTENABLE = {"The", "That", "Every", "No", "Some", "If", "There", "What", "Who", "Where"}


def soften(sentence: str) -> str:
    """Lowercase a clause-initial word only when it is not a proper name."""
    head = sentence.split(" ", 1)[0]
    if head in SOFTENABLE:
        return sentence[0].lower() + sentence[1:]
    return sentence


class Realizer:
    """ClauseProgram -> surface; certified per program by Parse(Realize(P)) term-digest identity."""

    def subject_surface(self, program: ClauseProgram, capital: bool = True) -> str:
        if program.quantifier == "proper":
            return str(program.subject)
        lemma = str(program.subject)
        if "'s" in lemma:
            owner, _, noun = lemma.partition("'s ")
            return f"{owner.capitalize()}'s {noun}"
        if lemma.startswith("that "):
            parts = lemma.split()
            return f"That the {parts[1]} is {parts[2]}"
        if lemma.startswith("one who "):
            return "the one who " + past_form(lemma[len("one who "):])
        article = "The" if capital else "the"
        return f"{article} {lemma}"

    def object_surface(self, obj: Any) -> str:
        text = str(obj)
        if text.startswith("to "):
            return text
        if text.startswith("what "):
            parts = text.split()  # what <subj> <verb...>
            return "what " + plural_form(parts[1]) + " had " + past_form(" ".join(parts[2:]))
        if text[:1].isupper():
            return text
        return "the " + text

    def _vp_surface(self, program: ClauseProgram) -> str:
        kind = program.predicate.get("kind")
        lemma = str(program.predicate.get("lemma"))
        negative = program.polarity == "-"
        copula = {"present": "is", "past": "was", "future": "will be"}[program.tense]
        if program.modality != "none" and kind in {"adjective", "nominal"}:
            return f"must be {lemma}" if not negative else f"must be not {lemma}"
        if kind == "adjective":
            return f"{copula} not {lemma}" if negative else f"{copula} {lemma}"
        if kind == "nominal":
            article = "an" if lemma[:1] in "aeiou" else "a"
            return f"{copula} not {article} {lemma}" if negative else f"{copula} {article} {lemma}"
        if kind == "location":
            return f"{copula} {lemma} {self.object_surface(program.obj)}"
        if kind == "comparative":
            head = f"{copula} not" if negative else copula
            return f"{head} {lemma}er than {self.object_surface(program.obj)}"
        if kind == "attitude":
            verb = lemma if program.tense != "present" else lemma
            inflected = past_form(lemma) if program.tense == "past" else third_form(lemma)
            return f"{inflected} {self.object_surface(program.obj)}"
        if kind == "passive":
            return f"{copula} not {participle_form(lemma)}" if negative else f"{copula} {participle_form(lemma)}"
        # verb
        if program.modality != "none":
            return f"{program.modality} {lemma}" + (f" {self.object_surface(program.obj)}" if program.obj else "")
        if negative:
            aux = {"present": "does", "past": "did", "future": "will"}[program.tense]
            return f"{aux} not {lemma}" + (f" {self.object_surface(program.obj)}" if program.obj else "")
        inflected = past_form(lemma) if program.tense == "past" else third_form(lemma)
        return inflected + (f" {self.object_surface(program.obj)}" if program.obj else "")

    def _statement(self, program: ClauseProgram) -> str:
        if program.quantifier in {"every", "no", "some"} and program.restrictor:
            head = {"every": "Every", "no": "No", "some": "Some"}[program.quantifier]
            restrictor = str(program.restrictor)
            if " " in restrictor and not any(restrictor.startswith(p) for p in ("tall ", "grey ")):
                # complex restrictor (reduced relative): head subj verb
                parts = restrictor.split()
                if len(parts) == 3:
                    inner = ClauseProgram(**{**program.__dict__, "quantifier": "proper",
                                             "subject": "X", "restrictor": None, "conjuncts": None, "condition": None})
                    return (f"{head} {parts[0]} the {parts[1]} would {parts[2]} "
                            f"{self._vp_surface(inner)}.")
            body = ClauseProgram(**{**program.__dict__, "conjuncts": None, "condition": None})
            return f"{head} {restrictor} {self._vp_surface(body)}."
        return f"{self.subject_surface(program)} {self._vp_surface(program)}."

    def realize(self, program: ClauseProgram) -> str:
        if program.kind == "disjunction" and program.conjuncts:
            first, second = program.conjuncts
            return f"{self.realize(first)[:-1]} or {soften(self.realize(second))[:-1]}."
        if program.kind == "conditional" and program.condition is not None:
            consequent = ClauseProgram(**{**program.__dict__, "kind": "statement", "condition": None})
            ant = soften(self.realize(program.condition))[:-1]
            cons = soften(self.realize(consequent))
            return f"If {ant}, {cons}"
        if program.conjuncts:
            # recipient pairs realize as datives; otherwise clause coordination
            if (len(program.conjuncts) == 2 and program.conjuncts[1].predicate.get("kind") == "recipient"):
                main, recipient = program.conjuncts
                if main.predicate.get("kind") == "passive":
                    return (f"{self.subject_surface(main)} {self._vp_surface(main)} "
                            f"to {recipient.obj}.")
                verb = past_form(main.predicate["lemma"]) if main.tense == "past" else third_form(main.predicate["lemma"])
                return (f"{self.subject_surface(main)} {verb} the {main.obj} to {recipient.obj}.")
            if (len(program.conjuncts) == 2 and program.conjuncts[1].predicate.get("kind") == "adjective"
                    and program.conjuncts[0].predicate.get("kind") == "verb"
                    and program.conjuncts[0].obj == program.conjuncts[1].subject):
                main, prop = program.conjuncts
                verb = past_form(main.predicate["lemma"]) if main.tense == "past" else third_form(main.predicate["lemma"])
                return f"{self.subject_surface(main)} {verb} the {main.obj} {prop.predicate['lemma']}."
            parts = [self.realize(part) for part in program.conjuncts]
            joined = parts[0][:-1]
            for part in parts[1:]:
                joined += " and " + soften(part)[:-1]
            return joined + "."
        if program.kind == "question":
            return self._question(program)
        return self._statement(program)

    def _question(self, program: ClauseProgram) -> str:
        kind = program.predicate.get("kind")
        if kind == "location" and program.predicate.get("lemma") == "?":
            return f"Where {'is' if program.tense == 'present' else 'was'} {self.subject_surface(program, capital=False)}?"
        if program.subject == "?x":
            body = ClauseProgram(**{**program.__dict__, "kind": "statement", "quantifier": "proper",
                                    "subject": "Who", "conjuncts": None, "condition": None})
            return self._statement(body)[:-1].replace("Who", "Who", 1) + "?"
        if program.obj == "?x":
            base = str(program.predicate.get("lemma"))
            return f"What did {self.subject_surface(program)} {base}?"
        if kind == "location" and program.predicate.get("lemma") == "?":
            return f"Where {'is' if program.tense == 'present' else 'was'} {self.subject_surface(program, capital=False)}?"
        statement = self._statement(ClauseProgram(**{**program.__dict__, "kind": "statement",
                                                     "conjuncts": None, "condition": None}))[:-1]
        low = statement.split()
        for index, word in enumerate(low):
            if word in {"is", "was", "are", "were", "must", "can", "could"}:
                return " ".join([word.capitalize(), *low[:index], *low[index + 1:]]) + "?"
        if program.predicate.get("kind") == "verb" and program.modality == "none":
            aux = {"present": "Does", "past": "Did", "future": "Will"}[program.tense]
            base = str(program.predicate.get("lemma"))
            tail = f" {self.object_surface(program.obj)}" if program.obj else ""
            return f"{aux} {self.subject_surface(program, capital=False)} {base}{tail}?"
        return statement + "?"


class IRPipeline2:
    """Full IR conversation path: statements, repair, yes/no/unknown, and wh answering."""

    def __init__(self, kernel):
        self.kernel = kernel

    def answer(self, passage: str) -> str:
        world = IRProofWorld()
        registry: list[dict] = []
        programs: list[ClauseProgram] = []
        last_proper = None
        question = None
        for tokens, is_question in self.kernel._sentences(passage):
            lows = [t.casefold() for t in tokens]
            if lows[:3] == ["no", "i", "meant"] and len(tokens) >= 4 and programs:
                replacement = tokens[3]
                target = programs[-1]
                old_core = core_term(target, subject_entity(target))
                for store in (world.polarity,):
                    store.pop(digest(old_core), None)
                if replacement[0].isupper():
                    if target.obj is not None:
                        target.obj = replacement
                    else:
                        target.subject = replacement
                else:
                    target.predicate = {**target.predicate, "lemma": replacement.casefold()}
                world.assert_program(target, "repair")
                continue
            tokens = [last_proper if (t.casefold() in PRONOUNS and last_proper) else t for t in tokens]
            program = self.kernel.compile_sentence(tokens, is_question)
            if program is None:
                continue
            if is_question:
                question = program if not program.conjuncts else program.conjuncts[-1]
            else:
                world.assert_program(program)
                target = program.conjuncts[0] if program.conjuncts and program.kind != "disjunction" else program
                programs.append(target)
                if target.subject and str(target.subject)[:1].isupper():
                    last_proper = str(target.subject)
        if question is None:
            return "none"
        world.saturate()
        if question.subject == "?x" or question.obj == "?x" or question.predicate.get("lemma") == "?":
            return self._wh(world, question)
        return world.ask(question)

    @staticmethod
    def _fields(core) -> dict | None:
        """Deconstruct a normalized core term into atom fields (view over terms)."""
        from stage5m13e4_oracle_logical_ir import App
        term = core
        tense = modality = None
        while isinstance(term, App) and isinstance(term.fn, Const):
            name = term.fn.name
            if name.startswith("tense:"):
                tense = name[6:]
                term = term.arg
            elif name.startswith("modal:"):
                modality = name[6:]
                term = term.arg
            else:
                break
        from stage5m13e4_oracle_logical_ir import App as A
        if isinstance(term, A) and isinstance(term.fn, A) and isinstance(term.fn.fn, Const):
            relation = term.fn.fn.name
            subject = term.fn.arg.name if isinstance(term.fn.arg, Const) else None
            obj = term.arg.name if isinstance(term.arg, Const) else None
            return {"relation": relation, "subject": subject, "obj": obj, "tense": tense, "modality": modality}
        if isinstance(term, A) and isinstance(term.fn, Const):
            return {"relation": term.fn.name, "subject": term.arg.name if isinstance(term.arg, Const) else None,
                    "obj": None, "tense": tense, "modality": modality}
        return None

    def _wh(self, world: IRProofWorld, question: ClauseProgram) -> str:
        kind = question.predicate.get("kind")
        lemma = question.predicate.get("lemma")
        matches = []
        for core in world._cores:
            if world.polarity.get(digest(core)) != "+":
                continue
            fields = self._fields(core)
            if fields is None:
                continue
            f_tense = fields["tense"] or "present"
            f_mod = fields["modality"] or "none"
            if kind == "location" and lemma == "?":
                if fields["relation"].startswith("location:") and fields["subject"] == digest_name(question.subject) \
                        and fields["obj"]:
                    matches.append(strip_ent(fields["obj"]))
                continue
            expected_relation = f"{kind}:{lemma}" if kind != "nominal" else "isa"
            if fields["relation"] != expected_relation or f_tense != question.tense or f_mod != question.modality:
                continue
            if question.subject == "?x" and (question.obj is None or strip_ent(fields["obj"] or "") == str(question.obj)):
                matches.append(strip_ent(fields["subject"] or ""))
            elif question.obj == "?x" and strip_ent(fields["subject"] or "") == str(question.subject):
                matches.append(strip_ent(fields["obj"] or ""))
        return " and ".join(sorted(set(m for m in matches if m and m != "?x"))) or "unknown"


def strip_ent(name: str) -> str:
    for prefix in ("ent:def:", "ent:sk:", "ent:", "class:"):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def digest_name(subject) -> str:
    return f"ent:def:{subject}" if subject and not str(subject)[:1].isupper() else f"ent:{subject}"


__all__ = ["IRPipeline2", "Realizer", "SCHEMA", "past_form", "third_form"]
