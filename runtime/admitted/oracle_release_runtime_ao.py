#!/usr/bin/env python3
"""Runtime AO - conversation conversions, PRODUCED BY THE META-FOLD (M53), not hand-written.

Generated from the residue of 161 unanswered turns in the dev split of the M52 corpus,
clustered into 4 constructions. Each construction is a REWRITE of a form the chain
cannot read into one it can, followed by re-dispatch through the unchanged chain. Nothing
here answers; the warrant is whatever the re-dispatched route provides.

Clusters and their support (surface form -> count), from the fold report:
  REFERENT_SUBSTITUTION    'how old is it?'x13; 'who discovered it?'x11; 'what is it made of?'x7; 'what lives there?'x7; 'where is it?'x7
  UNCLUSTERED              'what else?'x14; 'The thing from before.'x7; 'Explain the thing with the water.'x4; 'What is volcanoes?'x4; 'What is glaciers?'x4
  OPENER_ALIAS             'Tell me about earthquakes.'x3; 'Tell me about that place.'x3; 'Tell me about bees.'x2; 'Tell me about glaciers.'x2; 'Tell me about volcanoes.'x1
  ELLIPSIS_COMPLETION      'go on'x11; 'more about that'x10; 'tell me more'x8; 'What about the big one?'x2; 'the same for bees'x1
  REPAIR_ACCEPT            'I meant the Pacific Ocean'x1; 'I meant volcanoes'x1; 'I meant Mount Everest'x1; 'I meant the Sahara'x1; 'I meant rain'x1

Authority: candidate only. Admitted or rejected by the loop on HELD-OUT scripts.
"""

from __future__ import annotations

import re

from oracle_release_runtime_an import OracleReleaseRuntimeAN

DEICTIC = re.compile(r"\b(it|there|that|this|its|they|them|those|these|the same)\b", re.I)
ELLIPSIS = re.compile(r"^(?:and|what about|the same for)\s+(?P<t>.+?)\??$", re.I)
BARE = re.compile(r"^(?:the\s+)?[a-z][a-z \-']{2,40}$", re.I)
REPAIR = re.compile(r"^(?:i meant|i mean|no,?\s+|sorry,?\s+)(?P<t>.+?)\.?$", re.I)
OPENER = re.compile(r"^(?:tell me about|talk about|describe)\s+(?P<t>.+?)\.?$", re.I)
CONTINUATION = re.compile(r"^(?:go on|more|tell me more|more about (?:that|it)|what else|continue|"
                          r"thanks|thank you|ok|okay|got it|great|why|how do you know|"
                          r"what is your source|why did you say that)[?.!]*$", re.I)
PREDICATE_OF = {
    "what lives there": "What lives in {t}?",
    "is it big": "How big is {t}?",
    "where is it": "Where is {t}?",
    "how old is it": "How old is {t}?",
    "who discovered it": "Who discovered {t}?",
    "what is it made of": "What is {t} made of?",
    "is that true": "Summarize {t}.",
}


