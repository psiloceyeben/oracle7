#!/usr/bin/env python3
"""H3 — oracle_release_runtime: the single conversational front door.

One chat(text, session_id) composing, in routing order:
  1. session-relational path: statements/questions about session-introduced
     entities via the sealed M13e4 IR chain (IRPipeline2 over the K7b kernel;
     per-session persistent transcript);
  2. commonsense path: registered ConceptNet question forms (adapter, with
     provenance and explicit withholds);
  3. everything else: the frozen M13d2 anchored-document runtime over the
     M13e5 DBpedia specialist (essays, encyclopedic evidence, definitional,
     reasoning chain, abstention).

Composition only: every imported layer is a sealed/frozen artifact or an
additive successor; nothing is edited. Zero-model throughout.
Classification: development evidence until frozen and panel-run (H5).
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\BenHo\Desktop\ClaudeCode\_m13e0v4\control-install")

from stage5m13e2_construction_kernel_k7b import ConstructionKernelK7b
from stage5m13e4_migration2 import IRPipeline2
from stage5m13e6_realizer2b import Realizer2b
from oracle_release_conceptnet import ConceptNetAdapter
from stage5m13d2_anchored_general_document import OracleM13d2Runtime

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / "fable-content" / "oracle-m-series-2026-08-15"

QUESTION_HEAD = re.compile(r"^(is|are|was|were|does|do|did|will|can|what|who|where|when|why|how|which)\b", re.I)
PROPER_SUBJECT = re.compile(r"^[A-Z][a-z]+ ")
KNOWN_NAME = re.compile(r"\b(Ferra|Doran|Mira)\b")  # dev-session name space; H5 replaces with session registry


class OracleReleaseRuntime:
    def __init__(self, state_root: Path | str = PHASE / "m13e7_front_door_state_v1",
                 wikipedia_build: Path | str = PHASE / "m13e5_dbpedia_build_a_v2",
                 wordnet_build: Path | str = PHASE / "m13a_wordnet_build_a_v4"):
        self.state_root = Path(state_root)
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.kernel = ConstructionKernelK7b(compositional=True)
        self.pipeline = IRPipeline2(self.kernel)
        self.realizer = Realizer2b()
        self.commonsense = ConceptNetAdapter()
        self.documents = OracleM13d2Runtime(self.state_root / "documents",
                                            wordnet_build=wordnet_build,
                                            wikipedia_build=wikipedia_build)
        self.sessions: dict[str, list[str]] = {}

    # ── session-relational path ──────────────────────────────────────────
    def _session_file(self, session_id: str) -> Path:
        return self.state_root / f"session_{session_id}.json"

    def _history(self, session_id: str) -> list[str]:
        if session_id not in self.sessions:
            path = self._session_file(session_id)
            self.sessions[session_id] = json.loads(path.read_text(encoding="utf-8")) \
                if path.exists() else []
        return self.sessions[session_id]

    def _persist(self, session_id: str) -> None:
        self._session_file(session_id).write_text(
            json.dumps(self.sessions[session_id], ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8", newline="\n")

    def _relational_turn(self, text: str, session_id: str) -> dict | None:
        history = self._history(session_id)
        is_question = text.rstrip().endswith("?") or bool(QUESTION_HEAD.match(text.strip()))
        session_relevant = bool(KNOWN_NAME.search(text)) or \
            (history and any(KNOWN_NAME.search(h) for h in history) and is_question is False)
        if is_question:
            if not (history and (KNOWN_NAME.search(text) or "he " in text.lower() or "she " in text.lower())):
                return None
            answer = self.pipeline.answer("\n".join(history + [text]))
            if answer == "none":
                return None
            return {"status": "answered", "path": "session_relational",
                    "response": answer, "provenance": {"kind": "session_world",
                                                       "statements": len(history)}}
        if not session_relevant or not PROPER_SUBJECT.match(text.strip()):
            return None
        program = self.kernel.compile_text(text)
        if program is None:
            return None
        history.append(text.strip())
        self._persist(session_id)
        return {"status": "recorded", "path": "session_relational",
                "response": "Recorded.", "provenance": {"kind": "session_world",
                                                        "statements": len(history)}}

    # ── entry ────────────────────────────────────────────────────────────
    def chat(self, text: str, session_id: str = "default") -> dict:
        started = time.perf_counter()
        text = " ".join(text.strip().split())
        result = None
        try:
            result = self._relational_turn(text, session_id)
        except Exception:  # noqa: BLE001 — relational path must never block routing
            result = None
        if result is None:
            commonsense = self.commonsense.answer(text)
            if commonsense["status"] in ("answered", "withheld"):
                result = {"status": commonsense["status"], "path": "conceptnet_commonsense",
                          "response": commonsense["response"],
                          "provenance": {"kind": "conceptnet_edges",
                                         "claims": commonsense.get("claims", [])}}
        if result is None:
            value = self.documents.chat(text, session_id=f"doc-{session_id}")
            result = {"status": value.get("status", "unresolved"), "path": "document_runtime",
                      "response": str(value.get("response", "")),
                      "provenance": {"kind": "m13d2_envelope",
                                     "operation": value.get("operation"),
                                     "retrieval": value.get("retrieval")}}
        result["latency_ms"] = round(1000.0 * (time.perf_counter() - started), 1)
        result["zero_model_gate"] = {"lm_calls": 0, "transformer_calls": 0}
        return result
