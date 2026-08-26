#!/usr/bin/env python3
"""H2 slice 2b — relevance-gated paragraph compiler (additive over v2).

Claims pass the typed relevance gate BEFORE composition: only exact_topic and
explanatory claims may become TOPIC/EVIDENCE moves; every exclusion is
returned in a ledger with its class (nothing silently dropped, nothing
irrelevant attributed). With this gate in place, compiled paragraphs graduate
from 'development artifact' toward citable capability evidence per the
epistemic charter (final promotion still requires the H5 panel)."""

from __future__ import annotations

from stage5m13e8_paragraph_compiler_v2 import compile_paragraph_v2, recover_program_v2
from stage5m13e8_relevance_gate_v1 import gate_bundle


def compile_gated_paragraph(topic: str, claims: list[dict], **kwargs):
    admitted, excluded = gate_bundle(topic, claims)
    if not admitted:
        return None, None, excluded
    paragraph, program = compile_paragraph_v2(topic, admitted, **kwargs)
    return paragraph, program, excluded
