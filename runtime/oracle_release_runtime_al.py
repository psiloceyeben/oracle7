#!/usr/bin/env python3
"""Runtime AL - provenance replay must not deny answers it gave (additive over AK).

Opened by the M42 self-snapshot, which reported the ACTS layer wholly ungraded.

`_act_provenance_replay` dispatches on provenance["kind"] across four branches -
dbpedia_page, gated_paragraph, conceptnet_edges, session_world - and its ELSE branch
asserts:

    "It was a typed refusal: no admitted evidence licensed an answer, so none was given."

Measured: 7 of 8 answered routes emit a kind that is NOT in that list. gated_summary,
derived, selected_evidence, self_description, lexical_corpus, commonsense_edge and
simple_register all fall through. So "Summarize the Moon." returns six citations, and
"how do you know?" replies that nothing licensed an answer.

In a system whose entire claim is shown provenance, denying provenance it holds is the
worst available failure - worse than fabricating one, because it destroys warrant the
system actually earned.

Two fixes:
 1. NEVER infer refusal from an unrecognised kind. Refusal is read from `status`, which
    dialogue state already records. An unknown kind is reported as unknown.
 2. Carry the prior answer's citation tokens in dialogue state so the replay can restate
    the actual addresses rather than describing them abstractly.

No neural network; no LM call.
"""

from __future__ import annotations

import re

from oracle_release_runtime_ak import OracleReleaseRuntimeAK

CITE = re.compile(r"\[[a-z0-9_]+:?[a-z0-9_.\-]*\]")

KIND_PHRASE = {
    "dbpedia_page": "the definitional lead of an admitted encyclopedic page",
    "gated_summary": "a composed summary of page-addressed claims, each carrying its address",
    "gated_paragraph": "a composed paragraph of page-addressed claims",
    "conceptnet_edges": "admitted commonsense edges",
    "commonsense_edge": "a single admitted commonsense edge",
    "derived": "a derivation over admitted edges, with its premises shown",
    "selected_evidence": "evidence sentences selected from admitted pages",
    "lexical_corpus": "a curated lexical hierarchy (WordNet hypernym chains)",
    "simple_register": "an admitted page sentence re-registered in plain language",
    "self_description": "this system's own registered description",
    "session_world": "logic over the statements you asserted in this session",
    "observability_failure": "a conflict between two records, disclosed rather than resolved",
}


class OracleReleaseRuntimeAL(OracleReleaseRuntimeAK):
    def _act_provenance_replay(self, state: dict) -> dict:
        last = state.get("last_result")
        if not last:
            return {"status": "withheld", "path": "act:provenance_replay",
                    "response": "Nothing has been answered in this session yet, so there "
                                "is no provenance to replay."}
        prov = last.get("provenance") or {}
        kind = prov.get("kind", "unknown")
        route = last.get("path", "?")
        answered = str(last.get("status", "")) == "answered"
        cited = last.get("citations") or []
        lines = [f"My previous answer came via the {route} route."]

        if not answered:
            # refusal is read from STATUS, never inferred from an unrecognised kind
            lines.append("It was a typed refusal: no admitted evidence licensed an answer, "
                         "so none was given.")
        elif kind in KIND_PHRASE:
            lines.append(f"It rests on {KIND_PHRASE[kind]}.")
            if kind == "gated_paragraph" and prov.get("excluded"):
                lines.append("Excluded as insufficiently relevant (ledgered, not hidden): "
                             + ", ".join(f"{e['page']} ({e['relevance']})"
                                         for e in prov["excluded"][:4]) + ".")
            if kind == "derived" and prov.get("premises"):
                lines.append("Its premises were: "
                             + ", ".join(str(p) for p in prov["premises"][:4]) + ".")
        else:
            # honest non-recognition, NOT a denial that evidence existed
            lines.append(f"It was answered, and its provenance is recorded under the kind "
                         f"'{kind}', which I do not have a description for.")

        if answered and cited:
            lines.append(f"The addresses it carried were: {', '.join(cited[:6])}"
                         + (" and others." if len(cited) > 6 else "."))
        lines.append("Nothing in that answer was generated; each part is either addressed, "
                     "derived, or withheld.")
        return {"status": "answered", "path": "act:provenance_replay",
                "response": " ".join(lines),
                "provenance": {"kind": "dialogue_state_replay", "of_route": route,
                               "of_kind": kind, "of_status": last.get("status"),
                               "addresses_replayed": len(cited)}}

    def chat(self, text: str, session_id: str = "default") -> dict:
        result = super().chat(text, session_id)
        # carry the answer's actual addresses into dialogue state so replay can restate them
        try:
            slot = self.dialogue.get(session_id)
            if slot and isinstance(slot.get("last_result"), dict):
                if str(result.get("path", "")) != "act:provenance_replay":
                    slot["last_result"]["citations"] = CITE.findall(
                        str(result.get("response", "")))
        except Exception:  # noqa: BLE001
            pass
        return result
