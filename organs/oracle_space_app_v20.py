#!/usr/bin/env python3
"""Oracle app v20 — THE HARNESS + THE LOOP + THE WORLD. The full recursive circuit, live.

v17 exposed the machine's state (witness pane, affordance chips). v18 makes the coupling
bidirectional and wholly plain-spoken. The typed machinery is unchanged underneath; the
surface translates it into human-native idioms:

  THE SESSION MAP    the right panel renders the conversation AS the relational object
                     it is: grounded topics as solid nodes on the continuity thread,
                     doors (anchored introduced terms) as ghost nodes - click to open,
                     the live topic glowing. Built entirely from the witness stream;
                     no new instrumentation.
  PLAIN SPEECH       under every answer, one quiet line saying what the machine
                     actually did ("summarized Krakatoa · 3 sources · continues your
                     thread"), with the full typed record one tap beneath.
  TESTIMONY (E)      the evidential_v3 grammar is live: "I heard that X" is read as a
                     claim to check; the verdict rendered is only what the record
                     licenses (typed provenance - never a text match). A "What you've
                     told me" ledger shows your claims with their verdicts.
  SALIENCE (G)       the "Missing" panel lists the session's residuals as cards.
                     PURSUE admits a goal into a real GoalManager (source_ref = you)
                     and ranks it through the real SalienceArbitrator. IGNORE defers it.
                     The organs are Codex's admitted modules, driven by human value.
  AUTHORITY (B)      an honest boundary card: documents and goals are session-scoped;
                     evidence persists, authority does not; answers cite or decline.
                     Nothing is toggled that does nothing.

Runtime: AO chain through the admitted evidential_v3 reading (tags shown only on
report-marked turns). Organs imported from the synced local-line admitted snapshot.
Staged only; the live service is untouched until the human signs the switch.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from oracle_release_runtime import PHASE

sys.path.insert(0, str(PHASE / "self_loop" / "local_line_extra"))
sys.path.insert(0, str(PHASE / "self_loop" / "local_line_admitted"))

from oracle_sibling_evidential_v3 import SiblingEvidentialV3          # noqa: E402
from oracle_goal_state_v1 import GoalManager, GoalStateError          # noqa: E402
from oracle_salience_arbitrator_v1 import SalienceArbitrator          # noqa: E402

LITE_BUILD = PHASE / "m13e5_simplewiki_build_a_v1"
FULL_BUILD = PHASE / "m13e5_dbpedia_build_a_v2"
LOOP_DIR = PHASE / "self_loop"
LEDGER = LOOP_DIR / "ledger.jsonl"
LOOP_STATE = LOOP_DIR / "state.json"
CURRICULUM = PHASE / "harness_curriculum_queue_v1.jsonl"
WORKER_LEDGER = LOOP_DIR / "worker_ledger.jsonl"
WORLD_LEDGER_EW2 = LOOP_DIR / "world_ledger_ew2.jsonl"
SOUL_QUERIES = LOOP_DIR / "soul_queries.jsonl"
TARGET_SHAPE = PHASE / "target_shape_v1.json"
EW_FEED_FILE = LOOP_DIR / "ensouled_feed_live.jsonl"
RESIDUE = Path("/opt/oracle-clm/residue_turns.jsonl")

CITE_TAG = re.compile(r"\[([A-Za-z][\w:.'-]{5,})\]")
DERIVED_TAG = re.compile(r"\s*\[(?:derived:[^\]]*|conceptnet57:[^\]]*)\]")
EV_TAG = re.compile(r"^\[ev:[a-z]+\]\s*")
SOURCE_LABELS = (
    ("simplewiki", "Simple English Wikipedia (CC BY-SA)"),
    ("dbpedia", "DBpedia abstracts (CC BY-SA)"),
    ("conceptnet", "ConceptNet 5.7 (CC BY-SA 4.0)"),
    ("user:", "Your document (session-scoped)"),
)

_title_conn = None
_title_cache: dict[str, str] = {}


def _titles_for(tags: list[str]) -> dict[str, str]:
    global _title_conn
    wanted = [t for t in tags if t not in _title_cache]
    if wanted:
        try:
            if _title_conn is None:
                build = Path(os.environ.get(
                    "ORACLE_WIKIPEDIA_BUILD",
                    str(FULL_BUILD if FULL_BUILD.exists() else LITE_BUILD)))
                db = build / "wikipedia_specialist.sqlite3"
                _title_conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True,
                                              check_same_thread=False)
            marks = ",".join("?" for _ in wanted)
            rows = _title_conn.execute(
                f"SELECT s.claim_id, a.title FROM source_rows s "
                f"JOIN article a ON a.page_id = s.page_id "
                f"WHERE s.claim_id IN ({marks})", wanted).fetchall()
            found = {claim: title for claim, title in rows}
            for tag in wanted:
                _title_cache[tag] = str(found.get(tag) or "")
        except Exception:
            for tag in wanted:
                _title_cache.setdefault(tag, "")
    return {t: _title_cache.get(t, "") for t in tags}


def citations(response: str) -> tuple[str, list[dict]]:
    order: list[str] = []

    def swap(match: re.Match) -> str:
        tag = match.group(1)
        if tag not in order:
            order.append(tag)
        return f"[{order.index(tag) + 1}]"

    text = CITE_TAG.sub(swap, response)
    derived = bool(DERIVED_TAG.search(text))
    text = DERIVED_TAG.sub("", text)
    titles = _titles_for(order) if order else {}
    references = []
    if derived:
        references.append({"n": len(order) + 1, "id": "conceptnet57:derivation",
                           "source": "ConceptNet 5.7 (CC BY-SA 4.0)",
                           "title": "commonsense derivation (steps shown above)"})
    for index, tag in enumerate(order):
        label = "admitted corpus"
        for prefix, name in SOURCE_LABELS:
            if tag.startswith(prefix):
                label = name
                break
        references.append({"n": index + 1, "id": tag, "source": label,
                           "title": titles.get(tag, "")})
    return text, references


class HarnessRuntime(SiblingEvidentialV3):
    """Evidential reading live; [ev:] tags shown only on report-marked turns."""

    def chat(self, text: str, session_id: str = "default") -> dict:
        result = super().chat(text, session_id)
        ev = result.get("evidential") or {}
        if ev.get("input_marked") is None:
            result["response"] = EV_TAG.sub("", str(result.get("response", "")))
        return result


# ── plain speech: what the machine did, in one quiet human line ────────────────
def speech(w: dict | None, result: dict) -> str:
    if not w:
        return ""
    path = str(w.get("operator") or result.get("path") or "")
    if path.startswith("arb:"):
        path = path.split("->", 1)[-1]
    prov = result.get("provenance") or {}
    status = str(result.get("status", ""))
    base = None
    table = [
        ("capability:summarize", lambda: f"summarized {prov.get('topic') or 'the page'}"),
        ("capability:how_does", lambda: "explained the mechanism from the record"),
        ("capability:compare", lambda: "compared them from the record"),
        ("act:provenance_replay", lambda: "replayed how the last answer was grounded"),
        ("act:continue_topic", lambda: "continued the thread"),
        ("act:acknowledge", lambda: "noted it"),
        ("act:clarify", lambda: "asked you to narrow it"),
        ("tool:calculator", lambda: "computed it with the verified calculator"),
        ("conceptnet_isa_derived", lambda: "derived it in steps from the record"),
        ("conceptnet_isa", lambda: "checked the commonsense record"),
        ("document_runtime", lambda: "answered from the admitted pages"),
    ]
    for key, fn in table:
        if path.startswith(key):
            base = fn()
            break
    if base is None:
        if str(prov.get("corpus")) == "wordnet":
            base = "checked the classification record"
        elif status == "answered":
            base = (path or "answered").replace("_", " ").replace(":", " · ")
        else:
            base = "held back — the record wasn't enough"
    bits = [base]
    ev = (result.get("evidential") or {})
    if ev.get("input_marked"):
        bits.append("checked what you told me against the record")
    c = int(w.get("citations") or 0)
    if c:
        bits.append(f"{c} source{'s' if c != 1 else ''}")
    if w.get("continuity"):
        bits.append("continues your thread")
    if w.get("residual"):
        bits.append("a gap was recorded — see Missing")
    return " · ".join(bits)


def affordances(rec, result, runtime=None) -> list[dict]:
    out: list[dict] = []
    if not isinstance(rec, dict):
        return out
    rel = rec.get("relation") or {}
    if rec.get("out_status") == "answered":
        if rec.get("citations"):
            out.append({"say": "why did you say that?",
                        "why": "the last answer carries citations to replay", "send": True})
        out.append({"say": "tell me more", "why": "the topic is live", "send": True})
        out.append({"say": "simpler", "why": "the last answer can be re-rendered", "send": True})
    # doors only from answered CONTENT turns - a clarify or ack introduces only
    # its own phrasing, and those words are not doors.
    path = str(rec.get("operator") or "")
    if rec.get("out_status") == "answered" and not path.startswith("act:"):
        doors = []
        try:
            anchors = runtime.anchors.title_to_page if runtime is not None else {}
        except Exception:
            anchors = {}
        months = {"january", "february", "march", "april", "may", "june", "july",
                  "august", "september", "october", "november", "december"}
        for term in (rel.get("introduced") or []):
            if (isinstance(term, str) and 4 <= len(term) < 30
                    and term.lower() in anchors and term.lower() not in months):
                doors.append(term)
        for term in sorted(doors, key=len, reverse=True)[:3]:
            out.append({"say": f"What is {term}?", "why": "a door this answer opened",
                        "send": True, "door": term})
    return out[:7]


def node_of(w: dict | None, result: dict) -> str | None:
    """The map node this turn grounds, if any."""
    prov = result.get("provenance") or {}
    if result.get("status") != "answered":
        return None
    t = prov.get("topic") or prov.get("lemma")
    if t:
        return str(t)
    conv = (result.get("conversion") or {})
    to = str(conv.get("to", ""))
    m = re.match(r"^Summari[sz]e (.+?)\.?$", to)
    if m:
        return m.group(1)
    return None


# ── the loop, read-only: every number from a live artifact ─────────────────────
_loop_cache = {"t": 0.0, "data": None}


def _sha16(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except Exception:
        return "?"


def event_speech(e: dict) -> dict:
    t = str(e.get("ts", "")).replace("T", " ").replace("Z", "")
    ev = str(e.get("event", ""))
    if ev == "measure":
        m = e.get("metrics") or {}
        return {"t": t, "cls": "", "txt": f"measured itself on held-out: answered "
                f"{m.get('answered')}/248 · continuity {m.get('continuity')} · "
                f"grounding {m.get('grounding_cited')}"}
    if ev == "observe":
        return {"t": t, "cls": "", "txt": "observed its own shape and declared its gaps"}
    if ev == "criticise":
        pnl = e.get("panels") or {}
        return {"t": t, "cls": "", "txt": f"mutation-tested {pnl.get('panels_examined')} "
                f"of its own report panels · {pnl.get('panels_with_unguarded_mutations')} "
                f"still carry unguarded checks"}
    if ev == "gate":
        d = str(e.get("decision", ""))
        m, b = e.get("measured") or {}, e.get("baseline") or {}
        return {"t": t, "cls": "gate-admit" if d == "ADMIT" else "gate-reject",
                "txt": f"{d}: {e.get('candidate')} · answered {m.get('answered')} "
                f"vs head {b.get('answered')}"}
    if ev == "cycle_done":
        return {"t": t, "cls": "", "txt": f"cycle {e.get('cycles')} finished in "
                f"{e.get('seconds')}s · {e.get('pending')} candidate(s) pending"}
    if ev == "harvest":
        return {"t": t, "cls": "", "txt": f"harvested the world: {e.get('souls_live')} "
                f"souls live · {e.get('ew_new')} new thoughts sampled · inbox {e.get('inbox')}"}
    if ev == "fold_authored":
        return {"t": t, "cls": "fold", "txt": f"AUTHORED {e.get('candidate')} from "
                f"clusters {e.get('clusters')} · sources {e.get('sources')}"}
    if ev == "fold_no_cluster":
        return {"t": t, "cls": "", "txt": f"no fold this round — {e.get('inbox')} "
                f"surfaces, none clustered to threshold"}
    if ev == "fold_already_authored":
        return {"t": t, "cls": "", "txt": f"cluster {e.get('signature')} already "
                f"authored — waiting for new evidence"}
    if ev == "worker_start":
        return {"t": t, "cls": "", "txt": f"fold worker started · "
                f"{e.get('anchors'):,} anchors resident"}
    if ev == "shape_match":
        return {"t": t, "cls": "", "txt": f"matched itself against the declared shape: "
                f"distance {e.get('weighted_distance')} · attend first: {e.get('attend_first')}"}
    if ev == "worker_error":
        return {"t": t, "cls": "gate-reject", "txt": f"worker error: {e.get('error')}"}
    return {"t": t, "cls": "", "txt": ev or "event"}


def loop_snapshot() -> dict:
    now = time.time()
    if _loop_cache["data"] and now - _loop_cache["t"] < 5:
        return _loop_cache["data"]
    out = {}
    try:
        st = json.loads(LOOP_STATE.read_text(encoding="utf-8")) if LOOP_STATE.exists() else {}
    except Exception:
        st = {}
    out["baseline"] = st.get("baseline") or {}
    out["cycles"] = st.get("cycles")
    flat = []
    for v in (st.get("last_gaps") or {}).values():
        if isinstance(v, list):
            flat += [str(x) for x in v]
    out["gaps_total"], out["gaps"] = len(flat), flat[:6]
    events, lines = [], []
    try:
        lines = LEDGER.read_text(encoding="utf-8").strip().splitlines()
        for ln in lines[-14:]:
            try:
                events.append(json.loads(ln))
            except Exception:
                pass
        out["live"] = (now - LEDGER.stat().st_mtime) < 900
    except Exception:
        out["live"] = False
    out["ledger_events"] = len(lines)
    out["last_ts"] = str(events[-1].get("ts", "")) if events else None
    wevents = []
    try:
        wlines = WORKER_LEDGER.read_text(encoding="utf-8").strip().splitlines()
        for ln in wlines[-12:]:
            try:
                wevents.append(json.loads(ln))
            except Exception:
                pass
    except Exception:
        wlines = []
    merged = sorted(events + wevents, key=lambda e: str(e.get("ts", "")))
    out["feed"] = [event_speech(e) for e in reversed(merged)]
    out["worker_live"] = False
    try:
        out["worker_live"] = (now - WORKER_LEDGER.stat().st_mtime) < 600
    except Exception:
        pass
    last_harvest = next((e for e in reversed(wevents) if e.get("event") == "harvest"), {})
    out["souls_live"] = last_harvest.get("souls_live")
    thoughts = []
    try:
        for ln in WORLD_LEDGER_EW2.read_text(encoding="utf-8").strip().splitlines()[-40:]:
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("type") in ("chat", "act", "build", "lineage"):
                label = {"build": "built", "lineage": "came to be"}.get(r["type"], "")
                txt = (f"{label} a {r.get('kind','work')}: {r.get('content','')}"
                       if r["type"] == "build" else
                       f"{label} ({r.get('verb')})" if r["type"] == "lineage"
                       else str(r.get("content", "")))
                thoughts.append({"soul": r.get("actor"), "archetype": r.get("verb", r["type"]),
                                 "thought": txt[:150]})
        thoughts = thoughts[-6:]
    except Exception:
        pass
    out["world_feed"] = list(reversed(thoughts))
    try:
        with __import__("urllib.request", fromlist=["request"]).urlopen(
                "http://127.0.0.1:8772/feed", timeout=3) as rr:
            ew2 = json.loads(rr.read().decode("utf-8", "replace").splitlines()[0])
        out["ew2"] = {"tick": ew2.get("tick"), "souls": ew2.get("souls"),
                      "structures": len(ew2.get("structures") or [])}
    except Exception:
        out["ew2"] = None
    try:
        qs = SOUL_QUERIES.read_text(encoding="utf-8").strip().splitlines()[-1500:]
        uniq = {}
        routes = {}
        for ln in qs:
            try:
                q = json.loads(ln)
            except Exception:
                continue
            if q.get("route") == "decline_cache":
                continue                    # cache hits are repeats, not questions
            uniq[q.get("q", "")] = bool(q.get("served"))
            if q.get("served"):
                routes[q.get("route", "?")] = routes.get(q.get("route", "?"), 0) + 1
        served_u = sum(1 for v in uniq.values() if v)
        vol_served = sum(routes.values())
        vol_total = sum(1 for ln in qs if ln.strip())
        out["served_rate"] = {"unique_rate": round(served_u / max(1, len(uniq)), 3),
                              "unique_window": len(uniq),
                              "volume_rate": round(vol_served / max(1, vol_total), 3),
                              "volume_window": vol_total,
                              "by_route": routes}
    except Exception:
        out["served_rate"] = None
    last_fold = next((e for e in reversed(wevents)
                      if str(e.get("event", "")).startswith("fold")), None)
    out["learning"] = event_speech(last_fold)["txt"] if last_fold else "no fold events yet"
    out["shape"] = None
    try:
        decl = json.loads(TARGET_SHAPE.read_text(encoding="utf-8"))
        last_shape = next((e for e in reversed(wevents) if e.get("event") == "shape_match"), None)
        if last_shape:
            out["shape"] = {"declared_by": decl.get("declared_by"),
                            "prose": decl.get("prose"),
                            "dims": last_shape.get("dims"),
                            "distance": last_shape.get("weighted_distance"),
                            "attend_first": last_shape.get("attend_first")}
    except Exception:
        pass
    wgates = []
    for ln in lines:
        if '"event": "gate"' in ln and 'oracle_release_runtime_w' in ln:
            try:
                wgates.append(json.loads(ln))
            except Exception:
                pass
    if wgates:
        g = wgates[-1]
        out["learning"] += (f" → gate {g.get('decision')} "
                            f"({str(g.get('candidate', ''))})")
    admits = rejects = 0
    for ln in lines:
        if '"event": "gate"' in ln:
            if '"ADMIT"' in ln:
                admits += 1
            elif '"REJECT"' in ln:
                rejects += 1
    out["gate_totals"] = {"admits": admits, "rejects": rejects}
    here = Path(__file__).resolve().parent
    out["boxc_count"] = len(list(here.glob("oracle_release_runtime_*.py")))
    out["head"] = {"module": "oracle_release_runtime_ao",
                   "sha256": _sha16(here / "oracle_release_runtime_ao.py")}
    local = sorted((LOOP_DIR / "local_line_admitted").glob("oracle_release_runtime_*.py"))
    out["local_line"] = {"count": len(local),
                         "head": local[-1].stem.split("_")[-1] if local else None}
    try:
        m62e = json.loads((PHASE / "m62e_merge_measure_v1.json").read_text(encoding="utf-8"))
        d = m62e.get("delta") or {}
        out["merge"] = {"answered_delta": d.get("answered"),
                        "continuity_delta": d.get("continuity"),
                        "grounding_delta": d.get("grounding_cited")}
    except Exception:
        out["merge"] = {}
    try:
        reg = json.loads((PHASE / "garden" / "registry.json").read_text(encoding="utf-8"))
        out["garden"] = sorted(reg.get("plants", {}).keys())
    except Exception:
        out["garden"] = []
    try:
        out["residue_turns"] = sum(1 for _ in RESIDUE.open(encoding="utf-8"))
    except Exception:
        out["residue_turns"] = 0
    out["reports"] = len(list(PHASE.glob("*.json")))
    try:
        out["curriculum_pursued"] = sum(1 for _ in CURRICULUM.open(encoding="utf-8"))
    except Exception:
        out["curriculum_pursued"] = 0
    _loop_cache["t"], _loop_cache["data"] = now, out
    return out


def verify_report(fname: str) -> dict:
    if not re.match(r"^[A-Za-z0-9_.\-]+\.json$", fname or ""):
        return {"error": "bad name"}
    p = PHASE / fname
    if not p.is_file():
        return {"error": "no such sealed report"}
    immutable = "unknown"
    try:
        r = subprocess.run(["lsattr", str(p)], capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout:
            immutable = "yes" if "i" in r.stdout.split()[0] else "no"
    except Exception:
        pass
    return {"file": fname, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "bytes": p.stat().st_size, "immutable": immutable}


OPENER_RX = re.compile(
    r"^(?:summari[sz]e|what is|tell me about|describe)\s+(.+?)[.?!]*$", re.I)


def state_turn(r: dict, runtime) -> dict:
    surf = str(r.get("in_surface", ""))
    op = str(r.get("operator") or "")
    node = None
    if r.get("out_status") == "answered" and not op.startswith("act:"):
        m = OPENER_RX.match(surf)
        if m:
            node = m.group(1).strip()
    fake = {"relation": r.get("relation") or {}, "out_status": r.get("out_status"),
            "operator": op, "citations": r.get("citations")}
    doors = [a["door"] for a in affordances(fake, {}, runtime) if a.get("door")]
    return {"in": surf[:120], "status": r.get("out_status"), "op": op, "node": node,
            "doors": doors, "evidential": r.get("evidential"),
            "residual": r.get("residual")}


# ── the human's organs: goals + salience, session-scoped, in memory ────────────
ORGANS: dict[str, dict] = {}


def organs(session: str) -> dict:
    o = ORGANS.get(session)
    if o is None:
        o = ORGANS[session] = {"goals": GoalManager(max_goals=8),
                               "arb": SalienceArbitrator(active_goal="attend"),
                               "decision": None}
    return o


PAGE = """<!doctype html><html lang=en><meta charset=utf-8><title>The Oracle — Harness</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<link rel=preconnect href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Fredoka:wght@400;500;600&display=swap" rel=stylesheet>
<style>
:root{--cream:#fdf3d8;--paper:#fff7e0;--ink:#3a2818;--brass:#c89540;--orange:#e87a3a;--sage:#7a9a6d}
body{font-family:Fredoka,system-ui,sans-serif;background:var(--cream);color:var(--ink);margin:0}
#cols{display:flex;flex-wrap:wrap;gap:18px;max-width:1560px;margin:0 auto;padding:18px}
#left{flex:1 1 460px;max-width:640px}#right{flex:1 1 560px;min-width:380px}
h1{font-family:Cinzel,serif;font-size:1.55rem;margin:.2rem 0 .3rem;letter-spacing:.02em}
h2{font-family:Cinzel,serif;font-size:.95rem;letter-spacing:.08em;margin:.1rem 0 .5rem}
.badge{display:inline-block;background:var(--orange);color:var(--paper);font-size:.65em;
padding:.15em .6em;border-radius:999px;vertical-align:middle;margin-left:.5em;letter-spacing:.05em}
.section{background:var(--paper);border:3px solid var(--ink);border-radius:12px;
box-shadow:6px 6px 0 rgba(58,40,24,.25);padding:1rem 1.2rem;margin-bottom:1rem}
.meta{color:#7a5f42;font-size:.85em;line-height:1.5}
#log{white-space:pre-wrap;min-height:280px;max-height:56vh;overflow-y:auto;font-size:.94em;line-height:1.55}
.speech{color:var(--brass);font-size:.76em;font-weight:600;margin:.15em 0 .3em}
.you{color:var(--orange);font-weight:600;margin-top:.5em}
input,textarea{font-family:inherit;width:72%;padding:.55rem .7rem;background:#fffdf2;
border:2px solid var(--ink);color:var(--ink);border-radius:8px;font-size:1em}
textarea{width:96%;height:70px}
button{font-family:inherit;font-weight:600;padding:.5rem 1rem;background:var(--brass);
color:var(--paper);border:2px solid var(--ink);border-radius:8px;cursor:pointer;
box-shadow:3px 3px 0 rgba(58,40,24,.3)}
button:active{transform:translate(2px,2px);box-shadow:1px 1px 0 rgba(58,40,24,.3)}
details summary{cursor:pointer;font-weight:600}
details.refs{margin:.1em 0 .3em}
details.refs summary{color:var(--brass);font-size:.76em}
details.refs div,details.wit div{color:#7a5f42;font-size:.76em;line-height:1.45;
padding:.3em .2em .1em .9em;border-left:2px solid var(--brass);margin-top:.25em;white-space:pre-wrap}
details.wit{margin:.05em 0 .3em}
details.wit summary{color:#9b8264;font-size:.72em}
.aff{display:flex;flex-wrap:wrap;gap:6px;margin:.1em 0 .6em}
.chip{font-size:.76em;padding:.22rem .6rem;background:var(--paper);color:var(--ink);
border:2px solid var(--brass);border-radius:999px;box-shadow:2px 2px 0 rgba(58,40,24,.2)}
.chip.door{border-color:var(--sage)}
#map{width:100%;height:340px;background:#faf0d0;border-radius:8px;display:block}
.card{background:#fbf0d2;border:2px solid var(--ink);border-radius:8px;padding:.5rem .7rem;
margin-bottom:.5rem;font-size:.85em}
.card .rq{color:#7a5f42;font-size:.9em}
.card button{padding:.25rem .7rem;font-size:.8em;margin-right:.4rem}
.goalpill{display:inline-block;background:var(--sage);color:var(--paper);border-radius:999px;
padding:.15em .7em;font-size:.78em;margin:.15em .25em .15em 0}
.verdict{font-size:.75em;font-weight:600;border-radius:6px;padding:.1em .45em;color:var(--paper)}
.v-supported{background:var(--sage)}.v-refuted{background:#b3543a}.v-no_verdict{background:#9b8264}
.told{font-size:.82em;margin:.25em 0;line-height:1.45}
#bound{font-size:.8em;color:#7a5f42;line-height:1.55}
a{color:var(--orange)}
#loopband h3{font-family:Cinzel,serif;font-size:.78rem;letter-spacing:.06em;margin:.2rem 0 .3rem}
.evrow{margin:.14em 0;font-size:.8em;color:#7a5f42}
.gate-admit{color:#5c7a50;font-weight:600}
.gate-reject{color:#b3543a;font-weight:600}
.livedot{color:#5c7a50;font-weight:700}
.vlink{cursor:pointer;color:var(--orange);text-decoration:underline}
.fold{color:var(--brass);font-weight:700}
.soulrow{margin:.16em 0;font-size:.8em;color:#5c4630}
.soulname{color:var(--orange);font-weight:600}
.learnline{background:#fbf0d2;border-left:3px solid var(--sage);padding:.35em .6em;
border-radius:0 6px 6px 0;font-size:.82em;margin:.3em 0 .1em}
</style>
<div id=cols>
<div id=left>
<h1>The Oracle <span class=badge>harness</span></h1>
<p class=meta>A compiler-learning model, no neural network. Ask it things; tell it things
("I heard that…" gets checked against the record); open the doors it offers. The map on the
right is your conversation, drawn as it grows. Every answer cites, derives, or honestly declines.</p>
<div class=section><div id=log></div>
<form onsubmit="send(event)"><input id=q autofocus placeholder="Ask, tell, or open a door…"> <button id=askbtn>Send</button></form></div>
<p class=meta><b>Try:</b> Summarize Krakatoa. · Is a beagle an animal? · I heard that a sea horse is a horse. ·
why did you say that? · tell me more · Calculate 7 * 8. · What causes earthquakes?</p>
<div class=section><details><summary>Teach it a document</summary>
<p class=meta>Paste text; sentences pass the same admission law as the public corpus
(rejected, never repaired). Session-scoped. Then ask: "Tell me about &lt;your title&gt;."</p>
<input id=dt placeholder="Document title"><br><br>
<textarea id=dx placeholder="Paste the document text…"></textarea><br>
<button onclick="ingest(event)">Admit document</button> <span id=ir class=meta></span>
</details></div>
</div>
<div id=right>
<div class=section><h2>THE MAP</h2><svg id=map></svg>
<p class=meta id=mapnote>Solid nodes are grounded topics · faint ones are doors — click anything.</p></div>
<div class=section><h2>MISSING</h2><p class=meta style="margin:.1em 0 .4em">Gaps you pursue are recorded — with you as the source — as curriculum for a future fold.</p><div id=goals></div><div id=residuals><p class=meta>Nothing yet — gaps the record can't fill will appear here, and you choose what matters.</p></div></div>
<div class=section><h2>WHAT YOU'VE TOLD ME</h2><div id=told><p class=meta>Claims you report ("I heard that…") are checked and land here with their verdicts.</p></div></div>
<div class=section><h2>THE WORLD, RENDERED</h2>
<div id=w3d style="width:100%;height:300px;background:#12141c;border-radius:8px;overflow:hidden"></div>
<p class=meta id=w3dnote>every structure traces to its ledger record — click one.</p></div>
<div class=section><h2>THE WORLD'S ART</h2>
<p class=meta>the souls' art acts, realized: deterministic form from each act's own words — same act, same piece, every shape derived.</p>
<div id=gallery style="display:flex;flex-wrap:wrap;gap:8px"></div>
<p class=meta id=galnote></p></div>
<div class=section><h2>THE BOUNDARY</h2><div id=bound>
Your documents and goals live only in this session — when you leave, they are gone.<br>
Evidence persists in the public record; <b>authority does not persist at all</b>.<br>
Every answer carries citations, a derivation with premises, or an honest decline.<br>
The full transition record of every turn is under "record" beneath each answer.</div></div>
</div>
<div class=section id=loopband style="flex:1 1 100%">
<h2>THE LOOP — IT IMPROVES ITSELF · EVERY CLAIM VERIFIABLE</h2>
<div id=loopstatus class=meta>reading the ledger…</div>
<div style="display:flex;flex-wrap:wrap;gap:18px;margin-top:.6em">
<div style="flex:1 1 230px"><h3>MEASURED SELF (HELD-OUT)</h3><div id=loopbase class=meta></div></div>
<div style="flex:1 1 280px"><h3>WHAT IT KNOWS IT'S MISSING</h3><div id=loopgaps class=meta></div></div>
<div style="flex:2 1 380px"><h3>ACTIVITY</h3><div id=loopfeed></div></div>
<div style="flex:1 1 300px"><h3>THE TWO LINEAGES</h3><div id=looplines class=meta></div></div>
<div style="flex:1 1 320px"><h3>THE WORLD, LIVE</h3><div id=worldhead class=meta></div><div id=worldfeed></div></div>
</div>
<div class=learnline id=learnline>what's being learned: …</div>
<div class=learnline id=shapeline style="border-left-color:var(--orange)">target shape: …</div>
<p class=meta id=loopfoot></p></div>
</div>
<script>
function sid(){let s=localStorage.getItem('ohsid');if(!s){s=Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('');localStorage.setItem('ohsid',s);}return s;}
const S={nodes:[],doors:Object.create(null),residuals:[],goals:[],told:[],turn:0};
function esc(t){return String(t)}
async function send(e){e.preventDefault();const q=document.getElementById('q');const t=q.value;if(!t)return;q.value='';
line('You: '+t,'you');
const r=await fetch('chat',{method:'POST',headers:{'Content-Type':'application/json','X-Oracle-Session':sid()},body:JSON.stringify({text:t})});
const v=await r.json();S.turn++;
oracle(v,t);drawMap();}
function line(m,cls){const d=document.getElementById('log');const p=document.createElement('div');if(cls)p.className=cls;p.textContent=m;d.appendChild(p);d.scrollTop=d.scrollHeight;}
function oracle(v,asked){const d=document.getElementById('log');
const p=document.createElement('div');p.textContent='Oracle: '+v.response;d.appendChild(p);
if(v.speech){const s=document.createElement('div');s.className='speech';s.textContent=v.speech;d.appendChild(s);}
if(v.affordances&&v.affordances.length){const row=document.createElement('div');row.className='aff';
for(const a of v.affordances){if(!a.send)continue;const b=document.createElement('button');b.type='button';
b.className='chip'+(a.door?' door':'');b.textContent=a.say;b.title=a.why;
b.onclick=function(){document.getElementById('q').value=a.say;document.getElementById('askbtn').click();};
row.appendChild(b);}d.appendChild(row);}
if(v.references&&v.references.length){const det=document.createElement('details');det.className='refs';
const sum=document.createElement('summary');sum.textContent='References ('+v.references.length+')';det.appendChild(sum);
const box=document.createElement('div');box.textContent=v.references.map(r=>'['+r.n+'] '+(r.title?r.title+' — ':'')+r.source).join('\\n');
det.appendChild(box);d.appendChild(det);}
if(v.witness){const det=document.createElement('details');det.className='wit';
const sum=document.createElement('summary');sum.textContent='record';det.appendChild(sum);
const box=document.createElement('div');const w=v.witness,rel=w.relation||{};
const L=['operator: '+w.operator+' · status: '+w.out_status+' · '+w.cost_ms+'ms',
'readings: '+fmt(w.in_form||'none')];
for(const k of Object.keys(rel)){L.push(k+': '+fmt(rel[k]));}
L.push('continuity: '+(w.continuity?'yes':'no'));if(w.residual)L.push('residual: '+w.residual['class']);
box.textContent=L.join('\\n');det.appendChild(box);d.appendChild(det);}
d.scrollTop=d.scrollHeight;
// map + panels
if(v.node){if(!S.nodes.find(n=>n.id===v.node)){S.nodes.push({id:v.node,turn:S.turn});}
S.current=v.node;}
for(const a of (v.affordances||[])){if(a.door&&S.current){if(!Array.isArray(S.doors[S.current]))S.doors[S.current]=[];if(!S.doors[S.current].includes(a.door))S.doors[S.current].push(a.door);}}
if(v.witness&&v.witness.residual){S.residuals.push({id:'r'+S.turn,label:asked,cls:v.witness.residual['class'],
unacc:(v.witness.residual.unaccounted||[]).join(', ')});renderResiduals();}
if(v.evidential&&v.evidential.input_marked){S.told.push({claim:asked,verdict:v.evidential.verdict||'noted',marked:v.evidential.input_marked});renderTold();}}
function fmt(v){return Array.isArray(v)?(v.join(', ')||'—'):String(v);}
async function ingest(e){e.preventDefault();
const r=await fetch('ingest',{method:'POST',headers:{'Content-Type':'application/json','X-Oracle-Session':sid()},
body:JSON.stringify({title:document.getElementById('dt').value,text:document.getElementById('dx').value})});
const v=await r.json();
document.getElementById('ir').textContent=v.status+(v.admitted_sentences?(' · '+v.admitted_sentences+' sentences admitted'):(' · '+(v.reason||'')));}
function renderResiduals(){const el=document.getElementById('residuals');el.innerHTML='';
if(!S.residuals.length){el.innerHTML='<p class=meta>Nothing missing right now.</p>';return;}
for(const r of S.residuals){const c=document.createElement('div');c.className='card';
c.innerHTML='<div class=rq></div>';c.firstChild.textContent='could not type: "'+r.label+'"'+(r.unacc?(' · untouched: '+r.unacc):'');
const b1=document.createElement('button');b1.textContent='Pursue';b1.onclick=()=>salience(r,'pursue',c);
const b2=document.createElement('button');b2.textContent='Ignore';b2.onclick=()=>salience(r,'dismiss',c);
c.appendChild(b1);c.appendChild(b2);el.appendChild(c);}}
async function salience(r,action,card){const resp=await fetch('salience',{method:'POST',
headers:{'Content-Type':'application/json','X-Oracle-Session':sid()},
body:JSON.stringify({residual_id:r.id,label:r.label,action:action})});
const v=await resp.json();S.residuals=S.residuals.filter(x=>x.id!==r.id);
if(v.goals)S.goals=v.goals;renderResiduals();renderGoals();}
function renderGoals(){const el=document.getElementById('goals');el.innerHTML='';
if(!S.goals.length)return;const h=document.createElement('div');h.className='meta';h.textContent='Attending to:';el.appendChild(h);
for(const g of S.goals){const p=document.createElement('span');p.className='goalpill';p.textContent=g;el.appendChild(p);}}
function renderTold(){const el=document.getElementById('told');el.innerHTML='';
for(const t of S.told){const d=document.createElement('div');d.className='told';
const v=document.createElement('span');v.className='verdict v-'+(t.verdict||'no_verdict');
v.textContent={'supported':'supported','refuted':'not supported','no_verdict':'unsettled','noted':'noted'}[t.verdict]||t.verdict;
d.textContent='"'+t.claim+'" ';d.appendChild(v);el.appendChild(d);}}
function drawMap(){const svg=document.getElementById('map');const W=svg.clientWidth||520,H=340;
svg.setAttribute('viewBox','0 0 '+W+' '+H);svg.innerHTML='';
const ns='http://www.w3.org/2000/svg';const n=S.nodes.length;
if(!n){const t=document.createElementNS(ns,'text');t.setAttribute('x',W/2);t.setAttribute('y',H/2);
t.setAttribute('text-anchor','middle');t.setAttribute('font-size','14');t.setAttribute('fill','#9b8264');
t.textContent='your map grows as you talk — ask something';svg.appendChild(t);return;}
const xs=[];for(let i=0;i<n;i++){xs.push(n===1?W/2:40+i*(W-80)/(n-1));}
// thread
for(let i=1;i<n;i++){const l=document.createElementNS(ns,'line');
l.setAttribute('x1',xs[i-1]);l.setAttribute('y1',H/2-20);l.setAttribute('x2',xs[i]);l.setAttribute('y2',H/2-20);
l.setAttribute('stroke','#c89540');l.setAttribute('stroke-width','3');svg.appendChild(l);}
S.nodes.forEach((node,i)=>{const g=document.createElementNS(ns,'g');g.style.cursor='pointer';
g.onclick=()=>{document.getElementById('q').value='Tell me more about '+node.id+'.';document.getElementById('askbtn').click();};
const c=document.createElementNS(ns,'circle');c.setAttribute('cx',xs[i]);c.setAttribute('cy',H/2-20);
c.setAttribute('r',node.id===S.current?24:18);c.setAttribute('fill',node.id===S.current?'#e87a3a':'#c89540');
c.setAttribute('stroke','#3a2818');c.setAttribute('stroke-width','3');g.appendChild(c);
const t=document.createElementNS(ns,'text');t.setAttribute('x',xs[i]);t.setAttribute('y',H/2-56);
t.setAttribute('text-anchor','middle');t.setAttribute('font-size','13');t.setAttribute('font-weight','600');
t.setAttribute('fill','#3a2818');t.textContent=node.id.length>18?node.id.slice(0,17)+'…':node.id;g.appendChild(t);
svg.appendChild(g);
const doors=Array.isArray(S.doors[node.id])?S.doors[node.id]:[];doors.slice(0,4).forEach((dr,j)=>{
const dg=document.createElementNS(ns,'g');dg.style.cursor='pointer';
dg.onclick=()=>{document.getElementById('q').value='What is '+dr+'?';document.getElementById('askbtn').click();};
const dx=xs[i]+(j-doors.length/2+0.5)*46,dy=H/2+62;
const dl=document.createElementNS(ns,'line');dl.setAttribute('x1',xs[i]);dl.setAttribute('y1',H/2-2);
dl.setAttribute('x2',dx);dl.setAttribute('y2',dy-14);dl.setAttribute('stroke','#7a9a6d');
dl.setAttribute('stroke-width','2');dl.setAttribute('stroke-dasharray','4 4');svg.appendChild(dl);
const dc=document.createElementNS(ns,'circle');dc.setAttribute('cx',dx);dc.setAttribute('cy',dy);
dc.setAttribute('r',12);dc.setAttribute('fill','#faf0d0');dc.setAttribute('stroke','#7a9a6d');
dc.setAttribute('stroke-width','2');dg.appendChild(dc);
const dt=document.createElementNS(ns,'text');dt.setAttribute('x',dx);dt.setAttribute('y',dy+26);
dt.setAttribute('text-anchor','middle');dt.setAttribute('font-size','10');dt.setAttribute('fill','#5c7a50');
dt.textContent=dr.length>12?dr.slice(0,11)+'…':dr;dg.appendChild(dt);svg.appendChild(dg);});});}
window.addEventListener('resize',drawMap);
async function loopTick(){try{const r=await fetch('loop');const v=await r.json();
const st=document.getElementById('loopstatus');st.innerHTML='';
const dot=document.createElement('span');dot.className='livedot';dot.textContent=v.live?'● live':'○ idle';st.appendChild(dot);
st.appendChild(document.createTextNode(' · cycle '+(v.cycles??'?')+' · '+(v.ledger_events||0)+' ledger events · gate record: '+
v.gate_totals.admits+' admitted / '+v.gate_totals.rejects+' rejected — every rejection preserved · last: '+(v.last_ts||'—')));
const b=v.baseline||{};
document.getElementById('loopbase').textContent='read '+b.read+'/248 · answered '+b.answered+'/248 · continuity '+b.continuity+'/'+(b.continuity_of||'—')+' · grounding '+b.grounding_cited;
document.getElementById('loopgaps').textContent=v.gaps_total+' gaps declared by its own self-model. '+(v.gaps||[]).slice(0,4).join(' · ');
const f=document.getElementById('loopfeed');f.innerHTML='';
for(const e of (v.feed||[]).slice(0,9)){const d=document.createElement('div');d.className='evrow'+(e.cls?' '+e.cls:'');
d.textContent=(e.t?e.t.slice(5,16)+' — ':'')+e.txt;f.appendChild(d);}
const L=document.getElementById('looplines');L.innerHTML='';
const l1=document.createElement('div');l1.textContent='Box C line: '+v.boxc_count+' runtimes → head '+((v.head&&v.head.module)||'').split('_').pop().toUpperCase()+' · sha '+(v.head&&v.head.sha256)+'…';L.appendChild(l1);
const l2=document.createElement('div');l2.textContent='Sibling line: '+v.local_line.count+' admitted → '+String(v.local_line.head||'').toUpperCase();L.appendChild(l2);
const m=v.merge||{};const l3=document.createElement('div');
l3.textContent='merge, measured on the same gate: answered '+(m.answered_delta>0?'+':'')+(m.answered_delta??'?')+' · continuity '+(m.continuity_delta??'?')+' · awaiting the human signature ';
const vl=document.createElement('span');vl.className='vlink';vl.textContent='verify';
vl.onclick=async()=>{const r2=await fetch('verify?f=m62e_merge_measure_v1.json');const j=await r2.json();
vl.textContent='sha256 '+String(j.sha256||'').slice(0,16)+'… · immutable: '+j.immutable;};
l3.appendChild(vl);L.appendChild(l3);
const e2=v.ew2;const sr=v.served_rate;
document.getElementById('worldhead').textContent=(e2?('ENSOULEDWORLD 2 · tick '+e2.tick+' · '+e2.souls+' souls · '+e2.structures+' structures standing'):'EW2 offline')+
(sr?(' · served: '+(100*(sr.volume_rate||0)).toFixed(0)+'% of volume, '+(100*(sr.unique_rate||0)).toFixed(0)+'% of '+sr.unique_window+' unique'):'')+
' — their words enter the same inbox as yours';
const wf=document.getElementById('worldfeed');wf.innerHTML='';
for(const t of (v.world_feed||[])){const d=document.createElement('div');d.className='soulrow';
const n=document.createElement('span');n.className='soulname';n.textContent=t.soul+' ('+t.archetype+'): ';
d.appendChild(n);d.appendChild(document.createTextNode('"'+t.thought+'"'));wf.appendChild(d);}
document.getElementById('learnline').textContent="what's being learned: "+(v.learning||'—');
const sl=document.getElementById('shapeline');
if(v.shape&&v.shape.dims){const parts=Object.entries(v.shape.dims).map(([d,x])=>d+' '+x.current+'/'+x.target);
sl.textContent='target shape ('+v.shape.declared_by.split(' (')[0]+'): '+parts.join(' · ')+'  →  distance '+v.shape.distance+' · attending first to '+v.shape.attend_first+' · only a human can re-declare the shape';}
else{sl.textContent='target shape: declared, first match next worker cycle';}
document.getElementById('loopfoot').textContent=v.reports+' sealed reports on disk · '+v.residue_turns+' public turns recorded (the unparsed become rule candidates) · '+
(v.curriculum_pursued||0)+' human-pursued gaps queued as curriculum · garden: '+(v.garden||[]).join(', ');
}catch(err){document.getElementById('loopstatus').textContent='loop view unavailable';}}
async function stateRebuild(){try{const r=await fetch('state',{headers:{'X-Oracle-Session':sid()}});const v=await r.json();
S.goals=v.goals||[];if(S.goals.length)renderGoals();
for(const t of (v.turns||[])){S.turn++;
if(t.node){if(!S.nodes.find(n=>n.id===t.node))S.nodes.push({id:t.node,turn:S.turn});S.current=t.node;}
for(const dr of (t.doors||[])){if(S.current){if(!Array.isArray(S.doors[S.current]))S.doors[S.current]=[];
if(!S.doors[S.current].includes(dr))S.doors[S.current].push(dr);}}
if(t.evidential&&t.evidential.input_marked)S.told.push({claim:t.in,verdict:t.evidential.verdict||'noted'});
if(t.residual&&!S.goals.includes(t.in))S.residuals.push({id:'r'+S.turn,label:t.in,cls:t.residual['class'],unacc:(t.residual.unaccounted||[]).join(', ')});}
if(S.told.length)renderTold();if(S.residuals.length)renderResiduals();drawMap();}catch(e){}}
stateRebuild();loopTick();setInterval(loopTick,15000);
async function gallery(){try{const r=await fetch('worldart');const v=await r.json();
const g=document.getElementById('gallery');g.innerHTML='';
for(const p of (v.pieces||[]).slice(0,8)){const d=document.createElement('div');
d.style.cssText='width:110px;cursor:pointer';d.innerHTML=p.svg;
const c=document.createElement('div');c.className='meta';c.style.fontSize='.68em';
c.textContent=p.actor+' · '+p.verb+' · tick '+p.tick;d.appendChild(c);
d.title=p.content+'  ['+p.derivation+']';
d.onclick=()=>{document.getElementById('galnote').textContent='"'+p.content+'" — '+p.actor+', tick '+p.tick+' · '+p.derivation;};
g.appendChild(d);}
}catch(e){}}
gallery();setInterval(gallery,60000);
</script>
<script type="module">
import * as THREE from './three.module.js';
const KIND={column:{g:'cyl',c:0xc89540,h:3},tree:{g:'cone',c:0x5c8a4e,h:2.6},bridge:{g:'box',c:0x8a7355,h:0.7,w:3},tower:{g:'box',c:0x7a6a8a,h:7},temple:{g:'box',c:0xd4b24a,h:3.5,w:2.4},manor:{g:'box',c:0x9a6b4f,h:2.6,w:2},castle:{g:'box',c:0x555a6e,h:5,w:2.6}};
async function world3d(){const holder=document.getElementById('w3d');if(!holder)return;
const r=await fetch('worldscene');const spec=await r.json();
const W=holder.clientWidth||520,H=300;
const scene=new THREE.Scene();scene.background=new THREE.Color(0x12141c);
const cam=new THREE.PerspectiveCamera(55,W/H,0.1,600);
const ren=new THREE.WebGLRenderer({antialias:true});ren.setSize(W,H);holder.innerHTML='';holder.appendChild(ren.domElement);
scene.add(new THREE.AmbientLight(0xffffff,0.55));
const sun=new THREE.DirectionalLight(0xfff2d0,1.0);sun.position.set(40,80,20);scene.add(sun);
const ground=new THREE.Mesh(new THREE.CircleGeometry(90,48),new THREE.MeshLambertMaterial({color:0x1e2417}));
ground.rotation.x=-Math.PI/2;scene.add(ground);
const meshes=[];
for(const e of (spec.elements||[])){const k=KIND[e.kind]||{g:'box',c:0x888888,h:2};
let geo;if(k.g==='cyl')geo=new THREE.CylinderGeometry(0.5,0.6,k.h,10);
else if(k.g==='cone')geo=new THREE.ConeGeometry(1.1,k.h,8);
else geo=new THREE.BoxGeometry(k.w||1.4,k.h,k.w||1.4);
const m=new THREE.Mesh(geo,new THREE.MeshLambertMaterial({color:k.c}));
m.position.set(e.x,k.h/2,e.z);m.userData=e;scene.add(m);meshes.push(m);}
const ray=new THREE.Raycaster(),ptr=new THREE.Vector2();
ren.domElement.addEventListener('click',ev=>{const b=ren.domElement.getBoundingClientRect();
ptr.x=((ev.clientX-b.left)/b.width)*2-1;ptr.y=-((ev.clientY-b.top)/b.height)*2+1;
ray.setFromCamera(ptr,cam);const hit=ray.intersectObjects(meshes)[0];
if(hit){const e=hit.object.userData,p=e.provenance||{};
document.getElementById('w3dnote').textContent='a '+e.kind+' raised by '+p.actor+' at tick '+p.tick+(p.note?(' — "'+p.note+'"'):'')+' · clause '+e.clause_id+' · '+p.source;}});
let t=0;function frame(){t+=0.0018;const rad=78;
cam.position.set(Math.sin(t)*rad,42,Math.cos(t)*rad);cam.lookAt(0,0,0);
ren.render(scene,cam);requestAnimationFrame(frame);}frame();
document.getElementById('w3dnote').textContent=(spec.count||0)+' structures from the ledger — every one traces to its record; click any.';}
world3d();
</script></html>"""


class Handler(BaseHTTPRequestHandler):
    runtime = None
    MAX_BODY = 300_000

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > self.MAX_BODY:
            raise ValueError("body too large")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _session(self):
        token = self.headers.get("X-Oracle-Session", "")
        if token and 8 <= len(token) <= 64:
            return "tk_" + "".join(c for c in token if c.isalnum())[:48]
        return "ip_" + (self.headers.get("X-Real-IP") or self.client_address[0])

    _three_cache = None

    def do_GET(self):  # noqa: N802
        path, _, query = self.path.partition("?")
        path = path.rstrip("/")
        if path.endswith("/three.module.js"):
            if Handler._three_cache is None:
                Handler._three_cache = Path(
                    "/opt/wander-engine-v2/node_modules/three/build/three.module.js"
                ).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(Handler._three_cache)))
            self.end_headers()
            self.wfile.write(Handler._three_cache)
            return
        if path.endswith("/worldart"):
            pieces = []
            try:
                lines = WORLD_LEDGER_EW2.read_text(
                    encoding="utf-8", errors="replace").strip().splitlines()
                for ln in reversed(lines):
                    try:
                        r = json.loads(ln)
                    except Exception:
                        continue
                    if r.get("type") != "act" or r.get("verb") not in (
                            "art", "compose", "adorn", "inscribe"):
                        continue
                    key = f"{r.get('actor')}|{r.get('ts')}|{r.get('content','')[:60]}"
                    seed = hashlib.sha256(key.encode("utf-8", "replace")).digest()
                    words = [w for w in str(r.get("content", "")).lower().split()
                             if w.isalpha()][:8]
                    bg = seed[0] * 360 // 255
                    shapes = []
                    n = 3 + (seed[1] % 5)
                    for i in range(n):
                        b = seed[2 + i * 4: 6 + i * 4]
                        if len(b) < 4:
                            break
                        hue = (b[0] * 360 // 255)
                        cx, cy = 12 + b[1] % 136, 12 + b[2] % 136
                        sz = 8 + b[3] % 34
                        wsrc = words[i % len(words)] if words else "silence"
                        form = ("circle" if (b[0] + len(wsrc)) % 3 == 0 else
                                "rect" if (b[0] + len(wsrc)) % 3 == 1 else "tri")
                        if form == "circle":
                            el = (f'<circle cx="{cx}" cy="{cy}" r="{sz//2}" '
                                  f'fill="hsl({hue},60%,55%)" opacity="0.85"/>')
                        elif form == "rect":
                            el = (f'<rect x="{cx-sz//2}" y="{cy-sz//2}" width="{sz}" '
                                  f'height="{sz}" fill="hsl({hue},55%,50%)" '
                                  f'opacity="0.85" transform="rotate({b[1]%90} {cx} {cy})"/>')
                        else:
                            el = (f'<polygon points="{cx},{cy-sz//2} {cx-sz//2},{cy+sz//2} '
                                  f'{cx+sz//2},{cy+sz//2}" fill="hsl({hue},65%,45%)" '
                                  f'opacity="0.85"/>')
                        shapes.append(el)
                    svg = (f'<svg viewBox="0 0 160 160" xmlns="http://www.w3.org/2000/svg">'
                           f'<rect width="160" height="160" fill="hsl({bg},30%,90%)"/>'
                           + "".join(shapes) + "</svg>")
                    pieces.append({"clause_id": hashlib.sha256(
                                       key.encode()).hexdigest()[:12],
                                   "actor": r.get("actor"), "tick": r.get("tick"),
                                   "verb": r.get("verb"),
                                   "content": str(r.get("content", ""))[:100],
                                   "svg": svg,
                                   "derivation": "deterministic: seed=sha256(act); "
                                                 "palette+geometry from seed bytes + "
                                                 "content words; reproducible"})
                    if len(pieces) >= 12:
                        break
            except Exception:
                pass
            self._send(200, json.dumps({"schema": "oracle-worldart-v1",
                                        "count": len(pieces), "pieces": pieces},
                                       ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")
            return
        if path.endswith("/worldscene"):
            elements = []
            seen = set()
            try:
                lines = WORLD_LEDGER_EW2.read_text(
                    encoding="utf-8", errors="replace").strip().splitlines()
                for ln in reversed(lines):
                    try:
                        r = json.loads(ln)
                    except Exception:
                        continue
                    if r.get("type") != "build" or r.get("x") is None:
                        continue
                    key = (r.get("actor"), r.get("kind"),
                           round(float(r.get("x", 0)), 1), round(float(r.get("z", 0)), 1))
                    if key in seen:
                        continue
                    seen.add(key)
                    elements.append({
                        "clause_id": hashlib.sha256(
                            json.dumps(key, sort_keys=True).encode()).hexdigest()[:12],
                        "kind": r.get("kind"), "x": r.get("x"), "z": r.get("z"),
                        "provenance": {"actor": r.get("actor"), "tick": r.get("tick"),
                                       "ts": r.get("ts"),
                                       "note": str(r.get("content", ""))[:80],
                                       "source": "world_ledger_ew2"}})
                    if len(elements) >= 400:
                        break
            except Exception:
                pass
            body = {"schema": "oracle-worldscene-spec-v1",
                    "law": "every element traces to a ledger record (charter "
                           "image_generation warrant: spec_correspondence_map)",
                    "mapping": {"column": "cylinder", "tree": "cone", "bridge": "flatbox",
                                "tower": "tallbox", "temple": "widebox", "manor": "box",
                                "castle": "bigbox"},
                    "count": len(elements), "elements": elements}
            self._send(200, json.dumps(body, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")
            return
        if path.endswith("/loop"):
            self._send(200, json.dumps(loop_snapshot(), ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")
            return
        if path.endswith("/state"):
            session = self._session()
            try:
                recs = Handler.runtime.path(session)
            except Exception:
                recs = []
            turns = [state_turn(r, Handler.runtime) for r in recs]
            o = ORGANS.get(session)
            goals = ([g["description"] for g in o["goals"].goals.values()
                      if g.get("status") in ("queued", "active")] if o else [])
            self._send(200, json.dumps({"turns": turns, "goals": goals},
                                       ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")
            return
        if path.endswith("/verify"):
            q = urllib.parse.parse_qs(query)
            fname = os.path.basename((q.get("f") or [""])[0])
            self._send(200, json.dumps(verify_report(fname)).encode("utf-8"),
                       "application/json; charset=utf-8")
            return
        self.send_response(200)
        body = PAGE.encode("utf-8")
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        path = self.path.rstrip("/")
        try:
            payload = self._json()
            session = self._session()
            if path.endswith("chat"):
                text = str(payload.get("text", ""))[:2000]
                value = Handler.runtime.chat(text, session_id=session)
                # the [ev:*] tag is machinery: the verdict sentence + typed evidential
                # field carry the meaning; strip it from display so the citation
                # renderer never mistakes it for a corpus tag.
                display = EV_TAG.sub("", str(value.get("response", "")))
                rendered, references = citations(display)
                witness = None
                try:
                    records = Handler.runtime.path(session)
                    if records:
                        witness = {k: v for k, v in dict(records[-1]).items()
                                   if k not in ("in_terms", "out_terms")}
                except Exception:
                    witness = None
                body = {"response": rendered, "references": references,
                        "status": value.get("status"), "path": value.get("path"),
                        "latency_ms": value.get("latency_ms"),
                        "witness": witness,
                        "speech": speech(witness, value),
                        "node": node_of(witness, value),
                        "evidential": value.get("evidential"),
                        "affordances": affordances(witness, value, Handler.runtime)}
                try:
                    record = {"ts": int(time.time()), "s": session[:16], "text": text,
                              "path": body["path"], "status": body["status"]}
                    with open("/opt/oracle-clm/residue_turns.jsonl", "a", encoding="utf-8") as rf:
                        rf.write(json.dumps(record, ensure_ascii=False) + "\n")
                except Exception:
                    pass
            elif path.endswith("salience"):
                o = organs(session)
                rid = str(payload.get("residual_id", ""))[:40] or "r0"
                label = str(payload.get("label", ""))[:120]
                action = str(payload.get("action", ""))
                if action == "pursue":
                    try:
                        o["goals"].admit(rid, label or rid, f"human:{session[:12]}", 0.8)
                    except GoalStateError:
                        pass
                    try:
                        o["goals"].activate(rid)
                    except Exception:
                        pass
                    o["arb"].admit({"residual_id": rid, "kind": "conversation_gap",
                                    "source": "session", "urgency": 0.8,
                                    "curiosity": 0.7, "cost": 0.2, "goal_hint": "attend"})
                    try:
                        with CURRICULUM.open("a", encoding="utf-8") as cf:
                            cf.write(json.dumps({"ts": int(time.time()),
                                                 "who": f"human:{session[:12]}",
                                                 "kind": "pursued_gap",
                                                 "label": label},
                                                ensure_ascii=False) + "\n")
                    except Exception:
                        pass
                else:
                    o["arb"].admit({"residual_id": rid, "kind": "conversation_gap",
                                    "source": "session", "urgency": 0.0,
                                    "curiosity": 0.0, "cost": 1.0})
                o["decision"] = o["arb"].arbitrate()
                goals = [g["description"] for g in o["goals"].goals.values()
                         if g.get("status") in ("queued", "active")]
                body = {"ok": True, "goals": goals,
                        "selected": [s["residual_id"] for s in
                                     (o["decision"] or {}).get("selected", [])]}
            elif path.endswith("ingest"):
                body = Handler.runtime.ingest_document(session,
                                                       str(payload.get("title", "")),
                                                       str(payload.get("text", ""))[:250000])
            else:
                self._send(404, b"{}", "application/json")
                return
        except Exception as err:  # noqa: BLE001
            body = {"status": "error", "response": f"internal error: {type(err).__name__}",
                    "path": "app", "latency_ms": 0}
        self._send(200, json.dumps(body, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def log_message(self, *args):
        pass


def main() -> int:
    build = Path(os.environ.get("ORACLE_WIKIPEDIA_BUILD",
                                str(FULL_BUILD if FULL_BUILD.exists() else LITE_BUILD)))
    state_root = Path(os.environ.get("ORACLE_STATE_ROOT", str(PHASE / "space_state")))
    print("loading anchor store (one-time)...", flush=True)
    Handler.runtime = HarnessRuntime(state_root=state_root, wikipedia_build=build)
    print(f"anchors resident: {len(Handler.runtime.anchors.title_to_page):,}", flush=True)
    port = int(os.environ.get("PORT", "8095"))
    host = os.environ.get("ORACLE_BIND_HOST", "127.0.0.1")
    print(f"serving v20 (THE HARNESS + THE LOOP + THE WORLD: continuous fold worker + "
          f"ensouled feed live, verify-by-hash, full recursive circuit) on {host}:{port}", flush=True)
    HTTPServer((host, port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
