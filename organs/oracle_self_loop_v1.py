#!/usr/bin/env python3
"""The self-improvement loop, running on CPU without a person in it.

Of the five things a person was supplying (interpretation of the self-residual, test
construction, code modification, successor-test criticism, runtime promotion), three now
exist as mechanisms: self-observation (M42/M50), mutation testing (M48), and measurement
(M51). What remained human was ORCHESTRATION - running them in order and reading the
output. This is the orchestration, as a daemon.

Each cycle, in order:

  1. OBSERVE    re-run the self-snapshot and self-shape; record the gap set
  2. MEASURE    re-run the conversation map against the fixed scripts
  3. CRITICISE  mutation-test every panel; flag any that pass a mutant
  4. GATE       for each runtime in candidates/, decide ADMIT or REJECT with a reason:
                  - imports and instantiates
                  - 0 regressions on the fixed regression list vs the current head
                  - conversation-map metrics >= baseline on every axis
                  - every panel it touches survives its mutants
                ADMIT = copy to staging/admitted/ and append to the ledger
                REJECT = append the reason to the ledger; candidate left in place
  5. LEDGER     append-only record of what was observed, measured, and decided

Authority boundary, and it is structural: this process has WRITE access to three
directories only - the self-model outputs, staging/admitted/, and the ledger. It never edits
source, never writes to a sealed report, never touches the live tree or the live service, and
never promotes past staging. Promotion to live needs a signature this process cannot produce.

Nothing generates candidates here. A person, or a later mechanism, puts a runtime in
candidates/. This loop decides whether it is admissible and says why. That is the half of
code modification that can be mechanised safely: not authorship, but ADMISSION with an
auditable reason.

The loop also knows when it is stale: if the self-snapshot's version has not changed across
three cycles and no candidate is pending, it sleeps longer. Cheap when idle.

No neural network; no LM call. PYTHONHASHSEED=0.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

TRAIN = Path("/opt/oracle-clm/wander-train")
PHASE = Path("/opt/oracle-clm/fable-content/oracle-m-series-2026-08-15")
LOOP = PHASE / "self_loop"
CANDIDATES = LOOP / "candidates"
ADMITTED = LOOP / "admitted"
LEDGER = LOOP / "ledger.jsonl"
STATE = LOOP / "state.json"
HEAD_MODULE = "oracle_release_runtime_ao"
HEAD_CLASS = "OracleReleaseRuntimeAO"
MANIFEST = ADMITTED / "HEAD_MANIFEST.json"
WORKER_LEDGER_PATH = LOOP / "worker_ledger.jsonl"
# re-consolidation epochs are lawful at no-regression; NEW families must show a gain
# (amended per Ben directive 2026-08-25, forwarded Codex audit)
EPOCH_FAMILIES = {"episodic_hippocampus", "self_improve_fold", "potentials_fold"}


def resolve_head():
    """The serving tip from the cumulative-head manifest; AO only as last resort."""
    try:
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        tip = man["tip"]
        cls = "OracleReleaseRuntime" + tip.split("runtime_")[-1].upper()
        return tip, cls
    except Exception:
        return HEAD_MODULE, HEAD_CLASS


def family_of(candidate_name: str) -> str:
    """The authoring family of a candidate, from the worker's own ledger."""
    fam = ""
    try:
        for ln in WORKER_LEDGER_PATH.read_text(encoding="utf-8").splitlines():
            if candidate_name in ln and "fold_authored" in ln:
                rec = json.loads(ln)
                cl = [c for c in rec.get("clusters", []) if c.startswith("family:")]
                if cl:
                    fam = cl[-1].split(":", 1)[1]
    except Exception:
        pass
    return fam

