#!/usr/bin/env python3
"""Runtime Q — M17b: arbiter AUTHORITATIVE at the fallback boundary (additive over P).

Capture condition: the regex chain landed in the fallback tier
(document_runtime / session_relational) WITHOUT answering — i.e. it did not
understand the surface — AND the shadow arbiter bids a re-dispatchable family
with a clean margin (no clarification floor). Then, and only then, runtime Q
re-dispatches through the EXISTING route via a canonical surface:

  capture point 1 (capabilities + definitional): arbiter family + anchor-store
    topic extraction -> canonical surface ("Give me a rundown on the Moon."
    -> summarize + Moon -> "Summarize Moon.") -> parent chain.
  capture point 2 (conversation acts): fixed canonical act surfaces
    ("Keep going." -> "Tell me more.").

Canonical-surface carriers mirror the K131 carrier stage deliberately;
typed-goal carrier removal is a later arc (K152 pattern). If re-dispatch fails
to answer, the ORIGINAL fallback result is returned unchanged — authority can
narrow to improvement-only, never degrade. Per the K147 law, no raw input is
ever placed into any response text by this layer (topics are anchor-store
titles, not user substrings). Each capture point has its own ablation flag."""

from __future__ import annotations

import re

from oracle_release_runtime_p import OracleReleaseRuntimeP
from stage5m17_release_arbiter_v1 import features as arb_features

FALLBACK_PATHS = {"document_runtime", "session_relational"}
FALLBACK_OK = {"answered", "recorded"}

# words never usable as topic candidates (marker vocabulary + function words)
TOPIC_BLOCK = {
    "give", "me", "a", "an", "the", "of", "on", "about", "and", "or", "to",
    "for", "in", "what", "whats", "what's", "how", "why", "is", "are", "do",
    "does", "did", "you", "your", "i", "i'd", "id", "could", "would", "please",
    "rundown", "overview", "summary", "summarize", "summarise", "recap",
    "version", "short", "brief", "quick", "sum", "up", "like", "so",
    "difference", "differences", "differ", "different", "between", "compare",
    "contrast", "come", "timeline", "chronology", "history", "walk", "through",
    "year", "by", "show", "list", "name", "few", "couple", "several", "some",
    "things", "facts", "points", "items", "know", "tell", "talk", "mean",
    "means", "actually", "explain", "break", "down", "plain", "language",
    "simple", "simply", "simpler", "terms", "child", "follow", "it", "that",
    "this", "one", "two", "three", "four", "five", "six", "seven",
    "say", "said", "told", "know", "knew", "claim", "think", "thought",
    "call", "called", "gist", "story", "handful", "nutshell",
}

ACT_CANONICAL = {
    "act_refine": "Simpler.",
    "act_continue": "Tell me more.",
    "act_provenance": "Why did you say that?",
    "act_acknowledge": "Thanks!",
}

NUMBER_WORDS = {"two": "two", "three": "three", "four": "four", "five": "five",
                "six": "six", "seven": "seven", "2": "two", "3": "three",
                "4": "four", "5": "five", "6": "six", "7": "seven"}


class OracleReleaseRuntimeQ(OracleReleaseRuntimeP):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.capture_capability_enabled = True  # ablation flag, capture point 1
        self.capture_act_enabled = True         # ablation flag, capture point 2

    # ---------------------------------------------------- topic extraction
    def _arb_topics(self, text: str) -> list[str]:
        """Anchor-store titles found in the surface, longest-span first,
        returned in positional order, marker vocabulary excluded."""
        words = [w.strip("'-") for w in re.findall(r"[A-Za-z][\w'-]*|\d+", text)]
        words = [w for w in words if w]
        titles = self.anchors.title_to_page
        found: list[tuple[int, int, str]] = []  # (start, length, title)
        taken: set[int] = set()
        for n in (3, 2, 1):
            for i in range(len(words) - n + 1):
                if any(j in taken for j in range(i, i + n)):
                    continue
                span = words[i:i + n]
                if all(w.lower() in TOPIC_BLOCK for w in span):
                    continue
                cand = " ".join(span)
                if cand.lower() in titles:  # anchor keys are case-normalized
                    found.append((i, n, cand))
                    taken.update(range(i, i + n))
        return [t for _, _, t in sorted(found)]

    def _canonical_surface(self, family: str, text: str) -> str | None:
        if family in ACT_CANONICAL:
            return ACT_CANONICAL[family]
        topics = self._arb_topics(text)
        if family in ("compare", "why_different"):
            if len(topics) < 2:
                return None
            a, b = topics[0], topics[1]
            return (f"Compare {a} and {b}." if family == "compare"
                    else f"Why are {a} and {b} different?")
        if not topics:
            return None
        topic = topics[0]
        if family == "summarize":
            return f"Summarize {topic}."
        if family == "timeline":
            return f"Give me a timeline of {topic}."
        if family == "explain_simply":
            return f"Explain {topic} simply."
        if family == "list_n":
            tokens = [w.lower() for w in re.findall(r"[A-Za-z]+|\d+", text)]
            count = next((NUMBER_WORDS[t] for t in tokens if t in NUMBER_WORDS), "three")
            return f"List {count} facts about {topic}."
        if family == "definitional":
            # the definiendum is the LAST content NP ("what would you say a
            # glacier is?"), not the first
            return f"What is a {topics[-1].lower()}?"
        return None

    # ------------------------------------------------------------ dispatch
    def chat(self, text: str, session_id: str = "default") -> dict:
        result = super().chat(text, session_id)  # P: regex dispatch + shadow record
        arb = result.get("arbitration")
        if (arb is None or arb.get("floor")
                or result.get("path") not in FALLBACK_PATHS
                or result.get("status") in FALLBACK_OK):
            return result
        family = arb.get("winner")
        is_act = family in ACT_CANONICAL
        if is_act and not self.capture_act_enabled:
            return result
        if not is_act and not self.capture_capability_enabled:
            return result
        canonical = self._canonical_surface(family, text)
        if canonical is None:
            return result
        redispatch = super().chat(canonical, session_id)
        # improvement-only authority: a family-correct honest withhold still
        # beats the generic fallback clarification; anything else keeps the
        # original result unchanged
        if redispatch.get("status") not in ("answered", "withheld"):
            return result
        redispatch["path"] = f"arb:{family}->" + str(redispatch.get("path"))
        redispatch["arbitration"] = dict(arb)
        redispatch["arbitration"]["mode"] = "authoritative"
        redispatch["arbitration"]["canonical_surface"] = canonical
        redispatch["arbitration"]["capture_point"] = "act" if is_act else "capability"
        return redispatch
