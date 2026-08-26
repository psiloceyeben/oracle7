#!/usr/bin/env python3
"""M13e2 E2-K2: additive extension — wh-questions, disjunction, modality, pronouns, repair."""

from __future__ import annotations

from typing import Any

from stage5m13e2_construction_kernel import (
    ARTICLES, AUXILIARIES, CLOSED_CLASS, COPULAS, QUANTIFIERS, ClauseProgram, ConstructionKernel, Item,
    _get, _object_of, _sem, _subject_of,
)

SCHEMA = "oracle-stage5m13e2-construction-kernel-k2-v1"

WH_WORDS = {"who", "what", "which"}
MODALS = {"must": "must", "may": "may"}
PRONOUNS = {"he", "she", "it", "they"}

# K2 closed-class words join the ablation shape alphabet so shape memory stays honest.
CLOSED_CLASS |= WH_WORDS | set(MODALS) | {"or", "be"}


class ConstructionKernelK2(ConstructionKernel):
    """K1 plus: wh-questions, or-coordination with disjunctive syllogism, must/may
    modality as a typed feature, within-passage pronoun reference, and premise repair."""

    # ---------------- lexicon ----------------

    def _lexical(self, token: str, position: int) -> list[Item]:
        low = token.casefold()
        span = (position, position + 1)
        items = super()._lexical(token, position)
        if low in WH_WORDS:
            items = [item for item in items if item.category != "NAME"]
            items.append(Item("NAME", _sem(name="?x"), span))
        if low in MODALS:
            items.append(Item("MODAL", _sem(modality=MODALS[low]), span))
        if low == "be":
            items.append(Item("COPBASE", _sem(), span))
        if low == "or":
            items.append(Item("OR", _sem(), span))
        return items

    # ---------------- construction rules ----------------

    def _combine(self, left: Item, right: Item) -> list[Item]:
        out = super()._combine(left, right)
        span = (left.span[0], right.span[1])
        if left.category == "MODAL" and right.category == "COPBASE":
            out.append(Item("MODCOP", _sem(modality=_get(left.semantics, "modality"), tense="present"), span))
        if left.category == "MODCOP":
            if right.category == "ADJ":
                out.append(Item("VP", _sem(kind="adjective", lemma=_get(right.semantics, "lemma"), polarity="+",
                                           tense="present", modality=_get(left.semantics, "modality")), span))
            if right.category == "NEGADJ":
                out.append(Item("VP", _sem(kind="adjective", lemma=_get(right.semantics, "lemma"), polarity="-",
                                           tense="present", modality=_get(left.semantics, "modality")), span))
            if right.category == "DNP":
                out.append(Item("VP", _sem(kind="nominal", lemma=_get(right.semantics, "lemma"), polarity="+",
                                           tense="present", modality=_get(left.semantics, "modality")), span))
        if left.category == "OR" and right.category == "CL":
            out.append(Item("ORCL", right.semantics, span))
        if left.category == "CL" and right.category == "ORCL":
            out.append(Item("CLDISJ", _sem(first=left.semantics, second=right.semantics), span))
        return out

    # ---------------- parsing ----------------

    def _parse_tokens(self, tokens: list[str], question: bool):
        low0 = tokens[0].casefold() if tokens else ""
        if question and low0 in MODALS and len(tokens) >= 2:
            # modal inversion: Must NP be ADJ? -> NP must be ADJ
            rest = tokens[1:]
            np_length = 2 if len(rest) >= 2 and rest[0].casefold() in (ARTICLES | set(QUANTIFIERS)) else 1
            tokens = [*rest[:np_length], tokens[0], *rest[np_length:]]
        elif question and low0 in WH_WORDS and len(tokens) >= 4 and tokens[1].casefold() in AUXILIARIES:
            # wh-object: What did NP V? -> NP did V What
            wh, rest = tokens[0], tokens[1:]
            aux, after = rest[0], rest[1:]
            np_length = 2 if len(after) >= 2 and after[0].casefold() in (ARTICLES | set(QUANTIFIERS)) else 1
            tokens = [*after[:np_length], aux, *after[np_length:], wh]
        return super()._parse_tokens(tokens, question)

    # ---------------- item -> program ----------------

    @staticmethod
    def _clause_from(semantics: tuple, question: bool) -> ClauseProgram:
        program = ConstructionKernel._clause_from(semantics, question)
        vp = _get(semantics, "vp")
        program.modality = _get(vp, "modality") or "none"
        return program

    def compile_sentence(self, tokens: list[str], question: bool) -> ClauseProgram | None:
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
        program = super().compile_sentence(tokens, question)
        return program

    # ---------------- world + proof ----------------

    @staticmethod
    def fresh_world() -> dict[str, Any]:
        return {"facts": [], "rules": [], "conditionals": [], "disjunctions": [], "last_proper": None}

    def evaluate(self, text: str, world: dict[str, Any] | None = None) -> dict[str, Any]:
        if world is None:
            world = self.fresh_world()
        facts: list[ClauseProgram] = world["facts"]
        rules: list[ClauseProgram] = world["rules"]
        conditionals: list[ClauseProgram] = world["conditionals"]
        disjunctions: list[tuple[ClauseProgram, ClauseProgram]] = world["disjunctions"]
        question: ClauseProgram | None = None
        unparsed: list[str] = []
        last_proper: str | None = world.get("last_proper")
        repairs = 0
        for tokens, is_question in self._sentences(text):
            lows = [t.casefold() for t in tokens]
            if lows[:3] == ["no", "i", "meant"] and len(tokens) >= 4 and facts:
                replacement = tokens[3]
                target = facts[-1]
                if replacement[0].isupper():
                    # argument correction: replace the object if present, else the subject
                    if target.obj is not None:
                        target.obj = replacement
                    else:
                        target.subject = replacement
                else:
                    # predicate correction: replace the predicate lemma
                    target.predicate = {**target.predicate, "lemma": replacement.casefold()}
                repairs += 1
                continue
            tokens = [last_proper if (t.casefold() in PRONOUNS and last_proper) else t for t in tokens]
            program = self.compile_sentence(tokens, is_question)
            if program is None:
                unparsed.append(" ".join(tokens))
                continue
            if program.kind == "disjunction" and program.conjuncts:
                disjunctions.append((program.conjuncts[0], program.conjuncts[1]))
                continue
            targets = program.conjuncts if program.conjuncts else [program]
            for target in targets:
                if is_question:
                    question = target
                elif target.kind == "conditional" or program.kind == "conditional":
                    conditionals.append(program if program.kind == "conditional" else target)
                elif target.quantifier in {"every", "no"}:
                    rules.append(target)
                else:
                    facts.append(target)
                    if target.subject and target.subject[0].isupper():
                        last_proper = target.subject
        world["last_proper"] = last_proper
        if unparsed:
            return {"status": "clarification", "operation": "m13e2_unparsed_residue",
                    "response": "I could not compile: " + "; ".join(unparsed),
                    "unparsed": unparsed, "factual_release": False}
        if question is None:
            return {"status": "answered", "operation": "m13e2_world_update",
                    "response": f"Registered {len(facts)} facts, {len(rules)} rules, {len(conditionals)} "
                                f"conditionals, {len(disjunctions)} disjunctions, {repairs} repairs.",
                    "factual_release": False}
        derived, classes = self._derive(facts, rules, conditionals, disjunctions)
        if question.subject == "?x" or question.obj == "?x":
            matches = self._wh_matches(question, derived)
            if not matches:
                return {"status": "answered", "operation": "m13e2_wh_question",
                        "response": "Unknown. No entity in the supplied premises satisfies that description.",
                        "factual_release": False, "authority_class": "temporary_user_supplied_world",
                        "program": question.public()}
            surface = " and ".join(sorted(matches))
            return {"status": "answered", "operation": "m13e2_wh_question",
                    "response": f"{surface}.", "factual_release": False,
                    "authority_class": "temporary_user_supplied_world",
                    "proof": {"premises": [f"derived for {name}" for name in sorted(matches)],
                              "rule": "wh_extraction_over_derived_store", "conclusion": surface},
                    "program": question.public(), "program_digest": question.digest()}
        key = (question.subject, question.predicate["kind"], question.predicate["lemma"],
               question.obj, question.tense, question.modality)
        held = derived.get(key)
        if held is None:
            verdict, premises, rule_name = "unknown", [], "not_derivable"
        else:
            polarity, premise, rule_name = held
            verdict = "yes" if polarity == question.polarity else "no"
            premises = [premise]
        answers = {"yes": "Yes", "no": "No", "unknown": "Unknown"}
        conclusion = self._render(question, verdict)
        return {"status": "answered", "operation": "m13e2_compositional_premise_proof",
                "response": f"{answers[verdict]}. {conclusion}", "factual_release": False,
                "authority_class": "temporary_user_supplied_world",
                "proof": {"premises": premises, "rule": rule_name, "conclusion": conclusion},
                "program": question.public(), "program_digest": question.digest()}

    def _derive(self, facts, rules, conditionals, disjunctions):
        classes: dict[str, set[str]] = {}
        for fact in facts:
            if fact.predicate.get("kind") == "nominal" and fact.subject and fact.polarity == "+":
                classes.setdefault(fact.subject, set()).add(fact.predicate["lemma"])
        changed = True
        while changed:
            changed = False
            for rule in rules:
                if rule.predicate.get("kind") != "nominal" or rule.quantifier != "every":
                    continue
                for subject, kinds in classes.items():
                    if rule.restrictor in kinds and rule.predicate["lemma"] not in kinds:
                        kinds.add(rule.predicate["lemma"])
                        changed = True
        derived: dict[tuple, tuple[str, str, str]] = {}

        def key_of(p: ClauseProgram):
            return (p.subject, p.predicate["kind"], p.predicate["lemma"], p.obj, p.tense, p.modality)

        for fact in facts:
            k = key_of(fact)
            if k not in derived:
                derived[k] = (fact.polarity, self._render(fact, "yes" if fact.polarity == "+" else "no"), "supplied_fact")
        progressed = True
        iterations = 0
        while progressed and iterations < 64:
            progressed = False
            iterations += 1
            for rule in rules:
                for subject, kinds in classes.items():
                    if rule.restrictor not in kinds:
                        continue
                    polarity = "-" if rule.quantifier == "no" else rule.polarity
                    k = (subject, rule.predicate["kind"], rule.predicate["lemma"], rule.obj, rule.tense, rule.modality)
                    if k not in derived:
                        derived[k] = (polarity, self._render(rule, "yes"),
                                      "negative_universal_instantiation" if polarity == "-" else "universal_instantiation")
                        progressed = True
            for conditional in conditionals:
                antecedent = conditional.condition
                held = derived.get(key_of(antecedent))
                if held and held[0] == antecedent.polarity:
                    k = key_of(conditional)
                    if k not in derived:
                        derived[k] = (conditional.polarity, self._render(conditional, "yes"), "modus_ponens")
                        progressed = True
            for first, second in disjunctions:
                for this, other in ((first, second), (second, first)):
                    held = derived.get(key_of(this))
                    if held and held[0] != this.polarity:
                        k = key_of(other)
                        if k not in derived:
                            derived[k] = (other.polarity,
                                          self._render(this, "no") + "; " + self._render(other, "yes"),
                                          "disjunctive_syllogism")
                            progressed = True
        return derived, classes

    @staticmethod
    def _wh_matches(question: ClauseProgram, derived) -> list[str]:
        matches = []
        for (subject, kind, lemma, obj, tense, modality), (polarity, _premise, _rule) in derived.items():
            if kind != question.predicate["kind"] or lemma != question.predicate["lemma"]:
                continue
            if tense != question.tense or modality != question.modality or polarity != "+":
                continue
            if question.subject == "?x" and (question.obj is None or question.obj == obj):
                if subject and subject != "?x":
                    matches.append(str(subject))
            elif question.obj == "?x" and question.subject == subject:
                if obj and obj != "?x":
                    matches.append(str(obj))
        return matches


__all__ = ["ConstructionKernelK2", "SCHEMA"]