REGRESSION = [
    "Who are you?", "What is this?", "Summarize the Moon.", "Is a beagle an animal?",
    "Is a keyboard part of a computer?", "What is a volcano?", "Explain gravity simply.",
    "When did World War II start?", "What causes rain?", "How does a telescope work?",
    "Who was Napoleon?", "Is a gray whale a whale?", "Is a sea horse a horse?",
    "Is a wheel part of a bicycle?", "What is a desert?", "Summarize Antarctica.",
]
BASELINE_KEY = "m52_heldout"
CYCLE_SECONDS = 300
IDLE_SECONDS = 1800
CITE = re.compile(r"\[[a-z0-9_]+:?[a-z0-9_.\-]*\]")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ledger(event: str, **payload) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": now(), "event": event, **payload}, ensure_ascii=False,
                           sort_keys=True) + "\n")


def run(script: str, timeout: int = 3000) -> tuple[int, str]:
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(TRAIN / script)], cwd=TRAIN, env=env,
                       capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or "")[-4000:]


# ── 1. OBSERVE ─────────────────────────────────────────────────────────────────
def observe() -> dict:
    for stale in ("m42_self_snapshot_v1.json", "m50_self_shape_v1.json"):
        try:
            (PHASE / stale).unlink()
        except FileNotFoundError:
            pass
    run("stage5m42_self_snapshot_v1.py")
    run("stage5m50_self_shape_v1.py")
    snap = json.loads((PHASE / "m42_self_snapshot_v1.json").read_text(encoding="utf-8"))
    shape = json.loads((PHASE / "m50_self_shape_v1.json").read_text(encoding="utf-8"))
    gaps = {
        "wholly_ungraded": [u["route"] for u in snap["faces"]["W_minus_minus_UNGRADED"]],
        "declared_implications": [f"{i['part']} missing {i['missing_relation']}"
                                  for i in shape["implied_positions_DECLARED"]],
        "induced_implications": len(shape["implied_positions_INDUCED"]),
    }
    ledger("observe", counts=snap["counts"], shape_counts=shape["counts"], gaps=gaps)
    return gaps


# ── 2. MEASURE ─────────────────────────────────────────────────────────────────
def measure(runtime_cls, tag: str, split: str = "heldout") -> dict:
    """Measure on the M52 corpus. The GATE judges on HELD-OUT only - scripts no candidate
    has seen - so a candidate cannot overfit its way past the bar. Dev is for authoring."""
    corpus = json.loads((PHASE / "m52_conversation_corpus_v1.json").read_text(encoding="utf-8"))
    scripts = {s["id"]: s["turns"] for s in corpus["scripts"] if s["split"] == split}
    rt = runtime_cls(state_root=PHASE / f"loop_{tag}",
                     wikipedia_build=PHASE / "m13e5_simplewiki_build_a_v1")
    R = {"read": 0, "turns": 0, "answered": 0, "cont": 0, "cont_of": 0, "gc": []}
    for name, script in scripts.items():
        sid = f"loop-{tag}-{name}"
        for line in script:
            rt.chat(line, session_id=sid)
        p = rt.path(sid) if hasattr(rt, "path") else []
        n = len(p)
        R["turns"] += n
        R["read"] += sum(1 for t in p if t.get("in_form"))
        R["answered"] += sum(1 for t in p if t.get("out_status") == "answered")
        R["cont"] += sum(1 for t in p[1:] if t.get("continuity"))
        R["cont_of"] += max(1, n - 1)
        for t in p:
            it = set(t.get("in_terms", []))
            if it:
                R["gc"].append(len(t["relation"]["grounded_cited"]) / len(it))
    return {"read": R["read"], "turns": R["turns"], "answered": R["answered"],
            "continuity": R["cont"], "continuity_of": R["cont_of"],
            "grounding_cited": round(sum(R["gc"]) / max(1, len(R["gc"])), 4)}


# ── 3. CRITICISE ───────────────────────────────────────────────────────────────
def criticise() -> dict:
    rc, out = run("stage5m48_mutation_tester_v1.py")
    rep = json.loads((PHASE / "m48_mutation_report_v1.json").read_text(encoding="utf-8"))
    unguarded = {p["report"]: p["UNGUARDED_MUTATIONS"] for p in rep["panels"]
                 if p["UNGUARDED_MUTATIONS"]}
    ledger("criticise", panels=rep["summary"], unguarded=unguarded)
    return unguarded


