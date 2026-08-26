#!/usr/bin/env python3
"""Runtime S — M17b3: runtime R's capture logic driven by arbiter v3.
New file; P/Q/R untouched. Same fallback-boundary authority, improvement-only
rule, ablation flags, and canonical-surface carriers as R."""

from __future__ import annotations

from oracle_release_runtime_o import OracleReleaseRuntimeO
from oracle_release_runtime_q import ACT_CANONICAL, FALLBACK_OK, FALLBACK_PATHS
from oracle_release_runtime_r import OracleReleaseRuntimeR
from stage5m17_release_arbiter_v3 import arbitrate as arbitrate_v3
from stage5m17_release_arbiter_v3 import path_family


class OracleReleaseRuntimeS(OracleReleaseRuntimeR):
    def chat(self, text: str, session_id: str = "default") -> dict:
        result = OracleReleaseRuntimeO.chat(self, text, session_id)
        try:
            record = arbitrate_v3(" ".join(text.strip().split()))
        except Exception:  # noqa: BLE001
            return result
        regex_family = path_family(result.get("path"))
        arb = {"winner": record.winner, "runner_up": record.runner_up,
               "margin": round(record.margin, 3),
               "floor": record.clarification_floor_applied,
               "regex_family": regex_family,
               "agrees": record.winner == regex_family if regex_family else None,
               "mode": "shadow", "arbiter": "v3"}
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
            return result
        redispatch["path"] = f"arb:{family}->" + str(redispatch.get("path"))
        redispatch["arbitration"] = dict(arb)
        redispatch["arbitration"]["mode"] = "authoritative"
        redispatch["arbitration"]["canonical_surface"] = canonical
        redispatch["arbitration"]["capture_point"] = "act" if is_act else "capability"
        return redispatch
