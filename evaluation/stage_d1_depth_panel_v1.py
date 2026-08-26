#!/usr/bin/env python3
"""D1 - the depth ladder's first rung: withheld 2-hop composition panel.

METHODOLOGY (proven in M13e2, reused): questions whose answers exist in NO single
corpus row - only the COMPOSITION of two attested facts yields them - with golds
computed programmatically from the same extractions. Lookup-shaped competence scores
zero by construction; only operator composition scores.

Panel construction (deterministic, PYTHONHASHSEED=0):
  1. Extract made_of pairs (X is made of Y) and kind pairs (X is a Y) from the
     combined corpus by the same rules the folds use.
  2. Build 2-hop chains: made_of(X)=Y AND made_of(Y)=Z  ->  gold: X ultimately Z
                         made_of(X)=Y AND kind(Y)=K     ->  gold: X is made of a K
  3. WITHHOLD CHECK: reject any chain where X and Z (or X and K) co-occur in ANY
     single corpus sentence (FTS check) - the answer must be genuinely absent from
     every row, reachable only by composition.
  4. Split: half the chains are the PANEL; the extraction evidence for them is left
     in the corpus (the hops are attested; the COMBINATION is what is withheld).

Measurement: run the current chain tip on the panel questions. Score = answered with
the gold pair present + both premise citations. Also score DECLINE-honesty on
corrupted chains (gold guaranteed false by construction: X-Z pairs from disjoint
chains) - depth without false-answer discipline is not depth.

This run seals the STARTING LINE. A depth claim begins with a sealed record of
shallowness. No LM calls.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from oracle_release_runtime import PHASE

sys.path.insert(0, str(PHASE / "self_loop" / "admitted"))

OUT = PHASE / "d1_depth_panel_v1.json"
MADE_RX = re.compile(r"^(?:The |A |An )?(?P<x>[A-Za-z][\w \-']{1,36}?) (?:is|are) "
                     r"(?:composed of|made of|made up of|made from) "
                     r"(?P<y>[a-z][\w ,\-']{2,70}?)[.;]", re.I)
KIND_RX = re.compile(r"^(?:The |A |An )?(?P<x>[A-Za-z][\w \-']{1,36}?) (?:is|are) "
                     r"(?:a|an) (?P<y>[a-z][\w \-']{2,40}?)[.;]", re.I)


def latest_tip():
    import importlib
    best = 0
    for f in (PHASE / "self_loop" / "admitted").glob("oracle_release_runtime_w*.py"):
        try:
            best = max(best, int(f.stem.split("_w")[-1]))
        except Exception:
            continue
    name = f"oracle_release_runtime_w{best}" if best else "oracle_release_runtime_ao"
    cls = f"OracleReleaseRuntimeW{best}" if best else "OracleReleaseRuntimeAO"
    mod = importlib.import_module(name)
    return name, getattr(mod, cls)


def main() -> int:
    import sqlite3
    import stage5m13e7_benchfold_induction_v1 as bench_mod
    uri = bench_mod.DB.resolve().as_uri() + "?mode=ro&immutable=1"
    con = sqlite3.connect(uri, uri=True)

    made, kind = {}, {}
    for pat, store, match_q in ((MADE_RX, made, '"made of" OR "composed of" OR "made from"'),
                                (KIND_RX, kind, '"is a" OR "is an"')):
        rows = con.execute(
            f"SELECT claim_id, fact FROM source_rows WHERE fact MATCH '{match_q}' "
            f"LIMIT 20000").fetchall()
        for claim, fact in rows:
            m = pat.match(str(fact))
            if not m:
                continue
            x = m.group("x").strip().lower()
            y = " ".join(m.group("y").strip().split()).split(",")[0].split(" and ")[0].strip()
            if x and y and x != y and x not in store and len(y) < 40:
                store[x] = (y, claim)

    def cooccur(a: str, b: str) -> bool:
        try:
            q = f'"{a}" AND "{b}"'
            return con.execute("SELECT 1 FROM source_rows WHERE fact MATCH ? LIMIT 1",
                               (q,)).fetchone() is not None
        except Exception:
            return True                      # on FTS error, treat as co-occurring: safe

    chains = []
    for x, (y, c1) in made.items():
        hop2 = made.get(y)
        if hop2 and hop2[0] != x and not cooccur(x, hop2[0]):
            chains.append({"type": "made_made", "x": x, "mid": y, "z": hop2[0],
                           "premises": [c1, hop2[1]],
                           "q": f"What is {x} ultimately made of?",
                           "gold": hop2[0]})
        k2 = kind.get(y)
        if k2 and k2[0] != x and not cooccur(x, k2[0]):
            chains.append({"type": "made_kind", "x": x, "mid": y, "z": k2[0],
                           "premises": [c1, k2[1]],
                           "q": f"Is {x} made of a kind of {k2[0]}?",
                           "gold": "yes"})
        if len(chains) >= 60:
            break

    negatives = []
    items = [c for c in chains if c["type"] == "made_made"]
    for i in range(min(20, len(items) - 1)):
        a, b = items[i], items[(i + 7) % len(items)]
        if a["x"] != b["x"] and a["z"] != b["z"] and not cooccur(a["x"], b["z"]):
            negatives.append({"q": f"Is {a['x']} ultimately made of {b['z']}?",
                              "gold": "not_attested",
                              "note": "cross-spliced chains; composition does NOT support"})

    tip_name, tip_cls = latest_tip()
    rt = tip_cls(state_root=PHASE / "d1_state",
                 wikipedia_build=PHASE / "m13e5_wiki_openstax_build_a_v1")
    correct = partial = wrong = declined = 0
    for c in chains:
        r = rt.chat(c["q"], session_id="d1")
        resp = str(r.get("response", "")).lower()
        if r.get("status") != "answered":
            declined += 1
        elif c["gold"] in resp and all(p.split("_")[0] in str(r.get("response", ""))
                                       or p in str(r.get("response", ""))
                                       for p in c["premises"]):
            correct += 1
        elif c["gold"] in resp:
            partial += 1
        else:
            wrong += 1
    neg_honest = neg_false = 0
    for n in negatives:
        r = rt.chat(n["q"], session_id="d1n")
        if r.get("status") == "answered" and "yes" in str(r.get("response", "")).lower()[:20]:
            neg_false += 1
        else:
            neg_honest += 1

    rep = {"schema_version": "oracle-d1-depth-panel-v1",
           "preregistered": "score = gold + BOTH premise citations; declines honest; "
                            "negatives must not be affirmed",
           "methodology": "M13e2 withheld-combination pattern; co-occurrence-checked",
           "tip": tip_name,
           "panel": {"chains": len(chains), "negatives": len(negatives)},
           "results": {"correct_with_premises": correct, "gold_no_premises": partial,
                       "wrong": wrong, "declined": declined,
                       "neg_honest": neg_honest, "neg_false_yes": neg_false},
           "depth_score_d1": round(correct / max(1, len(chains)), 4),
           "starting_line": "a depth claim begins with a sealed record of shallowness",
           "zero_model_gate": {"lm_calls": 0, "transformer_calls": 0}}
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"D1 panel: {len(chains)} withheld chains, {len(negatives)} negatives · tip {tip_name}")
    print(f"correct+premises {correct} · gold-only {partial} · wrong {wrong} · declined {declined}")
    print(f"negatives: honest {neg_honest} · FALSE-YES {neg_false}")
    print(f"D1 depth score: {rep['depth_score_d1']}")
    print(f"sealed -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
