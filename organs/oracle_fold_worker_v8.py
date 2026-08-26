#!/usr/bin/env python3
"""The FOLD WORKER v2 - authoring organ with MECHANIZED FOLD-FAMILY INVENTION.

v2 adds TEMPLATE INDUCTION over the declined-query stream: recurring one-slot
templates (shared prefix+suffix, >=3 distinct anchor fillers) are induced
mechanically, then each template's mapping is learned BY EVIDENCE - fillers are
probed through existing capabilities and only mappings answering >=80% warranted
become candidate routes. Candidates now extend the LATEST ADMITTED w (the w-chain).
"The loop cannot invent fold families" was a one-run observation, not a law.

The daemon (oracle_self_loop_v1) gates continuously and RAISES ITS OWN BAR on every
admission - but nothing authors candidates continuously, so it starves (46 rejections,
2 admissions, then silence). This worker is the missing organ. Every cycle (~2 min):

  HARVEST   - EnsouledWorld: sample the live feed (:8771/feed) - 60 souls thinking on
              the holon; new thoughts are recorded to ensouled_feed_live.jsonl (the
              harness renders them) and a few per cycle enter the curriculum inbox as
              typed surfaces with provenance soul:<id>.
            - the public app's residue (residue_turns.jsonl, non-answered turns).
            - human-pursued gaps (harness_curriculum_queue_v1.jsonl).
  FOLD      cluster unresolved surfaces by a small typed pattern inventory (the
            OPENER-ALIAS family that produced runtime AO). A cluster is real only if
            >= MIN_CLUSTER distinct surfaces match, their topic tails resolve to
            CORPUS ANCHORS, and the head demonstrably FAILS them (probed live).
  AUTHOR    a candidate runtime (oracle_release_runtime_w<N>.py) - an additive
            subclass of the head adding only the clustered alias constructions, each
            conversion recorded with produced_by. Dropped into the daemon's
            candidates/ dir, where the EXISTING gate measures it on held-out within
            a cycle. ADMIT raises the daemon's bar; REJECT is preserved. Either way
            the circuit is complete and visible.

Separation of organs is deliberate: this worker only AUTHORS; the daemon only GATES;
the harness only SHOWS. All worker writes stay inside self_loop/ (oracle-loop-owned):
worker_ledger.jsonl, worker_state.json, ensouled_feed_live.jsonl, and candidates/.
Live service untouched; promotion stays a human signature. No LM calls; no network
beyond loopback. PYTHONHASHSEED=0 recommended.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from oracle_release_runtime import PHASE

LOOP_DIR = PHASE / "self_loop"
CANDIDATES = LOOP_DIR / "candidates"
ADMITTED = LOOP_DIR / "admitted"
WORKER_LEDGER = LOOP_DIR / "worker_ledger.jsonl"
WORKER_STATE = LOOP_DIR / "worker_state.json"
EW_FEED_FILE = LOOP_DIR / "ensouled_feed_live.jsonl"
RESIDUE = Path("/opt/oracle-clm/residue_turns.jsonl")
CURRICULUM = PHASE / "harness_curriculum_queue_v1.jsonl"
SOUL_QUERIES = LOOP_DIR / "soul_queries.jsonl"
ADMITTED_DIR = LOOP_DIR / "admitted"
WORLD_LEDGER = LOOP_DIR / "world_ledger.jsonl"
TARGET_SHAPE = PHASE / "target_shape_v2.json"
LOOP_STATE = LOOP_DIR / "state.json"
EW_URL = "http://127.0.0.1:8771/feed"

CYCLE_SECONDS = 120
MIN_CLUSTER = 3
MAX_PROBES_PER_CYCLE = 20
EW_SAMPLES_PER_CYCLE = 2
WORLD_SAMPLES_PER_CYCLE = 6
FEED_CAP_LINES = 3000

# the typed pattern inventory: the alias family (lineage of runtime AO's constructions)
PATTERNS = [
    ("more_about", r"^more about (?P<t>[a-z][a-z\s\-]{2,40})[.?!]*$", "Summarize {t}."),
    ("what_about", r"^what about (?P<t>[a-z][a-z\s\-]{2,40})[.?!]*$", "Summarize {t}."),
    ("about_bare", r"^about (?P<t>[a-z][a-z\s\-]{2,40})[.?!]*$", "Summarize {t}."),
    ("explain_bare", r"^explain (?P<t>[a-z][a-z\s\-]{2,40})[.?!]*$", "Summarize {t}."),
]

CANDIDATE_TEMPLATE = '''#!/usr/bin/env python3
"""{cand} - worker-authored alias fold (continuous recursive loop).

