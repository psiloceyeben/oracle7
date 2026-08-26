#!/usr/bin/env python3
"""M13d2: require query-anchor evidence before contextual long-form release."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from stage5m13d1e_prefix_ordinal_document import OracleM13d1eRuntime, PrefixOrdinalGeneralDocumentCompiler


RUNTIME_SCHEMA = "oracle-stage5m13d2-anchored-general-document-runtime-v1"


class AnchoredGeneralDocumentCompiler(PrefixOrdinalGeneralDocumentCompiler):
    def _claim_pool(self, topic: str, limit: int = 90):
        resolution, claims, metadata = super()._claim_pool(topic, limit=limit)
        if resolution.get("status") == "unresolved" and metadata.get("conjunctive_query_claims", 0) == 0:
            discarded = int(metadata.get("lexical_context_claims", 0))
            metadata = {
                **metadata,
                "status": "insufficient",
                "unique_claims": 0,
                "lexical_context_claims": 0,
                "discarded_unanchored_context_claims": discarded,
                "query_anchor_required": True,
                "query_anchor_present": False,
                "context_asserted_as_anchor_fact": False,
            }
            return resolution, [], metadata
        metadata = {**metadata, "query_anchor_required": resolution.get("status") == "unresolved", "query_anchor_present": bool(metadata.get("conjunctive_query_claims", 0) or metadata.get("exact_anchor_claims", 0)), "discarded_unanchored_context_claims": 0}
        return resolution, claims, metadata


class OracleM13d2Runtime(OracleM13d1eRuntime):
    def __init__(self, state_root: Path | str, *, wordnet_build: Path | str, wikipedia_build: Path | str, **options: Any):
        super().__init__(state_root, wordnet_build=wordnet_build, wikipedia_build=wikipedia_build, **options)
        self.general_documents = AnchoredGeneralDocumentCompiler(self)

    def capabilities(self) -> dict[str, Any]:
        value = super().capabilities(); value.update({"schema_version": RUNTIME_SCHEMA, "unresolved_general_document_requires_query_anchor": True, "unanchored_context_release": False}); return value


__all__ = ["AnchoredGeneralDocumentCompiler", "OracleM13d2Runtime", "RUNTIME_SCHEMA"]
