#!/usr/bin/env python3
"""M13e4 combinator/translation layer: ClauseProgram -> typed lambda IR + IR proof world.

Staged migration per spec: the K6 chart remains the parser; its ClauseProgram output
translates into beta-normalized, alpha-invariant, world-scoped IR terms. Inference
runs ON TERMS: universal instantiation IS beta-application of a stored scope lambda.
"""

from __future__ import annotations

from typing import Any

from stage5m13e2_construction_kernel import ClauseProgram
from stage5m13e4_oracle_logical_ir import (
    App, Const, E, EpistemicStore, Fun, GQ, Lam, T, Term, Var, digest, infer, normalize, pred,
)

SCHEMA = "oracle-stage5m13e4-combinators-v1"

ISA = Const("isa", pred(E, E, T))
NOT = Const("not", Fun(T, T))
TENSE = {name: Const(f"tense:{name}", Fun(T, T)) for name in ("present", "past", "future")}
MODAL = {name: Const(f"modal:{name}", Fun(T, T)) for name in ("must", "may", "can", "could")}

BINARY_KINDS = {"verb", "location", "comparative", "recipient", "attitude", "passive"}


def entity(name: Any) -> Const:
    return Const(f"ent:{name}", E)


def class_entity(lemma: Any) -> Const:
    return Const(f"class:{lemma}", E)


def _atom(program: ClauseProgram, subject_term: Term) -> Term:
    kind = program.predicate.get("kind")
    lemma = program.predicate.get("lemma")
    if kind == "nominal":
        return App(App(ISA, subject_term), class_entity(lemma))
    if kind in BINARY_KINDS and program.obj is not None:
        relation = Const(f"{kind}:{lemma}", pred(E, E, T))
        return App(App(relation, subject_term), entity(program.obj))
    predicate = Const(f"{kind}:{lemma}", pred(E, T))
    return App(predicate, subject_term)


def _wrap(program: ClauseProgram, atom: Term) -> Term:
    term = atom
    if program.modality and program.modality != "none":
        term = App(MODAL.get(program.modality, Const(f"modal:{program.modality}", Fun(T, T))), term)
    term = App(TENSE.get(program.tense, TENSE["present"]), term)
    return term


def core_term(program: ClauseProgram, subject_term: Term) -> Term:
    """Polarity is carried OUTSIDE the core (mirrors the kernel's key/polarity split)."""
    return normalize(_wrap(program, _atom(program, subject_term)))


def subject_entity(program: ClauseProgram) -> Term:
    if program.subject is not None:
        prefix = "ent:" if program.quantifier == "proper" else "ent:def:"
        return Const(prefix + str(program.subject), E)
    return Const(f"ent:sk:{program.restrictor}", E)  # existential skolem