Learned from {n_surfaces} unresolved surfaces across sources {sources};
clusters: {cluster_names}. Additive successor of the head; every conversion is
recorded with produced_by, and the unchanged chain supplies every answer with its
warrant. Authored {ts} by oracle_fold_worker_v1; judged only by the daemon gate."""

from __future__ import annotations

import re

from oracle_release_runtime_ao import OracleReleaseRuntimeAO

ALIASES = {aliases}
NORM = {norm}                       # witnessed surface -> anchor form, learned only
DEICTIC_SKIP = {{"that", "this", "it", "them", "those", "these", "him", "her"}}


class {cls}(OracleReleaseRuntimeAO):
    """Head + the worker-folded alias constructions. Nothing else changes."""

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        for pat, tmpl in ALIASES:
            m = re.match(pat, s, re.I)
            if m:
                t = m.group("t").strip()
                if t.lower() in DEICTIC_SKIP:
                    break              # deictic reference: the head's own conversion owns it
                t = NORM.get(t.lower(), t)
                probe = tmpl.format(t=t)
                pending = getattr(self, "_pending_conversion", None)
                if pending is None:
                    pending = self._pending_conversion = {{}}
                pending[session_id] = {{
                    "construction": "WORKER_ALIAS", "from": s[:80],
                    "to": probe[:80], "produced_by": "oracle_fold_worker_v1"}}
                return super().chat(probe, session_id)
        return super().chat(s, session_id)
'''


def ledger(event: str, **payload) -> None:
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": event}
    rec.update(payload)
    with WORKER_LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")


def load_state() -> dict:
    try:
        return json.loads(WORKER_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"offsets": {}, "seen": [], "authored": [], "wnum": 0}


def save_state(st: dict) -> None:
    st["seen"] = st.get("seen", [])[-4000:]
    WORKER_STATE.write_text(json.dumps(st, indent=1, sort_keys=True), encoding="utf-8")


def _h(x: str) -> str:
    return hashlib.blake2b(x.encode("utf-8", "replace"), digest_size=8).hexdigest()


def new_lines(path: Path, st: dict, key: str) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    lines = text.splitlines()
    start = int(st.get("offsets", {}).get(key, 0))
    if start > len(lines):
        start = 0
    st.setdefault("offsets", {})[key] = len(lines)
    return lines[start:]


def harvest_ew(st: dict) -> tuple[int, list[dict]]:
    """Sample the live EnsouledWorld feed; record new thoughts; return samples."""
    try:
        with urllib.request.urlopen(EW_URL, timeout=4) as r:
            feed = json.loads(r.read().decode("utf-8", "replace").splitlines()[0])
    except Exception:
        return 0, []
    agents = feed.get("agents") or []
    seen = set(st.get("seen", []))
    fresh = []
    for a in agents:
        thought = " ".join(str(a.get("thought", "")).split())
        if not thought:
            continue
        hh = _h(f"{a.get('id')}|{thought}")
        if hh in seen:
            continue
        seen.add(hh)
        st.setdefault("seen", []).append(hh)
        fresh.append({"ts": int(time.time()), "tick": feed.get("tick"),
                      "soul": str(a.get("id", "?"))[:24],
                      "archetype": str(a.get("archetype", ""))[:16],
                      "thought": thought[:220]})
    if fresh:
        with EW_FEED_FILE.open("a", encoding="utf-8") as f:
            for rec in fresh:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        try:  # cap the feed file
            lines = EW_FEED_FILE.read_text(encoding="utf-8").splitlines()
            if len(lines) > FEED_CAP_LINES:
                EW_FEED_FILE.write_text("\n".join(lines[-FEED_CAP_LINES // 2:]) + "\n",
                                        encoding="utf-8")
        except Exception:
            pass
    return len(agents), fresh[:EW_SAMPLES_PER_CYCLE]


def gather_inbox(st: dict, ew_samples: list[dict]) -> list[dict]:
    inbox = []
    for ln in new_lines(RESIDUE, st, "residue"):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if r.get("status") not in ("answered",):
            inbox.append({"who": "public", "surface": str(r.get("text", ""))[:160]})
    for ln in new_lines(CURRICULUM, st, "curriculum"):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        inbox.append({"who": str(r.get("who", "human")), "surface": str(r.get("label", ""))[:160]})
    for s in ew_samples:
        inbox.append({"who": f"soul:{s['soul']}", "surface": s["thought"][:160]})
    world_new = []
    for ln in new_lines(WORLD_LEDGER, st, "world_ledger"):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if r.get("type") in ("chat", "act") and r.get("content"):
            world_new.append({"who": f"soul:{r.get('actor','?')}",
                              "surface": str(r["content"])[:160]})
    inbox.extend(world_new[:WORLD_SAMPLES_PER_CYCLE])
    out, seen = [], set()
    for item in inbox:
        surf = " ".join(item["surface"].strip().split())
        if not surf:
            continue
        hh = _h("inbox|" + surf.lower())
        if hh in seen or hh in set(st.get("seen", [])):
            continue
        seen.add(hh)
        st.setdefault("seen", []).append(hh)
        out.append({"who": item["who"], "surface": surf})
    return out


def latest_admitted_w() -> tuple[str, str]:
    """(module_name, class_name) of the newest admitted w runtime; falls back to AO."""
    best = 0
    for f in ADMITTED_DIR.glob("oracle_release_runtime_w*.py"):
        try:
            n = int(f.stem.split("_w")[-1])
            best = max(best, n)
        except Exception:
            continue
    if best:
        return (f"oracle_release_runtime_w{best}", f"OracleReleaseRuntimeW{best}")
    return ("oracle_release_runtime_ao", "OracleReleaseRuntimeAO")


def induce_templates(st: dict, head_rt) -> None:
    """Fold-family invention, mechanized: one-slot templates from declined queries,
    mappings learned by evidence."""
    declined = []
    for ln in new_lines(SOUL_QUERIES, st, "soul_queries"):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if not r.get("served") and r.get("route") == "chain":
            q = " ".join(str(r.get("q", "")).lower().split())
            if 8 < len(q) < 120:
                declined.append(q)
    pool = st.setdefault("template_pool", [])
    for q in declined:
        if q not in pool:
            pool.append(q)
    st["template_pool"] = pool[-400:]
    if len(pool) < 6:
        return
    anchors = head_rt.anchors.title_to_page
    groups: dict[tuple, dict] = {}
    words_of = [q.split() for q in pool]
    for i, wi in enumerate(words_of):
        for j in range(i + 1, len(words_of)):
            wj = words_of[j]
            if len(wi) != len(wj) or len(wi) < 3:
                continue
            diff = [k for k in range(len(wi)) if wi[k] != wj[k]]
            if len(diff) != 1:
                continue
            k = diff[0]
            key = (" ".join(wi[:k]), " ".join(wi[k + 1:]))
            g = groups.setdefault(key, {"fillers": set()})
            for w in (wi[k], wj[k]):
                w2 = w.strip(".,?!")
                if w2 in anchors:
                    g["fillers"].add(w2)
    ready = {k: v for k, v in groups.items() if len(v["fillers"]) >= 3}
    if not ready:
        ledger("induction_none", pool=len(pool), groups=len(groups))
        return
    already = set(st.get("induced", []))
    for (pre, suf), g in sorted(ready.items(), key=lambda x: -len(x[1]["fillers"])):
        sig = f"tpl|{pre}|{suf}"
        if sig in already:
            continue
        fillers = sorted(g["fillers"])[:6]
        # INTENT CHECK (w2's rejection lesson): a mapping must address the template's
        # ACT, not merely answer warranted. Templates whose fixed text carries act-verbs
        # outside the knowledge class are preserved as unmapped residuals.
        ACT_MISMATCH = ("name", "call", "feel", "remember", "make", "build",
                        "say", "sing", "want", "wish", "dream")
        fixed_text = f"{pre} {suf}".lower()
        if any(w in fixed_text.split() for w in ACT_MISMATCH):
            st.setdefault("induced", []).append(sig)
            ledger("induction_unmapped", template=f"{pre} _ {suf}", fillers=fillers,
                   best_rate=None, note="act-mismatch: template's act is outside the "
                   "knowledge class; preserved as a residual naming a missing capability")
            continue
        # evidence-based mapping: which capability answers these fillers warranted?
        best_map, best_rate = None, 0.0
        for tmpl in ("What is {t}?", "Summarize {t}."):
            ok = 0
            for t in fillers[:5]:
                try:
                    r = head_rt.chat(tmpl.format(t=t), session_id="induction-probe")
                    if r.get("status") == "answered":
                        ok += 1
                except Exception:
                    pass
            rate = ok / max(1, len(fillers[:5]))
            if rate > best_rate:
                best_map, best_rate = tmpl, rate
        st.setdefault("induced", []).append(sig)
        if best_rate >= 0.8 and best_map:
            pattern = ("^" + re.escape(pre) + r" (?P<t>[a-z][a-z\s\-]{2,40}) " + re.escape(suf) + "$")
            base_mod, base_cls = latest_admitted_w()
            st["wnum"] = int(st.get("wnum", 0)) + 1
            cand = f"oracle_release_runtime_w{st['wnum']}"
            cls = f"OracleReleaseRuntimeW{st['wnum']}"
            src = CANDIDATE_TEMPLATE.format(
                cand=cand, cls=cls,
                aliases=repr([(pattern, best_map)]), norm=repr({}),
                n_surfaces=len(fillers), sources=["soul(induced)"],
                cluster_names=[f"induced:{pre[:20]}...{suf[:20]}"],
                ts=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()))
            src = src.replace(f"from oracle_release_runtime_ao import OracleReleaseRuntimeAO",
                              f"from {base_mod} import {base_cls}")
            src = src.replace(f"class {cls}(OracleReleaseRuntimeAO):",
                              f"class {cls}({base_cls}):")
            CANDIDATES.mkdir(parents=True, exist_ok=True)
            (CANDIDATES / f"{cand}.py").write_text(src, encoding="utf-8")
            ledger("fold_authored", candidate=f"{cand}.py",
                   clusters=[f"induced:{pre[:24]} _ {suf[:24]}"],
                   surfaces=fillers, sources=["template_induction"],
                   evidence_rate=best_rate, mapping=best_map, base=base_mod)
        else:
            ledger("induction_unmapped", template=f"{pre} _ {suf}",
                   fillers=fillers, best_rate=best_rate,
                   note="no existing capability answers >=80% - this is a residual "
                        "naming a MISSING capability, preserved for route authoring")


def attempt_fold(st: dict, inbox: list[dict], head_rt) -> None:
    anchors = head_rt.anchors.title_to_page
    clusters: dict[str, list[dict]] = {}
    probes = 0
    for item in inbox:
        s = item["surface"].lower()
        for name, pat, tmpl in PATTERNS:
            m = re.match(pat, s, re.I)
            if not m:
                continue
            tail = m.group("t").strip()
            if tail in ("that", "this", "it", "them", "those", "these"):
                break
            anchor_form = None
            for form in (tail,
                         tail[:-1] if tail.endswith("s") else None,
                         tail[:-2] if tail.endswith("es") else None):
                if form and form in anchors:
                    anchor_form = form
                    break
            if anchor_form is None:
                break
            item["anchor_form"] = anchor_form
            if probes >= MAX_PROBES_PER_CYCLE:
                break
            probes += 1
            try:
                res = head_rt.chat(item["surface"], session_id="worker-probe")
            except Exception:
                break
            if res.get("status") == "answered":
                break                      # head already handles it: not residue
            clusters.setdefault(name, []).append(item)
            break
    ready = {n: v for n, v in clusters.items()
             if len({x["surface"] for x in v}) >= MIN_CLUSTER}
    if not ready:
        ledger("fold_no_cluster", inbox=len(inbox), probes=probes,
               partial={n: len(v) for n, v in clusters.items()})
        return
    signature = "+".join(sorted(ready))
    if signature in st.get("authored", []):
        ledger("fold_already_authored", signature=signature)
        return
    aliases = [(pat, tmpl) for name, pat, tmpl in PATTERNS if name in ready]
    norm = {}
    for v in ready.values():
        for x in v:
            m2 = None
            for _n, pat, _t in PATTERNS:
                m2 = m2 or re.match(pat, x["surface"].lower(), re.I)
            if m2:
                tail = m2.group("t").strip()
                af = x.get("anchor_form", tail)
                if af != tail:
                    norm[tail] = af
    st["wnum"] = int(st.get("wnum", 0)) + 1
    cand = f"oracle_release_runtime_w{st['wnum']}"
    cls = f"OracleReleaseRuntimeW{st['wnum']}"
    src = CANDIDATE_TEMPLATE.format(
        cand=cand, cls=cls, aliases=repr(aliases), norm=repr(norm),
        n_surfaces=sum(len(v) for v in ready.values()),
        sources=sorted({x["who"].split(":")[0] for v in ready.values() for x in v}),
        cluster_names=sorted(ready), ts=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()))
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    (CANDIDATES / f"{cand}.py").write_text(src, encoding="utf-8")
    st.setdefault("authored", []).append(signature)
    ledger("fold_authored", candidate=f"{cand}.py", clusters=sorted(ready),
           surfaces=[x["surface"][:60] for v in ready.values() for x in v][:8],
           sources=sorted({x["who"] for v in ready.values() for x in v})[:8])


def shape_match() -> None:
    """Match the current measured self against the human-declared target shape.
    The shape steers SALIENCE (what the worker attends to), never admission -
    the daemon's bar remains the floor. Ledgered once per cycle when computable."""
    try:
        shape = json.loads(TARGET_SHAPE.read_text(encoding="utf-8"))
        st = json.loads(LOOP_STATE.read_text(encoding="utf-8"))
        base = st.get("baseline") or {}
    except Exception:
        return
    dims = shape.get("matched_dimensions") or {}
    weights = shape.get("weights") or {}
    report, weighted = {}, 0.0
    for dim, spec in dims.items():
        cur = base.get(dim)
        if cur is None:
            continue
        target = float(spec.get("target", 0)) or 1.0
        gap = max(0.0, (target - float(cur)) / target)
        report[dim] = {"current": cur, "target": spec.get("target"),
                       "gap": round(gap, 4)}
        # shape v2 stores weight INSIDE each dimension; top-level map is legacy
        weighted += float(spec.get("weight", weights.get(dim, 0.0))) * gap
    if report:
        largest = max(report, key=lambda d: report[d]["gap"])
        ledger("shape_match", declared_by=shape.get("declared_by"),
               dims=report, weighted_distance=round(weighted, 4),
               attend_first=largest)


