#!/usr/bin/env python3
"""M13d1b: surface-varied successor over unchanged M13d1 claim geometry."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from oracle_relational_v3.stage5m3a_evidence_addressed_realizer import SurfaceClause
from stage5m13d1_general_hierarchical_document import (
    GeneralHierarchicalDocumentCompiler,
    OracleM13d1Runtime,
    ROLE_DEFINITIONS,
    RoutedClaim,
    words,
)


RUNTIME_SCHEMA = "oracle-stage5m13d1b-surface-varied-runtime-v1"


class SurfaceVariedGeneralDocumentCompiler(GeneralHierarchicalDocumentCompiler):
    @staticmethod
    def _paragraph_clauses(topic: str, role: tuple[str, str, tuple[str, ...]], paragraph_index: int, claims: Sequence[RoutedClaim], citation_start: int) -> tuple[list[SurfaceClause], list[dict[str, Any]]]:
        role_name, role_title, _ = role
        shared = sorted(set.intersection(*(set(words(value.claim.title + " " + value.claim.fact)) for value in claims))) if claims else []
        query_terms = sorted({term for value in claims for term in value.query_shared_terms})
        relation_terms = (query_terms or shared)[:4]; relation_surface = ", ".join(relation_terms) if relation_terms else "the query-conditioned directional scores"
        intros = (
            f"Paragraph {paragraph_index} routes three sources through {role_title.casefold()} for {topic}. Retrieval relevance is not factual authority.",
            f"For {topic}, paragraph {paragraph_index} assigns three records to {role_title.casefold()}. The route organizes surfaces without upgrading their authority.",
            f"The {role_title.casefold()} pass places three {topic} records in paragraph {paragraph_index}. No directional score converts a candidate into an anchor fact.",
        )
        clauses = [SurfaceClause(f"p{paragraph_index:02d}_objective", intros[(paragraph_index - 1) % 3], "bounded_document_inference", tuple(value.claim.claim_id for value in claims), ("balanced_ten_direction_assignment", role_name, str(paragraph_index)))]
        templates = (
            "[{citation}] As a {selection}, preserved page {title} states: {fact}.",
            "[{citation}] Attributed evidence from {title}, retrieved as a {selection}, reads: {fact}.",
            "[{citation}] The {selection} addressed to {title} contributes: {fact}.",
            "[{citation}] In the preserved snapshot, {title} reports this {selection}: {fact}.",
            "[{citation}] Source page {title} supplies the following {selection}: {fact}.",
            "[{citation}] Bound to page {title}, this {selection} says: {fact}.",
        )
        references = []
        for offset, routed in enumerate(claims):
            claim = routed.claim; number = citation_start + offset; citation = f"P{number:03d}"
            selection = {"exact_article": "exact-anchor statement", "fts_candidate": "conjunctive-query statement", "fts_lexical_context_candidate": "lexical-context candidate"}.get(claim.selection, claim.selection.replace("_", "-"))
            text = templates[(number - 1) % len(templates)].format(citation=citation, selection=selection, title=claim.title, fact=claim.fact.rstrip(". "))
            clauses.append(SurfaceClause(f"p{paragraph_index:02d}_source_{offset + 1}", text, "attributed_secondary_source", (claim.claim_id,), (claim.selection, claim.claim_id, claim.raw_record_sha256, claim.fact_sha256), inline_citations=(citation,)))
            references.append({"citation_id": citation, "claim_id": claim.claim_id, "page_id": claim.page_id, "title": claim.title, "source_url": claim.canonical_url, "raw_record_sha256": claim.raw_record_sha256, "abstract_sha256": claim.abstract_sha256, "fact_sha256": claim.fact_sha256, "sentence_ordinal": claim.sentence_ordinal, "selection": claim.selection, "bm25_rank": claim.rank})
        boundaries = (
            f"At paragraph {paragraph_index}, shared surface {relation_surface} sets grouping only, not causation or truth about {topic}; each statement stays bound to its cited page.",
            f"This paragraph's overlap marker is {relation_surface}. It marks textual organization, not causation or truth about {topic}, and supplies no evidence of consensus, completeness, or freshness.",
            f"The local geometry turns on {relation_surface}, not causation or truth about {topic}; it releases no world relation beyond the cited records.",
        )
        clauses.append(SurfaceClause(f"p{paragraph_index:02d}_boundary", boundaries[(paragraph_index - 1) % 3], "epistemic_boundary", tuple(value.claim.claim_id for value in claims), ("surface_relation_not_world_relation", role_name, *relation_terms)))
        return clauses, references


class OracleM13d1bRuntime(OracleM13d1Runtime):
    def __init__(self, state_root: Path | str, *, wordnet_build: Path | str, wikipedia_build: Path | str, **options: Any):
        super().__init__(state_root, wordnet_build=wordnet_build, wikipedia_build=wikipedia_build, **options)
        self.general_documents = SurfaceVariedGeneralDocumentCompiler(self)

    def capabilities(self) -> dict[str, Any]:
        value = super().capabilities(); value.update({"schema_version": RUNTIME_SCHEMA, "citation_addressed_surface_variation": True, "general_document_surface_template_families": 6}); return value


__all__ = ["OracleM13d1bRuntime", "SurfaceVariedGeneralDocumentCompiler", "RUNTIME_SCHEMA"]
