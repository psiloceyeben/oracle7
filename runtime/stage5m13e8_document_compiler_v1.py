#!/usr/bin/env python3
"""H2 slice 3 — section and document programs (development evidence).

The supra-sentence ladder completed structurally:
  paragraph  = TOPIC/EVIDENCE/ANALYSIS moves (v2/v3, gated, premise-checked)
  section    = ordered gated paragraphs + a SECTION_CONCLUSION derived from
               the paragraphs' ANALYSIS moves (premises = those moves)
  document   = sections + a DOCUMENT_THESIS derived from section conclusions
Nothing at any level asserts without either a page address or a rule+premises
chain that bottoms out in page addresses. recover_document enforces the
chain: thesis premises -> section conclusions -> paragraph ANALYSIS moves ->
cited claims, all present in the emitted text in dependency order."""

from __future__ import annotations

import re

from stage5m13e8_paragraph_compiler_v2 import extract_year, recover_program_v2
from stage5m13e8_paragraph_compiler_v3 import compile_gated_paragraph


def compile_section(section_title: str, topics: list[tuple[str, list[dict], str | None]]):
    """topics: [(topic, claim_bundle, aggregation_term)]"""
    paragraphs = []
    exclusions = []
    analysis_moves = []
    for topic, bundle, term in topics:
        paragraph, program, excluded = compile_gated_paragraph(
            topic, bundle, evidence=2, aggregation_term=term)
        exclusions.extend(excluded)
        if paragraph is None:
            continue
        paragraphs.append({"topic": topic, "text": paragraph, "program": program})
        analysis_moves.extend(
            {"topic": topic, **m} for m in program.moves if m["move"] == "ANALYSIS")
    # SECTION_CONCLUSION: derived from the paragraphs' derived moves
    years = []
    for move in analysis_moves:
        years.extend(int(y) for y in re.findall(r"\((\d{4})\)", move["text"]))
    conclusion = None
    if analysis_moves:
        span = f" The dated evidence spans {min(years)} to {max(years)}." if len(years) >= 2 else ""
        text = (f"Across the {len(paragraphs)} topics of this section, "
                f"{len(analysis_moves)} derived observations were established from "
                f"cited records.{span}")
        conclusion = {"move": "SECTION_CONCLUSION", "rule": "section_synthesis",
                      "premises": [f"{m['topic']}:{m['rule']}" for m in analysis_moves],
                      "text": text}
    body = "\n\n".join(p["text"] for p in paragraphs)
    if conclusion:
        body += f"\n\n{conclusion['text']} [derived:section_synthesis<-{len(conclusion['premises'])}premises]"
    return {"title": section_title, "text": body, "paragraphs": paragraphs,
            "conclusion": conclusion, "exclusions": exclusions}


def compile_document(title: str, sections: list[dict]):
    concluded = [s for s in sections if s["conclusion"]]
    thesis = None
    if concluded:
        total_derived = sum(len(s["conclusion"]["premises"]) for s in concluded)
        noun = "section" if len(sections) == 1 else "sections"
        verb = "establishes" if len(sections) == 1 else "establish"
        text = (f"Taken together, the {len(sections)} {noun} of this document "
                f"{verb} {total_derived} derived observations, every one grounded "
                f"in page-bound evidence, and nothing asserted beyond what the cited "
                f"records and registered rules license.")
        thesis = {"move": "DOCUMENT_THESIS", "rule": "document_synthesis",
                  "premises": [s["title"] for s in concluded], "text": text}
    body = f"# {title}\n\n" + "\n\n".join(f"## {s['title']}\n\n{s['text']}" for s in sections)
    if thesis:
        body += f"\n\n{thesis['text']} [derived:document_synthesis<-{len(thesis['premises'])}sections]"
    return {"title": title, "text": body, "sections": sections, "thesis": thesis}


def recover_document(document: dict) -> bool:
    text = document["text"]
    for section in document["sections"]:
        for paragraph in section["paragraphs"]:
            if not recover_program_v2(paragraph["text"], paragraph["program"]):
                return False
        conclusion = section["conclusion"]
        if conclusion:
            position = text.find("[derived:section_synthesis")
            if position < 0 or conclusion["text"] not in text:
                return False
            before = text[:text.find(conclusion["text"])]
            for premise in conclusion["premises"]:
                topic = premise.split(":", 1)[0]
                if topic not in before:
                    return False
    thesis = document["thesis"]
    if thesis:
        if thesis["text"] not in text:
            return False
        before = text[:text.find(thesis["text"])]
        for section_title in thesis["premises"]:
            if section_title not in before:
                return False
    return True