# ── FOLD FAMILIES: combination · efficiency · regenerative · corpus-mining ──────
# Ben's directive 2026-08-25: the system produces actual folds. One candidate per
# cycle from this queue; each verified-before-author (the head must demonstrably
# lack the capability); each chained on the LATEST ADMITTED w; the daemon judges.
# Laws respected: compose transitivity never inheritance (M37); rejected never
# repaired; every answer cited or derived; conversions recorded.

MADE_OF_TEMPLATE = '''#!/usr/bin/env python3
"""{cand} - CORPUS-MINING fold: the made-of relation, mined from the admitted record.

{n_pairs} subject->material pairs extracted from attested sentences ("X is made of Y"),
each answer citing its source claim. Mined {ts} by oracle_fold_worker_v3 from the bench
corpus; subjects verified against anchors; the head demonstrably failed the question
form before authoring. Chained on {base_mod}. Judged only by the daemon gate."""

from __future__ import annotations

import re

from {base_mod} import {base_cls}

MADE_OF = {pairs}

MADE_RX = re.compile(
    r"^what (?:is|are) (?:the )?(?P<t>[a-z][\\w \\-']{{1,40}}?) made (?:of|from)[?.! ]*$",
    re.I)


class {cls}({base_cls}):
    """Base + the mined made-of route. Fires only when the record holds the pair."""

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        m = MADE_RX.match(s)
        if m:
            key = m.group("t").strip().lower()
            hit = MADE_OF.get(key) or MADE_OF.get(key.rstrip("s"))
            if hit:
                material, claim, title = hit
                pending = getattr(self, "_pending_conversion", None)
                if pending is None:
                    pending = self._pending_conversion = {{}}
                pending[session_id] = {{
                    "construction": "CORPUS_MADE_OF", "from": s[:80],
                    "to": f"made_of({{key}})", "produced_by": "oracle_fold_worker_v3"}}
                return {{"status": "answered", "path": "worker:made_of",
                         "response": f"According to {{title}}, {{key}} is made of "
                                     f"{{material}}. [{{claim}}]",
                         "provenance": {{"kind": "corpus_relation",
                                         "relation": "made_of", "claim_id": claim}},
                         "latency_ms": 1}}
        return super().chat(s, session_id)
'''

REGEN_TEMPLATE = '''#!/usr/bin/env python3
"""{cand} - REGENERATIVE fold: withhold-recovery via bounded typed transforms.

When the chain withholds or clarifies, attempt at most two typed surface transforms
(strip leading article; singularize the final content word) and retry once each.
A recovery answers with the conversion RECORDED (construction REGEN) - the plural
gap discovered 2026-08-24 ("Summarize bees." failing beside the bee page),
generalized into an organ. Never fires on answered turns; never invents content -
the unchanged chain supplies every recovered answer with its warrant.
Authored {ts} by oracle_fold_worker_v3, chained on {base_mod}."""

from __future__ import annotations

import re

from {base_mod} import {base_cls}

_WORD = re.compile(r"[A-Za-z][A-Za-z'\\-]*")


def _transforms(s: str):
    out = []
    low = s.lower()
    if low.startswith("the "):
        out.append(s[4:])
    words = s.rstrip(".?! ").split()
    if words:
        last = words[-1]
        if len(last) > 4 and last.lower().endswith("es"):
            out.append(" ".join(words[:-1] + [last[:-2]]) + s[len(s.rstrip(".?! ")):])
        elif len(last) > 3 and last.lower().endswith("s"):
            out.append(" ".join(words[:-1] + [last[:-1]]) + s[len(s.rstrip(".?! ")):])
    seen = set()
    for t in out:
        t = " ".join(t.split())
        if t and t.lower() != low and t not in seen:
            seen.add(t)
            yield t


class {cls}({base_cls}):
    """Base + withhold-recovery. Two bounded retries, conversions recorded."""

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        result = super().chat(s, session_id)
        if result.get("status") not in ("withheld", "clarification"):
            return result
        for probe in list(_transforms(s))[:2]:
            pending = getattr(self, "_pending_conversion", None)
            if pending is None:
                pending = self._pending_conversion = {{}}
            pending[session_id] = {{
                "construction": "REGEN", "from": s[:80], "to": probe[:80],
                "produced_by": "oracle_fold_worker_v3"}}
            retry = super().chat(probe, session_id)
            if retry.get("status") == "answered":
                return retry
        return result
'''

REPLAY_TEMPLATE = '''#!/usr/bin/env python3
"""{cand} - EFFICIENCY fold: verified answer replay (same warrant, fraction of cost).

A bounded cache of answered-with-citation results, keyed by the normalized surface.
A repeat question replays the EXACT prior answer with identical citations and
provenance kind "verified_replay" naming the original claim ids - deterministic,
auditable, never a paraphrase. The cat lesson as a runtime letter: identical yield,
fewer steps. Capacity {cap}; answered-only; citation-bearing only.
Authored {ts} by oracle_fold_worker_v3, chained on {base_mod}."""

from __future__ import annotations

import re

from {base_mod} import {base_cls}

_CITE = re.compile(r"\\[[\\w:.'\\-]{{4,}}\\]")
_CAP = {cap}


class {cls}({base_cls}):
    """Base + verified replay. First answer is computed; repeats are replayed."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._replay = {{}}

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        key = s.lower()
        hit = self._replay.get(key)
        if hit is not None:
            out = dict(hit)
            out["provenance"] = {{"kind": "verified_replay",
                                  "of_claims": _CITE.findall(str(hit.get("response", "")))[:6],
                                  "note": "deterministic replay of a prior verified answer"}}
            return out
        result = super().chat(s, session_id)
        if (result.get("status") == "answered"
                and _CITE.search(str(result.get("response", "")))):
            if len(self._replay) >= _CAP:
                self._replay.pop(next(iter(self._replay)))
            self._replay[key] = {{"status": result.get("status"),
                                  "path": result.get("path"),
                                  "response": result.get("response"),
                                  "latency_ms": 1}}
        return result
'''

COMBO_TEMPLATE = '''#!/usr/bin/env python3
"""{cand} - COMBINATION fold: two-hop made-of composition with premise chains.

made_of(X)=Y and made_of(Y)=Z compose transitively (the M37 law: transitivity is the
sound direction; inheritance is not composed). {n_pairs} two-hop chains computed at
author time from the admitted made-of relation; every answer carries BOTH premise
claim ids. Answers "what is X ultimately made of?".
Authored {ts} by oracle_fold_worker_v3, chained on {base_mod}."""

from __future__ import annotations

import re

from {base_mod} import {base_cls}

CHAIN2 = {pairs}

ULT_RX = re.compile(
    r"^what (?:is|are) (?:the )?(?P<t>[a-z][\\w \\-']{{1,40}}?) ultimately made "
    r"(?:of|from)[?.! ]*$", re.I)


class {cls}({base_cls}):
    """Base + the composed two-hop made-of route."""

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        m = ULT_RX.match(s)
        if m:
            key = m.group("t").strip().lower()
            hit = CHAIN2.get(key) or CHAIN2.get(key.rstrip("s"))
            if hit:
                mid, final, c1, c2 = hit
                pending = getattr(self, "_pending_conversion", None)
                if pending is None:
                    pending = self._pending_conversion = {{}}
                pending[session_id] = {{
                    "construction": "MADE_OF_2HOP", "from": s[:80],
                    "to": f"made_of(made_of({{key}}))",
                    "produced_by": "oracle_fold_worker_v3"}}
                return {{"status": "answered", "path": "worker:made_of_2hop",
                         "response": f"In steps: {{key}} is made of {{mid}} [{{c1}}]; "
                                     f"{{mid}} is made of {{final}} [{{c2}}]. So {{key}} "
                                     f"is ultimately made of {{final}}.",
                         "provenance": {{"kind": "derived", "rule": "transitive_made_of",
                                         "premises": [c1, c2]}},
                         "latency_ms": 1}}
        return super().chat(s, session_id)
'''


