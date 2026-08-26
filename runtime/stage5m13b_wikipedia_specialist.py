#!/usr/bin/env python3
"""Provenance-complete Wikipedia specialist and M13b integrated runtime."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
RELEASE_SRC = ROOT / "wander-release" / "oracle-relational-v3-hf-v1.0.1-release" / "src"
if str(RELEASE_SRC) not in sys.path:
    sys.path.insert(0, str(RELEASE_SRC))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from oracle_relational_v3.oracle_10d_resolution_state import canonical_sha256
from oracle_relational_v3.stage5m3a_evidence_addressed_realizer import EvidenceAddressedRealizer, RealizationRequest, SurfaceClause
from oracle_relational_v3.stage5m11a_schema_native_long_horizon_agent import SchemaTool
from stage5m13a_wordnet_specialist import LexicalSessionStore, OracleM13aRuntime


SCHEMA = "oracle-stage5m13b-wikipedia-specialist-v3"
INDEX_SCHEMA = "oracle-stage5m13b-wikipedia-sqlite-v3"
RUNTIME_SCHEMA = "oracle-stage5m13b-encyclopedic-runtime-v2"
STOP = frozenset({"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in", "is", "it", "of", "on", "or", "the", "to", "was", "were", "what", "when", "where", "which", "who", "why", "with"})


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value)).casefold().replace("_", " ")
    return " ".join(re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).split())


def validate_build(root: Path | str, *, deep: bool = False) -> dict[str, Any]:
    root = Path(root).resolve(); manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SCHEMA or manifest.get("status") != "compiled":
        raise ValueError("unsupported_wikipedia_specialist")
    if digest(manifest["semantic_identity"]) != manifest.get("semantic_identity_sha256"):
        raise ValueError("wikipedia_specialist_identity_changed")
    for relative, registration in manifest["files"].items():
        path = root / relative
        if not path.is_file() or path.stat().st_size != int(registration["bytes"]):
            raise ValueError(f"wikipedia_specialist_artifact_size_changed:{relative}")
        if deep or relative != "wikipedia_specialist.sqlite3":
            if sha_file(path) != registration["sha256"]:
                raise ValueError(f"wikipedia_specialist_artifact_changed:{relative}")
    inventory = json.loads((root / "corpus_inventory.json").read_text(encoding="utf-8"))
    if digest({key: value for key, value in inventory.items() if key != "semantic_identity_sha256"}) != inventory.get("semantic_identity_sha256"):
        raise ValueError("wikipedia_inventory_changed")
    if inventory.get("evaluation_inputs") or inventory.get("evaluation_data_read"):
        raise ValueError("evaluation_data_must_not_enter_wikipedia_specialist")
    uri = (root / "wikipedia_specialist.sqlite3").as_uri() + "?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    metadata = {key: json.loads(value) for key, value in connection.execute("SELECT key,value FROM metadata")}
    if metadata != manifest["metrics"] or metadata.get("index_schema") != INDEX_SCHEMA:
        raise ValueError("wikipedia_index_metadata_changed")
    if deep:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("wikipedia_index_integrity_failed")
        counts = {
            "articles": connection.execute("SELECT COUNT(*) FROM article").fetchone()[0],
            "claims": connection.execute("SELECT COUNT(*) FROM source_rows").fetchone()[0],
            "page_sentence_addresses": connection.execute("SELECT COUNT(*) FROM page_sentence").fetchone()[0],
        }
        if any(counts[key] != metadata[key] for key in counts):
            raise ValueError("wikipedia_index_count_changed")
        dangling = connection.execute(
            "SELECT COUNT(*) FROM page_sentence p LEFT JOIN article a ON a.page_id=p.page_id "
            "LEFT JOIN source_rows s ON s.rowid=p.source_rowid WHERE a.page_id IS NULL OR s.rowid IS NULL"
        ).fetchone()[0]
        if dangling:
            raise ValueError("wikipedia_index_dangling_address")
    connection.close(); return manifest


@dataclass(frozen=True)
class WikipediaClaim:
    claim_id: str
    fact: str
    fact_sha256: str
    page_id: str
    title: str
    canonical_url: str
    raw_record_sha256: str
    abstract_sha256: str
    sentence_ordinal: int
    selection: str
    rank: float | None = None

    def public(self) -> dict[str, Any]:
        return dict(self.__dict__)


class WikipediaSpecialist:
    def __init__(self, build_root: Path | str, *, deep_validate: bool = False):
        self.root = Path(build_root).resolve(); self.manifest = validate_build(self.root, deep=deep_validate)
        uri = (self.root / "wikipedia_specialist.sqlite3").as_uri() + "?mode=ro&immutable=1"
        self.connection = sqlite3.connect(uri, uri=True, check_same_thread=False); self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    @staticmethod
    def _candidate(value: sqlite3.Row) -> dict[str, Any]:
        return {
            "entity_id": "wikipedia:en:" + str(value["page_id"]), "page_id": str(value["page_id"]),
            "title": str(value["title"]), "canonical_url": str(value["canonical_url"]),
            "raw_record_sha256": str(value["raw_record_sha256"]), "abstract_sha256": str(value["abstract_sha256"]),
            "sentence_count": int(value["sentence_count"]), "admitted_sentence_count": int(value["admitted_sentence_count"]),
        }

    def resolve(self, query: str) -> dict[str, Any]:
        source = " ".join(str(query).split())
        page_id = None
        if match := re.fullmatch(r"wikipedia:en:(\d+)", source.casefold()):
            page_id = match.group(1)
        if page_id is not None:
            row = self.connection.execute("SELECT * FROM article WHERE page_id=?", (page_id,)).fetchone()
            return ({"status": "resolved", "method": "exact_page_id", **self._candidate(row)} if row
                    else {"status": "unresolved", "method": "unknown_page_id", "query": source})
        normalized = normalize_title(source)
        rows = self.connection.execute(
            "SELECT a.* FROM title_alias t JOIN article a ON a.page_id=t.page_id WHERE t.normalized_title=? ORDER BY CAST(a.page_id AS INTEGER)",
            (normalized,),
        ).fetchall()
        if len(rows) == 1:
            return {"status": "resolved", "method": "unique_exact_title", "query": source, **self._candidate(rows[0])}
        if rows:
            return {"status": "ambiguous", "method": "normalized_title_collision", "query": source, "candidate_count": len(rows), "candidates": [self._candidate(row) for row in rows]}
        # A bare numeral can be a real title (including a colliding one), so
        # title authority must be exhausted before retaining the convenience
        # fallback for callers that pass an unqualified numeric page id.
        if source.isdigit():
            row = self.connection.execute("SELECT * FROM article WHERE page_id=?", (source,)).fetchone()
            if row:
                return {"status": "resolved", "method": "bare_page_id_fallback", **self._candidate(row)}
        return {"status": "unresolved", "method": "no_exact_title", "query": source}

    @staticmethod
    def _claim(row: sqlite3.Row, selection: str, rank: float | None = None) -> WikipediaClaim:
        return WikipediaClaim(
            str(row["claim_id"]), str(row["fact"]), str(row["fact_sha256"]), str(row["page_id"]),
            str(row["title"]), str(row["canonical_url"]), str(row["raw_record_sha256"]),
            str(row["abstract_sha256"]), int(row["sentence_ordinal"]), selection, rank,
        )

    def article_claims(self, page_id: str, *, limit: int = 64) -> list[WikipediaClaim]:
        rows = self.connection.execute(
            "SELECT s.claim_id,s.fact,s.fact_sha256,s.page_id,s.sentence_ordinal,a.title,a.canonical_url," 
            "a.raw_record_sha256,a.abstract_sha256 FROM page_sentence p JOIN source_rows s ON s.rowid=p.source_rowid "
            "JOIN article a ON a.page_id=p.page_id WHERE p.page_id=? ORDER BY p.sentence_ordinal LIMIT ?",
            (str(page_id), int(limit)),
        ).fetchall()
        return [self._claim(row, "exact_article") for row in rows]

    @staticmethod
    def _terms(query: str, *, maximum: int = 8, minimum_length: int = 2) -> list[str]:
        tokens = []
        # Match SQLite FTS5 unicode61 word boundaries: retain Unicode letters
        # and digits, split punctuation/hyphens, and avoid Python casefold's
        # information-losing ß -> ss expansion.
        source = unicodedata.normalize("NFKC", str(query)).lower()
        for value in re.findall(r"[^\W_]+", source, flags=re.UNICODE):
            if len(value) >= minimum_length and value not in STOP and value not in tokens:
                tokens.append(value)
            if len(tokens) == maximum:
                break
        return tokens

    @staticmethod
    def _fts_variants(value: str) -> list[str]:
        variants = [value]
        # German-language ASCII transliteration commonly writes ß as ss,
        # whereas the preserved unicode61 index keeps ß.  Retain the literal
        # token and add a bounded alternative rather than rewriting identity.
        if "ss" in value:
            alternative = value.replace("ss", "ß")
            if alternative != value:
                variants.append(alternative)
        return variants

    @classmethod
    def _fts_clause(cls, value: str) -> str:
        variants = ['"' + item.replace('"', '""') + '"' for item in cls._fts_variants(value)]
        return variants[0] if len(variants) == 1 else "(" + " OR ".join(variants) + ")"

    @classmethod
    def _expression(cls, query: str) -> str | None:
        tokens = cls._terms(query)
        return " AND ".join(cls._fts_clause(value) for value in tokens) if tokens else None

    def search(self, query: str, *, limit: int = 20, exclude_page_ids: set[str] | None = None) -> list[WikipediaClaim]:
        expression = self._expression(query)
        if not expression:
            return []
        rows = self.connection.execute(
            "SELECT s.claim_id,s.fact,s.fact_sha256,s.page_id,s.sentence_ordinal,a.title,a.canonical_url," 
            "a.raw_record_sha256,a.abstract_sha256,bm25(source_rows) AS rank FROM source_rows s "
            "JOIN article a ON a.page_id=s.page_id WHERE source_rows MATCH ? ORDER BY rank,s.rowid LIMIT ?",
            (expression, max(int(limit) * 4, int(limit))),
        ).fetchall()
        excluded = exclude_page_ids or set(); selected = []
        for row in rows:
            if str(row["page_id"]) in excluded:
                continue
            selected.append(self._claim(row, "fts_candidate", float(row["rank"])))
            if len(selected) == limit:
                break
        return selected

    def related_context(
        self,
        article: Mapping[str, Any],
        anchors: list[WikipediaClaim],
        *,
        limit: int,
    ) -> tuple[list[WikipediaClaim], list[str]]:
        """Retrieve bounded lexical context without upgrading overlap to truth.

        Sparse abstracts cannot support a multi-paragraph document by
        themselves.  Expansion therefore uses an OR over deterministic terms
        from the exact title and its admitted anchor sentences.  Every result
        remains an attributed candidate, is limited to two claims per external
        page, and carries its exact record and sentence digests.  The caller
        must keep this authority distinct from exact-article statements.
        """
        if limit <= 0:
            return [], []
        seed = str(article["title"]) + " " + " ".join(value.fact for value in anchors)
        terms = self._terms(seed, maximum=16, minimum_length=3)
        if not terms:
            return [], []
        expression = " OR ".join(self._fts_clause(value) for value in terms)
        rows = self.connection.execute(
            "SELECT s.claim_id,s.fact,s.fact_sha256,s.page_id,s.sentence_ordinal,a.title,a.canonical_url,"
            "a.raw_record_sha256,a.abstract_sha256,bm25(source_rows) AS rank FROM source_rows s "
            "JOIN article a ON a.page_id=s.page_id WHERE source_rows MATCH ? ORDER BY rank,s.rowid LIMIT ?",
            (expression, max(int(limit) * 12, 256)),
        ).fetchall()
        excluded = {str(article["page_id"])}
        seen = {value.claim_id for value in anchors}
        per_page: dict[str, int] = {}
        selected: list[WikipediaClaim] = []
        for row in rows:
            page_id = str(row["page_id"])
            claim = str(row["claim_id"])
            if page_id in excluded or claim in seen or per_page.get(page_id, 0) >= 2:
                continue
            seen.add(claim); per_page[page_id] = per_page.get(page_id, 0) + 1
            selected.append(self._claim(row, "fts_lexical_context_candidate", float(row["rank"])))
            if len(selected) == limit:
                break
        return selected, terms

    @staticmethod
    def _hierarchical_spine(
        groups: list[list[SurfaceClause]],
        objective_sha: str,
    ) -> dict[str, Any]:
        """Carry a document as nested protected HRR states.

        A long document is not one flat bag of clause bindings.  Each paragraph
        first receives its own complete ten-node route and terminal cleanup.
        Only an opaque paragraph handle then enters the document route.  This
        preserves the 4:1 root/payload discipline while increasing composition
        capacity without early unbinding or a larger vector width.
        """
        leaf_spines = []
        paragraph_handles = []
        for index, group in enumerate(groups, 1):
            paragraph_sha = canonical_sha256({
                "document_objective": objective_sha,
                "paragraph": index,
                "clauses": [value.public() for value in group],
            })
            leaf = EvidenceAddressedRealizer._spine(group, paragraph_sha)
            leaf_spines.append({"paragraph": index, **leaf})
            paragraph_handles.append(SurfaceClause(
                f"paragraph_{index:02d}",
                paragraph_sha,
                "opaque_paragraph_handle",
                tuple(claim_id for value in group for claim_id in value.claim_ids),
                ("paragraph_terminal_cleanup", paragraph_sha),
            ))
        document_spine = EvidenceAddressedRealizer._spine(paragraph_handles, objective_sha)
        spines = [document_spine, *leaf_spines]
        recoveries = [
            {"level": "document", **value} for value in document_spine["recoveries"]
        ] + [
            {"level": f"paragraph_{leaf['paragraph']:02d}", **value}
            for leaf in leaf_spines for value in leaf["recoveries"]
        ]
        return {
            "schema_version": "oracle-stage5m13b-hierarchical-document-spine-v1",
            "levels": 2,
            "protected_root_ratio": "4:1",
            "route": document_spine["route"],
            "tree_nodes_registered": document_spine["tree_nodes_registered"],
            "tree_paths_registered": document_spine["tree_paths_registered"],
            "paragraph_states": len(leaf_spines),
            "pre_malkuth_payload_unbinds": sum(value["pre_malkuth_payload_unbinds"] for value in spines),
            "malkuth_payload_unbinds": sum(value["malkuth_payload_unbinds"] for value in spines),
            "minimum_protected_root_cosine": min(value["minimum_protected_root_cosine"] for value in spines),
            "terminal_cleanup_exact": all(value["terminal_cleanup_exact"] for value in spines),
            "minimum_cleanup_margin": min(value["minimum_cleanup_margin"] for value in spines),
            "document_spine": document_spine,
            "paragraph_spines": leaf_spines,
            "recoveries": recoveries,
        }

    def realize(self, page_id: str, *, artifact: str = "paragraph", paragraphs: int = 3, query: str | None = None) -> dict[str, Any]:
        started = time.perf_counter(); article = self.resolve("wikipedia:en:" + str(page_id))
        limits = {"sentence": 1, "paragraph": 8, "essay": 24, "paper": 36}
        if artifact not in limits:
            raise ValueError("unsupported Wikipedia artifact")
        if article["status"] != "resolved":
            return {"schema_version": RUNTIME_SCHEMA, "status": "withheld", "reason": "unknown_page_id", "response": "I need an exact authenticated Wikipedia page address before I can realize that article.", "factual_release": False}
        limit = limits[artifact]; claims = self.article_claims(str(page_id), limit=limit); context_terms: list[str] = []
        if len(claims) < limit and artifact in {"essay", "paper"}:
            context, context_terms = self.related_context(article, claims, limit=limit-len(claims))
            claims.extend(context)
        claims = claims[:limit]
        if not claims:
            return {"schema_version": RUNTIME_SCHEMA, "status": "withheld", "reason": "no_admitted_article_sentences", "response": "The exact article exists, but no complete provenance-admitted sentence is available for release.", "factual_release": False, "entity": article}
        clauses: list[SurfaceClause] = []; references = []
        if artifact != "sentence":
            contextual = any(value.selection == "fts_lexical_context_candidate" for value in claims)
            introduction = (
                f"This account begins with exact attributed statements from {article['title']} and then adds provenance-preserved lexical context from the Wikipedia snapshot."
                if contextual else
                f"This account assembles exact attributed statements for {article['title']} from the preserved Wikipedia snapshot."
            )
            clauses.append(SurfaceClause(
                "synthesis_intro", introduction,
                "inferred", tuple(value.claim_id for value in claims), ("exact_page_then_bounded_lexical_context", str(page_id), *context_terms),
            ))
        for index, claim in enumerate(claims, 1):
            citation = f"P{index}"
            proof = ("exact_article_sentence" if claim.selection == "exact_article" else "fts_lexical_context_candidate", claim.claim_id, claim.raw_record_sha256, claim.fact_sha256)
            clauses.append(SurfaceClause(
                f"claim_{index:02d}", claim.fact.rstrip(". ") + f" [{citation}].", "attributed_secondary_source",
                (claim.claim_id,), proof, inline_citations=(citation,),
            ))
            references.append({
                "citation_id": citation, "claim_id": claim.claim_id, "page_id": claim.page_id, "title": claim.title,
                "source_url": claim.canonical_url, "raw_record_sha256": claim.raw_record_sha256,
                "abstract_sha256": claim.abstract_sha256, "sentence_ordinal": claim.sentence_ordinal,
                "fact_sha256": claim.fact_sha256, "selection": claim.selection, "bm25_rank": claim.rank,
                "license": self.manifest["source"]["license_name"],
            })
        if artifact != "sentence":
            clauses.append(SurfaceClause(
                "synthesis_boundary", "These are attributed snapshot statements; lexical overlap and retrieval rank establish candidate context only and do not prove that contextual statements are facts about the anchor article, nor do they prove truth, freshness, completeness, or consensus.",
                "inferred", tuple(value.claim_id for value in claims), ("secondary_source_authority_boundary",),
            ))
        request = RealizationRequest("wikipedia", (str(page_id),), artifact, "explain", max(3, min(6, paragraphs)))
        groups = EvidenceAddressedRealizer._partition(clauses, request); response, inverse = EvidenceAddressedRealizer._layout(groups, request)
        if artifact == "paper":
            response = "## Evidence-addressed snapshot account\n\n" + response + "\n\n## Source boundary\n\nEvery numbered citation addresses an exact preserved Wikipedia record; the snapshot date is not present in the preserved source metadata."
        objective_sha = canonical_sha256({"page_id": str(page_id), "artifact": artifact, "query": query})
        spine = (
            self._hierarchical_spine(groups, objective_sha)
            if artifact in {"essay", "paper"}
            else EvidenceAddressedRealizer._spine(clauses, objective_sha)
        )
        result = {
            "schema_version": RUNTIME_SCHEMA, "status": "answered", "operation": "wikipedia_attributed_realization",
            "response": response, "factual_release": True, "authority_class": "attributed_secondary_source",
            "entity": article, "claims": [value.public() for value in claims], "clauses": [value.public() for value in clauses],
            "references": references, "paragraph_plan": [[value.clause_id for value in group] for group in groups],
            "tree_spine": spine, "whole_answer_inverse": inverse,
            "audit": {
                "exact_raw_record_digests": all(len(value.raw_record_sha256) == 64 for value in claims),
                "exact_fact_digests": all(hashlib.sha256(value.fact.encode("utf-8")).hexdigest() == value.fact_sha256 for value in claims),
                "retrieval_rank_treated_as_truth": False, "snapshot_freshness_claimed": False,
                "exact_article_claims": sum(value.selection == "exact_article" for value in claims),
                "lexical_context_claims": sum(value.selection == "fts_lexical_context_candidate" for value in claims),
                "lexical_context_terms": context_terms,
                "lexical_context_asserted_as_anchor_fact": False,
                "pre_malkuth_payload_unbinds": spine["pre_malkuth_payload_unbinds"], "terminal_cleanup_exact": spine["terminal_cleanup_exact"],
                "traditional_language_model_calls": 0, "transformer_calls": 0, "pretrained_embedding_calls": 0,
                "next_token_predictions": 0, "gradient_steps": 0,
            }, "latency_ms": 1000.0 * (time.perf_counter() - started),
        }
        result["artifact_sha256"] = canonical_sha256({key: value for key, value in result.items() if key not in {"latency_ms", "artifact_sha256"}})
        return result

    def realize_search(self, query: str, *, artifact: str = "paragraph", paragraphs: int = 3) -> dict[str, Any]:
        claims = self.search(query, limit={"sentence": 1, "paragraph": 8, "essay": 24, "paper": 36}.get(artifact, 8))
        if not claims:
            return {"schema_version": RUNTIME_SCHEMA, "status": "unresolved", "operation": "wikipedia_search_unresolved", "response": "No provenance-admitted Wikipedia sentence matched all bounded query terms.", "factual_release": False}
        # Anchor the realization on the top result's exact page while retaining
        # the original query as the bounded expansion objective.
        result = self.realize(claims[0].page_id, artifact=artifact, paragraphs=paragraphs, query=query)
        result["status"] = "partial"; result["operation"] = "wikipedia_attributed_search_roundup"
        result["reason"] = "no_exact_title_but_bounded_fts_evidence_available"
        result["response"] = (
            f"No exact preserved article title was found for {query!r}; the following is an attributed evidence roundup selected by bounded term relevance, not an assertion of page identity.\n\n"
            + result["response"]
        )
        result["artifact_sha256"] = canonical_sha256({key: value for key, value in result.items() if key not in {"latency_ms", "artifact_sha256"}})
        return result


class WikipediaConversation:
    DOCUMENT = re.compile(r"^\s*(?:please\s+)?(?:write|compose|draft|produce|create|give\s+me)\s+(?:a\s+|an\s+)?(?:(?P<count>[3-6])[-\s]+paragraph\s+)?(?P<artifact>essay|paper|paragraph|sentence)\s+(?:about|on|explaining|concerning)\s+(?P<topic>.+?)\s*[?.!]*$", re.I)
    QUESTION = re.compile(r"^\s*(?:(?:what|who)\s+(?:is|are)|tell\s+me\s+about|describe|explain|give\s+me\s+an?\s+(?:account|overview)\s+of)\s+(?P<topic>.+?)\s*[?.!]*$", re.I)
    MORE = re.compile(r"^\s*(?:tell\s+me\s+more|go\s+on|continue|expand(?:\s+that)?|say\s+more)\s*[?.!]*$", re.I)

    def __init__(self, specialist: WikipediaSpecialist, state_root: Path | str):
        self.specialist = specialist; self.sessions = LexicalSessionStore(Path(state_root) / "wikipedia_sessions")

    @staticmethod
    def clean_topic(value: str) -> str:
        value = value.strip()
        return re.sub(r"\s+(?:briefly|please|in detail)$", "", value, flags=re.I).strip(" .?!")

    def preview(self, text: str) -> dict[str, Any] | None:
        source = " ".join(str(text).split())
        if match := self.DOCUMENT.match(source):
            return {"topic": self.clean_topic(match.group("topic")), "artifact": match.group("artifact").casefold(), "paragraphs": int(match.group("count") or 3)}
        if match := self.QUESTION.match(source):
            artifact = "sentence" if source.casefold().startswith(("what is", "what are", "who is", "who are")) else "paragraph"
            return {"topic": self.clean_topic(match.group("topic")), "artifact": artifact, "paragraphs": 3}
        return None

    def chat(self, text: str, *, session_id: str = "default") -> dict[str, Any]:
        started = time.perf_counter(); source = " ".join(str(text).split()); act = self.preview(source); prior = self.sessions.load(session_id).get("last")
        if act is None and self.MORE.match(source) and prior:
            act = {"topic": "wikipedia:en:" + str(prior["page_id"]), "artifact": "essay", "paragraphs": 5}
        if act is None:
            return {"schema_version": RUNTIME_SCHEMA, "status": "unresolved", "operation": "wikipedia_act_unresolved", "response": "No encyclopedic discourse act was compiled.", "factual_release": False, "latency_ms": 1000.0 * (time.perf_counter() - started)}
        resolution = self.specialist.resolve(act["topic"])
        # Preserve literal title identity first (for example, "The Food
        # Album").  A conversational article is removed only as an explicitly
        # bounded fallback when no preserved literal title exists (for
        # example, "the French Revolution").
        if resolution["status"] == "unresolved" and re.match(r"^(?:the|a|an)\s+", act["topic"], re.I):
            fallback_topic = re.sub(r"^(?:the|a|an)\s+", "", act["topic"], count=1, flags=re.I)
            fallback = self.specialist.resolve(fallback_topic)
            if fallback["status"] != "unresolved":
                resolution = {**fallback, "conversational_article_fallback": True, "original_topic": act["topic"]}
        if resolution["status"] == "ambiguous":
            choices = "; ".join(f"{value['entity_id']} — {value['title']}" for value in resolution["candidates"])
            result = {"schema_version": RUNTIME_SCHEMA, "status": "clarification", "operation": "wikipedia_title_clarification", "response": "That normalized title identifies more than one preserved page. Specify a page ID: " + choices, "factual_release": False, "resolution": resolution}
            result["session"] = self.sessions.append(session_id, source, result, None); return result
        if resolution["status"] == "resolved":
            result = self.specialist.realize(resolution["page_id"], artifact=act["artifact"], paragraphs=act["paragraphs"], query=act["topic"])
            state = {"page_id": resolution["page_id"], "title": resolution["title"]}
        else:
            result = self.specialist.realize_search(act["topic"], artifact=act["artifact"], paragraphs=act["paragraphs"])
            state = {"page_id": result.get("entity", {}).get("page_id"), "title": result.get("entity", {}).get("title")} if result.get("entity") else None
        result["latency_ms"] = 1000.0 * (time.perf_counter() - started)
        result["session"] = self.sessions.append(session_id, source, result, state)
        return result


class OracleM13bRuntime:
    """M13a lexical Oracle plus a provenance-complete Wikipedia tier."""

    def __init__(self, state_root: Path | str, *, wordnet_build: Path | str, wikipedia_build: Path | str, **m12_options: Any):
        self.state_root = Path(state_root).resolve(); self.state_root.mkdir(parents=True, exist_ok=True)
        self.lexical_runtime = OracleM13aRuntime(self.state_root / "m13a", wordnet_build=wordnet_build, **m12_options)
        self.base = self.lexical_runtime.base; self.wordnet = self.lexical_runtime.wordnet
        self.wikipedia = WikipediaSpecialist(wikipedia_build); self.encyclopedic = WikipediaConversation(self.wikipedia, self.state_root / "encyclopedic")
        self._augment_tools()

    def _augment_tools(self) -> None:
        registry = self.base.tool_registry; wiki_claims = int(self.wikipedia.manifest["metrics"]["claims"])
        for name in ("inspect_oracle", "list_specialists"):
            tool = registry.tools[name]
            if name == "inspect_oracle":
                parent = tool.executor
                def inspect(value: Mapping[str, Any], executor=parent, count=wiki_claims) -> dict[str, Any]:
                    result = dict(executor(value)); result["version"] = "1.2.0-m13b-dev"; result["domains"] = int(result["domains"]) + 1; result["claims"] = int(result["claims"]) + count; return result
                registry.tools[name] = replace(tool, executor_id="oracle.m13b.inspect.v1", executor=inspect)
            else:
                parent = tool.executor
                def listed(value: Mapping[str, Any], executor=parent, count=wiki_claims) -> dict[str, Any]:
                    result = dict(executor(value)); domains = list(result["domains"]); domains.append({"domain": "wikipedia", "claims": count, "expert_id": "generalist_wikipedia_snapshot"}); return {"domains": domains, "total_claims": int(result["total_claims"]) + count}
                registry.tools[name] = replace(tool, executor_id="oracle.m13b.specialists.v1", executor=listed)

        def resolve_wikipedia(arguments: Mapping[str, Any]) -> dict[str, Any]:
            value = self.wikipedia.resolve(str(arguments["query"]))
            return {"status": value["status"], "method": value["method"], "entity_id": str(value.get("entity_id", "")), "candidate_count": int(value.get("candidate_count", 0)), "candidates": list(value.get("candidates", ()))}
        registry.register(SchemaTool(
            "resolve_wikipedia", "Resolve an exact preserved Wikipedia title or page identifier.",
            {"type": "object", "properties": {"query": {"type": "string", "minLength": 1, "maxLength": 256}}, "required": ["query"], "additionalProperties": False},
            {"type": "object", "properties": {"status": {"type": "string"}, "method": {"type": "string"}, "entity_id": {"type": "string"}, "candidate_count": {"type": "integer"}, "candidates": {"type": "array", "items": {"type": "object"}}}, "required": ["status", "method", "entity_id", "candidate_count", "candidates"], "additionalProperties": False},
            "read_only", "oracle.m13b.wikipedia-resolution.v1", resolve_wikipedia, ("resolve wikipedia title",),
        ))

        def search_wikipedia(arguments: Mapping[str, Any]) -> dict[str, Any]:
            rows = self.wikipedia.search(str(arguments["query"]), limit=int(arguments.get("limit", 5)))
            return {"query": str(arguments["query"]), "count": len(rows), "claims": [value.public() for value in rows]}
        registry.register(SchemaTool(
            "search_wikipedia", "Retrieve provenance-addressed attributed statements matching all bounded query terms.",
            {"type": "object", "properties": {"query": {"type": "string", "minLength": 1, "maxLength": 256}, "limit": {"type": "integer", "minimum": 1, "maximum": 20}}, "required": ["query"], "additionalProperties": False},
            {"type": "object", "properties": {"query": {"type": "string"}, "count": {"type": "integer"}, "claims": {"type": "array", "items": {"type": "object"}}}, "required": ["query", "count", "claims"], "additionalProperties": False},
            "read_only", "oracle.m13b.wikipedia-search.v1", search_wikipedia, ("search encyclopedia",),
        ))

    def chat(self, text: str, *, session_id: str = "default") -> dict[str, Any]:
        source = " ".join(str(text).split())
        if re.match(r"^(?:call|use)\b", source, re.I) or (re.search(r"\b(?:essay|document|account|treatise|report)\b", source, re.I) and re.search(r"\b(?:oracle|yourself|your architecture|what it is like|being this architecture)\b", source, re.I)):
            return self.lexical_runtime.chat(source, session_id=session_id)
        # Preserve the accepted curated tier wherever its own language program
        # resolves an authenticated topic.  Wikipedia is the fallback breadth
        # tier, not an authority upgrade over the more specific M10 sources.
        curated_program = self.base.conversation.transducer.compile(source, session_id=session_id)
        if curated_program.get("status") == "compiled" and curated_program.get("topics"):
            return self.base.chat(source, session_id=session_id)
        act = self.encyclopedic.preview(source)
        if act and len(act["topic"].split()) == 1:
            lexical = self.wordnet.resolve(act["topic"], pos="n", allow_dominant=True)
            if lexical.get("status") == "ambiguous":
                return self.lexical_runtime.chat(source, session_id=session_id)
        wiki = self.encyclopedic.chat(source, session_id=session_id)
        if wiki.get("status") in {"answered", "partial", "clarification"}:
            wiki["hot_loaded_specialist"] = "wikipedia_abstract_snapshot"
            return wiki
        return self.lexical_runtime.chat(source, session_id=session_id)

    def capabilities(self) -> dict[str, Any]:
        value = dict(self.lexical_runtime.capabilities())
        value.update({
            "schema_version": RUNTIME_SCHEMA,
            "wikipedia_articles": int(self.wikipedia.manifest["metrics"]["articles"]),
            "wikipedia_claims": int(self.wikipedia.manifest["metrics"]["claims"]),
            "wikipedia_unique_titles": int(self.wikipedia.manifest["metrics"]["unique_titles"]),
            "secondary_source_attribution_preserved": True,
            "retrieval_rank_is_factual_authority": False,
            "snapshot_date_known": False,
            "unrestricted_conversation": False,
        })
        return value


__all__ = ["OracleM13bRuntime", "WikipediaClaim", "WikipediaConversation", "WikipediaSpecialist", "validate_build", "RUNTIME_SCHEMA", "SCHEMA"]