class OracleReleaseRuntimeAO(OracleReleaseRuntimeAN):
    """Conversions are applied ONLY when the unchanged chain would not answer."""

    def _live_topic(self, session_id: str):
        """The referent for a deictic is the most recent GROUNDED topic on the path - the
        in_terms of the last turn that was answered by a knowledge route. Attempts 1-4 read
        last_topic (set only by ACTS routes) and fell back to the first out_term, which is a
        stopword or citation fragment ('according', 'baccce'). The referent was never found,
        so no conversion ever fired; continuity sat at 124/153 across four gate attempts
        for a reason none of the four fixes addressed. The map already held the answer."""
        slot = self.dialogue.get(session_id) or {}
        t = slot.get("last_topic")
        if t:
            return str(t)
        # the referent is the last GROUNDING turn - one whose surface opened a topic.
        # attempt 6 used the last ANSWERED turn, so "it" resolved to "causes earthquakes"
        # (a predicate) or "tell me more" (a continuation). Ground = opener form.
        for tr in reversed(self.path(session_id)):
            if tr.get("out_status") != "answered":
                continue
            surf = str(tr.get("in_surface", "")).strip()
            mo = (re.match(r"^(?:summari[sz]e|what is|tell me about|describe)\s+(?P<t>.+?)[.?!]*$",
                           surf, re.I))
            if mo:
                return mo.group("t").strip()
            # a converted turn carries its resolved topic
            cv = tr.get("conversion") or {}
            m2 = re.match(r"^summari[sz]e\s+(?P<t>.+?)[.?!]*$", str(cv.get("to", "")), re.I)
            if m2:
                return m2.group("t").strip()
        return None

    def _topic_or_referent(self, captured: str, session_id: str):
        """A captured 'topic' that is itself deictic ('that place', 'the big one') is not
        a topic - it is a reference. Resolve it against the live topic, or decline.
        Attempt 7 emitted 'Summarize that place.' and 'Summarize the big one.'"""
        t = captured.strip()
        if DEICTIC.search(t) or t.lower() in ("the big one", "the small one", "the other one"):
            return self._live_topic(session_id)
        return t

    def _convert(self, text: str, session_id: str):
        s = " ".join(str(text).strip().split())
        low = s.lower().rstrip("?.!")
        m = REPAIR.match(s)
        if m:
            t = self._topic_or_referent(m.group("t"), session_id)
            return (f"Summarize {t}.", "REPAIR_ACCEPT") if t else (None, None)
        m = OPENER.match(s)
        if m:
            t = self._topic_or_referent(m.group("t"), session_id)
            return (f"Summarize {t}.", "OPENER_ALIAS") if t else (None, None)
        m = ELLIPSIS.match(s)
        if m:
            t = self._topic_or_referent(m.group("t"), session_id)
            return (f"Summarize {t}.", "ELLIPSIS_COMPLETION") if t else (None, None)
        if BARE.match(s) and len(s.split()) <= 4 and not s.endswith("?"):
            # a bare phrase is a topic ONLY if it is not a continuation/ack the ACTS layer
            # already owns - attempt 6 rewrote "go on" as "Summarize go on."
            if not CONTINUATION.match(s):
                return f"Summarize {s.strip()}.", "ELLIPSIS_COMPLETION"
        topic = self._live_topic(session_id)
        if topic and DEICTIC.search(s):
            if low in PREDICATE_OF:
                return PREDICATE_OF[low].format(t=topic), "REFERENT_SUBSTITUTION"
            return DEICTIC.sub(topic, s, count=1), "REFERENT_SUBSTITUTION"
        return None, None

    def chat(self, text: str, session_id: str = "default") -> dict:
        # Decide the conversion BEFORE dispatch, then dispatch ONCE through the instrumented
        # chain. The first version re-dispatched through super().chat() after a failed
        # attempt, so every conversion recorded TWO transitions and the held-out turn count
        # inflated 248 -> 294. The gate rejected it for exactly that.
        # Probe against a SNAPSHOT of dialogue state, then restore it: the probe must not
        # write state (AM records at the top of the chain), or it pollutes continuity.
        # Attempt 2 was rejected for exactly that: continuity 153 -> 124.
        import copy as _copy
        from oracle_release_runtime_am import OracleReleaseRuntimeAM as _Plain
        saved = _copy.deepcopy(self.dialogue.get(session_id))
        probe = _Plain.chat(self, text, session_id)
        if saved is None:
            self.dialogue.pop(session_id, None)
        else:
            self.dialogue[session_id] = saved
        if str(probe.get("status", "")) == "answered":
            return super().chat(text, session_id)            # one recorded transition
        rewritten, construction = self._convert(text, session_id)
        if not rewritten or rewritten.strip().lower() == str(text).strip().lower():
            return super().chat(text, session_id)
        # Reference resolution was only the FIRST missing layer. The resolved form may
        # carry a predicate the chain has no route for ("How old is Moon?"). Probe the
        # specific predicate; if the chain cannot read it, fall back to the grounded
        # summary of the SAME topic - same cited route, warrant preserved, and the
        # transition records that the specific predicate was unserved.
        saved2 = _copy.deepcopy(self.dialogue.get(session_id))
        probe2 = _Plain.chat(self, rewritten, session_id)
        if saved2 is None:
            self.dialogue.pop(session_id, None)
        else:
            self.dialogue[session_id] = saved2
        unserved = None
        if str(probe2.get("status", "")) != "answered":
            topic = self._live_topic(session_id)
            if construction == "REFERENT_SUBSTITUTION" and topic:
                unserved = rewritten
                rewritten = f"Summarize {topic}."
        # declare the conversion BEFORE dispatch so the instrumented parent records it on
        # the transition it writes during this call (attempt 5: every real conversion cost
        # a continuity point because the field did not exist yet when it was read)
        self._pending_conversion[session_id] = {
            "construction": construction, "from": str(text)[:80], "to": rewritten[:80],
            "produced_by": "M53 meta-fold", "unserved_predicate": unserved}
        second = super().chat(rewritten, session_id)         # one recorded transition
        if str(second.get("status", "")) != "answered":
            return second
        if unserved:
            second["unserved_predicate"] = unserved
        second["conversion"] = {"construction": construction, "from": str(text)[:80],
                               "to": rewritten[:80], "produced_by": "M53 meta-fold",
                               "unserved_predicate": unserved}
        # the transition should show the ORIGINAL surface, with the conversion on it
        tr = self.transitions.get(session_id)
        if tr is not None:
            tr["in_surface"] = str(text)[:120]
            tr["conversion"] = second["conversion"]
        return second
