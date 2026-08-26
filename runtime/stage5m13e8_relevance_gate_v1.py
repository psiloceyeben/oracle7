#!/usr/bin/env python3
"""Typed relevance gate (task #18; release blocker for document evidence).

Classifies a retrieved claim relative to a topic:
  exact_topic     -- the claim's page IS the topic (normalized title match)
  explanatory     -- page title carries a distinctive topic token, or the
                     sentence contains the full topic phrase
  contextual      -- a distinctive topic token appears in the sentence only
  lexical_overlap -- only GENERIC topic tokens matched (the Antikythera
                     hand-fan class) -> must be REJECTED, never attributed
  rejected        -- no topic token at all

Distinctiveness v1 (deterministic): a topic token is generic if it is in the
GENERIC set or is a short lowercase common form; otherwise distinctive.
Registered limitation: corpus document-frequency statistics would sharpen
this; v1 is a conservative allowlist-free heuristic.
"""

from __future__ import annotations

import re
import unicodedata

GENERIC = {"mechanism", "machine", "device", "system", "man", "woman", "history",
           "city", "island", "river", "war", "battle", "world", "state", "house",
           "school", "church", "book", "film", "movie", "song", "album", "name",
           "people", "language", "century", "empire", "king", "queen", "north",
           "south", "east", "west", "new", "old", "great", "first", "second"}


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"[^\W_]+(?:[-'][^\W_]+)?", value))


def topic_tokens(topic: str) -> tuple[set[str], set[str]]:
    tokens = _norm(topic).split()
    distinctive = {t for t in tokens if t not in GENERIC and len(t) >= 5}
    generic = set(tokens) - distinctive
    return distinctive, generic


def classify_claim(topic: str, page: str, sentence: str) -> str:
    topic_norm, page_norm = _norm(topic), _norm(page)
    sentence_norm = _norm(sentence)
    distinctive, generic = topic_tokens(topic)
    if page_norm == topic_norm:
        return "exact_topic"
    page_words = set(page_norm.split())
    sentence_words = set(sentence_norm.split())
    if distinctive & page_words:
        return "explanatory"
    if topic_norm and topic_norm in sentence_norm:
        return "explanatory"
    if distinctive & sentence_words:
        return "contextual"
    if generic & (page_words | sentence_words):
        return "lexical_overlap"
    return "rejected"


ADMITTED = {"exact_topic", "explanatory"}


def gate_bundle(topic: str, claims: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split a claim bundle into (admitted, exclusion_ledger). Nothing dropped
    silently: every excluded claim is logged with its class."""
    admitted, excluded = [], []
    for claim in claims:
        cls = classify_claim(topic, claim["page"], claim["sentence"])
        record = {**claim, "relevance": cls}
        (admitted if cls in ADMITTED else excluded).append(record)
    return admitted, excluded
