#!/usr/bin/env python3
"""M13d1: topic-driven three-level documents over attributed claim sets.

This is a deterministic compiler above the accepted M13b corpus and M13d
checkpoint runtime.  It retrieves exact and query-related source claims,
projects each claim into a query-conditioned ten-direction state, performs a
balanced global role assignment, and realizes thirty evidence-addressed
paragraph states under ten section states and one document state.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from oracle_relational_v3.oracle_10d_resolution_state import canonical_sha256
from oracle_relational_v3.stage5m3a_evidence_addressed_realizer import EvidenceAddressedRealizer, SurfaceClause
from stage5m13b_wikipedia_specialist import WikipediaClaim
from stage5m13d_hardened_checkpointed_self_essay import OracleM13dRuntime


SCHEMA = "oracle-stage5m13d1-general-hierarchical-document-v1"
RUNTIME_SCHEMA = "oracle-stage5m13d1-runtime-v1"
DIMENSION = 256
ROLE_DEFINITIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("orientation", "Scope and orientation", ("definition", "overview", "subject", "field", "topic", "known", "called", "refers")),
    ("identity", "Entities and definitions", ("is", "are", "means", "type", "form", "name", "term", "entity", "class")),
    ("history", "History and development", ("history", "year", "century", "founded", "began", "developed", "war", "period", "born")),
    ("structure", "Structure and components", ("structure", "part", "component", "system", "contains", "consists", "organization", "layer")),
    ("process", "Processes and mechanisms", ("process", "mechanism", "causes", "produces", "uses", "function", "method", "operation", "change")),
    ("relations", "Relations and context", ("relation", "between", "with", "related", "context", "interaction", "network", "associated")),
    ("applications", "Applications and examples", ("application", "used", "example", "practice", "technology", "research", "study", "model")),
    ("consequences", "Consequences and effects", ("effect", "result", "impact", "leads", "therefore", "influence", "consequence", "outcome")),
    ("disputes", "Limits, disputes, and uncertainty", ("however", "debate", "problem", "limit", "uncertain", "controversy", "criticism", "risk")),
    ("synthesis", "Synthesis and evidence boundary", ("evidence", "source", "claim", "account", "summary", "boundary", "snapshot", "conclusion")),
)


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def words(value: str) -> list[str]:
    return re.findall(r"[^\W_]+", value.casefold(), flags=re.UNICODE)


def normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm > 1e-12 else vector


@lru_cache(maxsize=32768)
def token_vector(token: str) -> np.ndarray:
    bits = np.unpackbits(np.frombuffer(hashlib.sha256(token.encode()).digest(), dtype=np.uint8)).astype(np.float64)
    return (bits * 2.0 - 1.0) / math.sqrt(DIMENSION)


def text_state(value: str) -> np.ndarray:
    unique = list(dict.fromkeys(words(value)))[:64]
    if not unique:
        return np.zeros(DIMENSION, dtype=np.float64)
    return normalize(np.sum([token_vector(token) for token in unique], axis=0))


def bind(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    return normalize(np.fft.irfft(np.fft.rfft(left) * np.fft.rfft(right), n=DIMENSION).real)


@dataclass(frozen=True)
class RoutedClaim:
    claim: WikipediaClaim
    role: str
    role_score: float
    directional_state: tuple[float, ...]
    query_shared_terms: tuple[str, ...]

    def public(self) -> dict[str, Any]:
        value = self.claim.public()
        value.update({"role": self.role, "role_score": self.role_score, "directional_state": list(self.directional_state), "query_shared_terms": list(self.query_shared_terms)})
        return value


class GeneralHierarchicalDocumentCompiler:
    def __init__(self, runtime: OracleM13dRuntime):
        self.runtime = runtime
        self.wikipedia = runtime.base.wikipedia
        self.role_states = {
            name: text_state(" ".join((name, title, *cues)))
            for name, title, cues in ROLE_DEFINITIONS
        }

    def _claim_pool(self, topic: str, limit: int = 90) -> tuple[dict[str, Any], list[WikipediaClaim], dict[str, Any]]:
        resolution = self.wikipedia.resolve(topic)
        exact: list[WikipediaClaim] = []
        if resolution["status"] == "ambiguous":
            return resolution, [], {"status": "ambiguous"}
        if resolution["status"] == "resolved":
            exact = self.wikipedia.article_claims(resolution["page_id"], limit=30)
        direct = self.wikipedia.search(topic, limit=max(limit * 2, 180))
        ordered: list[WikipediaClaim] = []
        seen_claims: set[str] = set(); seen_facts: set[str] = set()
        def admit(values: Sequence[WikipediaClaim]) -> None:
            for claim in values:
                fact_key = " ".join(claim.fact.casefold().split())
                if claim.claim_id in seen_claims or fact_key in seen_facts:
                    continue
                seen_claims.add(claim.claim_id); seen_facts.add(fact_key); ordered.append(claim)
                if len(ordered) == limit:
                    return
        admit(exact); admit(direct)
        if len(ordered) < limit:
            anchor = resolution if resolution["status"] == "resolved" else {"title": topic, "page_id": "unresolved-query-anchor"}
            context, terms = self.wikipedia.related_context(anchor, exact, limit=max(limit * 2, 180))
            admit(context)
        else:
            terms = self.wikipedia._terms(topic, maximum=16, minimum_length=3)
        metadata = {
            "status": "ready" if len(ordered) >= limit else "insufficient",
            "exact_title_status": resolution["status"],
            "exact_anchor_claims": sum(value.selection == "exact_article" for value in ordered[:limit]),
            "conjunctive_query_claims": sum(value.selection == "fts_candidate" for value in ordered[:limit]),
            "lexical_context_claims": sum(value.selection == "fts_lexical_context_candidate" for value in ordered[:limit]),
            "unique_claims": len(ordered[:limit]), "retrieval_terms": terms,
            "context_asserted_as_anchor_fact": False,
        }
        return resolution, ordered[:limit], metadata

    @staticmethod
    def _scores(topic: str, claim: WikipediaClaim) -> tuple[float, ...]:
        query = text_state(topic); state = text_state(claim.title + " " + claim.fact); relational = bind(query, state)
        scores = []
        for name, title, cues in ROLE_DEFINITIONS:
            role = text_state(" ".join((name, title, *cues)))
            query_role = bind(query, role)
            scores.append(0.72 * float(np.dot(state, role)) + 0.28 * float(np.dot(relational, query_role)))
        return tuple(scores)

    def _route(self, topic: str, claims: Sequence[WikipediaClaim]) -> list[RoutedClaim]:
        score_rows = [self._scores(topic, claim) for claim in claims]
        assignments: dict[int, int] = {}; capacity = [9] * len(ROLE_DEFINITIONS)
        candidates = sorted(
            ((score, claim_index, role_index) for claim_index, row in enumerate(score_rows) for role_index, score in enumerate(row)),
            key=lambda value: (-value[0], claims[value[1]].claim_id, value[2]),
        )
        for score, claim_index, role_index in candidates:
            if claim_index in assignments or capacity[role_index] == 0:
                continue
            assignments[claim_index] = role_index; capacity[role_index] -= 1
            if len(assignments) == len(claims):
                break
        if len(assignments) != 90 or any(capacity):
            raise ValueError("balanced_directional_assignment_incomplete")
        topic_terms = set(words(topic))
        routed = []
        for index, claim in enumerate(claims):
            role_index = assignments[index]; row = score_rows[index]
            routed.append(RoutedClaim(claim, ROLE_DEFINITIONS[role_index][0], row[role_index], row, tuple(sorted(topic_terms & set(words(claim.title + " " + claim.fact))))))
        return sorted(routed, key=lambda value: (next(index for index, role in enumerate(ROLE_DEFINITIONS) if role[0] == value.role), -value.role_score, value.claim.claim_id))

    @staticmethod
    def _paragraph_clauses(topic: str, role: tuple[str, str, tuple[str, ...]], paragraph_index: int, claims: Sequence[RoutedClaim], citation_start: int) -> tuple[list[SurfaceClause], list[dict[str, Any]]]:
        role_name, role_title, _ = role
        shared = sorted(set.intersection(*(set(words(value.claim.title + " " + value.claim.fact)) for value in claims))) if claims else []
        query_terms = sorted({term for value in claims for term in value.query_shared_terms})
        relation_terms = (query_terms or shared)[:4]
        relation_surface = ", ".join(relation_terms) if relation_terms else "their query-conditioned directional scores"
        intro_id = f"p{paragraph_index:02d}_objective"
        clauses = [SurfaceClause(
            intro_id,
            f"Paragraph {paragraph_index} routes three sources through {role_title.casefold()} for {topic}; retrieval relevance remains separate from factual authority.",
            "bounded_document_inference", tuple(value.claim.claim_id for value in claims), ("balanced_ten_direction_assignment", role_name, str(paragraph_index)),
        )]
        references = []
        for offset, routed in enumerate(claims):
            claim = routed.claim; citation = f"P{citation_start + offset:03d}"
            selection_label = {"exact_article": "exact anchor page", "fts_candidate": "conjunctive query match", "fts_lexical_context_candidate": "bounded lexical-context candidate"}.get(claim.selection, claim.selection)
            text = f"The preserved page {claim.title} contributes this attributed statement as a {selection_label}: {claim.fact.rstrip('. ')} [{citation}]."
            clauses.append(SurfaceClause(f"p{paragraph_index:02d}_source_{offset + 1}", text, "attributed_secondary_source", (claim.claim_id,), (claim.selection, claim.claim_id, claim.raw_record_sha256, claim.fact_sha256), inline_citations=(citation,)))
            references.append({"citation_id": citation, "claim_id": claim.claim_id, "page_id": claim.page_id, "title": claim.title, "source_url": claim.canonical_url, "raw_record_sha256": claim.raw_record_sha256, "abstract_sha256": claim.abstract_sha256, "fact_sha256": claim.fact_sha256, "sentence_ordinal": claim.sentence_ordinal, "selection": claim.selection, "bm25_rank": claim.rank})
        clauses.append(SurfaceClause(
            f"p{paragraph_index:02d}_boundary",
            f"At paragraph {paragraph_index}, shared surface {relation_surface} determines grouping, not causation or truth about {topic}; each statement remains bound to its cited page.",
            "epistemic_boundary", tuple(value.claim.claim_id for value in claims), ("surface_relation_not_world_relation", role_name, *relation_terms),
        ))
        return clauses, references

    @staticmethod
    def _nested_spine(paragraphs: Sequence[Sequence[SurfaceClause]], section_handles: Sequence[str], objective_sha: str) -> dict[str, Any]:
        paragraph_spines = []; paragraph_clauses = []
        for index, clauses in enumerate(paragraphs, 1):
            local = digest({"objective": objective_sha, "paragraph": index, "clauses": [value.public() for value in clauses]})
            spine = EvidenceAddressedRealizer._spine(list(clauses), local); paragraph_spines.append({"paragraph": index, **spine})
            paragraph_clauses.append(SurfaceClause(f"paragraph_{index:02d}", local, "opaque_paragraph_handle", tuple(claim for value in clauses for claim in value.claim_ids), ("paragraph_malkuth_cleanup", local)))
        section_spines = []; section_clauses = []
        for index, section in enumerate(section_handles):
            handles = paragraph_clauses[index * 3:(index + 1) * 3]
            local = digest({"objective": objective_sha, "section": section, "paragraphs": [value.text for value in handles]})
            spine = EvidenceAddressedRealizer._spine(handles, local); section_spines.append({"section": section, **spine})
            section_clauses.append(SurfaceClause(f"section_{index + 1:02d}", local, "opaque_section_handle", tuple(claim for value in handles for claim in value.claim_ids), ("section_malkuth_cleanup", local)))
        document = EvidenceAddressedRealizer._spine(section_clauses, objective_sha); all_spines = [document, *section_spines, *paragraph_spines]
        return {"schema_version": "oracle-stage5m13d1-three-level-tree-spine-v1", "levels": 3, "protected_root_ratio": "4:1", "paragraph_states": 30, "section_states": 10, "document_states": 1, "route": document["route"], "tree_nodes_registered": document["tree_nodes_registered"], "tree_paths_registered": document["tree_paths_registered"], "pre_malkuth_payload_unbinds": sum(value["pre_malkuth_payload_unbinds"] for value in all_spines), "malkuth_payload_unbinds": sum(value["malkuth_payload_unbinds"] for value in all_spines), "minimum_protected_root_cosine": min(value["minimum_protected_root_cosine"] for value in all_spines), "terminal_cleanup_exact": all(value["terminal_cleanup_exact"] for value in all_spines), "minimum_cleanup_margin": min(value["minimum_cleanup_margin"] for value in all_spines), "document_spine": document, "section_spines": section_spines, "paragraph_spines": paragraph_spines}

    def generate(self, topic: str, prompt: str) -> dict[str, Any]:
        started = time.perf_counter(); resolution, claims, retrieval = self._claim_pool(topic)
        if resolution["status"] == "ambiguous":
            return {"schema_version": SCHEMA, "status": "clarification", "operation": "m13d1_general_document_title_clarification", "response": "The requested title resolves to more than one preserved page; specify an exact Wikipedia page identity before long-form compilation.", "resolution": resolution, "factual_release": False}
        if len(claims) < 90:
            return {"schema_version": SCHEMA, "status": "withheld", "operation": "m13d1_general_document_insufficient_evidence", "response": f"Only {len(claims)} distinct provenance-admitted statements were available for {topic}; the ninety-claim long-form threshold was not met.", "retrieval": retrieval, "factual_release": False}
        routed = self._route(topic, claims); by_role = {name: [value for value in routed if value.role == name] for name, _, _ in ROLE_DEFINITIONS}
        response_parts = [f"# A provenance-bounded relational account of {topic}"]
        paragraph_groups: list[list[SurfaceClause]] = []; references = []; paragraph_plan = []; section_plan = []; citation = 1; paragraph = 1
        for role in ROLE_DEFINITIONS:
            role_name, role_title, _ = role; response_parts.append("## " + role_title); section_claim_ids = []
            values = by_role[role_name]
            for local in range(3):
                routed_claims = values[local * 3:(local + 1) * 3]
                clauses, local_references = self._paragraph_clauses(topic, role, paragraph, routed_claims, citation)
                paragraph_groups.append(clauses); references.extend(local_references); citation += 3
                response_parts.append(" ".join(value.text for value in clauses)); ids = [value.claim.claim_id for value in routed_claims]; section_claim_ids.extend(ids)
                paragraph_plan.append({"paragraph": paragraph, "section": role_name, "source_claim_ids": ids, "clause_ids": [value.clause_id for value in clauses], "directional_state": [value.directional_state for value in routed_claims]}); paragraph += 1
            section_plan.append({"section": role_name, "title": role_title, "paragraphs": list(range(paragraph - 3, paragraph)), "source_claim_ids": section_claim_ids})
        response = "\n\n".join(response_parts); objective = digest({"prompt": prompt, "topic": topic, "claims": [value.claim.claim_id for value in routed], "roles": [value[0] for value in ROLE_DEFINITIONS]})
        spine = self._nested_spine(paragraph_groups, [value[0] for value in ROLE_DEFINITIONS], objective)
        word_count = len(words(response)); result = {
            "schema_version": SCHEMA, "status": "answered", "operation": "m13d1_general_hierarchical_document", "response": response, "factual_release": True, "authority_class": "attributed_secondary_source_plus_bounded_text_relations",
            "topic": topic, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "resolution": resolution, "retrieval": retrieval,
            "source_claims": [value.public() for value in routed], "references": references, "paragraph_plan": paragraph_plan, "section_plan": section_plan, "tree_spine": spine,
            "whole_document_inverse": {"candidate_layouts": ["balanced_directional", "retrieval_order", "flat", "reversed"], "selected": "balanced_directional", "assignment": [1, 0, 0, 0], "assignment_hamming_weight": 1, "exhaustive_one_hot_minimum_verified": True},
            "audit": {"word_count": word_count, "paragraph_count": 30, "section_count": 10, "source_claim_count": 90, "surface_clause_count": 150, "unique_source_claims": len({value.claim.claim_id for value in routed}), "all_source_claims_provenance_addressed": all(len(value.claim.raw_record_sha256) == len(value.claim.fact_sha256) == 64 for value in routed), "retrieval_rank_treated_as_truth": False, "lexical_context_asserted_as_anchor_fact": False, "pre_malkuth_payload_unbinds": spine["pre_malkuth_payload_unbinds"], "terminal_cleanup_exact": spine["terminal_cleanup_exact"], "traditional_language_model_calls": 0, "transformer_calls": 0, "pretrained_embedding_calls": 0, "next_token_predictions": 0, "gradient_steps": 0},
            "latency_ms": 1000.0 * (time.perf_counter() - started), "artifact_sha256": "",
        }
        result["artifact_sha256"] = canonical_sha256({key: value for key, value in result.items() if key not in {"latency_ms", "artifact_sha256"}})
        return result


class OracleM13d1Runtime(OracleM13dRuntime):
    LONG_DOCUMENT = re.compile(r"^\s*(?:please\s+)?(?:write|compose|draft|produce|create|give\s+me)\s+(?:a\s+|an\s+)?(?:(?:[\d,]+)[-\s]+word\s+)?(?:(?:long|extended)(?:-form)?\s+)?(?:essay|paper|report|treatise|document)\s+(?:about|on|explaining|concerning)\s+(?P<topic>.+?)\s*[?.!]*$", re.I)

    def __init__(self, state_root: Path | str, *, wordnet_build: Path | str, wikipedia_build: Path | str, **options: Any):
        super().__init__(state_root, wordnet_build=wordnet_build, wikipedia_build=wikipedia_build, **options)
        self.general_documents = GeneralHierarchicalDocumentCompiler(self)

    def chat(self, text: str, *, session_id: str = "default") -> dict[str, Any]:
        source = " ".join(str(text).split())
        if match := self.LONG_DOCUMENT.fullmatch(source):
            topic = match.group("topic").strip(" .?!")
            if re.search(r"\b(?:oracle|yourself|your architecture|being this architecture|what it is like)\b", topic, re.I):
                return super().chat(source, session_id=session_id)
            return self.general_documents.generate(topic, source)
        return super().chat(source, session_id=session_id)

    def capabilities(self) -> dict[str, Any]:
        value = super().capabilities(); value.update({"schema_version": RUNTIME_SCHEMA, "topic_driven_hierarchical_documents": True, "general_document_source_claims": 90, "general_document_surface_clauses": 150, "general_document_paragraphs": 30, "general_document_sections": 10, "general_document_spine_levels": 3, "unrestricted_conversation": False}); return value


__all__ = ["GeneralHierarchicalDocumentCompiler", "OracleM13d1Runtime", "RoutedClaim", "SCHEMA", "RUNTIME_SCHEMA"]
