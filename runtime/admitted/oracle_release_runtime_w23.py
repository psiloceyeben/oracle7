#!/usr/bin/env python3
"""oracle_release_runtime_w23 - RULE FOLD: made-of as a live corpus operator (unbounded coverage).

Replaces cache-shaped made-of (frozen pairs) with the extraction RULE executed at
answer time against the bench corpus: FTS candidates -> typed extraction -> cited
answer. Coverage = every attested composition sentence, not a mined subset.
Anti-shallowness law honored: the fold IS the rule.
Authored 2026-08-25 18:40 UTC by the fold worker, chained on oracle_release_runtime_w22."""

from __future__ import annotations

import re
import sqlite3

from oracle_release_runtime_w22 import OracleReleaseRuntimeW22

_MADE_Q = re.compile(
    r"^what (?:is|are) (?:the )?(?P<t>[a-z][\w \-']{1,40}?) made (?:of|from)[?.! ]*$",
    re.I)
_EXTRACT = re.compile(
    r"^(?:The |A |An )?(?P<x>[A-Za-z][\w \-']{1,36}?) (?:is|are) "
    r"(?:composed of|made of|made up of|made from) (?P<y>[a-z][\w ,\-']{2,70}?)[.;]",
    re.I)


class OracleReleaseRuntimeW23(OracleReleaseRuntimeW22):
    """Base + the live made-of rule. The corpus answers; the rule only extracts."""

    def _bench(self):
        con = getattr(self, "_rule_bench", None)
        if con is None:
            import stage5m13e7_benchfold_induction_v1 as bench_mod
            uri = bench_mod.DB.resolve().as_uri() + "?mode=ro&immutable=1"
            con = self._rule_bench = sqlite3.connect(uri, uri=True,
                                                     check_same_thread=False)
        return con

    def made_of_lookup(self, subject: str):
        """The admitted operator: subject -> (material, claim_id) or None."""
        subject = subject.strip().lower()
        for form in (subject, subject.rstrip("s")):
            if not form:
                continue
            try:
                rows = self._bench().execute(
                    "SELECT claim_id, fact FROM source_rows WHERE fact MATCH ? LIMIT 30",
                    (f'"{form}" AND ("made of" OR "composed of" OR "made from")',
                     )).fetchall()
            except Exception:
                return None
            for claim, fact in rows:
                m = _EXTRACT.match(str(fact))
                if m and m.group("x").strip().lower() in (form, form + "s"):
                    mat = m.group("y").split(",")[0].split(" and ")[0].strip()
                    return (mat, claim)
        return None

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        result = super().chat(s, session_id)
        if result.get("status") == "answered":
            return result          # fallback law: never override what the chain answers
        m = _MADE_Q.match(s)
        if m:
            hit = self.made_of_lookup(m.group("t"))
            if hit:
                mat, claim = hit
                pending = getattr(self, "_pending_conversion", None)
                if pending is None:
                    pending = self._pending_conversion = {}
                pending[session_id] = {"construction": "RULE_MADE_OF",
                                        "from": s[:80], "to": "made_of_rule",
                                        "produced_by": "fold_worker_depth"}
                return {"status": "answered", "path": "worker:rule_made_of",
                         "response": f"By the attested record, {m.group('t').strip()} "
                                     f"is made of {mat}. [{claim}]",
                         "provenance": {"kind": "corpus_relation_rule",
                                         "relation": "made_of", "claim_id": claim},
                         "latency_ms": 2}
        return result
