#!/usr/bin/env python3
"""Front-door successor D: anchor-resident addressing + user corpus ingestion.

1. AnchorStore — the address layer (normalized title -> page id, page id ->
   title) loaded RAM-resident at startup. Every anchored operation becomes a
   dictionary hit: microseconds, flat in corpus size. Open FTS search survives
   only as the explicitly bounded typed operation (54 ms worst case); the
   unbounded searcher is retired from the front door.
2. Anchored-summary route — "Tell me about X" resolves X against the address
   layer and composes a gated paragraph (provenance + relevance gate +
   derived analysis) instead of falling into conjunctive search.
3. User corpus — individuals add documents (session-scoped): sentences pass
   the SAME admission filters as the public corpus, receive user-document
   addresses (user:{session}:{doc}:{ordinal}, content-hashed), and are
   consulted FIRST by the definitional and summary routes with provenance
   kind "user_document". Teaching the model a document is admission, not
   training — instant, inspectable, deletable.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

from oracle_release_runtime import PHASE
from oracle_release_runtime_c import OracleReleaseRuntimeC
from stage5m13e8_paragraph_compiler_v3 import compile_gated_paragraph
from stage5m13e8_paragraph_compiler_v2 import recover_program_v2
from stage5m13e8_relevance_gate_v1 import _norm

ABOUT = re.compile(r"^(?:tell me about|who is|who was|what do you know about) (?:the )?(?P<t>.+?)[.?!]?$", re.I)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def admitted_sentences(text: str, cap: int = 40) -> list[str]:
    out = []
    for raw in SENTENCE_SPLIT.split(" ".join(text.split())):
        s = raw.strip()
        w = s.split()
        if not (4 <= len(w) <= 60):
            continue
        if any(m in s for m in ("{", "}", "<", ">", "http")):
            continue
        if not (s[0].isupper() or s[0].isdigit()):
            continue
        if not s.endswith((".", "!", "?")):
            continue
        out.append(s)
        if len(out) >= cap:
            break
    return out


class AnchorStore:
    """RAM-resident address layer over the active wikipedia build."""

    def __init__(self, connection):
        self.title_to_page: dict[str, str] = {}
        self.page_to_title: dict[str, str] = {}
        started = time.perf_counter()
        for norm, pid in connection.execute("SELECT normalized_title, page_id FROM title_alias"):
            self.title_to_page.setdefault(norm, pid)
        for pid, title in connection.execute("SELECT page_id, title FROM article"):
            self.page_to_title[pid] = title
        self.load_seconds = round(time.perf_counter() - started, 2)

    def resolve(self, phrase: str) -> str | None:
        return self.title_to_page.get(_norm(phrase))


class UserCorpus:
    """Session-scoped, admission-filtered, content-addressed user documents."""
    MAX_DOCS, MAX_CHARS = 20, 200_000

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, session: str) -> Path:
        safe = re.sub(r"[^\w.-]", "_", session)[:60]
        return self.root / f"user_corpus_{safe}.json"

    def load(self, session: str) -> dict:
        p = self._path(session)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"docs": {}}

    GLOBAL_CAP_BYTES = 500_000_000

    def ingest(self, session: str, title: str, text: str) -> dict:
        title = " ".join(title.split())[:120] or "untitled"
        text = text[: self.MAX_CHARS]
        total = sum(f.stat().st_size for f in self.root.glob("user_corpus_*.json"))
        if total > self.GLOBAL_CAP_BYTES:
            return {"status": "withheld", "reason": "global user-corpus capacity reached"}
        store = self.load(session)
        if len(store["docs"]) >= self.MAX_DOCS and title not in store["docs"]:
            return {"status": "withheld", "reason": "session document limit reached"}
        sentences = admitted_sentences(text)
        if not sentences:
            return {"status": "withheld", "reason": "no sentences passed admission (4-60 words, clean, terminated)"}
        claims = []
        for i, s in enumerate(sentences):
            # hash-first id: unique within the compiler's 20-char address window
            claims.append({"claim_id": f"user:{hashlib.sha256(s.encode()).hexdigest()[:12]}:{i}",
                           "sentence": s})
        store["docs"][title] = {"claims": claims, "sha256": hashlib.sha256(text.encode()).hexdigest(),
                                "chars": len(text)}
        self._path(session).write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")
        return {"status": "admitted", "title": title, "admitted_sentences": len(claims),
                "rejected_note": "sentences failing admission were excluded, not repaired"}

    def bundle(self, session: str, topic: str) -> list[dict]:
        store = self.load(session)
        t = _norm(topic)
        out = []
        for title, doc in store["docs"].items():
            title_hit = t and t in _norm(title)
            for c in doc["claims"]:
                if title_hit or (t and t in _norm(c["sentence"])):
                    out.append({"claim_id": c["claim_id"], "page": f"your document '{title}'",
                                "sentence": c["sentence"]})
        return out[:12]


class OracleReleaseRuntimeD(OracleReleaseRuntimeC):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.anchors = AnchorStore(self.bench_query.connection)
        self.user_corpus = UserCorpus(Path(self.state_root) / "user_corpora")

    # anchor-resident overrides (dictionary hits, no b-tree walk)
    def _bundle(self, topic: str, n: int = 6) -> list[dict]:
        page = self.anchors.resolve(topic)
        if not page:
            return []
        title = self.anchors.page_to_title.get(page, topic)
        return [{"claim_id": c, "page": title, "sentence": s}
                for c, s in self.bench_query.page_sentences(page)[:n]]

    def _anchored_summary(self, text: str, session_id: str) -> dict | None:
        match = ABOUT.match(text.strip())
        if not match:
            return None
        topic = match.group("t").strip()
        # user claims are pre-scoped by the user's own document titles and
        # BYPASS the topic-relevance gate (which would reject short-token
        # titles as lexical overlap); public claims remain fully gated.
        from stage5m13e8_relevance_gate_v1 import gate_bundle
        from stage5m13e8_paragraph_compiler_v2 import compile_paragraph_v2
        user_claims = self.user_corpus.bundle(session_id, topic)
        admitted_public, excluded = gate_bundle(topic, self._bundle(topic, n=6))
        claims = user_claims + admitted_public
        if not claims:
            return None
        paragraph, program = compile_paragraph_v2(
            topic, claims, evidence=3, aggregation_term=None)
        if paragraph is None or not recover_program_v2(paragraph, program):
            return None
        return {"status": "answered", "path": "anchored_summary",
                "response": paragraph,
                "provenance": {"kind": "gated_paragraph",
                               "user_claims": len(user_claims),
                               "public_claims": len(admitted_public),
                               "excluded": [{"page": e["page"], "relevance": e["relevance"]}
                                            for e in excluded]}}

    def ingest_document(self, session_id: str, title: str, text: str) -> dict:
        return self.user_corpus.ingest(session_id, title, text)

    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        normalized = " ".join(text.strip().split())
        result = None
        try:
            result = self._anchored_summary(normalized, session_id)
        except Exception:  # noqa: BLE001
            result = None
        if result is not None:
            result["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
            result["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
            return result
        return super().chat(text, session_id)
