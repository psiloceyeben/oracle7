#!/usr/bin/env python3
"""BenchFold induction pass 1 (development evidence; dev split only).

Five typed corpus-query rules induced from the pass-0 residue skeletons.
Admission gates per rule:
  multi-donor gate  -- >=2 independent dev donors must validate;
  evidence gate     -- validation = a gold alias appears in the retrieved
                       provenance-addressed sentence (never in a guess).
Admitted rules + their donor ledger are written to
stage5m13e7_benchfold_rule_ledger_v1.json; the front-door successor
(oracle_release_runtime_b) loads ONLY admitted rules. Answers are always
page-bound sentences with claim addresses — extraction is containment, so
released text remains authority-gated."""

from __future__ import annotations

import json
import re
import sqlite3
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / "fable-content" / "oracle-m-series-2026-08-15"
DB = Path(__import__("os").environ.get("ORACLE_BENCH_BUILD",
          str(PHASE / "m13e5_dbpedia_build_a_v2" / "wikipedia_specialist.sqlite3")))

TYPE_WORDS = r"(?:movie|film|show|song|album|series|book|game)"

RULES = [
    ("when_did_release",
     re.compile(rf"^when did (?:the )?(?:{TYPE_WORDS} )?(?P<ent>.+?) (?:come out|first come out|release|be released|premiere)\??$", re.I),
     ["released", "premiered", "debut", "come", "came", "out"]),
    ("when_does_start",
     re.compile(r"^when does (?:the )?(?P<ent>.+?) (?:start|begin|air|come out|return|take place)\??$", re.I),
     ["begins", "starts", "airs", "premieres", "scheduled", "held"]),
    ("surname_origin",
     re.compile(r"^where does the (?:last name|surname) (?P<ent>\w+) (?:come from|originate)\??$", re.I),
     ["surname", "origin", "derived", "name", "family"]),
    ("property_of",
     re.compile(r"^what is the (?P<prop>[\w ]{2,30}?) of (?:the )?(?P<ent>.+?)\??$", re.I),
     None),
    ("who_won_year",
     re.compile(r"^who won (?:the )?(?P<ent>.+?) in (?P<year>\d{4})\??$", re.I),
     ["won", "winner", "winning", "champion", "champions"]),
]

_TOKEN = re.compile(r"[A-Za-z0-9]+")


def normalize_title(title: str) -> str:
    value = unicodedata.normalize("NFKC", title).casefold()
    return " ".join(re.findall(r"[^\W_]+(?:[-'][^\W_]+)?", value))


class DBpediaQuery:
    def __init__(self, db_path: Path = DB):
        uri = db_path.resolve().as_uri() + "?mode=ro&immutable=1"
        self.connection = sqlite3.connect(uri, uri=True)

    def page_id(self, entity: str) -> str | None:
        row = self.connection.execute(
            "SELECT page_id FROM title_alias WHERE normalized_title=? LIMIT 1",
            (normalize_title(entity),)).fetchone()
        return row[0] if row else None

    def page_sentences(self, page_id: str) -> list[tuple[str, str]]:
        return self.connection.execute(
            "SELECT s.claim_id, s.fact FROM page_sentence p JOIN source_rows s ON s.rowid=p.source_rowid "
            "WHERE p.page_id=? ORDER BY p.sentence_ordinal", (page_id,)).fetchall()

    # Bounded-latency retrieval (release blocker fix, 2026-08-17): the original
    # ORDER BY rank forced global scoring over 17M rows — minutes per rare-term
    # query (pass-1 run took 46,873s). Now: LIMIT-first in storage order (no
    # global sort; deterministic) plus a progress-handler op budget so no query
    # can exceed ~a second; an interrupted query is a typed empty result.
    _OP_BUDGET_CALLBACKS = 400          # x 100k VM ops per callback

    def fts(self, terms: list[str], limit: int = 5) -> list[tuple[str, str]]:
        query = " ".join(_TOKEN.findall(" ".join(terms)))
        if not query:
            return []
        budget = {"left": self._OP_BUDGET_CALLBACKS}

        def _tick():
            budget["left"] -= 1
            return 1 if budget["left"] <= 0 else 0

        self.connection.set_progress_handler(_tick, 100_000)
        try:
            return self.connection.execute(
                "SELECT claim_id, fact FROM source_rows WHERE source_rows MATCH ? LIMIT ?",
                (query, limit)).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            self.connection.set_progress_handler(None, 0)


def apply_rule(query: DBpediaQuery, rule_id: str, match: re.Match) -> tuple[str, str] | None:
    groups = match.groupdict()
    entity = groups.get("ent", "").strip()
    if rule_id == "property_of":
        keywords = _TOKEN.findall(groups.get("prop", "").lower())
    elif rule_id == "who_won_year":
        keywords = [groups["year"], "won", "winner", "champion"]
    else:
        keywords = next(k for i, _, k in [(r[0], r[1], r[2]) for r in RULES] if i == rule_id) or []
    # path 1: exact page + keyword-filtered sentence
    candidates = []
    for title in (entity, f"{entity} (surname)" if rule_id == "surname_origin" else None):
        if not title:
            continue
        page = query.page_id(title)
        if page:
            for claim_id, fact in query.page_sentences(page):
                fact_low = fact.lower()
                score = sum(1 for k in keywords if k.lower() in fact_low)
                if score:
                    candidates.append((score, claim_id, fact))
            if candidates:
                candidates.sort(reverse=True)
                _, claim_id, fact = candidates[0]
                return claim_id, fact
    # path 2: conjunctive FTS
    hits = query.fts(_TOKEN.findall(entity) + [k for k in keywords if len(k) > 2][:3])
    if hits:
        return hits[0]
    return None


def main() -> int:
    started = time.perf_counter()
    query = DBpediaQuery()
    dev = [json.loads(line) for line in
           (PHASE / "benchfold" / "NQ-open.dev.jsonl").read_text(encoding="utf-8").splitlines()]
    ledger = []
    for rule_id, pattern, _ in RULES:
        donors = []
        for record in dev:
            match = pattern.match(record["question"].strip())
            if not match:
                continue
            result = apply_rule(query, rule_id, match)
            hit = bool(result) and any(g.casefold() in result[1].casefold()
                                       for g in record["answer"])
            donors.append({"q": record["question"], "validated": hit,
                           "claim": result[0] if result else None})
        validated = sum(1 for d in donors if d["validated"])
        admitted = validated >= 2
        ledger.append({"rule": rule_id, "donors_total": len(donors),
                       "donors_validated": validated, "admitted": admitted,
                       "validation_rate": round(validated / len(donors), 3) if donors else 0.0,
                       "donor_rows": donors})
        print(f"{'ADMIT ' if admitted else 'REJECT'} {rule_id}: {validated}/{len(donors)} donors validated", flush=True)
    out = {
        "schema_version": "oracle-stage5m13e7-benchfold-rule-ledger-v1",
        "classification": "development evidence; dev split only",
        "gates": {"multi_donor": ">=2 validated donors", "evidence": "gold alias in provenance-addressed sentence"},
        "rules": ledger,
        "elapsed_seconds": round(time.perf_counter() - started, 1),
    }
    (PHASE / "stage5m13e7_benchfold_rule_ledger_v1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({r["rule"]: f"{r['donors_validated']}/{r['donors_total']}" for r in ledger}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