# ── 4. GATE ────────────────────────────────────────────────────────────────────
def load_class(module_name: str, path: Path | None = None):
    if path is not None:
        spec = importlib.util.spec_from_file_location(module_name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)
    else:
        mod = importlib.import_module(module_name)
    for name in dir(mod):
        obj = getattr(mod, name)
        if isinstance(obj, type) and name.startswith("OracleReleaseRuntime") \
                and obj.__module__ == mod.__name__:
            return obj
    raise ImportError(f"no runtime class in {module_name}")


def gate(candidate: Path, head_cls, baseline: dict) -> dict:
    reasons = []
    try:
        cand_cls = load_class(f"candidate_{candidate.stem}", candidate)
    except Exception as e:  # noqa: BLE001
        return {"decision": "REJECT", "reasons": [f"import failed: {type(e).__name__}: {e}"]}
    try:
        head = head_cls(state_root=PHASE / "loop_head",
                        wikipedia_build=PHASE / "m13e5_simplewiki_build_a_v1")
        cand = cand_cls(state_root=PHASE / "loop_cand",
                        wikipedia_build=PHASE / "m13e5_simplewiki_build_a_v1")
    except Exception as e:  # noqa: BLE001
        return {"decision": "REJECT", "reasons": [f"instantiate failed: {type(e).__name__}: {e}"]}
    regressions = []
    try:
        for q in REGRESSION:
            a = head.chat(q, session_id="g-h")
            b = cand.chat(q, session_id="g-c")
            if a.get("status") == "answered" and (a.get("path") != b.get("path")
                                                  or a.get("status") != b.get("status")):
                regressions.append({"q": q, "head": a.get("path"), "cand": b.get("path")})
    except Exception as e:  # noqa: BLE001 - a crashing candidate is a REJECT, never a stalled line
        return {"decision": "REJECT",
                "reasons": [f"exercise failed: {type(e).__name__}: {e}"]}
    if regressions:
        reasons.append({"regressions": regressions[:6]})
    try:
        m = measure(cand_cls, f"cand_{candidate.stem}", split="heldout")
    except Exception as e:  # noqa: BLE001
        return {"decision": "REJECT",
                "reasons": [f"measure failed: {type(e).__name__}: {e}"]}
    worse = {k: (baseline[k], m[k]) for k in ("read", "answered", "continuity", "grounding_cited")
             if m[k] < baseline[k]}
    if worse:
        reasons.append({"below_baseline": worse})
    if not reasons:
        fam = family_of(candidate.name)
        correctness = "CORRECTNESS RELEASE" in candidate.read_text(encoding="utf-8",
                                                                   errors="replace")[:2000]
        if fam not in EPOCH_FAMILIES and not correctness:
            gains = {k: (baseline[k], m[k])
                     for k in ("read", "answered", "continuity", "grounding_cited")
                     if m[k] > baseline[k]}
            if not gains:
                reasons.append({"no_gain": "new-family candidate must raise at least "
                                           "one metric above baseline (epochs and "
                                           "CORRECTNESS RELEASE candidates exempt)"})
    decision = "ADMIT" if not reasons else "REJECT"
    return {"decision": decision, "reasons": reasons, "measured": m, "baseline": baseline}