def _mine_made_of(head_rt, cap=1200):
    """Extract (subject -> material, claim, title) from attested sentences."""
    import sqlite3
    import stage5m13e7_benchfold_induction_v1 as bench_mod
    uri = bench_mod.DB.resolve().as_uri() + "?mode=ro&immutable=1"
    con = sqlite3.connect(uri, uri=True)
    rx = re.compile(r"^(?:The |A |An )?(?P<x>[A-Za-z][\w \-']{1,36}?) (?:is|are) "
                    r"(?:composed of|made of|made up of|made from) "
                    r"(?P<y>[a-z][\w ,\-']{2,70}?)[.;]", re.I)
    anchors = head_rt.anchors.title_to_page
    pairs = {}
    rows = con.execute(
        "SELECT s.claim_id, s.fact, s.page_id FROM source_rows s "
        "WHERE s.fact MATCH '\"made of\" OR \"composed of\" OR \"made from\"' "
        "LIMIT 6000").fetchall()
    titles = {}
    for claim, fact, page in rows:
        m = rx.match(str(fact))
        if not m:
            continue
        x = m.group("x").strip().lower()
        y = " ".join(m.group("y").strip().split())[:70]
        if x in pairs or (x not in anchors and x.rstrip("s") not in anchors):
            continue
        if page not in titles:
            t = con.execute("SELECT title FROM article WHERE page_id=?",
                            (page,)).fetchone()
            titles[page] = t[0] if t else "the record"
        pairs[x] = (y, claim, titles[page])
        if len(pairs) >= cap:
            break
    con.close()
    return pairs


def _author(st, cand_src, family, note):
    st["wnum"] = int(st.get("wnum", 0)) + 1
    cand = f"oracle_release_runtime_w{st['wnum']}"
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    (CANDIDATES / f"{cand}.py").write_text(cand_src, encoding="utf-8", newline="\n")
    st.setdefault("families", {})[family] = f"{cand}.py"
    ledger("fold_authored", candidate=f"{cand}.py", clusters=[f"family:{family}"],
           sources=["fold_families"], note=note)
    return cand


def family_folds(st, head_rt) -> None:
    """Author at most ONE family candidate per cycle, verified-before-author."""
    done = st.get("families", {})
    base_mod, base_cls = latest_admitted_w()
    ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

    if "corpus_made_of" not in done:
        try:
            pairs = _mine_made_of(head_rt)
        except Exception as e:
            ledger("family_error", family="corpus_made_of",
                   error=f"{type(e).__name__}: {e}")
            return
        if len(pairs) < 25:
            ledger("family_skipped", family="corpus_made_of",
                   reason=f"only {len(pairs)} mined pairs")
        else:
            sample = list(pairs)[:3]
            fails = sum(
                1 for x in sample
                if head_rt.chat(f"What is {x} made of?",
                                session_id="fam-probe").get("status") != "answered")
            if fails < 2:
                ledger("family_skipped", family="corpus_made_of",
                       reason="head already answers the form")
            else:
                st["wnum"] = int(st.get("wnum", 0))
                cls = f"OracleReleaseRuntimeW{st['wnum'] + 1}"
                src = MADE_OF_TEMPLATE.format(
                    cand=f"oracle_release_runtime_w{st['wnum'] + 1}",
                    cls=cls, base_mod=base_mod, base_cls=base_cls,
                    pairs=repr(pairs), n_pairs=len(pairs), ts=ts)
                _author(st, src, "corpus_made_of",
                        f"{len(pairs)} mined pairs; head failed {fails}/3 probes")
        return

    if "regen_recovery" not in done:
        probe = head_rt.chat("Summarize bees.", session_id="fam-probe")
        if probe.get("status") == "answered":
            ledger("family_skipped", family="regen_recovery",
                   reason="head already recovers plural surfaces")
        else:
            st["wnum"] = int(st.get("wnum", 0))
            cls = f"OracleReleaseRuntimeW{st['wnum'] + 1}"
            src = REGEN_TEMPLATE.format(
                cand=f"oracle_release_runtime_w{st['wnum'] + 1}",
                cls=cls, base_mod=base_mod, base_cls=base_cls, ts=ts)
            _author(st, src, "regen_recovery",
                    "withhold-recovery via strip-article + singularize, 2 retries max")
        return

    if "replay_efficiency" not in done:
        st["wnum"] = int(st.get("wnum", 0))
        cls = f"OracleReleaseRuntimeW{st['wnum'] + 1}"
        src = REPLAY_TEMPLATE.format(
            cand=f"oracle_release_runtime_w{st['wnum'] + 1}",
            cls=cls, base_mod=base_mod, base_cls=base_cls, ts=ts, cap=4000)
        _author(st, src, "replay_efficiency",
                "verified answer replay, cap 4000, citation-bearing only")
        return

    if "combo_madeof_2hop" not in done:
        made = done.get("corpus_made_of", "")
        admitted_file = ADMITTED / made
        if not made or not admitted_file.exists():
            ledger("family_waiting", family="combo_madeof_2hop",
                   reason="requires corpus_made_of ADMITTED first")
            return
        import importlib
        mo = importlib.import_module(made[:-3]).MADE_OF
        chains = {}
        for x, (y, c1, _t1) in mo.items():
            ykey = y.strip().lower().split(",")[0].split(" and ")[0].strip()
            hit = mo.get(ykey) or mo.get(ykey.rstrip("s"))
            if hit and ykey != x:
                z, c2, _t2 = hit
                chains[x] = (ykey, z, c1, c2)
            if len(chains) >= 400:
                break
        if len(chains) < 5:
            ledger("family_skipped", family="combo_madeof_2hop",
                   reason=f"only {len(chains)} composable chains")
            st.setdefault("families", {})["combo_madeof_2hop"] = "skipped"
        else:
            st["wnum"] = int(st.get("wnum", 0))
            cls = f"OracleReleaseRuntimeW{st['wnum'] + 1}"
            src = COMBO_TEMPLATE.format(
                cand=f"oracle_release_runtime_w{st['wnum'] + 1}",
                cls=cls, base_mod=base_mod, base_cls=base_cls,
                pairs=repr(chains), n_pairs=len(chains), ts=ts)
            _author(st, src, "combo_madeof_2hop",
                    f"{len(chains)} transitive 2-hop chains with premise pairs")
        return


# ── REGION FOLDS: hippocampus (episodic) · basal ganglia (habit, witnessed) ─────
# Per REGION_FOLD_MAP_2026_08_25.md. Episodic acquisition = CONSOLIDATION: the fold
# is re-authored each epoch from the fresh world ledger, every epoch gate-judged.
# Habit = w5's replay repaired under the mapping law: a replay EMITS ITS OWN WITNESS.

EPISODIC_TEMPLATE = '''#!/usr/bin/env python3
"""{cand} - HIPPOCAMPUS fold: episodic binding from the world ledger (epoch {epoch}).

{n_actors} actors' episode lists and {n_kinds} object->builder indexes, bound as
(actor, act, object, tick) from attested world-ledger records - the same warrant class
as the scarcity route (observed-complete since world launch). Answers "what has X
done?" / "what happened with X?" / "who built a Y?". ACQUISITION IS CONSOLIDATION:
the worker re-authors this fold each epoch from the fresh ledger; every epoch passes
the gate; unreferenced episodes fade by cap. Authored {ts} by oracle_fold_worker_v4,
chained on {base_mod}."""

from __future__ import annotations

import re

from {base_mod} import {base_cls}

EPI = {epi}

WHO = {who}

EPI_RX = re.compile(
    r"^(?:what (?:has|have) (?P<a>[\\w'\\- ]{{2,24}}?) (?:done|been doing)"
    r"|what happened (?:with|to) (?P<b>[\\w'\\- ]{{2,24}}?))[?.! ]*$", re.I)
WHO_RX = re.compile(
    r"^who (?:built|made|raised) (?:a |an |the )?(?P<k>[\\w \\-]{{2,24}}?)[?.! ]*$", re.I)


class {cls}({base_cls}):
    """Base + episodic recall. Fires only on bound episodes; else the chain answers."""

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        m = EPI_RX.match(s)
        if m:
            actor = (m.group("a") or m.group("b") or "").strip().lower()
            eps = EPI.get(actor)
            if eps:
                bits = "; ".join(f"at tick {{t}} {{v}} {{o}}" for t, v, o in eps[-5:])
                pending = getattr(self, "_pending_conversion", None)
                if pending is None:
                    pending = self._pending_conversion = {{}}
                pending[session_id] = {{"construction": "EPISODIC_RECALL",
                                        "from": s[:80], "to": f"episodes({{actor}})",
                                        "produced_by": "oracle_fold_worker_v4"}}
                return {{"status": "answered", "path": "worker:episodic",
                         "response": f"The record holds for {{actor}}: {{bits}}. "
                                     f"[world_ledger_ew2]",
                         "provenance": {{"kind": "episodic_ledger", "actor": actor,
                                         "episodes": len(eps)}},
                         "latency_ms": 1}}
        w = WHO_RX.match(s)
        if w:
            kind = w.group("k").strip().lower()
            hits = WHO.get(kind) or WHO.get(kind.rstrip("s"))
            if hits:
                bits = ", ".join(f"{{a}} (tick {{t}})" for a, t in hits[-4:])
                return {{"status": "answered", "path": "worker:episodic_who",
                         "response": f"By the world record, {{kind}}s were raised by "
                                     f"{{bits}}. [world_ledger_ew2]",
                         "provenance": {{"kind": "episodic_ledger", "object": kind}},
                         "latency_ms": 1}}
        return super().chat(s, session_id)
'''

