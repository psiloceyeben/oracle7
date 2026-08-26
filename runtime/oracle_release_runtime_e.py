#!/usr/bin/env python3
"""Runtime E — conversation-act conversion layer, slice 1 (Ben's conversion
thesis: dialogue is a finite inventory of typed conversions, not an emergent
capability).

Acts this slice:
  provenance_replay  "why did you say that / how do you know / source?"
                     -> re-present the last answer's provenance (addresses,
                     rule+premises, or the typed reason for a withhold)
  continue_topic     "tell me more / what else / more about that"
                     -> next admitted claims from the last topic's page,
                     composed and verified like any paragraph
  acknowledge        "thanks / ok / great" -> typed acknowledgment, no fetch

Dialogue state is a per-session record {last_result, last_topic, last_offset}
— a dictionary, not a model. Every act is a conversion over existing
machinery; nothing generates."""

from __future__ import annotations

import re
import time

from oracle_release_runtime_d import OracleReleaseRuntimeD
from stage5m13e8_paragraph_compiler_v2 import compile_paragraph_v2, recover_program_v2

WHY = re.compile(r"^(?:why(?: did you say that| do you say that)?|how do you know(?: that)?|"
                 r"what(?:'s| is) your source(?: for that)?|source\??|prove it|citation\??)[.?!]?$", re.I)
MORE = re.compile(r"^(?:tell me more|more|what else|go on|continue|more about (?:that|it))[.?!]?$", re.I)
ACK = re.compile(r"^(?:thanks|thank you|ok|okay|got it|great|cool|nice|perfect)[.?!]?$", re.I)


class OracleReleaseRuntimeE(OracleReleaseRuntimeD):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dialogue: dict[str, dict] = {}

    # ── act conversions ──────────────────────────────────────────────────
    def _act_provenance_replay(self, state: dict) -> dict:
        last = state.get("last_result")
        if not last:
            return {"status": "withheld", "path": "act:provenance_replay",
                    "response": "Nothing has been answered in this session yet, so there is no provenance to replay."}
        prov = last.get("provenance") or {}
        kind = prov.get("kind", "unknown")
        lines = [f"My previous answer came via the {last.get('path','?')} route."]
        if kind == "dbpedia_page":
            lines.append(f"It is the definitional lead of the page '{prov.get('page')}', claim {prov.get('claim_id')}.")
        elif kind == "gated_paragraph":
            lines.append(f"It composed {prov.get('public_claims',0)} page-addressed claims"
                         + (f" and {prov['user_claims']} claims from your own documents" if prov.get('user_claims') else "")
                         + "; every sentence carries its claim address in brackets.")
            if prov.get("excluded"):
                lines.append("Excluded as insufficiently relevant (ledgered, not hidden): "
                             + ", ".join(f"{e['page']} ({e['relevance']})" for e in prov["excluded"][:4]) + ".")
        elif kind == "conceptnet_edges":
            claims = prov.get("claims", [])
            lines.append(f"It rests on {len(claims)} ConceptNet edges: "
                         + "; ".join(c.get("provenance", "?") for c in claims[:4]) + ".")
        elif kind == "session_world":
            lines.append(f"It was computed from the {prov.get('statements',0)} statements you asserted "
                         "in this session's typed world — logic over your own facts, not retrieval.")
        else:
            lines.append("It was a typed refusal: no admitted evidence licensed an answer, so none was given.")
        lines.append("Nothing in that answer was generated; each part is either addressed, derived, or withheld.")
        return {"status": "answered", "path": "act:provenance_replay", "response": " ".join(lines),
                "provenance": {"kind": "dialogue_state_replay"}}

    def _act_continue(self, state: dict, session_id: str) -> dict:
        topic = state.get("last_topic")
        if not topic:
            return {"status": "withheld", "path": "act:continue_topic",
                    "response": "There is no active topic yet — ask about something first."}
        offset = state.get("last_offset", 0) + 6
        page = self.anchors.resolve(topic)
        if not page:
            return {"status": "withheld", "path": "act:continue_topic",
                    "response": f"No further admitted material for {topic}."}
        title = self.anchors.page_to_title.get(page, topic)
        rows = self.bench_query.page_sentences(page)[offset:offset + 4]
        if not rows:
            return {"status": "withheld", "path": "act:continue_topic",
                    "response": f"The admitted record on {title} is exhausted — "
                                f"every stored sentence has been shown."}
        claims = [{"claim_id": c, "page": title, "sentence": s} for c, s in rows]
        paragraph, program = compile_paragraph_v2(topic, claims, evidence=3, aggregation_term=None)
        if paragraph is None or not recover_program_v2(paragraph, program):
            return {"status": "withheld", "path": "act:continue_topic",
                    "response": "Continuation failed verification and is withheld."}
        state["last_offset"] = offset
        return {"status": "answered", "path": "act:continue_topic", "response": paragraph,
                "provenance": {"kind": "gated_paragraph", "topic": topic, "offset": offset}}

    # ── entry ────────────────────────────────────────────────────────────
    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        normalized = " ".join(text.strip().split())
        state = self.dialogue.setdefault(session_id, {})
        result = None
        if WHY.match(normalized):
            result = self._act_provenance_replay(state)
        elif MORE.match(normalized):
            result = self._act_continue(state, session_id)
        elif ACK.match(normalized):
            result = {"status": "answered", "path": "act:acknowledge",
                      "response": "Noted. The session state is kept; ask on.",
                      "provenance": {"kind": "dialogue_state"}}
        if result is not None:
            result["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
            result["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
        else:
            result = super().chat(text, session_id)
            # topic tracking for continuation acts
            path = result.get("path", "")
            prov = result.get("provenance") or {}
            if path == "anchored_summary":
                match = re.match(r"^(?:tell me about|who is|who was|what do you know about) (?:the )?(.+?)[.?!]?$",
                                 normalized, re.I)
                if match:
                    state["last_topic"] = match.group(1).strip()
                    state["last_offset"] = 0
            elif path == "definitional_encyclopedic" and prov.get("page"):
                state["last_topic"] = prov["page"]
                state["last_offset"] = 0
        self.dialogue[session_id]["last_result"] = {k: result.get(k) for k in ("path", "provenance", "status")}
        return result
