#!/usr/bin/env python3
"""M13d1c: make every meta-clause ordinal-bearing and non-repeating."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

from oracle_relational_v3.stage5m3a_evidence_addressed_realizer import SurfaceClause
from stage5m13d1_general_hierarchical_document import ROLE_DEFINITIONS, RoutedClaim, words
from stage5m13d1b_surface_varied_document import OracleM13d1bRuntime, SurfaceVariedGeneralDocumentCompiler


RUNTIME_SCHEMA = "oracle-stage5m13d1c-ordinal-surface-runtime-v1"


class OrdinalSurfaceGeneralDocumentCompiler(SurfaceVariedGeneralDocumentCompiler):
    @staticmethod
    def _paragraph_clauses(topic: str, role: tuple[str, str, tuple[str, ...]], paragraph_index: int, claims: Sequence[RoutedClaim], citation_start: int) -> tuple[list[SurfaceClause], list[dict[str, Any]]]:
        clauses, references = SurfaceVariedGeneralDocumentCompiler._paragraph_clauses(topic, role, paragraph_index, claims, citation_start)
        _role_name, role_title, _ = role
        shared = sorted(set.intersection(*(set(words(value.claim.title + " " + value.claim.fact)) for value in claims))) if claims else []
        query_terms = sorted({term for value in claims for term in value.query_shared_terms})
        relation_terms = (query_terms or shared)[:4]; relation_surface = ", ".join(relation_terms) if relation_terms else "the query-conditioned directional scores"
        intros = (
            f"Paragraph {paragraph_index} routes three sources through {role_title.casefold()} for {topic}, while keeping retrieval relevance separate from factual authority.",
            f"For {topic}, paragraph {paragraph_index} assigns three records to {role_title.casefold()} without upgrading the authority of their source surfaces.",
            f"The {role_title.casefold()} pass places three {topic} records in paragraph {paragraph_index}, but no directional score converts a candidate into an anchor fact.",
        )
        boundaries = (
            f"At paragraph {paragraph_index}, shared surface {relation_surface} sets grouping only, not causation or truth about {topic}, and each statement stays bound to its cited page.",
            f"Paragraph {paragraph_index} uses overlap marker {relation_surface} for textual organization, not causation or truth about {topic}, consensus, completeness, or freshness.",
            f"Paragraph {paragraph_index} turns its local geometry on {relation_surface}, not causation or truth about {topic}, and releases no world relation beyond the cited records.",
        )
        clauses[0] = replace(clauses[0], text=intros[(paragraph_index - 1) % 3])
        clauses[-1] = replace(clauses[-1], text=boundaries[(paragraph_index - 1) % 3])
        return clauses, references


class OracleM13d1cRuntime(OracleM13d1bRuntime):
    def __init__(self, state_root: Path | str, *, wordnet_build: Path | str, wikipedia_build: Path | str, **options: Any):
        super().__init__(state_root, wordnet_build=wordnet_build, wikipedia_build=wikipedia_build, **options)
        self.general_documents = OrdinalSurfaceGeneralDocumentCompiler(self)

    def capabilities(self) -> dict[str, Any]:
        value = super().capabilities(); value.update({"schema_version": RUNTIME_SCHEMA, "ordinal_bearing_meta_clauses": True}); return value


__all__ = ["OracleM13d1cRuntime", "OrdinalSurfaceGeneralDocumentCompiler", "RUNTIME_SCHEMA"]