HABIT_TEMPLATE = '''#!/usr/bin/env python3
"""{cand} - BASAL GANGLIA fold v3: witnessed AND context-free replay only.

Two gate lessons encoded: w5 (habits must stay witnessed) and w7 (habits may only
form over CONTEXT-FREE steps - replaying a state-dependent turn is semantically
wrong; continuity collapsed 149->58). Cache admits only non-act, deictic-free,
conversion-free answered turns with citations.

w5 was refused because its replays skipped the transition record - an optimization
that made the machine faster by making it less witnessed, caught by the gate. This
version emits a full witness record for every replay (operator worker:verified_replay)
so the step stays explicitly mapped. Same yield, fewer steps, nothing invisible.
Cap {cap}; answered-with-citation results only.
Authored {ts} by oracle_fold_worker_v4, chained on {base_mod}."""

from __future__ import annotations

import re
import time as _time
from collections import deque as _deque

from {base_mod} import {base_cls}

_CITE = re.compile(r"\\[[\\w:.'\\-]{{4,}}\\]")
_DEICTIC = re.compile(
    r"\\b(?:this|that|these|those|here|there|it|they|them|previous|earlier|"
    r"again|you|your|my|me|we|our|now|then)\\b", re.I)
_CAP = {cap}


class {cls}({base_cls}):
    """Base + witnessed replay: the habit records itself like every other step."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._replay = {{}}

    def _witness_replay(self, session_id, surface, response):
        hist = getattr(self, "_paths", None)
        if hist is None:
            hist = self._paths = {{}}
        q = hist.setdefault(session_id, _deque(maxlen=64))
        prev_turn = q[-1]["turn"] if q else 0
        q.append({{"turn": prev_turn + 1, "in_surface": str(surface)[:120],
                   "in_form": ["replay"], "operator": "worker:verified_replay",
                   "out_status": "answered", "in_terms": [], "out_terms": [],
                   "relation": {{"grounded": [], "grounded_cited": [],
                                 "introduced": [], "unaccounted": []}},
                   "carried_from_prior": [], "continuity_lexical": False,
                   "continuity": False,
                   "citations": len(_CITE.findall(str(response))),
                   "residual": None, "cost_ms": 0.2,
                   "conversion": {{"construction": "VERIFIED_REPLAY",
                                   "from": str(surface)[:80], "to": "replay",
                                   "produced_by": "oracle_fold_worker_v4"}}}})

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        key = s.lower()
        hit = self._replay.get(key)
        if hit is not None:
            out = dict(hit)
            out["provenance"] = {{"kind": "verified_replay",
                                  "of_claims": _CITE.findall(str(hit.get("response", "")))[:6]}}
            self._witness_replay(session_id, s, out.get("response", ""))
            return out
        result = super().chat(s, session_id)
        path = str(result.get("path") or "")
        context_free = (not path.startswith("act:")
                        and not _DEICTIC.search(s)
                        and result.get("conversion") is None)
        if (context_free and result.get("status") == "answered"
                and _CITE.search(str(result.get("response", "")))):
            if len(self._replay) >= _CAP:
                self._replay.pop(next(iter(self._replay)))
            self._replay[key] = {{"status": "answered", "path": path,
                                  "response": result.get("response"),
                                  "latency_ms": 1}}
        return result
'''


def _mine_episodes(cap_actors=300, per_actor=10):
    epi, who = {}, {}
    try:
        lines = (LOOP_DIR / "world_ledger_ew2.jsonl").read_text(
            encoding="utf-8", errors="replace").strip().splitlines()[-8000:]
    except Exception:
        return epi, who
    for ln in lines:
        try:
            r = json.loads(ln)
        except Exception:
            continue
        actor = str(r.get("actor", "")).strip().lower()
        if not actor:
            continue
        tick = r.get("tick") or 0
        typ = r.get("type")
        if typ == "build" and r.get("kind"):
            kind = str(r["kind"]).lower()
            obj = f"raised a {kind}"
            who.setdefault(kind, [])
            if len(who[kind]) < 8:
                who[kind].append((actor, tick))
        elif typ == "act":
            obj = f"{r.get('verb', 'acted')}: {str(r.get('content', ''))[:40]}"
        elif typ == "lineage":
            obj = f"came to be ({r.get('verb')})"
        elif typ == "chat":
            obj = f"said: {str(r.get('content', ''))[:40]}"
        else:
            continue
        lst = epi.setdefault(actor, [])
        lst.append((tick, typ if typ != "build" else "make", obj))
        if len(lst) > per_actor:
            del lst[0]
        if len(epi) > cap_actors:
            break
    return epi, who


def _pending_candidate() -> bool:
    try:
        return any(CANDIDATES.glob("oracle_release_runtime_w*.py"))
    except Exception:
        return False


def region_folds(st, head_rt) -> bool:
    """Author at most one region fold per cycle. Returns True if authored."""
    if _pending_candidate():
        ledger("author_waiting_gate", note="one candidate in flight; linear chain preserved")
        return True

    done = st.get("families", {})
    base_mod, base_cls = latest_admitted_w()
    ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    now = time.time()

    epoch_due = ("episodic_hippocampus" in done
                 and now - st.get("epi_epoch_ts", 0) > 21600)
    if "episodic_hippocampus" not in done or epoch_due:
        epi, who = _mine_episodes()
        if len(epi) < 10:
            ledger("family_skipped", family="episodic_hippocampus",
                   reason=f"only {len(epi)} actors mined")
        else:
            sample = list(epi)[:2]
            fails = sum(
                1 for a in sample
                if head_rt.chat(f"What has {a} done?",
                                session_id="fam-probe").get("status") != "answered")
            if fails < 1 and "episodic_hippocampus" not in done:
                ledger("family_skipped", family="episodic_hippocampus",
                       reason="head already answers episodic forms")
            else:
                st["wnum"] = int(st.get("wnum", 0))
                epoch = st.get("epi_epoch_n", 0) + 1
                cls = f"OracleReleaseRuntimeW{st['wnum'] + 1}"
                src = EPISODIC_TEMPLATE.format(
                    cand=f"oracle_release_runtime_w{st['wnum'] + 1}",
                    cls=cls, base_mod=base_mod, base_cls=base_cls,
                    epi=repr(epi), who=repr(who), n_actors=len(epi),
                    n_kinds=len(who), ts=ts, epoch=epoch)
                _author(st, src, "episodic_hippocampus",
                        f"epoch {epoch}: {len(epi)} actors, {len(who)} kinds; "
                        f"consolidation from fresh ledger")
                st["epi_epoch_ts"] = now
                st["epi_epoch_n"] = epoch
                return True
        return False

    if "habit_replay_v3" not in done:
        st["wnum"] = int(st.get("wnum", 0))
        cls = f"OracleReleaseRuntimeW{st['wnum'] + 1}"
        src = HABIT_TEMPLATE.format(
            cand=f"oracle_release_runtime_w{st['wnum'] + 1}",
            cls=cls, base_mod=base_mod, base_cls=base_cls, ts=ts, cap=4000)
        _author(st, src, "habit_replay_v3",
                "witnessed + context-free only (w5 and w7 lessons encoded)")
        return True
    return False


# ── META FOLDS: potentials · self-improvement · open-ended conversation ─────────
# Ben's directive 2026-08-25: recursive self-improvement of intelligence over what is
# KNOWN and what is POTENTIALLY POSSIBLE. Three organs, each epoch-consolidated (like
# the hippocampus) so their content is always the fresh ledger, every epoch gated:
#   potentials      - the typed space of what could become capable, with sources
#   self_improve    - the loop speaking about itself FROM ITS LEDGERS (admissions,
#                     refusals WITH REASONS - the read-the-reasons law as capability)
#   open_converse   - grounded continuation: anchor-verified doors as a runtime route

POTENTIALS_TEMPLATE = '''#!/usr/bin/env python3
"""{cand} - POTENTIALS fold (epoch {epoch}): the typed space of the possible.

{n_pot} potentials bound from live sources: the self-model's declared gaps, the
human-signed target-shape distances, pending fold families, unmapped induced templates
(residuals naming missing capabilities), and refused candidates whose lessons are
encoded. A potential CONVERTS to an actual when a fold family admits - the conversion
rate across epochs is the measurable throughput of self-improvement.
Authored {ts} by oracle_fold_worker_v6, chained on {base_mod}."""

from __future__ import annotations

import re

from {base_mod} import {base_cls}

POTENTIALS = {potentials}

POT_RX = re.compile(
    r"(what (?:could|can) you (?:learn|become)|what are your potentials"
    r"|what is potentially possible|what might you become)", re.I)


class {cls}({base_cls}):
    """Base + the potentials route."""

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        if POT_RX.search(s):
            bits = "; ".join(f"{{p['kind']}}: {{p['name']}}" for p in POTENTIALS[:6])
            return {{"status": "answered", "path": "worker:potentials",
                     "response": f"By my own ledgers, {{len(POTENTIALS)}} typed "
                                 f"potentials stand open, among them {{bits}}. Each "
                                 f"converts to an actual only through the gate. "
                                 f"[potentials_epoch_{epoch}]",
                     "provenance": {{"kind": "potentials_ledger", "epoch": {epoch},
                                     "count": len(POTENTIALS)}},
                     "latency_ms": 1}}
        return super().chat(s, session_id)
'''

