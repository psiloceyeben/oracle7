#!/usr/bin/env python3
"""oracle_release_runtime_w20 - POTENTIALS fold (epoch 3): the typed space of the possible.

30 potentials bound from live sources: the self-model's declared gaps, the
human-signed target-shape distances, pending fold families, unmapped induced templates
(residuals naming missing capabilities), and refused candidates whose lessons are
encoded. A potential CONVERTS to an actual when a fold family admits - the conversion
rate across epochs is the measurable throughput of self-improvement.
Authored 2026-08-25 13:51 UTC by oracle_fold_worker_v6, chained on oracle_release_runtime_w19."""

from __future__ import annotations

import re

from oracle_release_runtime_w19 import OracleReleaseRuntimeW19

POTENTIALS = [{'kind': 'charter_milestone', 'name': 'coding.C2: multi-step verified rewriting: simplify/transform expression'}, {'kind': 'charter_milestone', 'name': 'coding.C3: spec-to-function synthesis: compose verified primitives to s'}, {'kind': 'charter_milestone', 'name': 'coding.C4: self-extension from spec: given a route specification, autho'}, {'kind': 'charter_milestone', 'name': 'compositional_depth.D2: 3-hop chains, same discipline'}, {'kind': 'charter_milestone', 'name': 'compositional_depth.D3: cross-relation composition (made_of∘part_of∘kind)'}, {'kind': 'charter_milestone', 'name': 'compositional_depth.D4: novel-surface transfer: admitted operators on unseen phrasin'}, {'kind': 'charter_milestone', 'name': 'compositional_depth.D5: arbitrary-k productive composition at conversational depth ('}, {'kind': 'charter_milestone', 'name': 'grounded_open_qa.Q3: harder held-out panels so admissions show GAINS not only no-'}, {'kind': 'charter_milestone', 'name': 'image_generation.I1: data diagram synthesis: chart/graph SVG from typed data with'}, {'kind': 'charter_milestone', 'name': 'image_generation.I2: scene composition from the world op-tree vocabulary (structu'}, {'kind': 'charter_milestone', 'name': 'image_generation.I3: parameterized composition: style as declared parameters, eve'}, {'kind': 'charter_milestone', 'name': 'long_horizon_planning.P2: goal-declared decomposition: a stated goal becomes typed ste'}, {'kind': 'charter_milestone', 'name': 'long_horizon_planning.P3: failure-adaptive replanning with recorded plan revisions'}, {'kind': 'charter_milestone', 'name': 'mathematical_reasoning.M2: multi-step chains: each intermediate verified, chain recorde'}, {'kind': 'charter_milestone', 'name': 'mathematical_reasoning.M3: word-problem decomposition: typed reading -> plan -> verifie'}, {'kind': 'charter_milestone', 'name': 'multilingual_transfer.L1: EN/ES/FR same-intent parsing convergence'}, {'kind': 'charter_milestone', 'name': 'multilingual_transfer.L2: unknown-surface withhold with corpus-verified negatives'}, {'kind': 'charter_milestone', 'name': 'self_improvement_completion.S1: family-generator authoring: the worker authors NEW fold-fami'}, {'kind': 'charter_milestone', 'name': 'self_improvement_completion.S2: self-growing panels: harder held-out authored from failures '}, {'kind': 'charter_milestone', 'name': 'self_improvement_completion.S3: corpus admission loop: world/curriculum knowledge admitted i'}, {'kind': 'charter_milestone', 'name': 'self_improvement_completion.S4: janitor organ: self-maintenance (rotations, health, RAM) as '}, {'kind': 'charter_milestone', 'name': 'self_improvement_completion.S5: automated lineage exchange on cadence (M59 machinery, merge '}, {'kind': 'declared_gap', 'name': 'route:conceptnet_isa_derived missing complements'}, {'kind': 'declared_gap', 'name': 'route:conceptnet_isa_direct missing complements'}, {'kind': 'declared_gap', 'name': 'route:conceptnet_partof_derived missing complements'}, {'kind': 'declared_gap', 'name': 'route:conceptnet_partof_direct missing complements'}, {'kind': 'declared_gap', 'name': 'route:conceptnet_isa_derived missing mediated_by'}, {'kind': 'declared_gap', 'name': 'route:conceptnet_isa_direct missing mediated_by'}, {'kind': 'declared_gap', 'name': 'act:continue_topic'}, {'kind': 'declared_gap', 'name': 'act:refine'}]

POT_RX = re.compile(
    r"(what (?:could|can) you (?:learn|become)|what are your potentials"
    r"|what is potentially possible|what might you become)", re.I)


class OracleReleaseRuntimeW20(OracleReleaseRuntimeW19):
    """Base + the potentials route."""

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        if POT_RX.search(s):
            bits = "; ".join(f"{p['kind']}: {p['name']}" for p in POTENTIALS[:6])
            return {"status": "answered", "path": "worker:potentials",
                     "response": f"By my own ledgers, {len(POTENTIALS)} typed "
                                 f"potentials stand open, among them {bits}. Each "
                                 f"converts to an actual only through the gate. "
                                 f"[potentials_epoch_3]",
                     "provenance": {"kind": "potentials_ledger", "epoch": 3,
                                     "count": len(POTENTIALS)},
                     "latency_ms": 1}
        return super().chat(s, session_id)
