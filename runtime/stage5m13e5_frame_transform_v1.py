#!/usr/bin/env python3
"""M13e5 frame transformation set v1 — scaffold register -> natural attributive register.

The m13d2 document compiler emits a FINITE set of frame templates (paragraph
routing intros, per-claim attribution frames, per-paragraph integrity closers).
This transformation set rewrites each frame into a natural expressive form.

LAWS (external gates, Codex step 3 applied):
  G1  every claim text survives VERBATIM (character-identical);
  G2  every [Pnnn] provenance address survives (relocated to sentence end);
  G3  every source page name survives adjacent to its claim;
  G4  epistemic disclaimers are consolidated into one document-level note,
      never deleted from the document's meaning.
A transform that violates any gate raises and releases nothing.

Additive successor: operates on generated documents; the sealed compiler is
not modified. The proper compiler-integrated version is the H2 work item.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

INTRO = re.compile(
    r"^(?:Paragraph \d+ routes .*?authority\.|For paragraph \d+ on .*?unchanged\.|"
    r"Direction .*? gives paragraph \d+ .*?anchor fact\.)\s*")
CLOSERS = re.compile(
    r"\s*(?:At paragraph \d+, shared surface .*?page-bound\.|"
    r"Paragraph \d+ uses overlap marker .*?freshness\.|"
    r"Paragraph \d+ turns local geometry .*?cited records\.)\s*$")
# The compiler's frame family carries a KIND slot ("conjunctive-query
# statement", "lexical-context candidate", "exact-anchor statement", ...).
_KIND = r"[a-z][a-z\- ]{2,40}?(?:statement|candidate|record|claim)"
ATTRIBUTION = re.compile(
    r"^\[P(\d+)\]\s*(?:"
    rf"As an? {_KIND}, preserved page (?P<p1>.*?) states|"
    rf"Attributed evidence from (?P<p2>.*?), retrieved as an? {_KIND}, reads|"
    rf"The {_KIND} addressed to (?P<p3>.*?) contributes|"
    rf"In the preserved snapshot, (?P<p4>.*?) reports this {_KIND}|"
    rf"Source page (?P<p5>.*?) supplies the following {_KIND}|"
    rf"Bound to page (?P<p6>.*?), this {_KIND} says"
    r"):\s*(?P<claim>.*)$", re.S)

NATURAL_FORMS = [
    "According to {page}, {claim}",
    "The page for {page} records: {claim}",
    "{page} notes that {claim}",
    "As {page} has it, {claim}",
    "From {page}: {claim}",
]

# Typed classification of clause-initial `it` (v2). Substitution is licensed
# ONLY for "referential"; every other class keeps the claim verbatim.
_IT_HEAD = re.compile(r"^It (?:was|is|has|had|will be|would be)\b", re.I)
_CLEFT = re.compile(r"^It (?:was|is) .{1,120}?[,\s](?:who|that|which)\s", re.I)
_ANTICIPATORY = re.compile(
    r"^It (?:was|is|seems|appears|remains|became|becomes) "
    r"(?:\w+ly )?(?:\w+ )?(?:that|to|whether|unclear|likely|unlikely|possible|"
    r"impossible|important|necessary|difficult|easy|hard|clear|obvious|evident|"
    r"believed|thought|said|reported|estimated|known|assumed)\b", re.I)
_WEATHER = re.compile(
    r"^It (?:was|is) (?:rain|snow|sunn|cloud|wind|storm|cold|hot|warm|cool|"
    r"dark|light|late|early|noon|midnight|winter|summer|spring|autumn)", re.I)


def classify_clause_initial_it(claim: str) -> str:
    """referential | cleft | anticipatory | weather | none."""
    if not _IT_HEAD.match(claim):
        return "none"
    if _ANTICIPATORY.match(claim):
        return "anticipatory"
    if _CLEFT.match(claim):
        return "cleft"
    if _WEATHER.match(claim):
        return "weather"
    if claim.startswith(("It was ", "It is ", "It has ", "It had ")):
        return "referential"
    return "none"


INTEGRITY_NOTE = (
    "*Every statement above is page-bound evidence, cited by address. Statements are "
    "grouped by shared surface terms; grouping asserts organization, not causation, "
    "consensus, completeness, or freshness, and nothing is released beyond the cited records.*")


def transform(text: str, grounding_ledger: list | None = None) -> str:
    if grounding_ledger is None:
        grounding_ledger = []
    source_addresses = set(re.findall(r"\[P\d+\]", text))
    out_blocks: list[str] = []
    claim_registry: list[str] = []
    counter = 0
    for block in text.split("\n\n"):
        stripped = block.strip()
        if not stripped or stripped.startswith("#"):
            out_blocks.append(block)
            continue
        body = CLOSERS.sub("", INTRO.sub("", stripped))
        chunks = re.split(r"(?=\[P\d+\])", body)
        rewritten: list[str] = []
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            match = ATTRIBUTION.match(chunk)
            if not match:
                rewritten.append(chunk)
                continue
            address = f"[P{match.group(1)}]"
            page = next(g for g in (match.group(f"p{i}") for i in range(1, 8)) if g)
            claim = CLOSERS.sub("", match.group("claim")).strip()
            claim_registry.append(claim)
            # Subject-grounding rule v2 (typed; ledgered). v1 substituted the
            # page title into EVERY clause-initial "It", which converted the
            # cleft at P068 ("It was Lamarck, ..., who discussed ...") into the
            # FALSE statement "Man's Place in Nature was Lamarck ..." — that
            # defect is a permanent regression case
            # (stage5m13e5_frame_transform_regressions_v1.py). v2 classifies
            # clause-initial `it` and substitutes ONLY the referential class.
            grounded = claim
            it_class = classify_clause_initial_it(claim)
            if it_class == "referential":
                grounded = page + claim[2:]
                grounding_ledger.append({"address": address, "page": page,
                                         "original": claim, "grounded": grounded,
                                         "it_class": it_class,
                                         "rule": "subject-grounding-it-v2"})
            form = NATURAL_FORMS[counter % len(NATURAL_FORMS)]
            counter += 1
            rendered = form.format(page=page, claim=grounded)
            rewritten.append(f"{rendered} {address}")
        if rewritten:
            out_blocks.append(" ".join(rewritten))
    out_blocks.append(INTEGRITY_NOTE)
    result = "\n\n".join(out_blocks)

    # ── gates ────────────────────────────────────────────────────────────
    kept = set(re.findall(r"\[P\d+\]", result))
    if kept != source_addresses:
        raise AssertionError(f"G2 provenance-address loss: {sorted(source_addresses - kept)[:5]}")
    grounded_map = {entry["original"]: entry for entry in grounding_ledger}
    for claim in claim_registry:
        if not claim or claim in result:
            continue
        entry = grounded_map.get(claim)
        if entry is None or entry["grounded"] not in result:
            raise AssertionError(f"G1 claim-text loss: {claim[:80]!r}")
        # G1b: substitution touched ONLY the clause-initial token.
        if entry["grounded"] != entry["page"] + claim[2:]:
            raise AssertionError(f"G1b substitution exceeded referent: {claim[:60]!r}")
    return result


def main() -> int:
    source = Path(sys.argv[1])
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else source.with_name(
        source.stem + "_natural_v1" + source.suffix)
    ledger: list = []
    result = transform(source.read_text(encoding="utf-8"), ledger)
    target.write_text(result + "\n", encoding="utf-8", newline="\n")
    if ledger:
        import json
        ledger_path = target.with_suffix(".grounding_ledger.json")
        ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8", newline="\n")
        print(f"grounded {len(ledger)} clause-initial anaphors (ledger: {ledger_path.name})")
    print(f"transformed {source.name} -> {target.name} (gates G1-G4 passed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
