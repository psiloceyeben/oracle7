#!/usr/bin/env python3
"""Front-door successor B: adds the benchmark-induced corpus-query route.

Additive subclass of oracle_release_runtime (not edited). Loads ONLY rules
admitted by the induction ledger (multi-donor + evidence gates). The route
fires between commonsense and the document fallback; every answer is a
provenance-addressed sentence."""

from __future__ import annotations

import json

from oracle_release_runtime import OracleReleaseRuntime, PHASE
from stage5m13e7_benchfold_induction_v1 import RULES, DBpediaQuery, apply_rule


class OracleReleaseRuntimeB(OracleReleaseRuntime):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ledger = json.loads((PHASE / "stage5m13e7_benchfold_rule_ledger_v1.json").read_text(encoding="utf-8"))
        admitted = {r["rule"] for r in ledger["rules"] if r["admitted"]}
        self.bench_rules = [(rid, pat) for rid, pat, _ in RULES if rid in admitted]
        self.bench_query = DBpediaQuery()

    def _benchmark_turn(self, text: str) -> dict | None:
        stripped = text.rstrip("?.! ").strip()
        for rule_id, pattern in self.bench_rules:
            match = pattern.match(stripped + "?") or pattern.match(stripped)
            if not match:
                continue
            result = apply_rule(self.bench_query, rule_id, match)
            if result is None:
                return {"status": "withheld", "path": f"corpus_query:{rule_id}",
                        "response": "No provenance-admitted sentence in the abstracts corpus answers that.",
                        "provenance": {"kind": "dbpedia_query", "rule": rule_id}}
            claim_id, fact = result
            return {"status": "answered", "path": f"corpus_query:{rule_id}",
                    "response": fact,
                    "provenance": {"kind": "dbpedia_query", "rule": rule_id,
                                   "claim_id": claim_id}}
        return None

    def chat(self, text: str, session_id: str = "default") -> dict:
        import time
        started = time.perf_counter()
        normalized = " ".join(text.strip().split())
        result = None
        try:
            result = self._relational_turn(normalized, session_id)
        except Exception:  # noqa: BLE001
            result = None
        if result is None:
            commonsense = self.commonsense.answer(normalized)
            if commonsense["status"] in ("answered", "withheld"):
                result = {"status": commonsense["status"], "path": "conceptnet_commonsense",
                          "response": commonsense["response"],
                          "provenance": {"kind": "conceptnet_edges",
                                         "claims": commonsense.get("claims", [])}}
        if result is None:
            result = self._benchmark_turn(normalized)
        if result is None:
            value = self.documents.chat(normalized, session_id=f"doc-{session_id}")
            result = {"status": value.get("status", "unresolved"), "path": "document_runtime",
                      "response": str(value.get("response", "")),
                      "provenance": {"kind": "m13d2_envelope",
                                     "operation": value.get("operation"),
                                     "retrieval": value.get("retrieval")}}
        result["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
        result["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
        return result
