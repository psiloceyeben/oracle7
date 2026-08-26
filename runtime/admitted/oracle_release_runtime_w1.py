#!/usr/bin/env python3
"""oracle_release_runtime_w1 - worker-authored alias fold (continuous recursive loop).

Learned from 3 unresolved surfaces across sources ['human'];
clusters: ['more_about']. Additive successor of the head; every conversion is
recorded with produced_by, and the unchanged chain supplies every answer with its
warrant. Authored 2026-08-23 20:09 UTC by oracle_fold_worker_v1; judged only by the daemon gate."""

from __future__ import annotations

import re

from oracle_release_runtime_ao import OracleReleaseRuntimeAO

ALIASES = [('^more about (?P<t>[a-z][a-z\\s\\-]{2,40})[.?!]*$', 'Summarize {t}.')]
NORM = {'penguins': 'penguin', 'whales': 'whale', 'hurricanes': 'hurricane'}                       # witnessed surface -> anchor form, learned only
DEICTIC_SKIP = {"that", "this", "it", "them", "those", "these", "him", "her"}


class OracleReleaseRuntimeW1(OracleReleaseRuntimeAO):
    """Head + the worker-folded alias constructions. Nothing else changes."""

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        for pat, tmpl in ALIASES:
            m = re.match(pat, s, re.I)
            if m:
                t = m.group("t").strip()
                if t.lower() in DEICTIC_SKIP:
                    break              # deictic reference: the head's own conversion owns it
                t = NORM.get(t.lower(), t)
                probe = tmpl.format(t=t)
                pending = getattr(self, "_pending_conversion", None)
                if pending is None:
                    pending = self._pending_conversion = {}
                pending[session_id] = {
                    "construction": "WORKER_ALIAS", "from": s[:80],
                    "to": probe[:80], "produced_by": "oracle_fold_worker_v1"}
                return super().chat(probe, session_id)
        return super().chat(s, session_id)
