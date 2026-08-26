#!/usr/bin/env python3
"""Runtime AH - honest exclusion rendering (additive over AG).

AG fixed the affirmative citation but left the SAME defect class in the exclusion
path. Two problems, both of which fabricate structure:

1. Sense interleaving. The closure is a union over all senses, so rendering it as
   one arrow-path splices unrelated lineages:

       "guinea pig: entity -> physical entity -> causal agent -> object ->
        person -> whole -> guinea pig"

   That path does not exist. It mixes the rodent with the separate sense of a
   person used as a test subject.

2. Truncated scope. The text asserted a term "does not appear anywhere in that
   chain" while displaying only a six-node prefix, inviting the reader to verify
   an exhaustive claim against partial evidence.

Fix: an exclusion no longer claims a path. It reports the most specific categories
the record actually assigns - which are the sense-characteristic ones - as a SET,
and states plainly that the exclusion was checked against the complete closure
while what is shown is a summary of it. The affirmative path still shows a real
chain, because there a single genuine lineage exists and contains the cited term.

Say only what the record supports, and show evidence in the shape it actually has.
No neural network; no LM call.
"""

from __future__ import annotations

from oracle_release_runtime_ag import OracleReleaseRuntimeAG

SHOW_CATEGORIES = 6


class OracleReleaseRuntimeAH(OracleReleaseRuntimeAG):
    def _specific_categories(self, lemma: str, limit: int = SHOW_CATEGORIES) -> list:
        """Deepest hypernyms = the sense-characteristic ones. A set, not a path."""
        rows = self._wn.execute(
            "SELECT hypernym FROM lemma_closure WHERE lemma=? ORDER BY depth DESC, hypernym ASC "
            "LIMIT ?", (lemma, limit)).fetchall()
        return [r[0] for r in rows]

    def _closure_size(self, lemma: str) -> int:
        row = self._wn.execute(
            "SELECT COUNT(*) FROM lemma_closure WHERE lemma=?", (lemma,)).fetchone()
        return int(row[0]) if row else 0

    def _wordnet_turn(self, text: str) -> dict | None:
        result = super()._wordnet_turn(text)
        if result is None or result.get("path") != "wordnet_kind_excluded":
            return result
        prov = result.get("provenance", {})
        lemma = prov.get("lemma")
        parsed = self._parse_kind(text)
        if not lemma or parsed is None:
            return result
        _x, y = parsed
        cats = self._specific_categories(lemma)
        total = self._closure_size(lemma)
        listed = ", ".join(cats) if cats else "no categories on record"
        result["response"] = (
            f"No. The record classifies {lemma} under {listed}"
            f"{' and other broader categories' if total > len(cats) else ''}. "
            f"{y.capitalize()} is not among the {total} categories on record for it, and "
            f"that record is complete, so this is an exclusion rather than a gap. "
            f"[cited:wordnet:{lemma}]")
        result["provenance"] = {
            "kind": "lexical_corpus", "corpus": "wordnet",
            "relation": "hypernym_excluded", "lemma": lemma,
            "categories_shown": cats, "categories_total": total,
            "note": ("categories are a set drawn from all senses, not a single lineage; "
                     "the exclusion was checked against the complete closure"),
        }
        return result