SELF_IMPROVE_TEMPLATE = '''#!/usr/bin/env python3
"""{cand} - SELF-IMPROVEMENT fold (epoch {epoch}): the loop speaking from its ledgers.

Answers "how do you improve?" / "what did you learn recently?" / "what was refused
and why?" from the actual admission and rejection records - including refusal REASONS,
because the read-the-reasons law is now a capability, not just a discipline. Robustness
is queryable: the bar never falls, refusals are preserved, every step is witnessed.
Authored {ts} by oracle_fold_worker_v6, chained on {base_mod}."""

from __future__ import annotations

import re

from {base_mod} import {base_cls}

RECENT_ADMITS = {admits}
RECENT_REFUSALS = {refusals}

HOW_RX = re.compile(r"(how do you (?:improve|learn)|how does your improvement work)", re.I)
LEARNED_RX = re.compile(r"(what (?:did|have) you learn(?:ed)?( recently)?)", re.I)
REFUSED_RX = re.compile(r"(what was (?:refused|rejected)( and why)?)", re.I)


class {cls}({base_cls}):
    """Base + the improvement-ledger routes."""

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        if HOW_RX.search(s):
            return {{"status": "answered", "path": "worker:self_improve",
                     "response": "A worker authors candidate folds from residue - "
                                 "mined relations, induced templates, world episodes; "
                                 "a gate measures each on held-out and admits only "
                                 "no-regression; the bar rises with each admission and "
                                 "never falls; refusals are preserved with reasons; "
                                 "every step is witnessed. [improvement_ledger]",
                     "provenance": {{"kind": "improvement_ledger", "epoch": {epoch}}},
                     "latency_ms": 1}}
        if LEARNED_RX.search(s):
            bits = "; ".join(RECENT_ADMITS[:4]) or "no recent admissions"
            return {{"status": "answered", "path": "worker:self_improve",
                     "response": f"Recently admitted: {{bits}}. [improvement_ledger]",
                     "provenance": {{"kind": "improvement_ledger", "epoch": {epoch}}},
                     "latency_ms": 1}}
        if REFUSED_RX.search(s):
            bits = "; ".join(RECENT_REFUSALS[:3]) or "no recent refusals"
            return {{"status": "answered", "path": "worker:self_improve",
                     "response": f"Refused, with reasons preserved: {{bits}}. "
                                 f"[improvement_ledger]",
                     "provenance": {{"kind": "improvement_ledger", "epoch": {epoch}}},
                     "latency_ms": 1}}
        return super().chat(s, session_id)
'''

CONVERSE_TEMPLATE = '''#!/usr/bin/env python3
"""{cand} - OPEN-ENDED CONVERSATION fold: grounded continuation as a runtime route.

"What should we talk about?" answered from the live dialogue state: the last answered
turn's introduced terms, filtered to CORPUS ANCHORS (doors that actually open), plus a
standing potential from the improvement ledger. Open-endedness with warrant: every
offered continuation is a door the record can walk through. Continuations taken are
recorded via conversions - the acquisition signal for later epochs.
Authored {ts} by oracle_fold_worker_v6, chained on {base_mod}."""

from __future__ import annotations

import re

from {base_mod} import {base_cls}

CONV_RX = re.compile(
    r"(what should we (?:talk|speak) about|what can we explore"
    r"|where should we go next|what else is there)", re.I)
_MONTHS = {{"january", "february", "march", "april", "may", "june", "july",
            "august", "september", "october", "november", "december"}}


class {cls}({base_cls}):
    """Base + grounded continuation offers."""

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        if CONV_RX.search(s):
            doors = []
            try:
                anchors = self.anchors.title_to_page
                for rec in reversed(list(self.path(session_id))):
                    if rec.get("out_status") != "answered":
                        continue
                    for t in (rec.get("relation", {{}}).get("introduced") or []):
                        tl = str(t).lower()
                        if (4 <= len(tl) < 30 and tl in anchors
                                and tl not in _MONTHS and tl not in doors):
                            doors.append(tl)
                    if len(doors) >= 3:
                        break
            except Exception:
                pass
            if doors:
                offer = ", ".join(doors[:3])
                resp = (f"From where we stand, the record opens doors to: {{offer}}. "
                        f"Name one and I will ground it. [dialogue_state]")
            else:
                resp = ("Nothing is introduced yet - ground a topic first and I will "
                        "offer the doors it opens. [dialogue_state]")
            return {{"status": "answered", "path": "worker:open_converse",
                     "response": resp,
                     "provenance": {{"kind": "dialogue_state", "doors": doors[:3]}},
                     "latency_ms": 1}}
        return super().chat(s, session_id)
'''


CHARTER = PHASE / "capability_charter_v1.json"


def _mine_potentials(st):
    pot = []
    try:
        charter = json.loads(CHARTER.read_text(encoding="utf-8"))
        for cname, cap in (charter.get("capabilities") or {}).items():
            for ms in cap.get("milestones", []):
                status = str(ms.get("status", ""))
                if status.startswith(("OPEN", "EMBRYONIC", "PARTIAL", "UNVERIFIED")):
                    pot.append({"kind": "charter_milestone",
                                "name": f"{cname}.{ms['id']}: "
                                        f"{str(ms.get('definition',''))[:60]}"})
    except Exception:
        pass
    try:
        loop_state = json.loads(LOOP_STATE.read_text(encoding="utf-8"))
        for v in (loop_state.get("last_gaps") or {}).values():
            if isinstance(v, list):
                for g in v[:6]:
                    pot.append({"kind": "declared_gap", "name": str(g)[:70]})
    except Exception:
        pass
    try:
        shape = json.loads(TARGET_SHAPE.read_text(encoding="utf-8"))
        base = json.loads(LOOP_STATE.read_text(encoding="utf-8")).get("baseline", {})
        for dim, spec in (shape.get("matched_dimensions") or {}).items():
            cur = base.get(dim)
            if cur is None and spec.get("instrument"):
                pot.append({"kind": "instrument_missing",
                            "name": f"{dim}: build the measure ({str(spec.get('meaning',''))[:50]})"})
            elif cur is not None and float(cur) < float(spec.get("target", 0)):
                pot.append({"kind": "shape_distance",
                            "name": f"{dim} {cur} -> {spec.get('target')}"})
    except Exception:
        pass
    done = st.get("families", {})
    for fam in ("combo_madeof_2hop", "habit_replay_v3", "w_inhibit_pfc",
                "w_calibrate_cerebellum", "mining_used_for", "mining_causes"):
        if fam not in done:
            pot.append({"kind": "pending_family", "name": fam})
    try:
        for ln in WORKER_LEDGER.read_text(encoding="utf-8").splitlines()[-400:]:
            if '"induction_unmapped"' in ln:
                r = json.loads(ln)
                pot.append({"kind": "unmapped_template",
                            "name": str(r.get("template", ""))[:60]})
    except Exception:
        pass
    return pot[:30]


