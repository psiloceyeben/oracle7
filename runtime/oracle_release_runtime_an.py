#!/usr/bin/env python3
"""Runtime AN - emit the LiminalTransition for every turn (additive over AM).

Spec v3 s3 defines it and nothing built it. Without it the space between an input and its
answer is narratable but not measurable, and spec v3 B3 forbids narration as evidence.

Every turn now records, as an execution artefact:

  in_surface     the raw input
  in_form        the typed reading the system recovered (or None - itself a finding)
  operator       the route that carried the turn
  alternatives   matchers that were tried and declined, with why
  carried        what was taken from the prior turn (session state actually used)
  out_status     answered | withheld | clarification
  residual       what the turn did not account for
  cost_ms        wall time

The geometric content is the RELATION between in_form and out_form, recorded per step. A
conversation is then a path: turns are steps, and continuity is whether consecutive steps
share structure. A sequence of individually-correct answers with no continuity is not a
conversation, and that distinction is only visible once the relation is written down.

Authority: emits records; changes no answer. AN.chat returns exactly what AM.chat returns.
"""

from __future__ import annotations

import re
import time
from collections import deque

from oracle_release_runtime_am import OracleReleaseRuntimeAM

CITE = re.compile(r"\[[a-z0-9_]+:?[a-z0-9_.\-]*\]")
CONTENT = re.compile(r"[a-z][a-z'\-]{3,}")
STOP = {"what", "when", "where", "which", "does", "did", "the", "a", "an", "is", "are",
        "was", "were", "how", "why", "who", "that", "this", "with", "from", "about",
        "tell", "more", "you", "your", "can", "could", "would", "there", "their", "them"}


def content_terms(text: str) -> set:
    return {w for w in CONTENT.findall(str(text).lower()) if w not in STOP}


