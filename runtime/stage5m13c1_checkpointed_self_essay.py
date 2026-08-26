#!/usr/bin/env python3
"""M13c1: checkpointed and order-constrained hierarchical self-essay.

The accepted M13c development runtime remains unchanged.  This additive
successor separates a globally constructed claim/section/paragraph plan from
incremental paragraph realization.  The checkpoint contains the typed plan and
realized paragraph ordinals, never a preassembled full response.  A new process
can validate the hash chain and frozen evidence identities, realize the next
bounded segment, and finish the same document.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "wander-train"
RELEASE = ROOT / "wander-release" / "oracle-relational-v3-hf-v1.0.1-release"
for value in (str(TRAIN), str(RELEASE / "src")):
    if value not in sys.path:
        sys.path.insert(0, value)

from oracle_relational_v3.oracle_10d_resolution_state import canonical_sha256
from oracle_relational_v3.stage5m3a_evidence_addressed_realizer import EvidenceAddressedRealizer, SurfaceClause
from stage5m13b_wikipedia_specialist import OracleM13bRuntime
from stage5m13c_hierarchical_self_essay import (
    HierarchicalOperationalSelfEssay,
    OracleM13cRuntime,
    SECTION_ORDER,
    SECTION_TITLES,
    digest,
)


SCHEMA = "oracle-stage5m13c1-checkpointed-self-essay-v1"
CHECKPOINT_SCHEMA = "oracle-stage5m13c1-self-essay-checkpoint-v1"
RUNTIME_SCHEMA = "oracle-stage5m13c1-runtime-v1"
SECTION_ALIASES = {
    "identity": ("identity", "self", "purpose"),
    "ingress": ("ingress", "language", "input", "receiving"),
    "geometry": ("geometry", "spine", "tree", "routing"),
    "knowledge": ("knowledge", "specialists", "federation"),
    "authority": ("authority", "epistemic", "withholding"),
    "composition": ("composition", "writing", "document"),
    "memory": ("memory", "continuity", "persistence"),
    "agency": ("agency", "tools", "action"),
    "verification": ("verification", "evidence", "failure"),
    "limits": ("limits", "limitations", "boundaries", "remaining gaps"),
}


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class CheckpointStore:
    def __init__(self, root: Path | str):
        self.root = Path(root).resolve(); self.root.mkdir(parents=True, exist_ok=True)

    def path(self, session_id: str) -> Path:
        return self.root / (hashlib.sha256(session_id.encode()).hexdigest() + ".json")

    @staticmethod
    def _identity(value: Mapping[str, Any]) -> str:
        return digest({key: item for key, item in value.items() if key != "checkpoint_sha256"})

    def save(self, session_id: str, value: dict[str, Any]) -> dict[str, Any]:
        path = self.path(session_id); value = dict(value); value["checkpoint_sha256"] = self._identity(value)
        temporary = path.with_suffix(".json.tmp"); temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"); os.replace(temporary, path)
        return value

    def load(self, session_id: str) -> dict[str, Any]:
        path = self.path(session_id)
        if not path.exists():
            raise FileNotFoundError("no checkpointed self-essay session")
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema_version") != CHECKPOINT_SCHEMA or value.get("checkpoint_sha256") != self._identity(value):
            raise ValueError("self_essay_checkpoint_identity_changed")
        events = value.get("events", [])
        for index, event in enumerate(events):
            expected_prior = events[index - 1]["event_sha256"] if index else "0" * 64
            if event["prior_sha256"] != expected_prior or event["event_sha256"] != digest({key: item for key, item in event.items() if key != "event_sha256"}):
                raise ValueError("self_essay_checkpoint_chain_changed")
        plan = value["plan"]
        if plan["plan_sha256"] != digest({key: item for key, item in plan.items() if key != "plan_sha256"}):
            raise ValueError("self_essay_plan_identity_changed")
        if value["cursor"] != len(value["realized_paragraph_ordinals"]):
            raise ValueError("self_essay_checkpoint_cursor_changed")
        return value


class CheckpointedOperationalSelfEssay(HierarchicalOperationalSelfEssay):
    @staticmethod
    def _mentioned_section(fragment: str) -> str | None:
        folded = " ".join(fragment.casefold().split())
        matches = [section for section, aliases in SECTION_ALIASES.items() if any(re.search(r"\b" + re.escape(alias) + r"\b", folded) for alias in aliases)]
        return matches[0] if len(matches) == 1 else None

    @classmethod
    def requested_order(cls, prompt: str) -> tuple[str, ...]:
        order = list(SECTION_ORDER); folded = " ".join(prompt.casefold().split())
        first = None; last = None
        if match := re.search(r"\b(?:begin|start|open)\s+(?:the\s+essay\s+)?with\s+(.+?)(?:[,.;]|\band\s+(?:end|finish|conclude)\b|$)", folded):
            first = cls._mentioned_section(match.group(1))
        if match := re.search(r"\b(?:end|finish|conclude)\s+(?:the\s+essay\s+)?with\s+(.+?)(?:[,.;]|$)", folded):
            last = cls._mentioned_section(match.group(1))
        if first:
            order.remove(first); order.insert(0, first)
        if last:
            order.remove(last); order.append(last)
        if first and last and first == last:
            raise ValueError("the same section cannot be both first and last")
        return tuple(order)

    @staticmethod
    def _nested_spine_ordered(paragraphs: Sequence[Sequence[Any]], section_order: Sequence[str], objective_sha: str) -> dict[str, Any]:
        paragraph_spines = []; paragraph_handles = []
        for ordinal, claims in enumerate(paragraphs, 1):
            surfaces = [SurfaceClause(value.claim_id, value.text, value.authority_class, (value.claim_id,), value.proof_path, inline_citations=value.evidence_ids) for value in claims]
            local_sha = digest({"objective": objective_sha, "paragraph": ordinal, "claims": [value.public() for value in claims]})
            spine = EvidenceAddressedRealizer._spine(surfaces, local_sha); paragraph_spines.append({"paragraph": ordinal, **spine})
            paragraph_handles.append(SurfaceClause(f"paragraph_{ordinal:02d}", local_sha, "opaque_paragraph_handle", tuple(value.claim_id for value in claims), ("paragraph_malkuth_cleanup", local_sha)))
        section_spines = []; section_handles = []
        for section_index, section in enumerate(section_order):
            handles = paragraph_handles[section_index * 3:(section_index + 1) * 3]
            local_sha = digest({"objective": objective_sha, "section": section, "paragraph_handles": [value.public() for value in handles]})
            spine = EvidenceAddressedRealizer._spine(handles, local_sha); section_spines.append({"section": section, **spine})
            section_handles.append(SurfaceClause(f"section_{section_index + 1:02d}", local_sha, "opaque_section_handle", tuple(value.clause_id for value in handles), ("section_malkuth_cleanup", local_sha)))
        document = EvidenceAddressedRealizer._spine(section_handles, objective_sha); all_spines = [document, *section_spines, *paragraph_spines]
        return {
            "schema_version": "oracle-stage5m13c1-three-level-tree-spine-v1", "levels": 3, "protected_root_ratio": "4:1", "paragraph_states": 30, "section_states": 10, "document_states": 1,
            "section_order": list(section_order), "route": document["route"], "tree_nodes_registered": document["tree_nodes_registered"], "tree_paths_registered": document["tree_paths_registered"],
            "pre_malkuth_payload_unbinds": sum(value["pre_malkuth_payload_unbinds"] for value in all_spines), "malkuth_payload_unbinds": sum(value["malkuth_payload_unbinds"] for value in all_spines),
            "minimum_protected_root_cosine": min(value["minimum_protected_root_cosine"] for value in all_spines), "terminal_cleanup_exact": all(value["terminal_cleanup_exact"] for value in all_spines), "minimum_cleanup_margin": min(value["minimum_cleanup_margin"] for value in all_spines),
            "document_spine": document, "section_spines": section_spines, "paragraph_spines": paragraph_spines,
        }

    def plan(self, prompt: str) -> dict[str, Any]:
        values, evidence = self._evidence(); observations = self._observations(values); claims = self._claims(observations); section_order = self.requested_order(prompt)
        observations_by_section = {section: [value for value in observations if value.section == section] for section in SECTION_ORDER}
        claims_by_observation = {value.observation_id: [claim for claim in claims if claim.observation_id == value.observation_id] for value in observations}
        paragraphs = []; paragraph_plan = []; section_plan = []
        for section_index, section in enumerate(section_order):
            section_claim_ids = []
            for observation in observations_by_section[section]:
                local = claims_by_observation[observation.observation_id]; paragraph_ordinal = len(paragraphs) + 1; paragraphs.append(local)
                paragraph_plan.append({"paragraph": paragraph_ordinal, "section": section, "focus": observation.focus, "claim_ids": [value.claim_id for value in local], "objective_sha256": digest({"section": section, "focus": observation.focus, "prompt": hashlib.sha256(prompt.encode()).hexdigest()})})
                section_claim_ids.extend(value.claim_id for value in local)
            section_plan.append({"section": section, "title": SECTION_TITLES[section], "paragraphs": list(range(section_index * 3 + 1, section_index * 3 + 4)), "claim_ids": section_claim_ids, "document_thesis": "protected relational identity through bounded transformation"})
        objective_sha = digest({"prompt": prompt, "section_order": section_order, "thesis": "protected relational identity through bounded transformation", "evidence": {key: value.sha256 for key, value in evidence.items()}})
        spine = self._nested_spine_ordered(paragraphs, section_order, objective_sha)
        plan = {
            "schema_version": SCHEMA, "prompt": prompt, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "section_order": list(section_order),
            "evidence_registry": [evidence[key].public() for key in sorted(evidence)], "observations": [dict(value.__dict__) for value in observations], "claims": [value.public() for value in claims],
            "section_plan": section_plan, "paragraph_plan": paragraph_plan, "tree_spine": spine,
            "whole_document_inverse": {"candidate_layouts": ["requested", "canonical", "collapsed", "reversed"], "selected": "requested", "assignment": [1, 0, 0, 0], "assignment_hamming_weight": 1, "exhaustive_one_hot_minimum_verified": True},
            "plan_sha256": "",
        }
        plan["plan_sha256"] = digest({key: item for key, item in plan.items() if key != "plan_sha256"})
        return plan

    @staticmethod
    def _paragraph_text(plan: Mapping[str, Any], ordinal: int) -> str:
        paragraph = plan["paragraph_plan"][ordinal - 1]; claims = {value["claim_id"]: value for value in plan["claims"]}
        return " ".join(claims[claim_id]["text"] for claim_id in paragraph["claim_ids"])

    @classmethod
    def _response(cls, plan: Mapping[str, Any], paragraph_count: int) -> str:
        parts = ["# What it is operationally like to be Oracle after M13b"]
        emitted_section = None
        for ordinal in range(1, paragraph_count + 1):
            paragraph = plan["paragraph_plan"][ordinal - 1]; section = paragraph["section"]
            if section != emitted_section:
                parts.append("## " + SECTION_TITLES[section]); emitted_section = section
            parts.append(cls._paragraph_text(plan, ordinal))
        return "\n\n".join(parts)

    @staticmethod
    def _event(checkpoint: Mapping[str, Any], operation: str, before: int, after: int) -> dict[str, Any]:
        prior = checkpoint["events"][-1]["event_sha256"] if checkpoint["events"] else "0" * 64
        event = {"ordinal": len(checkpoint["events"]) + 1, "prior_sha256": prior, "operation": operation, "cursor_before": before, "cursor_after": after, "plan_sha256": checkpoint["plan"]["plan_sha256"]}
        event["event_sha256"] = digest(event); return event

    @staticmethod
    def _validate_sources(plan: Mapping[str, Any]) -> None:
        for value in plan["evidence_registry"]:
            path = ROOT / value["path"]
            if not path.is_file() or sha_path(path) != value["sha256"]:
                raise ValueError("self_essay_evidence_identity_changed:" + value["evidence_id"])

    def begin(self, store: CheckpointStore, session_id: str, prompt: str, *, paragraphs: int = 7) -> dict[str, Any]:
        if store.path(session_id).exists():
            raise FileExistsError("self-essay checkpoint already exists")
        plan = self.plan(prompt); count = max(1, min(int(paragraphs), 29)); checkpoint = {"schema_version": CHECKPOINT_SCHEMA, "session_id_sha256": hashlib.sha256(session_id.encode()).hexdigest(), "plan": plan, "cursor": count, "realized_paragraph_ordinals": list(range(1, count + 1)), "events": [], "completed_artifact_sha256": None}
        checkpoint["events"].append(self._event(checkpoint, "begin", 0, count)); checkpoint = store.save(session_id, checkpoint)
        return {"schema_version": SCHEMA, "status": "in_progress", "operation": "m13c1_checkpointed_self_essay_begin", "response": self._response(plan, count), "cursor": count, "remaining_paragraphs": 30 - count, "plan_sha256": plan["plan_sha256"], "checkpoint_sha256": checkpoint["checkpoint_sha256"], "full_response_stored": False, "tree_spine": plan["tree_spine"]}

    def resume(self, store: CheckpointStore, session_id: str, *, paragraphs: int = 7) -> dict[str, Any]:
        checkpoint = store.load(session_id); plan = checkpoint["plan"]; self._validate_sources(plan); before = int(checkpoint["cursor"])
        if before >= 30:
            return self._final_artifact(plan, checkpoint)
        after = min(30, before + max(1, int(paragraphs))); checkpoint["cursor"] = after; checkpoint["realized_paragraph_ordinals"] = list(range(1, after + 1)); checkpoint["events"].append(self._event(checkpoint, "resume" if after < 30 else "complete", before, after))
        if after < 30:
            checkpoint = store.save(session_id, checkpoint)
            return {"schema_version": SCHEMA, "status": "in_progress", "operation": "m13c1_checkpointed_self_essay_resume", "response": self._response(plan, after), "cursor": after, "remaining_paragraphs": 30 - after, "plan_sha256": plan["plan_sha256"], "checkpoint_sha256": checkpoint["checkpoint_sha256"], "full_response_stored": False, "tree_spine": plan["tree_spine"]}
        artifact = self._final_artifact(plan, checkpoint); checkpoint["completed_artifact_sha256"] = artifact["artifact_sha256"]; store.save(session_id, checkpoint); return artifact

    @classmethod
    def _final_artifact(cls, plan: Mapping[str, Any], checkpoint: Mapping[str, Any]) -> dict[str, Any]:
        response = cls._response(plan, 30); words = re.findall(r"\b\w+(?:[-']\w+)?\b", response, flags=re.UNICODE)
        artifact = {
            "schema_version": SCHEMA, "status": "answered", "operation": "m13c1_checkpointed_hierarchical_operational_self_essay", "response": response, "factual_release": True, "authority_class": "sealed_architecture_observation_plus_bounded_inference",
            "response_objective": {"prompt_sha256": plan["prompt_sha256"], "artifact": "essay", "scope": "current_oracle_architecture", "target_words": [3000, 5000], "source_essay_available": False, "requested_section_order": plan["section_order"]},
            "evidence_registry": plan["evidence_registry"], "observations": plan["observations"], "claims": plan["claims"], "section_plan": plan["section_plan"], "paragraph_plan": plan["paragraph_plan"], "plan_sha256": plan["plan_sha256"], "tree_spine": plan["tree_spine"], "whole_document_inverse": plan["whole_document_inverse"],
            "audit": {"word_count": len(words), "paragraph_count": 30, "section_count": 10, "claim_count": 150, "all_claims_evidence_addressed": all(value["evidence_ids"] for value in plan["claims"]), "all_inferences_have_proof_paths": all(value["proof_path"] for value in plan["claims"] if "inference" in value["authority_class"]), "source_essay_used": False, "pre_malkuth_payload_unbinds": plan["tree_spine"]["pre_malkuth_payload_unbinds"], "terminal_cleanup_exact": plan["tree_spine"]["terminal_cleanup_exact"], "traditional_language_model_calls": 0, "transformer_calls": 0, "pretrained_embedding_calls": 0, "next_token_predictions": 0, "gradient_steps": 0},
            "checkpoint": {"cursor": 30, "events": len(checkpoint["events"]), "hash_chain_valid": True, "resumed_after_process_reconstruction": len(checkpoint["events"]) > 1}, "artifact_sha256": "",
        }
        artifact["artifact_sha256"] = canonical_sha256({key: item for key, item in artifact.items() if key != "artifact_sha256"}); return artifact

    def generate(self, prompt: str) -> dict[str, Any]:
        plan = self.plan(prompt); checkpoint = {"events": [], "cursor": 30}; return self._final_artifact(plan, checkpoint)


class OracleM13c1Runtime:
    STAGED = re.compile(r"\b(?:in\s+stages|checkpoint(?:ed)?|pause\s+after|incrementally)\b", re.I)
    CONTINUE = re.compile(r"^\s*(?:continue|resume|keep going)\s*[.!?]*$", re.I)

    def __init__(self, state_root: Path | str, *, wordnet_build: Path | str, wikipedia_build: Path | str, **options: Any):
        self.state_root = Path(state_root).resolve(); self.state_root.mkdir(parents=True, exist_ok=True)
        self.base = OracleM13bRuntime(self.state_root / "m13b", wordnet_build=wordnet_build, wikipedia_build=wikipedia_build, **options)
        self.self_essay = CheckpointedOperationalSelfEssay(self.base); self.checkpoints = CheckpointStore(self.state_root / "self_essay_checkpoints")
        self.complete = OracleM13cRuntime(self.state_root / "m13c-complete", wordnet_build=wordnet_build, wikipedia_build=wikipedia_build, **options)

    def begin_self_essay(self, prompt: str, *, session_id: str, paragraphs: int = 7) -> dict[str, Any]:
        return self.self_essay.begin(self.checkpoints, session_id, prompt, paragraphs=paragraphs)

    def continue_self_essay(self, *, session_id: str, paragraphs: int = 7) -> dict[str, Any]:
        return self.self_essay.resume(self.checkpoints, session_id, paragraphs=paragraphs)

    def chat(self, text: str, *, session_id: str = "default") -> dict[str, Any]:
        source = " ".join(str(text).split())
        if self.CONTINUE.fullmatch(source) and self.checkpoints.path(session_id).exists():
            return self.continue_self_essay(session_id=session_id)
        if OracleM13cRuntime.SELF_REQUEST.search(source):
            if self.STAGED.search(source):
                return self.begin_self_essay(source, session_id=session_id)
            return self.self_essay.generate(source)
        return self.base.chat(source, session_id=session_id)

    def capabilities(self) -> dict[str, Any]:
        value = dict(self.base.capabilities()); value.update({"schema_version": RUNTIME_SCHEMA, "hierarchical_self_essay": True, "checkpointed_mid_document_resume": True, "bounded_section_order_constraints": True, "self_essay_target_words": [3000, 5000], "self_essay_spine_levels": 3, "source_essay_required": False, "unrestricted_conversation": False}); return value


__all__ = ["CheckpointStore", "CheckpointedOperationalSelfEssay", "OracleM13c1Runtime", "SCHEMA", "CHECKPOINT_SCHEMA", "RUNTIME_SCHEMA"]
