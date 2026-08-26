#!/usr/bin/env python3
"""K7 — natural-prose construction kernel (additive successor to K6).

Strategy: DECOMPOSITION. Complex natural-prose sentences decompose into
K6-parseable clauses linked by a typed relation; K6 itself is unchanged and
does all clause-level parsing. New meaning is represented by LinkedProgram,
translated to IR terms by stage5m13e6_combinators2 (which composes the sealed
IR primitives; no sealed file is edited).

Families implemented this pass (per stage5m13e6_k7_precommitment_v1.md):
  F1  subordinate connectives (because/although/so/while/when/before/after)
  F3  appositives (NAME, a DESCRIPTION, ...)
  F4  fronted adverbials (In the morning, ...)
  F6  existentials + locative inversion (There is X on Y / On Y stands X)
Remaining families (F2, F5, F7-F14) are later passes; their residue stays banked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import stage5m13e2_construction_kernel as k1
from stage5m13e2_construction_kernel import ClauseProgram
from stage5m13e2_construction_kernel_k6 import ConstructionKernelK6

# K7 irregular-past supplement (same runtime-additive mechanism K6 uses).
k1.IRREGULAR_PAST.update({
    "lit": "light", "slept": "sleep", "stood": "stand", "sat": "sit",
    "lay": "lie", "rang": "rang" if False else "ring", "sank": "sink",
    "swept": "sweep", "wept": "weep", "crept": "creep", "leapt": "leap",
    "wrote": "write", "spoke": "speak", "drove": "drive", "rose": "rise",
    "chose": "choose", "froze": "freeze", "flew": "fly", "drew": "draw",
    "threw": "throw", "grew": "grow", "knew": "know",
})

# Trailing adverbials K7 lifts off the clause before K6 parses it; they are
# stashed on predicate["k7_adverbial"] and re-appended by Realizer2 (symmetric,
# so round-trip is preserved).
TRAILING_ADVERBS = {"early", "late", "soon", "quickly", "slowly", "yesterday",
                    "today", "tomorrow", "everywhere", "nearby", "easily",
                    "precisely", "cleanly", "patiently"}
TRAILING_TEMPORAL_NP = re.compile(r"\b(each|every) (\w+)$")
PRE_ADVERBS = {"still", "already", "often", "always", "never" if False else "rarely", "usually"}

RELATIVE = re.compile(r"^(The \w+(?: \w+)?) (who|that|which) (.+)$")
CLEFT_IT = re.compile(r"^It (was|is) ([A-Z]\w+(?: \w+)*?) (who|that) (.+?)\.?$")
ATTITUDE = re.compile(r"^([A-Z]\w+(?:'s \w+)?|The \w+) (said|says|believes|believed|thinks|thought|claims|claimed|reported|reports) that (.+?)\.?$")
POSSESSIVE_CHAIN = re.compile(r"^((?:[A-Z]\w+['’]s )(?:\w+['’]s )*)(\w+) (.+?)\.?$")
MEASURE = re.compile(r"^(.+?) (is|was|are|were) (\w+|\d+) (meters?|feet|centuries|years|decades|kilometers?|miles) (tall|old|long|wide|high|deep)\.?$")
NEG_SCOPE = re.compile(r"^Not every (\w+) (.+?)\.?$")
VERBAL_SUBJECT = re.compile(r"^((?:[A-Z]\w+ing|To \w+)(?: [a-z]\w+)*) (requires|required|is|was|takes|took|demands|demanded) (.+?)\.?$")

# relation name -> (surface connective, fronted_allowed)
CONNECTIVES = {
    "because": ("cause", True),
    "although": ("concession", True),
    "so": ("result", False),
    "while": ("simultaneity", True),
    "when": ("temporal", True),
    "before": ("before", True),
    "after": ("after", True),
}

FRONTED_PP = re.compile(r"^(In|On|At|During|After|Before) ([^,]+), (.+)$")
APPOSITIVE = re.compile(r"^([A-Z][\w']*(?: [A-Z][\w']*)*), (an?) ([^,]+), (.+)$")
EXISTENTIAL = re.compile(r"^There (is|are|was|were) (an? |the |three |two |[\w]+ )?(.+?) (on|in|at|near|by) (.+?)\.?$")
LOCATIVE_INV = re.compile(r"^(On|In|At|Near|By) (.+?) (stands|stand|stood|sits|sat|lies|lay) (an? |the )?(.+?)\.?$")
_FINITE_HINT = re.compile(r"\b(is|are|was|were|has|have|had|\w+ed|\w+s)\b")


@dataclass
class LinkedProgram:
    """Two clause programs joined by a typed relation, or one clause plus a
    typed setting. Realized/translated by the m13e6 successors."""
    relation: str
    main: ClauseProgram
    subordinate: ClauseProgram | None = None
    setting: dict[str, Any] | None = None      # e.g. {"prep": "in", "np": "the morning"}
    surface_order: str = "trailing"            # trailing | fronted
    meta: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        return {"relation": self.relation, "main": self.main.public(),
                "subordinate": self.subordinate.public() if self.subordinate else None,
                "setting": self.setting, "surface_order": self.surface_order}


class ConstructionKernelK7(ConstructionKernelK6):
    """K6 plus sentence-level decomposition. compile_text() is the new entry:
    it returns a LinkedProgram for the new families and otherwise falls back
    to K6's compile_sentence path unchanged."""

    def _clause(self, text: str) -> ClauseProgram | None:
        text = text.strip().rstrip(".!?").strip().rstrip(",")
        if not text:
            return None
        adverbial = None
        words = text.split()
        if len(words) > 2 and words[-1].lower() in TRAILING_ADVERBS:
            adverbial = words[-1].lower()
            text = " ".join(words[:-1])
        else:
            match = TRAILING_TEMPORAL_NP.search(text)
            if match and len(text.split()) > 3:
                adverbial = match.group(0).lower()
                text = text[:match.start()].strip()
        sentences = self._sentences(text + ".")
        if not sentences:
            return None
        tokens, is_question = sentences[0]
        program = self.compile_sentence(tokens, is_question)
        if program is not None and adverbial:
            program.predicate = {**program.predicate, "k7_adverbial": adverbial}
        return program

    # ── F1: subordinate connectives ──────────────────────────────────────
    def _connective(self, text: str) -> LinkedProgram | None:
        body = text.strip().rstrip(".")
        for conn, (relation, fronted_ok) in CONNECTIVES.items():
            # fronted: "Although B, A"  /  "When B, A"
            if fronted_ok and body.lower().startswith(conn + " "):
                rest = body[len(conn):].strip()
                if ", " in rest:
                    sub_text, main_text = rest.split(", ", 1)
                    main = self._clause(main_text)
                    sub = self._clause(sub_text)
                    if main is not None and sub is not None:
                        return LinkedProgram(relation, main, sub, surface_order="fronted")
            # trailing: "A because B"  /  "A, so B"
            for sep in (f", {conn} ", f" {conn} "):
                if sep in body:
                    main_text, sub_text = body.split(sep, 1)
                    main = self._clause(main_text)
                    sub = self._clause(sub_text)
                    if main is not None and sub is not None:
                        return LinkedProgram(relation, main, sub, surface_order="trailing")
        return None

    # ── F3: appositives ──────────────────────────────────────────────────
    def _appositive(self, text: str) -> LinkedProgram | None:
        match = APPOSITIVE.match(text.strip().rstrip("."))
        if not match:
            return None
        name, article, description, rest = match.groups()
        main = self._clause(f"{name} {rest}")
        isa = self._clause(f"{name} is {article} {description}")
        if main is None or isa is None:
            return None
        return LinkedProgram("apposition", main, isa,
                             meta={"name": name, "article": article, "description": description})

    # ── F4: fronted adverbials (no finite verb in the fronted part) ─────
    def _fronted_adverbial(self, text: str) -> LinkedProgram | None:
        match = FRONTED_PP.match(text.strip().rstrip("."))
        if not match:
            return None
        prep, np, main_text = match.groups()
        if _FINITE_HINT.search(np):        # a clause, not a bare adverbial -> F1's business
            return None
        main = self._clause(main_text)
        if main is None:
            return None
        return LinkedProgram("setting", main, None,
                             setting={"prep": prep.lower(), "np": np.strip()},
                             surface_order="fronted")

    # ── F6: existential there / locative inversion ───────────────────────
    def _existential(self, text: str) -> LinkedProgram | None:
        body = text.strip()
        match = EXISTENTIAL.match(body)
        if match:
            copula, article, entity_np, prep, loc_np = match.groups()
            main = self._clause(f"{(article or '').strip()} {entity_np} exists".strip())
            if main is None:
                return None
            tense = "past" if copula in ("was", "were") else "present"
            main.tense = tense
            return LinkedProgram("located", main, None,
                                 setting={"prep": prep, "np": loc_np.strip()},
                                 meta={"copula": copula, "entity_np": entity_np,
                                       "article": (article or "").strip()})
        match = LOCATIVE_INV.match(body)
        if match:
            prep, loc_np, verb, article, entity_np = match.groups()
            main = self._clause(f"{(article or '').strip()} {entity_np} exists".strip())
            if main is None:
                return None
            main.tense = "past" if verb in ("stood", "sat", "lay") else "present"
            return LinkedProgram("located", main, None,
                                 setting={"prep": prep.lower(), "np": loc_np.strip()},
                                 surface_order="fronted",
                                 meta={"verb": verb, "entity_np": entity_np,
                                       "article": (article or "").strip()})
        return None

    # ── F2: relative clauses (parse-driven split) ────────────────────────
    def _relative(self, text: str) -> LinkedProgram | None:
        match = RELATIVE.match(text.strip().rstrip("."))
        if not match:
            return None
        head_np, relativizer, tail = match.groups()
        words = tail.split()
        # try every split point: [rel VP] [main VP]; the kernel itself is the
        # oracle for where the relative clause ends.
        for split in range(1, len(words)):
            rel_part, main_part = " ".join(words[:split]), " ".join(words[split:])
            if relativizer == "that" and not rel_part.startswith(("was", "were", "is", "are")):
                # object relative candidate: "The book that Mira wrote won a prize"
                head_obj = head_np[0].lower() + head_np[1:]
                rel_clause = self._clause(f"{rel_part} {head_obj}") \
                    if len(rel_part.split()) >= 2 else None
            else:
                rel_clause = self._clause(f"{head_np} {rel_part}")
            main_clause = self._clause(f"{head_np} {main_part}")
            if rel_clause is not None and main_clause is not None:
                return LinkedProgram("relative", main_clause, rel_clause,
                                     meta={"head": head_np, "relativizer": relativizer,
                                           "rel_surface": rel_part, "object_relative":
                                           relativizer == "that" and not rel_part.startswith(("was", "were", "is", "are"))})
        return None

    # ── F5: coordination ellipsis ────────────────────────────────────────
    def _coordination_ellipsis(self, text: str) -> LinkedProgram | None:
        body = text.strip().rstrip(".")
        if " and " not in body:
            return None
        left_text, right_text = body.split(" and ", 1)
        left = self._clause(left_text)
        if left is None or len(right_text.split()) > 4 or " " not in right_text.strip():
            return None
        # right side must be NP NP with no verb: distribute left's verb token
        left_words = left_text.split()
        right_words = right_text.strip().split()
        lemma = left.predicate.get("lemma")
        right = None
        verb_token = None
        for word in left_words:
            for position in range(1, len(right_words)):
                candidate = self._clause(
                    " ".join(right_words[:position] + [word] + right_words[position:]))
                if candidate is not None and candidate.predicate.get("lemma") == lemma:
                    verb_token, right = word, candidate
                    break
            if right is not None:
                break
        if right is None:
            return None
        return LinkedProgram("conjunction_ellipsis", left, right,
                             meta={"verb_token": verb_token, "right_surface": right_text.strip()})

    # ── F8: it-clefts ────────────────────────────────────────────────────
    def _cleft(self, text: str) -> LinkedProgram | None:
        match = CLEFT_IT.match(text.strip())
        if not match:
            return None
        copula, focus, relativizer, rest = match.groups()
        base = self._clause(f"{focus} {rest}")
        if base is None:
            return None
        return LinkedProgram("cleft_focus", base, None,
                             meta={"focus": focus, "copula": copula, "relativizer": relativizer})

    # ── F9: attitude reports (registered reported-world crossing) ───────
    def _attitude(self, text: str) -> LinkedProgram | None:
        match = ATTITUDE.match(text.strip())
        if not match:
            return None
        holder, verb, content_text = match.groups()
        content = self._clause(content_text)
        if content is None:
            return None
        lemma = {"said": "say", "says": "say", "believes": "believe", "believed": "believe",
                 "thinks": "think", "thought": "think", "claims": "claim", "claimed": "claim",
                 "reported": "report", "reports": "report"}[verb]
        tense = "past" if verb in ("said", "believed", "thought", "claimed", "reported") else "present"
        return LinkedProgram("attitude", content, None,
                             meta={"holder": holder, "verb_lemma": lemma, "tense": tense,
                                   "world": "reported"})

    # ── F10: negated universal scope ─────────────────────────────────────
    def _neg_scope(self, text: str) -> LinkedProgram | None:
        match = NEG_SCOPE.match(text.strip())
        if not match:
            return None
        noun, rest = match.groups()
        inner = self._clause(f"Every {noun} {rest}")
        if inner is None:
            return None
        return LinkedProgram("neg_universal", inner, None, meta={"noun": noun})

    # ── F11: possessive chains ───────────────────────────────────────────
    def _possessive_chain(self, text: str) -> LinkedProgram | None:
        match = POSSESSIVE_CHAIN.match(text.strip())
        if not match:
            return None
        chain, head, rest = match.groups()
        base = self._clause(f"The {head} {rest}")
        if base is None:
            return None
        owners = [w.rstrip("'s’") for w in chain.split()]
        return LinkedProgram("possessive", base, None,
                             meta={"chain": chain.strip(), "owners": owners, "head": head})

    # ── F13: verbal subjects (gerund / infinitive) ───────────────────────
    def _verbal_subject(self, text: str) -> LinkedProgram | None:
        match = VERBAL_SUBJECT.match(text.strip())
        if not match:
            return None
        subject_np, verb, rest = match.groups()
        base = self._clause(f"The activity {verb} {rest}")
        if base is None:
            return None
        return LinkedProgram("verbal_subject", base, None,
                             meta={"subject_np": subject_np, "form":
                                   "infinitive" if subject_np.startswith("To ") else "gerund"})

    # ── F7: measure / age predicates ─────────────────────────────────────
    def _measure(self, text: str) -> LinkedProgram | None:
        match = MEASURE.match(text.strip())
        if not match:
            return None
        np, copula, value, unit, dim = match.groups()
        base = self._clause(f"{np} vanished")   # borrowed intransitive for NP analysis only
        if base is None:
            return None
        base.tense = "past" if copula in ("was", "were") else "present"
        base.predicate = {"kind": "measure", "value": value, "unit": unit, "dimension": dim}
        return LinkedProgram("measure", base, None,
                             meta={"np": np, "copula": copula, "value": value,
                                   "unit": unit, "dimension": dim})

    # ── F12: phrasal verbs (registered idiom lexicon) ────────────────────
    PHRASAL = {("broke", "down"): ("break_down", "past"), ("breaks", "down"): ("break_down", "present"),
               ("break", "down"): ("break_down", "present")}

    def _phrasal(self, text: str) -> LinkedProgram | None:
        words = text.strip().rstrip(".").split()
        if len(words) < 3:
            return None
        pair = (words[-2].lower(), words[-1].lower())
        if pair not in self.PHRASAL:
            return None
        lemma, tense = self.PHRASAL[pair]
        np = " ".join(words[:-2])
        base = self._clause(f"{np} vanished")
        if base is None:
            return None
        base.tense = tense
        base.predicate = {"kind": "verb", "lemma": lemma}
        return LinkedProgram("phrasal", base, None,
                             meta={"np": np, "surface_verb": f"{words[-2]} {words[-1]}"})

    # ── F14: agentful passives ───────────────────────────────────────────
    PASSIVE_AGENT = re.compile(r"^(.+?) (was|were) (\w+) by (.+?)\.?$")

    def _passive_agent(self, text: str) -> LinkedProgram | None:
        match = self.PASSIVE_AGENT.match(text.strip())
        if not match:
            return None
        patient_np, copula, participle, agent_np = match.groups()
        # the active clause is parsed directly with the participle as the verb
        # (past form == participle for the covered class; the kernel's own
        # lemma tables are the oracle — no separate recovery table needed)
        active = self._clause(f"{agent_np[0].upper() + agent_np[1:]} {participle} {patient_np[0].lower() + patient_np[1:]}")
        if active is None or active.predicate.get("lemma") is None:
            return None
        return LinkedProgram("passive_agent", active, None,
                             meta={"patient_np": patient_np, "agent_np": agent_np,
                                   "copula": copula, "participle": participle})

    # ── entry ────────────────────────────────────────────────────────────
    def compile_text(self, text: str) -> LinkedProgram | ClauseProgram | None:
        stripped = text.strip()
        # pre-verb adverb lift ("The old rules still hold.")
        pre_adverb = None
        words = stripped.rstrip(".").split()
        for adverb in PRE_ADVERBS:
            if adverb in words[1:-1]:
                index = words.index(adverb)
                candidate = " ".join(words[:index] + words[index + 1:]) + "."
                pre_adverb, stripped = adverb, candidate
                break
        disabled = getattr(self, "disabled_families", frozenset())
        family_builders = (
            ("F8", self._cleft), ("F9", self._attitude), ("F10", self._neg_scope),
            ("F3", self._appositive), ("F13", self._verbal_subject),
            ("F7", self._measure), ("F12", self._phrasal), ("F14", self._passive_agent),
            ("F11", self._possessive_chain), ("F2", self._relative),
            ("F4", self._fronted_adverbial), ("F6", self._existential),
            ("F1", self._connective), ("F5", self._coordination_ellipsis))
        for family, builder in family_builders:
            if family in disabled:
                continue
            program = builder(stripped)
            if program is not None:
                if pre_adverb and program.main is not None:
                    program.main.predicate = {**program.main.predicate, "k7_pre_adverb": pre_adverb}
                return program
        clause = self._clause(stripped)
        if clause is not None and pre_adverb:
            clause.predicate = {**clause.predicate, "k7_pre_adverb": pre_adverb}
        return clause
