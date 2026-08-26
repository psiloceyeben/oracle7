#!/usr/bin/env python3
"""Runtime P — M17a shadow arbitration (additive over O).

Every chat turn is scored by the M-series release arbiter (frozen K138 bid
geometry + M-series families) and the ArbitrationRecord summary is attached to
the result as advisory metadata. Dispatch is UNCHANGED — the regex chain still
commits every action; the arbiter observes. Agreement per turn is recorded so
the live residue log accumulates the shadow scoreboard for the M17b promotion
gate. Advisory failure can never break a turn."""

from __future__ import annotations

from oracle_release_runtime_o import OracleReleaseRuntimeO
from stage5m17_release_arbiter_v1 import arbitrate, path_family


class OracleReleaseRuntimeP(OracleReleaseRuntimeO):
    def chat(self, text: str, session_id: str = "default") -> dict:
        result = super().chat(text, session_id)
        try:
            record = arbitrate(" ".join(text.strip().split()))
            regex_family = path_family(result.get("path"))
            result["arbitration"] = {
                "winner": record.winner,
                "runner_up": record.runner_up,
                "margin": round(record.margin, 3),
                "floor": record.clarification_floor_applied,
                "regex_family": regex_family,
                "agrees": record.winner == regex_family if regex_family else None,
                "mode": "shadow",
            }
        except Exception:  # noqa: BLE001 — advisory only, never break dispatch
            pass
        return result