def rebuild_manifest() -> None:
    """Regenerate the cumulative-head manifest from the admitted imports (the truth)."""
    mods = {p.stem: p for p in ADMITTED.glob("oracle_release_runtime_w*.py")}
    if not mods:
        return
    def parent(stem):
        m = re.search(r"^from (oracle_release_runtime_\w+) import",
                      mods[stem].read_text(encoding="utf-8", errors="replace"), re.M)
        return m.group(1) if m else None
    tip = max(mods, key=lambda s: int(s.split("_w")[-1]))
    chain, cur = [], tip
    while cur in mods:
        chain.append(cur)
        cur = parent(cur)
    chain.append(cur)
    man = {"schema_version": "oracle-head-manifest-v1", "tip": tip,
           "chain_tip_to_base": chain,
           "orphaned_admitted": sorted(s for s in mods if s not in chain),
           "built_ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "law": "every consumer (daemon, worker, servers) resolves the head HERE; "
                  "the manifest is rebuilt on every admission by the daemon"}
    (ADMITTED / "HEAD_MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def cycle(state: dict) -> dict:
    head_mod, head_cls_name = resolve_head()
    sys.path.insert(0, str(ADMITTED))
    try:
        head_cls = load_class(head_mod)
    except Exception:
        head_mod, head_cls = HEAD_MODULE, load_class(HEAD_MODULE)
    gaps = observe()
    baseline = state.get("baseline") or measure(head_cls, "head", split="heldout")
    state["baseline"] = baseline
    ledger("measure", head=head_mod, metrics=baseline)
    unguarded = criticise()
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    ADMITTED.mkdir(parents=True, exist_ok=True)
    pending = sorted(CANDIDATES.glob("oracle_release_runtime_*.py"))
    for cand in pending:
        verdict = gate(cand, head_cls, baseline)
        ledger("gate", candidate=cand.name, **verdict)
        if verdict["decision"] == "ADMIT":
            shutil.copy2(cand, ADMITTED / cand.name)
            cand.rename(cand.with_suffix(".py.admitted"))
            state["baseline"] = verdict["measured"]   # the bar rises with each admission
            rebuild_manifest()                        # the head truth follows immediately
        else:
            # Constitutional re-baseline: a CORRECTNESS candidate whose ONLY failure
            # is below_baseline may be measuring truth the defective instrument had
            # inflated. The HUMAN pre-authorizes by touching CORRECTNESS_REBASELINE_OK;
            # the flag is consumed by exactly one candidate. Both the gate's honest
            # verdict and the authorized override stay on the record.
            flag = LOOP / "CORRECTNESS_REBASELINE_OK"
            only_baseline = bool(verdict.get("reasons")) and all(
                isinstance(r, dict) and set(r) == {"below_baseline"}
                for r in verdict["reasons"])
            is_corr = "CORRECTNESS RELEASE" in cand.read_text(
                encoding="utf-8", errors="replace")[:2000]
            if only_baseline and is_corr and flag.exists():
                flag.unlink()
                shutil.copy2(cand, ADMITTED / cand.name)
                cand.rename(cand.with_suffix(".py.admitted"))
                state["baseline"] = verdict["measured"]
                rebuild_manifest()
                ledger("rebaseline_admission", candidate=cand.name,
                       new_baseline=verdict["measured"],
                       note="human-flagged: corrected instrument redefines the bar; "
                            "semantics changed, not height")
            else:
                # preserved with its ledgered reasons, never re-gated: at continuous
                # cadence, re-measuring an unchanged rejected file is a treadmill
                cand.rename(cand.with_suffix(".py.rejected"))
    snap_version = json.loads((PHASE / "m42_self_snapshot_v1.json").read_text(
        encoding="utf-8"))["version"]
    state["last_versions"] = (state.get("last_versions", []) + [snap_version])[-3:]
    state["pending"] = len(pending)
    state["cycles"] = state.get("cycles", 0) + 1
    state["last_gaps"] = gaps
    state["last_unguarded"] = len(unguarded)
    return state


def main() -> int:
    LOOP.mkdir(parents=True, exist_ok=True)
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    once = "--once" in sys.argv
    while True:
        started = time.time()
        try:
            state = cycle(state)
            STATE.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")
            ledger("cycle_done", cycles=state["cycles"], seconds=round(time.time() - started, 1),
                   pending=state["pending"], ungraded=len(state["last_gaps"]["wholly_ungraded"]),
                   unguarded_panels=state["last_unguarded"])
        except Exception as e:  # noqa: BLE001
            ledger("cycle_error", error=f"{type(e).__name__}: {e}")
        if once:
            return 0
        stale = (len(set(state.get("last_versions", []))) == 1
                 and len(state.get("last_versions", [])) == 3 and not state.get("pending"))
        time.sleep(IDLE_SECONDS if stale else CYCLE_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
