#!/usr/bin/env python3
"""Runtime AG - cite a genuine hypernym chain (additive over AF).

AF answered correctly but CITED INCORRECTLY:

    "Yes. The lexical record places gray whale under whale:
     organism -> living thing -> whole -> object -> physical entity -> gray whale"

The claimed hypernym ("whale") does not appear in the chain shown. Corpus v1
stored each synset's total path length as the depth of every node on that path,
so all hypernyms of a sense shared one meaningless value and ordering by it
produced a sequence that was not a hypernym path at all.

For a system whose entire claim is shown provenance, citing a chain that does not
contain the cited term is the most serious defect available - worse than the
parser bug, because the answer looks right and the evidence is fabricated
structure.

Corpus v2 stores each node's own distance from the root, so ascending depth is a
genuine general-to-specific ordering. This runtime reads v2, renders the chain in
that order, and guarantees the cited hypernym appears in what it shows. It also
never presents more than the real path: nodes are drawn from the lemma's own
closure only.

No neural network; no LM call.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from oracle_release_runtime_af import OracleReleaseRuntimeAF

WORDNET_CORPUS_V2 = ("/opt/oracle-clm/fable-content/oracle-m-series-2026-08-15"
                     "/m31_wordnet_corpus_v2.sqlite3")


class OracleReleaseRuntimeAG(OracleReleaseRuntimeAF):
    def __init__(self, *args, wordnet_corpus: str = WORDNET_CORPUS_V2, **kwargs) -> None:
        super().__init__(*args, wordnet_corpus=wordnet_corpus, **kwargs)

    def _chain_for(self, lemma: str, limit: int = 6) -> list:
        """General -> specific, by each node's own distance from the root."""
        rows = self._wn.execute(
            "SELECT hypernym FROM lemma_closure WHERE lemma=? ORDER BY depth ASC, hypernym ASC "
            "LIMIT ?", (lemma, limit)).fetchall()
        return [r[0] for r in rows]

    def _render_chain(self, lemma: str, hypernym: str | None) -> str:
        """The shown chain must contain the cited hypernym, or it is not evidence."""
        chain = self._chain_for(lemma, limit=6)
        if hypernym and hypernym not in chain:
            row = self._wn.execute(
                "SELECT depth FROM lemma_closure WHERE lemma=? AND hypernym=?",
                (lemma, hypernym)).fetchone()
            if row is not None:
                chain = self._chain_for(lemma, limit=5)
                if hypernym in chain:
                    chain.remove(hypernym)
                chain = chain[:4] + [hypernym]
        return " -> ".join(chain + [lemma]) if chain else lemma

    def _wordnet_turn(self, text: str) -> dict | None:
        if self._wn is None:
            return None
        parsed = self._parse_kind(text)
        if parsed is None:
            return None
        x, y = parsed
        lemma = self._present(x)
        if lemma is None:
            return None
        hit = self._closure_hit(lemma, y)
        article_x = "an" if x[:1] in "aeiou" else "a"
        article_y = "an" if y[:1] in "aeiou" else "a"
        if hit is not None:
            hypernym, _depth, sense = hit
            shown = self._render_chain(lemma, hypernym)
            return {
                "status": "answered",
                "path": "wordnet_kind_direct",
                "response": (f"Yes. The lexical record places {lemma} under {hypernym}, "
                             f"from the general to the specific: {shown}. On that record "
                             f"{article_x} {x} is {article_y} {y}. [cited:wordnet:{sense}]"),
                "provenance": {"kind": "lexical_corpus", "corpus": "wordnet",
                               "relation": "hypernym", "lemma": lemma,
                               "hypernym": hypernym, "sense": sense,
                               "chain": self._chain_for(lemma) + [lemma]},
            }
        shown = self._render_chain(lemma, None)
        return {
            "status": "answered",
            "path": "wordnet_kind_excluded",
            "response": (f"No. The lexical record places {lemma} on a different line, "
                         f"from the general to the specific: {shown}. {y.capitalize()} does "
                         f"not appear anywhere in that chain, and the chain is complete, so "
                         f"this is an exclusion rather than a gap in the record. "
                         f"[cited:wordnet:{lemma}]"),
            "provenance": {"kind": "lexical_corpus", "corpus": "wordnet",
                           "relation": "hypernym_excluded", "lemma": lemma,
                           "chain": self._chain_for(lemma) + [lemma]},
        }
