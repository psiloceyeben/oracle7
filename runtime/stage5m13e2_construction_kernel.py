#!/usr/bin/env python3
"""M13e2 E2-K1: productive construction kernel.

Typed lexicon + CKY chart parse over construction rules -> ClauseProgram IR ->
temporary premise world with forward-chaining proof -> answer with premises/rule/
conclusion. Negation, tense, and quantification are feature transformers that
compose with every clause rule, so withheld combinations of known constructions
parse without combination-specific rules. `compositional=False` ablates the
kernel to whole-signature memory for the causal transfer test.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "oracle-stage5m13e2-construction-kernel-v1"

QUANTIFIERS = {"every": "every", "each": "every", "no": "no", "some": "some"}
ARTICLES = {"a", "an", "the"}
COPULAS = {"is": ("present", "sg"), "are": ("present", "pl"), "was": ("past", "sg"), "were": ("past", "pl")}
AUXILIARIES = {"did": "past", "does": "present", "do": "present", "will": "future"}
NEGATIONS = {"not", "never"}
IRREGULAR_PAST = {"went": "go", "made": "make", "took": "take", "gave": "give", "held": "hold",
                  "built": "build", "sold": "sell", "bought": "buy", "taught": "teach", "kept": "keep"}


def _lemma_from_past(token: str) -> str | None:
    if token in IRREGULAR_PAST:
        return IRREGULAR_PAST[token]
    if token.endswith("ied") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("ed") and len(token) > 3:
        base = token[:-2]
        if base.endswith(("v", "s", "z", "c", "u")) or base[-1] not in "aeiou" and base[-1] * 2 == base[-2:]:
            pass
        candidate = base + "e"
        return candidate if base and base[-1] in "vszcu" else base
    return None


def _lemma_from_3sg(token: str) -> str | None:
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("es") and re.search(r"(?:s|x|z|ch|sh)es$", token):
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss") and len(token) > 2:
        return token[:-1]
    return None


def _singular(noun: str) -> str:
    if noun.endswith("ies") and len(noun) > 4:
        return noun[:-3] + "y"
    if noun.endswith("es") and re.search(r"(?:s|x|z|ch|sh)es$", noun):
        return noun[:-2]
    if noun.endswith("s") and not noun.endswith("ss") and len(noun) > 2:
        return noun[:-1]
    return noun


@dataclass(frozen=True)
class Item:
    category: str
    semantics: tuple  # hashable payload
    span: tuple


CLOSED_CLASS = set(QUANTIFIERS) | ARTICLES | set(COPULAS) | set(AUXILIARIES) | NEGATIONS | {"and", "if"}


def _subject_of(item: "Item") -> tuple:
    if item.category == "NAME":
        return ("proper", _get(item.semantics, "name"))
    if item.category == "QNP":
        return ("quant", (_get(item.semantics, "quant"), _get(item.semantics, "restrictor")))
    return ("definite", _get(item.semantics, "lemma"))


def _object_of(item: "Item") -> tuple:
    if item.category == "NAME":
        return ("proper", _get(item.semantics, "name"))
    if item.category == "QNP":
        return ("quant", (_get(item.semantics, "quant"), _get(item.semantics, "restrictor")))
    return ("definite", _get(item.semantics, "lemma"))


def _sem(**kwargs) -> tuple:
    return tuple(sorted(kwargs.items()))


def _get(semantics: tuple, key: str, default=None):
    for name, value in semantics:
        if name == key:
            return value
    return default


@dataclass
class ClauseProgram:
    kind: str = "statement"          # statement | question | conditional
    quantifier: str = "proper"       # proper | every | no | some | definite
    restrictor: str | None = None
    subject: str | None = None
    predicate: dict[str, Any] = field(default_factory=dict)
    obj: str | None = None
    polarity: str = "+"
    tense: str = "present"
    modality: str = "none"
    condition: "ClauseProgram | None" = None
    conjuncts: "list[ClauseProgram] | None" = None

    def public(self) -> dict[str, Any]:
        value = {
            "kind": self.kind, "quantifier": self.quantifier, "restrictor": self.restrictor,
            "subject": self.subject, "predicate": self.predicate, "object": self.obj,
            "polarity": self.polarity, "tense": self.tense, "modality": self.modality,
        }
        if self.condition is not None:
            value["condition"] = self.condition.public()
        if self.conjuncts is not None:
            value["conjuncts"] = [item.public() for item in self.conjuncts]
        return value

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.public(), sort_keys=True).encode()).hexdigest()


class ConstructionKernel:
    def __init__(self, *, compositional: bool = True):
        self.compositional = compositional
        self.memorized_signatures: set[tuple] = set()

    # ---------------- tokenization ----------------

    @staticmethod
    def _sentences(text: str) -> list[tuple[list[str], bool]]:
        out = []
        for raw in re.split(r"(?<=[.?!])\s+", " ".join(str(text).split())):
            raw = raw.strip()
            if not raw:
                continue
            question = raw.endswith("?")
            tokens = [t for t in re.findall(r"[A-Za-z][A-Za-z'-]*", raw) if t.casefold() not in {"then"}]
            if tokens:
                out.append((tokens, question))
        return out

    # ---------------- lexicon ----------------

    @staticmethod
    def _lexical(token: str, position: int) -> list[Item]:
        low = token.casefold()
        items: list[Item] = []
        span = (position, position + 1)
        if low in QUANTIFIERS:
            items.append(Item("Q", _sem(quant=QUANTIFIERS[low]), span))
        if low in ARTICLES:
            items.append(Item("DET", _sem(article=low), span))
        if low in COPULAS:
            tense, number = COPULAS[low]
            items.append(Item("COP", _sem(tense=tense, number=number), span))
        if low in AUXILIARIES:
            items.append(Item("AUX", _sem(tense=AUXILIARIES[low]), span))
        if low in NEGATIONS:
            items.append(Item("NEG", _sem(), span))
        if low == "and":
            items.append(Item("AND", _sem(), span))
        if low == "if":
            items.append(Item("IF", _sem(), span))
        if token[0].isupper() and position > 0 and low not in QUANTIFIERS and low not in {"if"}:
            items.append(Item("NAME", _sem(name=token), span))
        if token[0].isupper() and position == 0:
            # sentence-initial capitalized token: could be a name or an ordinary word
            items.append(Item("NAME", _sem(name=token), span))
        if low.isalpha():
            items.append(Item("N", _sem(lemma=_singular(low)), span))
            items.append(Item("ADJ", _sem(lemma=low), span))
            items.append(Item("VBASE", _sem(lemma=low), span))
            past = _lemma_from_past(low)
            if past:
                items.append(Item("VF", _sem(lemma=past, tense="past"), span))
            third = _lemma_from_3sg(low)
            if third:
                items.append(Item("VF", _sem(lemma=third, tense="present"), span))
        return items

    # ---------------- construction rules ----------------

    @staticmethod
    def _combine(left: Item, right: Item) -> list[Item]:
        out: list[Item] = []
        span = (left.span[0], right.span[1])
        if left.category == "Q" and right.category == "N":
            out.append(Item("QNP", _sem(quant=_get(left.semantics, "quant"), restrictor=_get(right.semantics, "lemma")), span))
        if left.category == "DET" and right.category == "N":
            out.append(Item("DNP", _sem(article=_get(left.semantics, "article"), lemma=_get(right.semantics, "lemma")), span))
        if left.category == "NEG" and right.category == "ADJ":
            out.append(Item("NEGADJ", _sem(lemma=_get(right.semantics, "lemma")), span))
        if left.category == "NEG" and right.category == "DNP":
            out.append(Item("NEGDNP", _sem(lemma=_get(right.semantics, "lemma")), span))
        if left.category == "COP":
            tense = _get(left.semantics, "tense")
            if right.category == "ADJ":
                out.append(Item("VP", _sem(kind="adjective", lemma=_get(right.semantics, "lemma"), polarity="+", tense=tense), span))
            if right.category == "NEGADJ":
                out.append(Item("VP", _sem(kind="adjective", lemma=_get(right.semantics, "lemma"), polarity="-", tense=tense), span))
            if right.category == "DNP":
                out.append(Item("VP", _sem(kind="nominal", lemma=_get(right.semantics, "lemma"), polarity="+", tense=tense), span))
            if right.category == "NEGDNP":
                out.append(Item("VP", _sem(kind="nominal", lemma=_get(right.semantics, "lemma"), polarity="-", tense=tense), span))
        if left.category == "VF" and right.category in {"NAME", "QNP", "DNP"}:
            out.append(Item("VP", _sem(kind="verb", lemma=_get(left.semantics, "lemma"),
                                       obj=_object_of(right), polarity="+", tense=_get(left.semantics, "tense")), span))
        if left.category == "VBASE" and right.category in {"NAME", "QNP", "DNP"}:
            out.append(Item("VPBASE", _sem(lemma=_get(left.semantics, "lemma"), obj=_object_of(right)), span))
        if left.category == "AUX" and right.category == "VPBASE":
            out.append(Item("VP", _sem(kind="verb", lemma=_get(right.semantics, "lemma"), obj=_get(right.semantics, "obj"),
                                       polarity="+", tense=_get(left.semantics, "tense")), span))
        if left.category == "AUX" and right.category == "NEG":
            out.append(Item("AUXNEG", _sem(tense=_get(left.semantics, "tense")), span))
        if left.category == "AUXNEG" and right.category == "VPBASE":
            out.append(Item("VP", _sem(kind="verb", lemma=_get(right.semantics, "lemma"), obj=_get(right.semantics, "obj"),
                                       polarity="-", tense=_get(left.semantics, "tense")), span))
        if left.category in {"NAME", "QNP", "DNP"} and right.category == "VP":
            out.append(Item("CL", _sem(subject=_subject_of(left), vp=right.semantics), span))
        if left.category == "AND" and right.category == "CL":
            out.append(Item("ANDCL", right.semantics, span))
        if left.category == "CL" and right.category == "ANDCL":
            out.append(Item("CLCONJ", _sem(first=left.semantics, second=right.semantics), span))
        if left.category == "IF" and right.category in {"CL", "CLCONJ"}:
            out.append(Item("IFCL", right.semantics, span))
        if left.category == "IFCL" and right.category in {"CL", "CLCONJ"}:
            out.append(Item("COND", _sem(condition=left.semantics, consequent=right.semantics), span))
        return out

    # ---------------- parsing ----------------

    def _parse_tokens(self, tokens: list[str], question: bool) -> tuple[list[Item], tuple]:
        if question and tokens and tokens[0].casefold() in (set(COPULAS) | set(AUXILIARIES)):
            # subject-auxiliary inversion: [COP|AUX] NP REST -> NP [COP|AUX] REST,
            # where NP spans two tokens when it opens with a determiner or quantifier
            aux, rest = tokens[0], tokens[1:]
            np_length = 2 if len(rest) >= 2 and rest[0].casefold() in (ARTICLES | set(QUANTIFIERS)) else 1
            tokens = [*rest[:np_length], aux, *rest[np_length:]]
        n = len(tokens)
        chart: dict[tuple, list[Item]] = {}
        for i, token in enumerate(tokens):
            chart[(i, i + 1)] = self._lexical(token, i)
        for width in range(2, n + 1):
            for start in range(0, n - width + 1):
                end = start + width
                cell: list[Item] = []
                seen: set[tuple] = set()
                for middle in range(start + 1, end):
                    for left in chart.get((start, middle), ()):
                        for right in chart.get((middle, end), ()):
                            for item in self._combine(left, right):
                                key = (item.category, item.semantics)
                                if key not in seen:
                                    seen.add(key)
                                    cell.append(item)
                chart[(start, end)] = cell
        shape = tuple(t.casefold() if t.casefold() in CLOSED_CLASS else "W" for t in tokens)
        return chart.get((0, n), []), shape

    # ---------------- item -> program ----------------

    @staticmethod
    def _clause_from(semantics: tuple, question: bool) -> ClauseProgram:
        subject_kind, subject_value = _get(semantics, "subject")
        vp = _get(semantics, "vp")
        program = ClauseProgram(kind="question" if question else "statement")
        if subject_kind == "proper":
            program.subject = subject_value
        elif subject_kind == "quant":
            program.quantifier, program.restrictor = subject_value
        else:
            program.quantifier, program.subject = "definite", subject_value
        program.predicate = {"kind": _get(vp, "kind"), "lemma": _get(vp, "lemma")}
        obj = _get(vp, "obj")
        if obj is not None:
            program.obj = obj[1] if obj[0] == "proper" else obj[1]
        program.polarity = _get(vp, "polarity")
        program.tense = _get(vp, "tense")
        return program

    def compile_sentence(self, tokens: list[str], question: bool) -> ClauseProgram | None:
        items, shape = self._parse_tokens(tokens, question)
        if not self.compositional:
            if shape not in self.memorized_signatures:
                return None
        else:
            self.memorized_signatures.add(shape)
        for category in ("COND", "CLCONJ", "CL"):
            for item in items:
                if item.category != category:
                    continue
                if category == "CL":
                    return self._clause_from(item.semantics, question)
                if category == "CLCONJ":
                    first = self._clause_from(_get(item.semantics, "first"), question)
                    second = self._clause_from(_get(item.semantics, "second"), question)
                    program = ClauseProgram(kind="question" if question else "statement", conjuncts=[first, second])
                    return program
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
        return None

    # ---------------- world + proof ----------------

    def evaluate(self, text: str) -> dict[str, Any]:
        """Compile a passage; statements build the temporary world; a final question is proved."""
        facts: list[ClauseProgram] = []
        rules: list[ClauseProgram] = []
        conditionals: list[ClauseProgram] = []
        question: ClauseProgram | None = None
        unparsed: list[str] = []
        for tokens, is_question in self._sentences(text):
            program = self.compile_sentence(tokens, is_question)
            if program is None:
                unparsed.append(" ".join(tokens))
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
        if unparsed:
            return {"status": "clarification", "operation": "m13e2_unparsed_residue",
                    "response": "I could not compile: " + "; ".join(unparsed),
                    "unparsed": unparsed, "factual_release": False}
        if question is None:
            return {"status": "answered", "operation": "m13e2_world_update",
                    "response": f"Registered {len(facts)} facts, {len(rules)} quantified rules, "
                                f"{len(conditionals)} conditionals in the temporary world.",
                    "factual_release": False}
        verdict, premises, rule_name = self._prove(question, facts, rules, conditionals)
        answers = {"yes": "Yes", "no": "No", "unknown": "Unknown"}
        conclusion = self._render(question, verdict)
        return {
            "status": "answered", "operation": "m13e2_compositional_premise_proof",
            "response": f"{answers[verdict]}. {conclusion}",
            "factual_release": False, "authority_class": "temporary_user_supplied_world",
            "proof": {"premises": premises, "rule": rule_name, "conclusion": conclusion},
            "program": question.public(), "program_digest": question.digest(),
        }

    def _prove(self, question: ClauseProgram, facts, rules, conditionals) -> tuple[str, list[str], str]:
        # derive class memberships (kindOf closure over nominal facts and rules)
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
        # derived positive/negative property store: (subject, kind, lemma, obj, tense) -> polarity
        derived: dict[tuple, tuple[str, str, str]] = {}

        def note(subject, predicate, obj, tense, polarity, premise, rule_name):
            key = (subject, predicate["kind"], predicate["lemma"], obj, tense)
            if key not in derived:
                derived[key] = (polarity, premise, rule_name)

        for fact in facts:
            note(fact.subject, fact.predicate, fact.obj, fact.tense, fact.polarity,
                 self._render(fact, "yes" if fact.polarity == "+" else "no"), "supplied_fact")
        progressed = True
        iterations = 0
        while progressed and iterations < 32:
            progressed = False
            iterations += 1
            for rule in rules:
                for subject, kinds in classes.items():
                    if rule.restrictor not in kinds:
                        continue
                    polarity = "-" if rule.quantifier == "no" else rule.polarity
                    key = (subject, rule.predicate["kind"], rule.predicate["lemma"], rule.obj, rule.tense)
                    if key not in derived:
                        derived[key] = (polarity, self._render(rule, "yes"),
                                        "negative_universal_instantiation" if polarity == "-" else "universal_instantiation")
                        progressed = True
            for conditional in conditionals:
                antecedent = conditional.condition
                key = (antecedent.subject, antecedent.predicate["kind"], antecedent.predicate["lemma"],
                       antecedent.obj, antecedent.tense)
                held = derived.get(key)
                if held and held[0] == antecedent.polarity:
                    consequent_key = (conditional.subject, conditional.predicate["kind"],
                                      conditional.predicate["lemma"], conditional.obj, conditional.tense)
                    if consequent_key not in derived:
                        derived[consequent_key] = (conditional.polarity,
                                                   self._render(conditional, "yes"), "modus_ponens")
                        progressed = True
        key = (question.subject, question.predicate["kind"], question.predicate["lemma"], question.obj, question.tense)
        held = derived.get(key)
        if held is None:
            return "unknown", [], "not_derivable"
        polarity, premise, rule_name = held
        if polarity == question.polarity:
            return "yes", [premise], rule_name
        return "no", [premise], rule_name

    @staticmethod
    def _render(program: ClauseProgram, verdict: str) -> str:
        negative = (verdict == "no") ^ (program.polarity == "-")
        subject = program.subject if program.subject else (
            {"every": "every", "no": "no", "some": "some"}.get(program.quantifier, "") + " " + str(program.restrictor)).strip()
        predicate = program.predicate.get("lemma", "")
        kind = program.predicate.get("kind")
        if program.kind == "conditional" and program.condition is not None:
            condition = ConstructionKernel._render(program.condition, "yes")
            consequent = ConstructionKernel._render(
                ClauseProgram(subject=program.subject, quantifier=program.quantifier, restrictor=program.restrictor,
                              predicate=program.predicate, obj=program.obj, polarity=program.polarity,
                              tense=program.tense), "yes")
            return f"if {condition} then {consequent}"
        copula = {"present": "is", "past": "was", "future": "will be"}[program.tense]
        if kind == "verb":
            verb = predicate if program.tense == "present" else predicate
            aux = {"present": "does", "past": "did", "future": "will"}[program.tense]
            if negative:
                return f"{subject} {aux} not {verb} {program.obj}"
            return f"{subject} {verb}{'s' if program.tense == 'present' and program.quantifier == 'proper' else ''} {program.obj}".strip()
        if kind == "nominal":
            article = "a "
            return f"{subject} {copula}{' not' if negative else ''} {article}{predicate}"
        return f"{subject} {copula}{' not' if negative else ''} {predicate}"


__all__ = ["ClauseProgram", "ConstructionKernel", "SCHEMA"]
