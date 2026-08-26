#!/usr/bin/env python3
"""M13d1e: move the remaining meta-clause ordinal into the start prefix."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

from oracle_relational_v3.stage5m3a_evidence_addressed_realizer import SurfaceClause
from stage5m13d1_general_hierarchical_document import RoutedClaim
from stage5m13d1d_interior_ordinal_document import InteriorOrdinalGeneralDocumentCompiler, OracleM13d1dRuntime


RUNTIME_SCHEMA = "oracle-stage5m13d1e-prefix-ordinal-runtime-v1"


class PrefixOrdinalGeneralDocumentCompiler(InteriorOrdinalGeneralDocumentCompiler):
    @staticmethod
    def _paragraph_clauses(topic: str, role: tuple[str, str, tuple[str, ...]], paragraph_index: int, claims: Sequence[RoutedClaim], citation_start: int) -> tuple[list[SurfaceClause], list[dict[str, Any]]]:
        clauses, references = InteriorOrdinalGeneralDocumentCompiler._paragraph_clauses(topic, role, paragraph_index, claims, citation_start)
        if (paragraph_index - 1) % 3 == 1:
            _role_name, role_title, _ = role
            clauses[0] = replace(clauses[0], text=f"For paragraph {paragraph_index} on {topic}, assignment {paragraph_index} binds three records to {role_title.casefold()} and leaves their source authority unchanged.")
        return clauses, references


class OracleM13d1eRuntime(OracleM13d1dRuntime):
    def __init__(self, state_root: Path | str, *, wordnet_build: Path | str, wikipedia_build: Path | str, **options: Any):
        super().__init__(state_root, wordnet_build=wordnet_build, wikipedia_build=wikipedia_build, **options)
        self.general_documents = PrefixOrdinalGeneralDocumentCompiler(self)

    def capabilities(self) -> dict[str, Any]:
        value = super().capabilities(); value.update({"schema_version": RUNTIME_SCHEMA, "prefix_ordinal_surface_identity": True}); return value


__all__ = ["OracleM13d1eRuntime", "PrefixOrdinalGeneralDocumentCompiler", "RUNTIME_SCHEMA"]
