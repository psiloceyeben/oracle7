#!/usr/bin/env python3
"""Runtime R — M17b2: runtime Q's capture logic driven by arbiter v2.

New file; P and Q untouched. Dispatch goes through the O chain directly (the
regex front door), then arbiter v2 (widened prototypes + ConceptNet marker
projection) is recorded per turn and made authoritative at the same fallback
boundary with the same improvement-only rule as Q: capture only when the regex
chain failed to answer, re-dispatch via canonical surface, keep the original
on anything but answered/withheld. Ablation flags inherited from Q."""

from __future__ import annotations

from oracle_release_runtime_o import OracleReleaseRuntimeO
from oracle_release_runtime_q import (
    ACT_CANONICAL,
    FALLBACK_OK,
    FALLBACK_PATHS,
    OracleReleaseRuntimeQ,
)
from stage5m17_release_arbiter_v2 import arbitrate as arbitrate_v2
from stage5m17_release_arbiter_v2 import path_family


class OracleReleaseRuntimeR(OracleReleaseRuntimeQ):
    def chat(self, text: str, session_id: str = "default") -> dict:
        result = OracleReleaseRuntimeO.chat(self, text, session_id)
        try:
            record = arbitrate_v2(" ".join(text.strip().split()))
        except Exception:  # noqa: BLE001 — advisory layer must never break a turn
            return result
        regex_family = path_family(result.get("path"))
        arb = {"winner": record.winner, "runner_up": record.runner_up,
               "margin": round(record.margin, 3),
               "floor": record.clarification_floor_applied,
               "regex_family": regex_family,
               "agrees": record.winner == regex_family if regex_family else None,
               "mode": "shadow", "arbiter": "v2"}
        result["arbitration"] = arb
        if (arb["floor"] or result.get("path") not in FALLBACK_PATHS
                or result.get("status") in FALLBACK_OK):
            return result
        family = record.winner
        is_act = family in ACT_CANONICAL
        if is_act and not self.capture_act_enabled:
            return result
        if not is_act and not self.capture_capability_enabled:
            return result
        canonical = self._canonical_surface(family, text)
        if canonical is None:
            return result
        redispatch = OracleReleaseRuntimeO.chat(self, canonical, session_id)
        if redispatch.get("status") not in ("answered", "withheld"):
            return result  # improvement-only: keep the original
        redispatch["path"] = f"arb:{family}->" + str(redispatch.get("path"))
        redispatch["arbitration"] = dict(arb)
        redispatch["arbitration"]["mode"] = "authoritative"
        redispatch["arbitration"]["canonical_surface"] = canonical
        redispatch["arbitration"]["capture_point"] = "act" if is_act else "capability"
        return redispatch
