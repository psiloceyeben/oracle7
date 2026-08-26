#!/usr/bin/env python3
"""Runtime AM - record dialogue state from the FINAL result (additive over AL).

M46 passed and two defects survived it, both visible the moment turn-1 used a route other
than summarize:

    "Is a gray whale a whale?"  -> answered by wordnet_kind_direct
        replay: "came via the DOCUMENT_RUNTIME route ... typed refusal"
    "What causes rain?"         -> answered by capability:what_causes
        replay: "Nothing has been answered in this session yet"

Cause: dialogue state is written inside runtime E's chat, but answers are produced at many
layers of the chain. Routes resolved ABOVE E never write state at all; routes resolved
after E (the whole AD..AL tier) leave E's record of the INNER result in place. The ACTS
layer therefore reads a state describing a different answer than the user received.

Fix: the top of the chain records what the user actually saw. State is written once, from
the final result, after every turn - overwriting whatever inner layers recorded. Acts are
conversions over the delivered answer, so the delivered answer is what must be stored.

M46 could not see this because every turn-1 probe in it was "Summarize X" - a single route,
which happens to be one that flows through E. The test distribution must cover the route
inventory, not one member of it.

No neural network; no LM call.
"""

from __future__ import annotations

import re

from oracle_release_runtime_al import OracleReleaseRuntimeAL

CITE = re.compile(r"\[[a-z0-9_]+:?[a-z0-9_.\-]*\]")
ACT_PATHS = ("act:provenance_replay", "act:acknowledge", "act:continue_topic", "act:refine")


class OracleReleaseRuntimeAM(OracleReleaseRuntimeAL):
    def chat(self, text: str, session_id: str = "default") -> dict:
        result = super().chat(text, session_id)
        path = str(result.get("path", ""))
        # acts are conversions OVER the last answer; they must not overwrite it
        if path in ACT_PATHS:
            return result
        try:
            slot = self.dialogue.setdefault(session_id, {})
            slot["last_result"] = {
                "path": result.get("path"),
                "provenance": result.get("provenance"),
                "status": result.get("status"),
                "citations": CITE.findall(str(result.get("response", ""))),
            }
        except Exception:  # noqa: BLE001
            pass
        return result