def _ledger_digest():
    admits, refusals = [], []
    try:
        daemon = (LOOP_DIR / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
        for ln in daemon[-300:]:
            if '"event": "gate"' not in ln:
                continue
            r = json.loads(ln)
            cand = str(r.get("candidate", ""))[:34]
            if r.get("decision") == "ADMIT":
                admits.append(f"{cand} admitted")
            else:
                reason = str(r.get("reasons"))[:90]
                refusals.append(f"{cand}: {reason}")
    except Exception:
        pass
    return admits[-5:][::-1], refusals[-4:][::-1]


REFLECT_TEMPLATE = '''#!/usr/bin/env python3
"""{cand} - REFLECTION + TURN CONTINUATION fold: the witness as mirror, every turn forward-edged.

Two capabilities in one letter (Ben's directive 2026-08-25):
SELF-REFLECTION: "reflect" / "how is this conversation going" / "what have you failed
at here" answered FROM THE SESSION'S OWN WITNESS PATH - answered/declined counts,
conversions used, standing residuals, doors opened. Reflection with warrant: the
witness is the substrate, nothing is self-flattery. Loop-level reflection composes
from the self-improvement fold already in this chain.
TURN CONTINUATION: every answered turn carries result["continuation"] =
{{"doors": [...], "offer": "..."}} - introduced terms filtered to corpus anchors,
a structural forward edge on every step. The response text is NEVER mutated
(witness fidelity); surfaces opt in to render or speak the offer.
Authored {ts} by oracle_fold_worker_v6, chained on {base_mod}."""

from __future__ import annotations

import re

from {base_mod} import {base_cls}

REFL_RX = re.compile(
    r"(^reflect |^reflect$\b|how is this conversation going|what have you failed at"
    r"|reflect on (?:this|the) conversation|how are we doing)", re.I)
_MONTHS2 = {{"january", "february", "march", "april", "may", "june", "july",
             "august", "september", "october", "november", "december"}}


class {cls}({base_cls}):
    """Base + witness reflection + structural turn continuation."""

    def _doors_from(self, session_id):
        doors = []
        try:
            anchors = self.anchors.title_to_page
            for rec in reversed(list(self.path(session_id))):
                if rec.get("out_status") != "answered":
                    continue
                for t in (rec.get("relation", {{}}).get("introduced") or []):
                    tl = str(t).lower()
                    if (4 <= len(tl) < 30 and tl in anchors
                            and tl not in _MONTHS2 and tl not in doors):
                        doors.append(tl)
                if len(doors) >= 3:
                    break
        except Exception:
            pass
        return doors[:3]

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        if REFL_RX.search(s):
            try:
                p = list(self.path(session_id))
            except Exception:
                p = []
            answered = sum(1 for r in p if r.get("out_status") == "answered")
            declined = sum(1 for r in p
                           if r.get("out_status") in ("withheld", "clarification"))
            convs = sum(1 for r in p if r.get("conversion"))
            residuals = [r.get("residual", {{}}).get("class") for r in p
                         if r.get("residual")][-2:]
            doors = self._doors_from(session_id)
            bits = (f"this session holds {{len(p)}} witnessed turns: {{answered}} "
                    f"answered, {{declined}} honestly declined, {{convs}} conversions")
            if residuals:
                bits += f"; standing residuals: {{', '.join(str(x) for x in residuals)}}"
            if doors:
                bits += f"; open doors: {{', '.join(doors)}}"
            return {{"status": "answered", "path": "worker:reflect",
                     "response": f"By my own witness, {{bits}}. [witness_reflection]",
                     "provenance": {{"kind": "witness_reflection", "turns": len(p)}},
                     "latency_ms": 1}}
        result = super().chat(s, session_id)
        if result.get("status") == "answered" and "continuation" not in result:
            doors = self._doors_from(session_id)
            if doors:
                offer = " or ".join(doors[:2])
                result["continuation"] = {{"doors": doors,
                                           "offer": f"from here, {{offer}} stand open"}}
        return result
'''


def meta_folds(st, head_rt) -> bool:
    """Author at most one meta fold per cycle; potentials + self_improve re-epoch 6h."""
    if _pending_candidate():
        ledger("author_waiting_gate", note="one candidate in flight; linear chain preserved")
        return True

    done = st.get("families", {})
    base_mod, base_cls = latest_admitted_w()
    ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    now = time.time()

    pot_due = ("potentials_fold" in done
               and now - st.get("pot_epoch_ts", 0) > 21600)
    if "potentials_fold" not in done or pot_due:
        pot = _mine_potentials(st)
        if len(pot) < 3:
            ledger("family_skipped", family="potentials_fold",
                   reason=f"only {len(pot)} potentials mined")
        else:
            st["wnum"] = int(st.get("wnum", 0))
            epoch = st.get("pot_epoch_n", 0) + 1
            cls = f"OracleReleaseRuntimeW{st['wnum'] + 1}"
            src = POTENTIALS_TEMPLATE.format(
                cand=f"oracle_release_runtime_w{st['wnum'] + 1}", cls=cls,
                base_mod=base_mod, base_cls=base_cls,
                potentials=repr(pot), n_pot=len(pot), ts=ts, epoch=epoch)
            _author(st, src, "potentials_fold",
                    f"epoch {epoch}: {len(pot)} typed potentials")
            st["pot_epoch_ts"] = now
            st["pot_epoch_n"] = epoch
            return True
        return False

    meta_due = ("self_improve_fold" in done
                and now - st.get("meta_epoch_ts", 0) > 21600)
    if "self_improve_fold" not in done or meta_due:
        admits, refusals = _ledger_digest()
        st["wnum"] = int(st.get("wnum", 0))
        epoch = st.get("meta_epoch_n", 0) + 1
        cls = f"OracleReleaseRuntimeW{st['wnum'] + 1}"
        src = SELF_IMPROVE_TEMPLATE.format(
            cand=f"oracle_release_runtime_w{st['wnum'] + 1}", cls=cls,
            base_mod=base_mod, base_cls=base_cls,
            admits=repr(admits), refusals=repr(refusals), ts=ts, epoch=epoch)
        _author(st, src, "self_improve_fold",
                f"epoch {epoch}: {len(admits)} admits, {len(refusals)} refusals digested")
        st["meta_epoch_ts"] = now
        st["meta_epoch_n"] = epoch
        return True

    if "reflect_continuation_fold" not in done:
        probe = head_rt.chat("Reflect on this conversation.",
                             session_id="fam-probe")
        if probe.get("status") == "answered" and "witness" in str(probe.get("provenance", {})):
            ledger("family_skipped", family="reflect_continuation_fold",
                   reason="head already reflects")
        else:
            st["wnum"] = int(st.get("wnum", 0))
            cls = f"OracleReleaseRuntimeW{st['wnum'] + 1}"
            src = REFLECT_TEMPLATE.format(
                cand=f"oracle_release_runtime_w{st['wnum'] + 1}", cls=cls,
                base_mod=base_mod, base_cls=base_cls, ts=ts)
            _author(st, src, "reflect_continuation_fold",
                    "witness reflection + structural continuation field on every "
                    "answered turn (response text never mutated)")
            return True
        return False

    if "open_converse_fold" not in done:
        st["wnum"] = int(st.get("wnum", 0))
        cls = f"OracleReleaseRuntimeW{st['wnum'] + 1}"
        src = CONVERSE_TEMPLATE.format(
            cand=f"oracle_release_runtime_w{st['wnum'] + 1}", cls=cls,
            base_mod=base_mod, base_cls=base_cls, ts=ts)
        _author(st, src, "open_converse_fold",
                "grounded continuation: anchor-verified doors as a runtime route")
        return True
    return False


# ── DEPTH FOLDS: rule-fold (unbounded made_of) + the 2-hop composer ─────────────
# The D1 climbers, per the anti-shallowness laws: a fold admits the EXTRACTION RULE
# querying the live corpus (never a frozen pair-list), and depth = composition of
# admitted operators with every hop cited, declining when any hop is unattested.

RULE_MADEOF_TEMPLATE = '''#!/usr/bin/env python3
"""{cand} - RULE FOLD: made-of as a live corpus operator (unbounded coverage).

Replaces cache-shaped made-of (frozen pairs) with the extraction RULE executed at
answer time against the bench corpus: FTS candidates -> typed extraction -> cited
answer. Coverage = every attested composition sentence, not a mined subset.
Anti-shallowness law honored: the fold IS the rule.
Authored {ts} by the fold worker, chained on {base_mod}."""

from __future__ import annotations

import re
import sqlite3

from {base_mod} import {base_cls}

_MADE_Q = re.compile(
    r"^what (?:is|are) (?:the )?(?P<t>[a-z][\\w \\-']{{1,40}}?) made (?:of|from)[?.! ]*$",
    re.I)
_EXTRACT = re.compile(
    r"^(?:The |A |An )?(?P<x>[A-Za-z][\\w \\-']{{1,36}}?) (?:is|are) "
    r"(?:composed of|made of|made up of|made from) (?P<y>[a-z][\\w ,\\-']{{2,70}}?)[.;]",
    re.I)


class {cls}({base_cls}):
    """Base + the live made-of rule. The corpus answers; the rule only extracts."""

    def _bench(self):
        con = getattr(self, "_rule_bench", None)
        if con is None:
            import stage5m13e7_benchfold_induction_v1 as bench_mod
            uri = bench_mod.DB.resolve().as_uri() + "?mode=ro&immutable=1"
            con = self._rule_bench = sqlite3.connect(uri, uri=True,
                                                     check_same_thread=False)
        return con

    def made_of_lookup(self, subject: str):
        """The admitted operator: subject -> (material, claim_id) or None."""
        subject = subject.strip().lower()
        for form in (subject, subject.rstrip("s")):
            if not form:
                continue
            try:
                rows = self._bench().execute(
                    "SELECT claim_id, fact FROM source_rows WHERE fact MATCH ? LIMIT 30",
                    (f'"{{form}}" AND ("made of" OR "composed of" OR "made from")',
                     )).fetchall()
            except Exception:
                return None
            for claim, fact in rows:
                m = _EXTRACT.match(str(fact))
                if m and m.group("x").strip().lower() in (form, form + "s"):
                    mat = m.group("y").split(",")[0].split(" and ")[0].strip()
                    return (mat, claim)
        return None

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        result = super().chat(s, session_id)
        if result.get("status") == "answered":
            return result          # fallback law: never override what the chain answers
        m = _MADE_Q.match(s)
        if m:
            hit = self.made_of_lookup(m.group("t"))
            if hit:
                mat, claim = hit
                pending = getattr(self, "_pending_conversion", None)
                if pending is None:
                    pending = self._pending_conversion = {{}}
                pending[session_id] = {{"construction": "RULE_MADE_OF",
                                        "from": s[:80], "to": "made_of_rule",
                                        "produced_by": "fold_worker_depth"}}
                return {{"status": "answered", "path": "worker:rule_made_of",
                         "response": f"By the attested record, {{m.group('t').strip()}} "
                                     f"is made of {{mat}}. [{{claim}}]",
                         "provenance": {{"kind": "corpus_relation_rule",
                                         "relation": "made_of", "claim_id": claim}},
                         "latency_ms": 2}}
        return result
'''

COMPOSER_TEMPLATE = '''#!/usr/bin/env python3
"""{cand} - THE COMPOSER (D1): two-hop composition of admitted operators, hops cited.

"What is X ultimately made of?"  = made_of(made_of(X)) - both hops extracted LIVE
by the rule operator, both claims cited, honest partial when hop 2 is unattested.
"Is X made of a kind of K?"      = made_of(X)=Y then the CHAIN'S OWN kind operator
judges "Is Y a K?" - composition ACROSS admitted operators, premises from both.
Declines when any hop is unattested: depth without false-answer discipline is not
depth (D1 negative sets must stay 0 false-yes).
Authored {ts} by the fold worker, chained on {base_mod}."""

from __future__ import annotations

import re

from {base_mod} import {base_cls}

_ULT_Q = re.compile(
    r"^what (?:is|are) (?:the )?(?P<t>[a-z][\\w \\-']{{1,40}}?) ultimately made "
    r"(?:of|from)[?.! ]*$", re.I)
_MKIND_Q = re.compile(
    r"^is (?:the )?(?P<t>[a-z][\\w \\-']{{1,40}}?) made of a kind of "
    r"(?P<k>[a-z][\\w \\-']{{1,40}}?)[?.! ]*$", re.I)


class {cls}({base_cls}):
    """Base + two-hop composition. Every hop cited; unattested hops decline."""

    def chat(self, text: str, session_id: str = "default") -> dict:
        s = " ".join(str(text).strip().split())
        result = super().chat(s, session_id)
        if result.get("status") == "answered":
            return result          # fallback law: compose only where the chain declines
        m = _ULT_Q.match(s)
        if m and hasattr(self, "made_of_lookup"):
            x = m.group("t").strip().lower()
            h1 = self.made_of_lookup(x)
            if h1:
                mid_head = h1[0].split()[-1] if h1[0] else ""
                h2 = self.made_of_lookup(h1[0]) or (
                    self.made_of_lookup(mid_head) if mid_head else None)
                pending = getattr(self, "_pending_conversion", None)
                if pending is None:
                    pending = self._pending_conversion = {{}}
                pending[session_id] = {{"construction": "COMPOSE_2HOP",
                                        "from": s[:80], "to": "made_of^2",
                                        "produced_by": "fold_worker_depth"}}
                if h2:
                    return {{"status": "answered", "path": "worker:compose_2hop",
                             "response": f"In steps: {{x}} is made of {{h1[0]}} "
                                         f"[{{h1[1]}}]; {{h1[0]}} is made of {{h2[0]}} "
                                         f"[{{h2[1]}}]. So {{x}} is ultimately made "
                                         f"of {{h2[0]}}.",
                             "provenance": {{"kind": "derived",
                                             "rule": "transitive_made_of",
                                             "premises": [h1[1], h2[1]]}},
                             "latency_ms": 3}}
                return {{"status": "withheld", "path": "worker:compose_2hop",
                         "response": f"The record attests {{x}} is made of {{h1[0]}} "
                                     f"[{{h1[1]}}], but the composition of {{h1[0]}} "
                                     f"is not attested - I won't guess the second hop.",
                         "provenance": {{"kind": "partial_chain",
                                         "premises": [h1[1]]}},
                         "latency_ms": 3}}
        km = _MKIND_Q.match(s)
        if km and hasattr(self, "made_of_lookup"):
            x, k = km.group("t").strip().lower(), km.group("k").strip().lower()
            h1 = self.made_of_lookup(x)
            if h1:
                mid = h1[0].split()[-1]
                kind_r = super().chat(f"Is a {{mid}} a {{k}}?", session_id)
                resp_l = str(kind_r.get("response", "")).lower()
                if kind_r.get("status") == "answered" and resp_l.startswith(("yes",)):
                    return {{"status": "answered", "path": "worker:compose_made_kind",
                             "response": f"In steps: {{x}} is made of {{h1[0]}} "
                                         f"[{{h1[1]}}]; and {{mid}} is a kind of "
                                         f"{{k}}. So yes.",
                             "provenance": {{"kind": "derived",
                                             "rule": "made_of_then_kind",
                                             "premises": [h1[1], kind_r.get(
                                                 "provenance", {{}})]}},
                             "latency_ms": 3}}
                if kind_r.get("status") == "answered" and resp_l.startswith("no"):
                    return kind_r
                return {{"status": "withheld", "path": "worker:compose_made_kind",
                         "response": f"The record attests {{x}} is made of {{h1[0]}} "
                                     f"[{{h1[1]}}], but whether {{mid}} is a kind of "
                                     f"{{k}} is not attested - I won't guess.",
                         "provenance": {{"kind": "partial_chain",
                                         "premises": [h1[1]]}},
                         "latency_ms": 2}}
        return result
'''


def depth_folds(st, head_rt) -> bool:
    """The D1 climbers, one per cycle: rule fold first, then the composer on it."""
    if _pending_candidate():
        ledger("author_waiting_gate", note="one candidate in flight; linear chain preserved")
        return True

    done = st.get("families", {})
    base_mod, base_cls = latest_admitted_w()
    ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

    if "rule_made_of" not in done:
        cls = f"OracleReleaseRuntimeW{int(st.get('wnum', 0)) + 1}"
        src = RULE_MADEOF_TEMPLATE.format(
            cand=f"oracle_release_runtime_w{int(st.get('wnum', 0)) + 1}", cls=cls,
            base_mod=base_mod, base_cls=base_cls, ts=ts)
        _author(st, src, "rule_made_of",
                "the extraction rule as a live operator - unbounded coverage")
        return True

    if "composer_2hop" not in done:
        made = done.get("rule_made_of", "")
        if not made or not (ADMITTED / made).exists():
            ledger("family_waiting", family="composer_2hop",
                   reason="requires rule_made_of ADMITTED (composer calls its operator)")
            return False
        cls = f"OracleReleaseRuntimeW{int(st.get('wnum', 0)) + 1}"
        src = COMPOSER_TEMPLATE.format(
            cand=f"oracle_release_runtime_w{int(st.get('wnum', 0)) + 1}", cls=cls,
            base_mod=base_mod, base_cls=base_cls, ts=ts)
        _author(st, src, "composer_2hop",
                "two-hop composition, hops cited, partial-chain honesty")
        return True
    return False


def _manifest_head():
    """The probe head = the manifest tip on the SERVED corpus (correctness release:
    probe what actually serves, never AO on simplewiki)."""
    import importlib
    sys.path.insert(0, str(ADMITTED))
    tip_mod, tip_cls = "oracle_release_runtime_ao", "OracleReleaseRuntimeAO"
    try:
        man = json.loads((ADMITTED / "HEAD_MANIFEST.json").read_text(encoding="utf-8"))
        tip_mod = man["tip"]
        tip_cls = "OracleReleaseRuntime" + tip_mod.split("runtime_")[-1].upper()
    except Exception:
        tip_mod, tip_cls = latest_admitted_w()
    mod = importlib.import_module(tip_mod)
    return tip_mod, getattr(mod, tip_cls)


def main() -> int:
    tip_mod, head_cls = _manifest_head()
    head_rt = head_cls(
        state_root=LOOP_DIR / "worker_probe_state",
        wikipedia_build=PHASE / "m13e5_wiki_openstax_build_a_v1")
    ledger("worker_start", pid=int(time.time()) % 100000, probe_head=tip_mod,
           anchors=len(head_rt.anchors.title_to_page))
    once = "--once" in sys.argv
    while True:
        st = load_state()
        try:
            souls, ew_samples = harvest_ew(st)
            inbox = gather_inbox(st, ew_samples)
            ledger("harvest", souls_live=souls, ew_new=len(ew_samples),
                   inbox=len(inbox))
            shape_match()
            paused = (LOOP_DIR / "PAUSE_AUTHORING").exists()
            if paused:
                ledger("authoring_paused",
                       note="correctness release in progress; no new candidates")
            if not paused and inbox:
                attempt_fold(st, inbox, head_rt)
            if not paused:
                induce_templates(st, head_rt)
                authored = region_folds(st, head_rt)
                if not authored:
                    authored = meta_folds(st, head_rt)
                if not authored:
                    authored = depth_folds(st, head_rt)
                if not authored:
                    family_folds(st, head_rt)
        except Exception as e:  # noqa: BLE001
            ledger("worker_error", error=f"{type(e).__name__}: {e}")
        save_state(st)
        if once:
            return 0
        time.sleep(CYCLE_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
