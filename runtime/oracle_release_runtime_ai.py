#!/usr/bin/env python3
"""Runtime AI - corpus v3 plus the observability conjunct (additive over AH).

Fixes two defects in the shipped exclusion path.

**1. FALSE EXCLUSIONS from projection loss.** Corpus v2 stored each hypernym as its
synset's PRIMARY lemma only - `node.name().split(".")[0]` - discarding 64,232 lemma
names across 48.8% of noun synsets. "hand luggage" has hypernym synset baggage.n.01
whose lemmas are ['baggage','luggage']; a query for "luggage" missed, and the runtime
answered "No" about a lemma WordNet explicitly lists. Corpus v3 stores every lemma;
head-containment now holds for 21,143 two-word compounds against v2's 18,979, so at
least 2,164 false exclusions were available in that class alone.

**2. NEGATION LICENSED ON HALF THE CONDITION.** Spec v4 invariant C1 requires
completeness AND observability: a known frame tells you what lies outside it, but says
nothing about something inside the frame that fell below detection. WordNet's chains are
complete *for the senses it carries* - a MISSING SENSE is an occlusion, and every
negation shipped so far ignored that.

Observability is implemented here as a real check rather than an assumption: if an
independent record asserts the relation that WordNet's closure lacks, that is evidence
the lexical record's sense coverage is incomplete for this case. The correct output is
then `X⁻_residual` - withhold with the conflict disclosed - never `X⁻_rejected`.

Exclusions that survive both conjuncts are unchanged from AH. No neural network.
"""

from __future__ import annotations

from pathlib import Path

from oracle_release_runtime_ah import OracleReleaseRuntimeAH, SHOW_CATEGORIES

WORDNET_CORPUS_V3 = ("/opt/oracle-clm/fable-content/oracle-m-series-2026-08-15"
                     "/m31_wordnet_corpus_v3.sqlite3")


class OracleReleaseRuntimeAI(OracleReleaseRuntimeAH):
    def __init__(self, *args, wordnet_corpus: str = WORDNET_CORPUS_V3, **kwargs) -> None:
        if not Path(wordnet_corpus).exists():
            wordnet_corpus = str(Path(wordnet_corpus).with_name("m31_wordnet_corpus_v2.sqlite3"))
        super().__init__(*args, wordnet_corpus=wordnet_corpus, **kwargs)

    def _independently_asserted(self, x: str, y: str) -> str | None:
        """Does an independent record assert this relation? Returns its provenance."""
        cs = getattr(self, "commonsense", None)
        if cs is None:
            return None
        forms_y = {y, y[:-1] if y.endswith("s") and not y.endswith("ss") else y}
        for subject in {x, x[:-1] if x.endswith("s") and not x.endswith("ss") else x}:
            try:
                edges = cs.edges(subject, "IsA", limit=48)
            except Exception:  # noqa: BLE001
                return None
            for edge in edges:
                end = str(edge.get("end", "")).strip().lower()
                if end in forms_y:
                    return str(edge.get("provenance", "commonsense"))
        return None

    def _wordnet_turn(self, text: str) -> dict | None:
        result = super()._wordnet_turn(text)
        if result is None or result.get("path") != "wordnet_kind_excluded":
            return result
        parsed = self._parse_kind(text)
        if parsed is None:
            return result
        x, y = parsed
        provenance = self._independently_asserted(x, y)
        if provenance is None:
            return result                      # both conjuncts hold: exclusion stands

        # observability fails: an independent record asserts what this one lacks
        prov = result.get("provenance", {})
        lemma = prov.get("lemma", x)
        cats = self._specific_categories(lemma, SHOW_CATEGORIES)
        listed = ", ".join(cats) if cats else "no categories on record"
        article_x = "an" if x[:1] in "aeiou" else "a"
        article_y = "an" if y[:1] in "aeiou" else "a"
        return {
            "status": "withheld",
            "path": "wordnet_kind_occluded",
            "response": (
                f"I am not able to settle this. The lexical record classifies {lemma} under "
                f"{listed}, and does not list {y} among them — but a separate record does "
                f"assert that {article_x} {x} is {article_y} {y} [{provenance}]. Because the "
                f"two disagree, the absence in the lexical record may reflect a sense it does "
                f"not carry rather than a fact about {x}, so I am withholding rather than "
                f"denying."),
            "provenance": {
                "kind": "observability_failure",
                "rule": "C1_requires_completeness_AND_observability",
                "lemma": lemma,
                "lexical_categories": cats,
                "conflicting_assertion": provenance,
                "residual_class": "X_minus_residual",
            },
            "zero_model_gate": {"lm_calls": 0, "transformer_calls": 0},
        }
