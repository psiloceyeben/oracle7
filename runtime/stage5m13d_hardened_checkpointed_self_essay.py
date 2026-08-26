#!/usr/bin/env python3
"""M13d: semantic checkpoint binding above the accepted M13c1 runtime."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from stage5m13c_hierarchical_self_essay import SECTION_ORDER
from stage5m13c1_checkpointed_self_essay import (
    CheckpointStore,
    CheckpointedOperationalSelfEssay,
    OracleM13c1Runtime,
)


RUNTIME_SCHEMA = "oracle-stage5m13d-hardened-checkpoint-runtime-v1"


class SemanticallyBoundCheckpointStore(CheckpointStore):
    """Validate meaning-bearing invariants in addition to content hashes."""

    def load(self, session_id: str) -> dict[str, Any]:
        value = super().load(session_id)
        if value.get("session_id_sha256") != hashlib.sha256(session_id.encode()).hexdigest():
            raise ValueError("self_essay_checkpoint_session_binding_changed")
        cursor = value.get("cursor")
        if not isinstance(cursor, int) or isinstance(cursor, bool) or not 1 <= cursor <= 30:
            raise ValueError("self_essay_checkpoint_cursor_domain_changed")
        if value.get("realized_paragraph_ordinals") != list(range(1, cursor + 1)):
            raise ValueError("self_essay_checkpoint_realized_ordinal_sequence_changed")

        plan = value["plan"]
        order = plan.get("section_order")
        if not isinstance(order, list) or len(order) != 10 or set(order) != set(SECTION_ORDER):
            raise ValueError("self_essay_plan_section_permutation_changed")
        if len(plan.get("paragraph_plan", [])) != 30 or len(plan.get("section_plan", [])) != 10 or len(plan.get("observations", [])) != 30 or len(plan.get("claims", [])) != 150:
            raise ValueError("self_essay_plan_cardinality_changed")
        claim_ids = [item.get("claim_id") for item in plan["claims"]]
        if len(set(claim_ids)) != 150 or any(len(item.get("claim_ids", [])) != 5 for item in plan["paragraph_plan"]):
            raise ValueError("self_essay_plan_claim_partition_changed")
        spine = plan.get("tree_spine", {})
        if spine.get("levels") != 3 or spine.get("paragraph_states") != 30 or spine.get("section_states") != 10 or spine.get("document_states") != 1 or not spine.get("terminal_cleanup_exact") or spine.get("pre_malkuth_payload_unbinds") != 0:
            raise ValueError("self_essay_plan_spine_invariant_changed")

        events = value.get("events")
        if not isinstance(events, list) or not events:
            raise ValueError("self_essay_checkpoint_event_history_changed")
        prior_cursor = 0
        for index, event in enumerate(events):
            if event.get("ordinal") != index + 1:
                raise ValueError("self_essay_checkpoint_event_ordinal_changed")
            if event.get("plan_sha256") != plan["plan_sha256"]:
                raise ValueError("self_essay_checkpoint_event_plan_binding_changed")
            before = event.get("cursor_before"); after = event.get("cursor_after")
            if not isinstance(before, int) or not isinstance(after, int) or before != prior_cursor or not before < after <= 30:
                raise ValueError("self_essay_checkpoint_event_cursor_continuity_changed")
            expected_operation = "begin" if index == 0 else ("complete" if after == 30 else "resume")
            if event.get("operation") != expected_operation:
                raise ValueError("self_essay_checkpoint_event_operation_changed")
            if after == 30 and index != len(events) - 1:
                raise ValueError("self_essay_checkpoint_event_after_completion_changed")
            prior_cursor = after
        if prior_cursor != cursor:
            raise ValueError("self_essay_checkpoint_event_terminal_cursor_changed")

        completed = value.get("completed_artifact_sha256")
        if cursor < 30:
            if completed is not None:
                raise ValueError("self_essay_checkpoint_premature_completion_identity")
        else:
            if not isinstance(completed, str) or re.fullmatch(r"[0-9a-f]{64}", completed) is None:
                raise ValueError("self_essay_checkpoint_completed_artifact_identity_changed")
            expected = CheckpointedOperationalSelfEssay._final_artifact(plan, value)["artifact_sha256"]
            if completed != expected:
                raise ValueError("self_essay_checkpoint_completed_artifact_identity_changed")
        return value

    def save(self, session_id: str, value: dict[str, Any]) -> dict[str, Any]:
        super().save(session_id, value)
        return self.load(session_id)


class OracleM13dRuntime(OracleM13c1Runtime):
    def __init__(self, state_root: Path | str, *, wordnet_build: Path | str, wikipedia_build: Path | str, **options: Any):
        super().__init__(state_root, wordnet_build=wordnet_build, wikipedia_build=wikipedia_build, **options)
        self.checkpoints = SemanticallyBoundCheckpointStore(self.state_root / "self_essay_checkpoints")

    def capabilities(self) -> dict[str, Any]:
        value = super().capabilities()
        value.update({
            "schema_version": RUNTIME_SCHEMA,
            "semantic_checkpoint_binding": True,
            "checkpoint_session_binding": True,
            "checkpoint_cursor_continuity": True,
            "checkpoint_plan_event_binding": True,
            "checkpoint_completion_identity": True,
        })
        return value


__all__ = ["OracleM13dRuntime", "SemanticallyBoundCheckpointStore", "RUNTIME_SCHEMA"]