class OracleReleaseRuntimeAN(OracleReleaseRuntimeAM):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.transitions: dict = {}
        self._pending_conversion: dict = {}

    def _probe_matchers(self, text: str) -> list:
        """Which typed readings were available but not taken. A route that could have
        matched and did not is part of the shape of the decision, not noise."""
        out = []
        try:
            if self._parse_kind(text) is not None:
                out.append("kind_question")
        except Exception:  # noqa: BLE001
            pass
        low = " ".join(str(text).lower().split())
        for name, pat in (("provenance_request", r"^(why|how do you know|source|prove)"),
                          ("continuation", r"^(tell me more|more|what else|go on|continue)"),
                          ("acknowledgement", r"^(thanks|thank you|ok|okay|got it|great)"),
                          ("summarise", r"^summari[sz]e "),
                          ("definition", r"^what is "),
                          ("causal", r"^what causes "),
                          ("temporal", r"^when (did|was)")):
            if re.match(pat, low):
                out.append(name)
        return out

    @staticmethod
    def _verified_conversion(result: dict, prior: dict) -> bool:
        """A conversion counts for continuity only if the rewritten form actually carries
        a term the prior turn produced. A self-reported 'conversion' flag with no such
        term is not continuity - a mutant claiming a conversion on every turn scored
        209/209 before this check existed."""
        conv = result.get("conversion")
        if not isinstance(conv, dict):
            conv = prior.get("_pending_conversion") if isinstance(prior, dict) else None
        if not isinstance(conv, dict):
            return False
        to_terms = content_terms(conv.get("to", ""))
        from_terms = content_terms(conv.get("from", ""))
        prior_terms = set(prior.get("out_terms", set())) | set(prior.get("in_terms", []))
        # the rewrite must INTRODUCE a prior-turn term the original surface lacked
        return bool((to_terms - from_terms) & prior_terms)

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        prior = self.transitions.get(session_id)
        prior_terms = prior["out_terms"] if prior else set()
        # a subclass may declare a conversion BEFORE dispatch (AN records the transition
        # inside this call, before the subclass can attach anything to the result)
        pending = getattr(self, "_pending_conversion", {}).pop(session_id, None)
        result = super().chat(text, session_id)
        if pending and "conversion" not in result:
            result["conversion"] = pending
        in_terms = content_terms(text)
        out_terms = content_terms(result.get("response", ""))
        status = str(result.get("status", ""))
        carried = sorted(in_terms & prior_terms) if prior else []
        # the RELATION between input and output, per step
        grounded = sorted(in_terms & out_terms)
        introduced = sorted(out_terms - in_terms - prior_terms)
        unaccounted = sorted(in_terms - out_terms - set(carried))
        # GROUNDING must not be satisfiable by ECHO. An input term counts as grounded only
        # if it appears inside a CITED span - so repeating the question scores zero, and
        # padding with topic words scores zero, because neither is cited. This ties the
        # metric to warrant, which is the property the system actually has.
        # the CLAIM a citation supports is the text preceding it since the previous
        # citation. Taking from the last period instead captured only the citation token,
        # so cited terms were ID fragments and grounding floored at zero for every
        # substantive turn.
        cited_spans = []
        resp = str(result.get("response", ""))
        cursor = 0
        for m in CITE.finditer(resp):
            cited_spans.append(resp[cursor:m.start()].lower())
            cursor = m.end()
        cited_terms = set()
        for span in cited_spans:
            cited_terms |= content_terms(span)
        grounded_cited = sorted(in_terms & cited_terms)
        rec = {
            "turn": (prior["turn"] + 1) if prior else 1,
            "in_surface": str(text)[:120],
            "in_form": self._probe_matchers(text) or None,
            "operator": result.get("path"),
            "out_status": status,
            "in_terms": sorted(in_terms), "out_terms": sorted(out_terms)[:24],
            "relation": {
                "grounded": grounded,            # raw overlap (GAMEABLE by echo - reported, not scored)
                "grounded_cited": grounded_cited,  # input terms addressed INSIDE a citation
                "introduced": introduced[:16],   # what the answer brought that was not asked
                "unaccounted": unaccounted,      # input terms the answer never touched
            },
            "carried_from_prior": carried,
            "continuity_lexical": bool(carried) or bool(prior and (out_terms & prior_terms)),
            # continuity = the turn STRUCTURALLY used prior state. Two ways that can happen:
            # an act route consumed it, OR a conversion resolved a reference against it.
            # The first version counted only act routes, so a resolved anaphor answered by
            # a knowledge route scored ZERO continuity - penalising the exact behaviour
            # continuity exists to reward. (Fold candidate AO, rejected 3x at 124/153.)
            # act:clarify is a REFUSAL to continue, not a continuation. The baseline was
            # scoring "I didn't parse that" as continuity, so a candidate that ANSWERED the
            # same turn lost the point for doing strictly better. Third instrument defect
            # surfaced by the AO candidate; it was the one holding the admission.
            "continuity": bool(prior) and bool(
                self.dialogue.get(session_id, {}).get("last_result")) and (
                (str(result.get("path", "")).startswith("act:")
                 and str(result.get("path", "")) != "act:clarify")
                or self._verified_conversion(result, prior)),
            "citations": len(CITE.findall(str(result.get("response", "")))),
            "residual": (None if status == "answered"
                         else {"class": "no_typed_reading" if not self._probe_matchers(text)
                               else "reading_found_no_operator_answered",
                               "unaccounted": unaccounted}),
            "cost_ms": round(1000.0 * (time.perf_counter() - started), 1),
        }
        if isinstance(result.get("conversion"), dict):
            rec["conversion"] = result["conversion"]
        rec["out_terms_set"] = out_terms
        self.transitions[session_id] = {**rec, "out_terms": out_terms}
        hist = getattr(self, "_paths", None)
        if hist is None:
            hist = self._paths = {}
        hist.setdefault(session_id, deque(maxlen=64)).append(
            {k: v for k, v in rec.items() if k != "out_terms_set"})
        return result

    def path(self, session_id: str = "default") -> list:
        return list(getattr(self, "_paths", {}).get(session_id, []))
