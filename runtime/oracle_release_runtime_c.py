#!/usr/bin/env python3
"""Front-door successor C (additive over B): essay route + definitional route.

Essay route: "write an essay about X" -> the H2 gated document compiler over
the topic page plus up to two related pages (title matches carrying a
distinctive topic token, relevance-gated). Output is a structured document
whose thesis/conclusions/analyses/claims chain is verified by
recover_document before release; an unverifiable document is withheld.

Definitional route (closes the registered debt): "what is a/an X?" answers
with the gated definitional lead of X's page when the page exists, instead of
sense clarification."""

from __future__ import annotations

import re
import time

from oracle_release_runtime_b import OracleReleaseRuntimeB
from stage5m13e8_document_compiler_v1 import compile_section, compile_document, recover_document
from stage5m13e8_paragraph_compiler_v1 import _definitional_score
from stage5m13e8_relevance_gate_v1 import topic_tokens, classify_claim

ESSAY = re.compile(r"^(?:please )?(?:write|compose)(?: me)?(?: a| an)?(?: short| brief)?(?: \d+[- ]word)? essay (?:about|on) (?P<topic>.+?)\.?$", re.I)
DEFINITIONAL = re.compile(r"^what is (?:a |an |the )?(?P<term>[\w \-']{2,60})\?$", re.I)


class OracleReleaseRuntimeC(OracleReleaseRuntimeB):
    def _bundle(self, topic: str, n: int = 6) -> list[dict]:
        page = self.bench_query.page_id(topic)
        if not page:
            return []
        return [{"claim_id": c, "page": topic, "sentence": s}
                for c, s in self.bench_query.page_sentences(page)[:n]]

    def _related_titles(self, topic: str, cap: int = 2) -> list[str]:
        distinctive, _ = topic_tokens(topic)
        if not distinctive:
            return []
        token = sorted(distinctive)[0]
        # indexed prefix range on title_alias (no full scan over 6M articles)
        rows = self.bench_query.connection.execute(
            "SELECT a.title FROM title_alias t JOIN article a ON a.page_id = t.page_id "
            "WHERE t.normalized_title >= ? AND t.normalized_title < ? LIMIT 12",
            (token, token + "￿")).fetchall()
        related = []
        for (title,) in rows:
            if title.lower() == topic.lower():
                continue
            if classify_claim(topic, title, title) in ("explanatory", "exact_topic"):
                related.append(title)
            if len(related) >= cap:
                break
        return related

    def _essay_turn(self, text: str) -> dict | None:
        match = ESSAY.match(text.strip())
        if not match:
            return None
        topic = match.group("topic").strip()
        topics = [topic] + self._related_titles(topic)
        bundles = [(t, self._bundle(t), None) for t in topics]
        bundles = [(t, b, None) for t, b, _ in bundles if b]
        if not bundles:
            return {"status": "withheld", "path": "gated_document",
                    "response": f"No provenance-admitted page for {topic} is available to ground an essay.",
                    "provenance": {"kind": "gated_document", "topic": topic}}
        section = compile_section(f"The record on {topic}", bundles)
        document = compile_document(f"A provenance-bounded account of {topic}", [section])
        if not recover_document(document):
            return {"status": "withheld", "path": "gated_document",
                    "response": "Document failed its own derivation-chain verification and is withheld.",
                    "provenance": {"kind": "gated_document", "topic": topic,
                                   "failure": "recover_document"}}
        return {"status": "answered", "path": "gated_document",
                "response": document["text"],
                "provenance": {"kind": "gated_document", "topics": topics,
                               "exclusions": [{"page": e["page"], "relevance": e["relevance"]}
                                              for e in section["exclusions"]]}}

    def _definitional_turn(self, text: str) -> dict | None:
        match = DEFINITIONAL.match(text.strip())
        if not match:
            return None
        term = match.group("term").strip()
        bundle = self._bundle(term.title()) or self._bundle(term)
        if not bundle:
            return None  # fall through to sense machinery
        lead = max(bundle, key=lambda c: _definitional_score(term, c["sentence"]))
        if _definitional_score(term, lead["sentence"]) < 6:
            return None
        return {"status": "answered", "path": "definitional_encyclopedic",
                "response": f"{lead['sentence']} [{lead['claim_id']}]",
                "provenance": {"kind": "dbpedia_page", "page": lead["page"],
                               "claim_id": lead["claim_id"]}}

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        normalized = " ".join(text.strip().split())
        result = None
        for route in (lambda: self._essay_turn(normalized),
                      lambda: self._definitional_turn(normalized)):
            try:
                result = route()
            except Exception:  # noqa: BLE001
                result = None
            if result is not None:
                break
        if result is None:
            return super().chat(text, session_id)
        result["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
        result["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
        return result
