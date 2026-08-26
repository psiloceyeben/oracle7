#!/usr/bin/env python3
"""Bed 2 - four more plants, one per unoccupied catalogue position.

Ben: "plants want more expressions." Each sibling differs from Oracle7even at the SUBSTRATE
on one catalogued axis. None is a register. Each goes through the same three gates: M56
(category or costume), M58 (garden admission), M59 (residual exchange). Same instruments;
the family-coverage number is the garden's yield.

  TOPOLOGICAL   memory_geometry = topological. Recall by POSITION IN THE SHAPE, not recency:
                the referent for a deictic is the topic with the most relational mass in the
                session (most turns touching it, most citations under it), not the last one.
                A mind for which "it" means "the thing this conversation is ABOUT."

  COMPRESSED    provenance_retention = transformation_families. Warrant is compressed to the
                OPERATOR that produced it; "how do you know?" replays the family, not the
                addresses. Tests whether provenance survives compression.

  EPOCHAL       temporal_rhythm = epochal. Dialogue state integrates only at declared
                boundaries (every K turns); between boundaries the mind answers from the
                last sealed state. A mind that does not change mid-conversation.

  EVIDENTIAL    the first NON-ENGLISH position. Readings drawn from a grammar with obligatory
                evidentiality (Turkish -mIs/-DI, Quechua -mi/-si/-cha, Tariana): every
                statement must mark HOW the speaker knows. This mind reads input through that
                grammar - "I heard X", "I saw X", "X, apparently" are DIFFERENT typed forms -
                and its answers carry the evidential the record licenses: direct (cited),
                inferred (derived), reported (attested by a source), unknown (withheld).
                English has no such reading; the catalogue's inherited frame was all English.

Every plant preserves the digest law: answers come from the unchanged chain with their
warrant. A plant changes WHICH reading, WHICH referent, WHEN state moves, or HOW warrant
is rendered - never what counts as warrant.

No neural network; no LM call.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from oracle_release_runtime_ao import OracleReleaseRuntimeAO

CITE = re.compile(r"\[[a-z0-9_]+:?[a-z0-9_.\-]*\]")
DEICTIC = re.compile(r"\b(it|there|that|this|its|they|them|those|these)\b", re.I)
OPENER = re.compile(r"^(?:summari[sz]e|what is|tell me about|describe|what causes)\s+(?P<t>.+?)[.?!]*$", re.I)


# ── 1. TOPOLOGICAL memory ───────────────────────────────────────────────────────
class SiblingTopological(OracleReleaseRuntimeAO):
    """Referent = the topic with the most relational MASS in the session, not the latest."""

    def _live_topic(self, session_id: str):
        mass = Counter()
        for tr in self.path(session_id):
            if tr.get("out_status") != "answered":
                continue
            t = None
            m = OPENER.match(str(tr.get("in_surface", "")).strip())
            if m:
                t = m.group("t").strip()
            else:
                cv = tr.get("conversion") or {}
                m2 = re.match(r"^summari[sz]e\s+(?P<t>.+?)[.?!]*$", str(cv.get("to", "")), re.I)
                t = m2.group("t").strip() if m2 else None
            if t:
                mass[t.lower()] += 1 + int(tr.get("citations", 0) or 0)
        if not mass:
            return super()._live_topic(session_id)
        return mass.most_common(1)[0][0]


# ── 2. COMPRESSED provenance ────────────────────────────────────────────────────
FAMILY_OF = {
    "capability:summarize": "page-summary", "definitional_encyclopedic": "page-lead",
    "capability:what_causes": "evidence-selection", "capability:explain_simply": "re-register",
    "conceptnet_isa_derived": "transitive-derivation", "conceptnet_isa_direct": "edge-citation",
    "conceptnet_partof_direct": "edge-citation", "conceptnet_partof_derived": "transitive-derivation",
    "wordnet_kind_direct": "hierarchy-lookup", "wordnet_kind_excluded": "hierarchy-exclusion",
    "wordnet_kind_occluded": "conflict-disclosure",
}


class SiblingCompressed(OracleReleaseRuntimeAO):
    """Warrant compressed to the TRANSFORMATION FAMILY; replay names the family, not addresses."""

    def _act_provenance_replay(self, state: dict) -> dict:
        last = state.get("last_result") or {}
        if not last:
            return {"status": "withheld", "path": "act:provenance_replay",
                    "response": "Nothing has been answered in this session yet."}
        fam = FAMILY_OF.get(str(last.get("path", "")), "unregistered-family")
        n = len(last.get("citations") or [])
        answered = str(last.get("status", "")) == "answered"
        if not answered:
            return {"status": "answered", "path": "act:provenance_replay",
                    "response": f"My previous turn was a typed refusal; no family produced an answer.",
                    "provenance": {"kind": "family_replay", "family": None}}
        return {"status": "answered", "path": "act:provenance_replay",
                "response": (f"My previous answer was produced by the {fam} family"
                             + (f", over {n} admitted addresses" if n else "")
                             + ". I retain the family, not the addresses."),
                "provenance": {"kind": "family_replay", "family": fam, "address_count": n}}


# ── 3. EPOCHAL rhythm ───────────────────────────────────────────────────────────
class SiblingEpochal(OracleReleaseRuntimeAO):
    """Dialogue state integrates only every K turns; between seals, answers come from the
    last sealed state."""
    K = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sealed: dict = {}
        self._count: Counter = Counter()

    def chat(self, text: str, session_id: str = "default") -> dict:
        import copy
        self._count[session_id] += 1
        if session_id in self._sealed:
            self.dialogue[session_id] = copy.deepcopy(self._sealed[session_id])
        result = super().chat(text, session_id)
        if self._count[session_id] % self.K == 0:
            self._sealed[session_id] = copy.deepcopy(self.dialogue.get(session_id) or {})
        return result


# ── 4. EVIDENTIAL grammar ───────────────────────────────────────────────────────
HEARSAY = re.compile(r"^(?:i heard (?:that )?|they say (?:that )?|apparently,?\s*|reportedly,?\s*|"
                     r"someone said (?:that )?|is it true (?:that )?)(?P<p>.+?)[.?!]*$", re.I)
DIRECT = re.compile(r"^(?:i saw (?:that )?|i know (?:that )?|i noticed (?:that )?)(?P<p>.+?)[.?!]*$", re.I)
INFER = re.compile(r"^(?:so |then |i guess |presumably,?\s*|it seems (?:that )?)(?P<p>.+?)[.?!]*$", re.I)


class SiblingEvidential(OracleReleaseRuntimeAO):
    """Reads input through an obligatory-evidentiality grammar and marks every answer with
    the evidential the record licenses."""

    def _evidential_of(self, result: dict) -> str:
        if result.get("status") != "answered":
            return "unknown"
        kind = str(result.get("provenance", {}).get("kind", ""))
        cites = CITE.findall(str(result.get("response", "")))
        if kind in ("derived",):
            return "inferred"
        if kind in ("lexical_corpus", "commonsense_edge") or cites:
            return "direct"
        if kind in ("gated_summary", "selected_evidence", "dbpedia_page"):
            return "reported"
        return "unknown"

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        marked, proposition = None, s
        for name, pat in (("hearsay", HEARSAY), ("direct", DIRECT), ("inferred", INFER)):
            m = pat.match(s)
            if m:
                marked, proposition = name, m.group("p").strip()
                break
        if marked:
            # a hearsay/inference-marked input is a claim to CHECK, not a question to answer:
            # re-read it as a kind or summary probe of its proposition
            probe = proposition if re.match(r"^(is|are|what|who|when|how)\b", proposition, re.I) \
                else f"Summarize {proposition}."
            self._pending_conversion[session_id] = {
                "construction": f"EVIDENTIAL:{marked}", "from": s[:80], "to": probe[:80],
                "produced_by": "sibling:evidential"}
            result = super().chat(probe, session_id)
        else:
            result = super().chat(s, session_id)
        ev = self._evidential_of(result)
        result["evidential"] = {"input_marked": marked, "answer_licensed": ev}
        if result.get("status") == "answered":
            tag = {"direct": "[ev:direct]", "inferred": "[ev:inferred]",
                   "reported": "[ev:reported]", "unknown": "[ev:unknown]"}[ev]
            if marked == "hearsay" and ev in ("direct", "inferred"):
                result["response"] = f"{tag} What you heard is supported. " + str(result.get("response", ""))
            elif marked == "hearsay":
                result["response"] = f"{tag} " + str(result.get("response", ""))
            else:
                result["response"] = f"{tag} " + str(result.get("response", ""))
        hist = getattr(self, "_paths", {}).get(session_id)
        if hist:
            hist[-1]["evidential"] = result["evidential"]
        return result


BED2 = {"topological": SiblingTopological, "compressed": SiblingCompressed,
        "epochal": SiblingEpochal, "evidential": SiblingEvidential}