class IRProofWorld:
    """Ground store + lambda rules; the four inference laws run on normalized terms."""

    def __init__(self, world: str = "user_temporary_world"):
        self.world = world
        self.store = EpistemicStore()
        self.polarity: dict[str, str] = {}
        self.rules: list[dict] = []
        self.conditionals: list[dict] = []
        self.disjunctions: list[dict] = []
        self.entities: set[str] = set()
        self._cores: list[Term] = []

    # ---- assertion ----

    def _assert_core(self, core: Term, polarity: str, provenance: str):
        self.store.assert_(self.world, core, polarity == "+", provenance)
        self._cores.append(core)
        key = digest(core)
        held = self.polarity.get(key)
        self.polarity[key] = polarity if held in (None, polarity) else "!"

    def assert_program(self, program: ClauseProgram, provenance: str = "supplied"):
        if program.conjuncts and program.kind == "disjunction":
            first, second = program.conjuncts
            self.disjunctions.append({
                "a": core_term(first, subject_entity(first)), "pa": first.polarity,
                "b": core_term(second, subject_entity(second)), "pb": second.polarity})
            for side in (first, second):
                self.entities.add(digest(subject_entity(side)))
            return
        if program.kind == "conditional" and program.condition is not None:
            antecedent = program.condition
            self.conditionals.append({
                "ant": core_term(antecedent, subject_entity(antecedent)), "ant_pol": antecedent.polarity,
                "cons_program": program})
            return
        if program.conjuncts:
            for part in program.conjuncts:
                self.assert_program(part, provenance)
            return
        if program.quantifier in {"every", "no"}:
            x = Var("x", E)
            scope = Lam(x, _wrap(program, _atom(program, x)))
            infer(scope)
            self.rules.append({"restrictor": str(program.restrictor), "scope": scope,
                               "polarity": "-" if program.quantifier == "no" else program.polarity})
            return
        subject = subject_entity(program)
        self.entities.add(digest(subject))
        if program.quantifier == "some" and program.restrictor:
            self._assert_core(normalize(App(TENSE[program.tense], App(App(ISA, subject), class_entity(program.restrictor)))),
                              "+", provenance)
        self._assert_core(core_term(program, subject), program.polarity, provenance)

    # ---- inference: instantiation IS beta-application ----

    def saturate(self, budget: int = 64):
        constants: dict[str, Term] = {}

        def collect(term: Term):
            if isinstance(term, Const) and term.ctype == E and term.name.startswith("ent:"):
                constants[term.name] = term
            elif isinstance(term, App):
                collect(term.fn)
                collect(term.arg)
            elif isinstance(term, Lam):
                collect(term.body)

        for record in self.rules:
            collect(record["scope"])
        for record in self.conditionals:
            collect(record["ant"])
        for record in self.disjunctions:
            collect(record["a"])
            collect(record["b"])
        for core in self._cores:
            collect(core)

        progressed = True
        iterations = 0
        while progressed and iterations < budget:
            progressed = False
            iterations += 1
            for rule in self.rules:
                member_class = class_entity(rule["restrictor"])
                for name, const in list(constants.items()):
                    membership = None
                    for tense_const in TENSE.values():
                        candidate = normalize(App(tense_const, App(App(ISA, const), member_class)))
                        if self.polarity.get(digest(candidate)) == "+":
                            membership = True
                            break
                    if not membership:
                        continue
                    derived = normalize(App(rule["scope"], const))
                    key = digest(derived)
                    if key not in self.polarity:
                        self._assert_core(derived, rule["polarity"], f"instantiation:{rule['restrictor']}")
                        collect(derived)
                        progressed = True
            for conditional in self.conditionals:
                if self.polarity.get(digest(conditional["ant"])) == conditional["ant_pol"]:
                    consequent = conditional["cons_program"]
                    core = core_term(consequent, subject_entity(consequent))
                    if digest(core) not in self.polarity:
                        self._assert_core(core, consequent.polarity, "modus_ponens")
                        collect(core)
                        progressed = True
            for disjunction in self.disjunctions:
                for this_core, this_pol, other_core, other_pol in (
                        (disjunction["a"], disjunction["pa"], disjunction["b"], disjunction["pb"]),
                        (disjunction["b"], disjunction["pb"], disjunction["a"], disjunction["pa"])):
                    held = self.polarity.get(digest(this_core))
                    if held is not None and held != this_pol and digest(other_core) not in self.polarity:
                        self._assert_core(other_core, other_pol, "disjunctive_syllogism")
                        collect(other_core)
                        progressed = True

    def ask(self, program: ClauseProgram) -> str:
        core = core_term(program, subject_entity(program))
        held = self.polarity.get(digest(core))
        if held is None or held == "!":
            return "unknown" if held is None else ("yes" if program.polarity == "+" else "no")
        return "yes" if held == program.polarity else "no"


class IRPipeline:
    """kernel parse -> translate -> IR world -> verdict (yes/no/unknown path)."""

    def __init__(self, kernel):
        self.kernel = kernel

    def answer(self, passage: str) -> str:
        world = IRProofWorld()
        last_proper = None
        from stage5m13e2_construction_kernel_k2 import PRONOUNS
        question_program = None
        for tokens, is_question in self.kernel._sentences(passage):
            lows = [t.casefold() for t in tokens]
            if lows[:3] == ["no", "i", "meant"] and len(tokens) >= 4:
                # repair handled by the kernel path; replay via kernel world instead
                return "UNSUPPORTED_REPAIR"
            tokens = [last_proper if (t.casefold() in PRONOUNS and last_proper) else t for t in tokens]
            program = self.kernel.compile_sentence(tokens, is_question)
            if program is None:
                continue
            if is_question:
                question_program = program if not program.conjuncts else program.conjuncts[-1]
            else:
                world.assert_program(program)
                target = program.conjuncts[0] if program.conjuncts and program.kind != "disjunction" else program
                if target.subject and str(target.subject)[:1].isupper():
                    last_proper = str(target.subject)
        if question_program is None:
            return "none"
        world.saturate()
        return world.ask(question_program)


def translate(program: ClauseProgram) -> Term:
    """Full typed translation of one program (for the translation gate)."""
    if program.conjuncts:
        AND = Const("and", Fun(T, Fun(T, T)))
        term = translate(program.conjuncts[0])
        for part in program.conjuncts[1:]:
            term = App(App(AND, term), translate(part))
        return normalize(term)
    if program.kind == "conditional" and program.condition is not None:
        IF = Const("if", Fun(T, Fun(T, T)))
        consequent = ClauseProgram(**{**program.__dict__, "kind": "statement", "condition": None, "conjuncts": None})
        return normalize(App(App(IF, translate(program.condition)), translate(consequent)))
    if program.quantifier in {"every", "no", "some"} and program.restrictor:
        quant = Const(program.quantifier, GQ)
        x = Var("x", E)
        restrictor = Lam(x, App(App(ISA, x), class_entity(program.restrictor)))
        scope = Lam(x, _wrap(program, _atom(program, x)))
        term = App(App(quant, restrictor), scope)
        return normalize(term if program.polarity == "+" else App(NOT, term))
    core = _wrap(program, _atom(program, subject_entity(program)))
    return normalize(core if program.polarity == "+" else App(NOT, core))


__all__ = ["IRPipeline", "IRProofWorld", "SCHEMA", "core_term", "translate"]
