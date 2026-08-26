#!/usr/bin/env python3
"""M17a — release-runtime shadow arbiter (M-series operation families).

Wraps the FROZEN K138 bid geometry (stage5k138_geometric_ingress_shadow_arbiter
.encode — role-bound word states + bigram bindings over unitary phasors; import
only, never edited) with the M-series release runtime's interpretation families.
Every family bids SIMULTANEOUSLY: bid = 1.4 * geometric resonance against the
family's prototype state + typed marker evidence. Winner/runner-up/margin with
the K138 clarification floor. Shadow mode: controls no dispatch.

Prototype phrases are generic paraphrase templates authored for this module —
not panel surfaces, not residue surfaces (K138 law). No LM, no transformer,
no gradient; deterministic seeded phasors throughout.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np

from stage5k138_geometric_ingress_shadow_arbiter import encode  # frozen geometry
from stage5k138_typed_interpretation_candidate import (
    ArbitrationRecord,
    InterpretationCandidate,
)

CLARIFICATION_FLOOR = 0.55
MARGIN_TAU = 0.08

M_FAMILIES = (
    "summarize", "compare", "list_n", "multi_step", "timeline",
    "why_different", "what_if", "explain_simply", "definitional",
    "act_refine", "act_continue", "act_provenance", "act_acknowledge",
    "open_topic", "clarification",
)


def path_family(path: str | None) -> str | None:
    """Map a runtime dispatch path to its interpretation family."""
    if not path:
        return None
    if path.startswith("act:refine"):
        return "act_refine"
    table = {
        "act:continue_topic": "act_continue",
        "act:provenance_replay": "act_provenance",
        "act:acknowledge": "act_acknowledge",
        "capability:summarize": "summarize", "anchored_summary": "summarize",
        "capability:compare": "compare",
        "capability:list_n": "list_n",
        "capability:multi_step": "multi_step",
        "capability:timeline": "timeline",
        "capability:why_different": "why_different",
        "capability:what_if": "what_if",
        "capability:explain_simply": "explain_simply",
        "definitional_encyclopedic": "definitional",
        "conceptnet_commonsense": "open_topic",
        "session_relational": "open_topic",
        "document_runtime": "open_topic",
        "gated_document": "open_topic",
    }
    return table.get(path)


PROTOTYPES: dict[str, tuple[str, ...]] = {
    "summarize": (
        "summarize the topic for me",
        "give me a brief summary of the subject",
        "give me the short version of the topic",
        "provide an overview of the subject",
        "recap the main points about the topic",
    ),
    "compare": (
        "compare the first thing and the second thing",
        "what is the difference between one thing and another",
        "how do the two subjects differ from each other",
        "contrast the first topic with the second topic",
    ),
    "list_n": (
        "list three facts about the topic",
        "give me five facts about the subject",
        "name a few things about the topic",
        "tell me several points about the subject",
    ),
    "multi_step": (
        "summarize the first topic and then list facts about the second",
        "define the term then compare two subjects",
        "first give an overview then name some facts",
    ),
    "timeline": (
        "give me a timeline of the topic",
        "show the chronology of the subject",
        "walk me through the history year by year",
        "lay out the dated events of the topic in order",
    ),
    "why_different": (
        "why are the two things different",
        "explain why one subject differs from the other",
        "how come the first thing and the second thing are so different",
    ),
    "what_if": (
        "what if the thing had no part",
        "what would happen if the subject lost its feature",
        "suppose the thing had no part what then",
        "imagine the subject without its feature",
    ),
    "explain_simply": (
        "explain the topic simply",
        "explain the subject in simple terms",
        "break the topic down in plain language",
        "explain the idea so a child could follow it",
    ),
    "definitional": (
        "what is a concept",
        "what does the term mean",
        "define the following word",
        "what are those things exactly",
    ),
    "act_refine": (
        "simpler",
        "make it simpler",
        "shorter please",
        "say that more simply",
        "again but simpler",
    ),
    "act_continue": (
        "tell me more",
        "keep going",
        "go on",
        "tell me more about that",
        "continue please",
    ),
    "act_provenance": (
        "why did you say that",
        "how do you know that",
        "where did that answer come from",
        "what is the source for that",
    ),
    "act_acknowledge": (
        "thanks that helped",
        "thank you",
        "great answer cheers",
        "nice that was helpful",
    ),
    "open_topic": (
        "tell me about a broad topic",
        "share background knowledge on the subject",
        "talk to me about the matter",
        "what do you know about the topic",
    ),
}

NUMBER_WORDS = {"one", "two", "three", "four", "five", "six", "seven", "eight",
                "nine", "ten", "few", "couple", "several", "some"}
LIST_NOUNS = {"facts", "things", "points", "items", "examples", "reasons"}
SUMMARY_TOKENS = {"summarize", "summarise", "summary", "overview", "recap", "rundown"}
COMPARE_TOKENS = {"compare", "contrast", "versus", "vs", "difference", "differences", "differ"}
SIMPLE_TOKENS = {"simply", "simple", "simpler", "plain", "plainly", "easy", "easier"}
REFINE_TOKENS = {"simpler", "shorter", "briefer"}
ACK_TOKENS = {"thanks", "thank", "cheers", "helpful", "perfect", "great", "nice"}
TIMELINE_TOKENS = {"timeline", "chronology", "chronological"}
DIFFERENT_TOKENS = {"different", "differs", "differ", "differently"}

PROVENANCE_PHRASES = ("why did you say", "how do you know", "where did that",
                      "what is the source", "what's the source", "came from")
CONTINUE_PHRASES = ("tell me more", "keep going", "go on", "continue", "elaborate")
WHATIF_PHRASES = ("what if", "what would happen if", "suppose ", "imagine ")
DEFINITION_LEADS = ("what is ", "what are ", "define ", "what does ")
TELL_ABOUT_LEADS = ("tell me about ", "talk to me about ", "what do you know about ")


def _terms(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9'-]*", text.casefold())


def features(text: str) -> dict[str, float]:
    lower = " ".join(text.casefold().strip().split())
    tokens = _terms(lower)
    token_set = set(tokens)
    first = tokens[0] if tokens else ""
    why_lead = first == "why" or lower.startswith("how come")
    count_present = bool(token_set & NUMBER_WORDS) or any(t.isdigit() for t in tokens)
    sentence_break_then = bool(re.search(r"[,.?!;] *(and )?then ", lower)) or " and then " in lower
    refine_phrase = "more simply" in lower or "more briefly" in lower
    return {
        "question": float(lower.endswith("?")),
        "summary_token": float(bool(token_set & SUMMARY_TOKENS) or "short version" in lower
                               or "brief version" in lower or "sum up" in lower),
        "compare_token": float(bool(token_set & COMPARE_TOKENS)),
        "list_count": float(count_present and bool(token_set & LIST_NOUNS)),
        "timeline_token": float(bool(token_set & TIMELINE_TOKENS) or "year by year" in lower
                                or "in order" in lower and "events" in lower),
        "why_lead": float(why_lead),
        "different_token": float(bool(token_set & DIFFERENT_TOKENS)),
        "whatif_marker": float(any(lower.startswith(p) or f" {p}" in lower
                                   for p in WHATIF_PHRASES)),
        "simple_token": float(bool(token_set & SIMPLE_TOKENS) or "in simple terms" in lower
                              or "five year old" in lower or "a child" in lower
                              or "new to" in lower or "for beginners" in lower),
        "refine_short": float(len(tokens) <= 5
                              and (bool(token_set & REFINE_TOKENS) or refine_phrase)),
        "ack_marker": float(len(tokens) <= 6 and bool(token_set & ACK_TOKENS)),
        "provenance_phrase": float(any(p in lower for p in PROVENANCE_PHRASES)),
        "continue_phrase": float(any(p in lower for p in CONTINUE_PHRASES)
                                 and "about" not in lower.split("more")[0]),
        "chain_marker": float(sentence_break_then),
        "definition_lead": float(lower.startswith(DEFINITION_LEADS)),
        "tell_about_lead": float(lower.startswith(TELL_ABOUT_LEADS)
                                 and not any(p in lower for p in CONTINUE_PHRASES)),
        "very_short": float(len(tokens) <= 3),
    }


FEATURE_WEIGHTS: dict[str, dict[str, float]] = {
    "summarize": {"summary_token": 1.00, "list_count": -0.40, "chain_marker": -0.70,
                  "timeline_token": -0.50, "refine_short": -0.60},
    "compare": {"compare_token": 0.90, "why_lead": -0.70, "chain_marker": -0.70,
                "whatif_marker": -0.60},
    "list_n": {"list_count": 1.00, "chain_marker": -0.70, "summary_token": -0.30},
    "multi_step": {"chain_marker": 1.20},
    "timeline": {"timeline_token": 1.00, "chain_marker": -0.70},
    "why_different": {"why_lead": 0.55, "different_token": 0.55, "compare_token": 0.10,
                      "whatif_marker": -0.60, "chain_marker": -0.70},
    "what_if": {"whatif_marker": 1.00, "chain_marker": -0.70},
    "explain_simply": {"simple_token": 0.95, "refine_short": -0.50, "chain_marker": -0.70},
    "definitional": {"definition_lead": 0.85, "compare_token": -0.80, "chain_marker": -0.70,
                     "whatif_marker": -0.80, "different_token": -0.50, "simple_token": -0.40,
                     "list_count": -0.60, "timeline_token": -0.60, "summary_token": -0.50},
    "act_refine": {"refine_short": 1.10, "simple_token": 0.15, "question": -0.30},
    "act_continue": {"continue_phrase": 1.00, "very_short": 0.15},
    "act_provenance": {"provenance_phrase": 1.10},
    "act_acknowledge": {"ack_marker": 1.00, "question": -0.50},
    "open_topic": {"tell_about_lead": 0.80, "definition_lead": -0.40, "summary_token": -0.40,
                   "compare_token": -0.40, "whatif_marker": -0.50, "simple_token": -0.40,
                   "timeline_token": -0.50, "list_count": -0.50, "chain_marker": -0.50,
                   "refine_short": -0.60, "ack_marker": -0.60, "provenance_phrase": -0.60},
}

_PROTOTYPE_STATES: dict[str, np.ndarray] = {}


def prototype(family: str) -> np.ndarray:
    state = _PROTOTYPE_STATES.get(family)
    if state is None:
        phrases = PROTOTYPES.get(family, ())
        stacked = np.sum([encode(phrase) for phrase in phrases], axis=0)
        norm = np.linalg.norm(stacked)
        state = stacked / norm if norm else stacked
        _PROTOTYPE_STATES[family] = state
    return state


def resonance(bundle: np.ndarray, family: str) -> float:
    state = prototype(family)
    if not np.any(state):
        return 0.0
    return float(np.real(np.vdot(state, bundle)))


def arbitrate(text: str) -> ArbitrationRecord:
    bundle = encode(text)
    evidence = features(text)
    candidates: list[InterpretationCandidate] = []
    for family in M_FAMILIES:
        if family == "clarification":
            continue
        weights = FEATURE_WEIGHTS.get(family, {})
        typed = {name: weights[name] * evidence[name]
                 for name in weights if evidence.get(name)}
        geometric = resonance(bundle, family)
        bid = 1.4 * geometric + sum(typed.values())
        candidates.append(InterpretationCandidate(family, geometric, typed, bid))
    candidates.sort(key=lambda value: (-value.bid, value.family))
    top, second = candidates[0], candidates[1]
    margin = top.bid - second.bid
    floor_applied = top.bid < CLARIFICATION_FLOOR or margin < MARGIN_TAU
    winner = "clarification" if floor_applied else top.family
    runner_up = top.family if floor_applied else second.family
    return ArbitrationRecord(
        utterance_sha256=hashlib.sha256(text.encode()).hexdigest(),
        candidates=tuple(candidates),
        winner=winner,
        runner_up=runner_up,
        margin=margin,
        clarification_floor_applied=floor_applied,
    )


__all__ = ["CLARIFICATION_FLOOR", "MARGIN_TAU", "M_FAMILIES",
           "arbitrate", "features", "path_family", "prototype", "resonance"]
