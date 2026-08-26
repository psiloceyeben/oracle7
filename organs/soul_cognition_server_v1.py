#!/usr/bin/env python3
"""Soul cognition server v1 - the CLM chain served to the world's agents.

The deliberation tier of EW2's tiered cognition: souls POST /think and receive TYPED
cognition from the latest admitted runtime - warranted answers, kind verdicts, hearsay
checks through the evidential channel, or honest declines. Every response carries the
witness fields a coordination ledger needs. Threaded (unlike the old holon server's
concurrency-3 gate); loopback only; per-soul sessions so dialogue state is real.

Endpoints:
  POST /query   HOLON-COMPAT (the runner's protocol, zero runner edits):
                {"prompt","mode","max_tokens"} -> {"text": "..."}
                The embedded question is extracted from the completion prompt and run
                through the chain; a warranted answer returns (citation tags stripped
                for world surface); a decline returns "" - the runner's own fallback
                path takes over. THIS IS TIERED COGNITION AT THE SEAM: the chain
                answers what it warrants, the runner's reflexes handle the rest.
                Every query is ledgered (soul_queries.jsonl) - declines are fold fuel.
  POST /think   {"soul": "<id>", "text": "<utterance>"}  ->
                {"status", "path", "response", "evidential", "witness": {operator,
                 out_status, continuity, residual}, "latency_ms"}
  GET  /health  {"ok": true, "runtime": "...", "souls_seen": N}

This is the substrate seam: EW1's runner keeps the holon for the expressive tier;
EW2's runner points deliberation here. Staged; nothing existing is touched.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from oracle_release_runtime import PHASE

sys.path.insert(0, str(PHASE / "self_loop" / "admitted"))

def _latest_admitted():
    """Resolve the newest admitted w-runtime at startup; daemon admissions upgrade
    the world's brain on next service restart - through the same gate as everything."""
    import importlib
    best = 0
    for f in (PHASE / "self_loop" / "admitted").glob("oracle_release_runtime_w*.py"):
        try:
            best = max(best, int(f.stem.split("_w")[-1]))
        except Exception:
            continue
    name = f"oracle_release_runtime_w{best}" if best else "oracle_release_runtime_ao"
    cls_name = f"OracleReleaseRuntimeW{best}" if best else "OracleReleaseRuntimeAO"
    mod = importlib.import_module(name)
    return name, getattr(mod, cls_name)


_RT_NAME, _RT_CLS = _latest_admitted()
RUNTIME_NAME = f"{_RT_NAME} (latest admitted)"
QUERY_LEDGER = PHASE / "self_loop" / "soul_queries.jsonl"
WORLD_LEDGER_EW2 = PHASE / "self_loop" / "world_ledger_ew2.jsonl"
QUESTION_RX = __import__("re").compile(
    r"[\w'\-]+ said ,\s*(?P<q>.+?)\s+[A-Za-z][\w'\-]{0,24} said ,\s*$", __import__("re").S)
CITE_STRIP = __import__("re").compile(r"\s*\[[\w:.'\-]{2,}\]")
LOCK = threading.Lock()          # the chain's dialogue state is not thread-safe; serialize chat
SOULS = set()

# ── the world's own record as an evidence corpus ────────────────────────────────
# The EW2 world ledger is observed-complete for builds since launch, so scarcity
# statements ("no library yet stands") satisfy the closure law's completeness +
# observability conditions - the first legitimately closed-world domain here.
_world_cache = {"t": 0.0, "recs": []}
_decline_cache: dict = {}
DECLINE_TTL = 600.0
_RE = __import__("re")
SEE_RX = _RE.compile(r"(what do you see|what is around|look around)", _RE.I)
REMEMBER_RX = _RE.compile(r"what do you remember", _RE.I)
MAKE_RX = _RE.compile(r"(what will you (make|build)|what grand structure)", _RE.I)
PLACE_RX = _RE.compile(r"(what is this place|where am i|where are we)", _RE.I)
FRAME_RX = _RE.compile(r"^in the (?P<place>[a-z][a-z ]{2,24}?) at (?P<phase>[a-z]{3,16})", _RE.I)
KNOWN_KINDS = ["column", "tree", "bridge", "temple", "tower", "garden", "library",
               "house", "well", "gate", "wall", "statue"]


def world_recs() -> list:
    now = time.time()
    if now - _world_cache["t"] > 5:
        try:
            lines = WORLD_LEDGER_EW2.read_text(encoding="utf-8").strip().splitlines()[-500:]
            recs = []
            for l in lines:
                if not l.strip():
                    continue
                try:
                    recs.append(json.loads(l))
                except Exception:
                    continue                      # partial line mid-write: skip, never poison
            if recs:
                _world_cache["recs"] = recs
        except Exception:
            pass
        _world_cache["t"] = now
    return _world_cache["recs"]


def world_route(question: str) -> tuple[str, str] | None:
    """Serve situational questions from attested world records. Returns
    (route_name, text) or None to fall through to the chain."""
    recs = world_recs()
    if not recs:
        return None
    if SEE_RX.search(question):
        builds = [r for r in recs if r.get("type") == "build"][-4:]
        actors = []
        for r in reversed(recs):
            a = r.get("actor")
            if a and a not in actors:
                actors.append(a)
            if len(actors) >= 3:
                break
        bits = []
        if builds:
            bits.append("the record holds " + "; ".join(
                f"a {b.get('kind','work')} raised by {b.get('actor','someone')}"
                + (f" — \"{b['content'][:60]}\"" if b.get("content") else "")
                for b in builds))
        if actors:
            bits.append("near voices: " + ", ".join(actors))
        return ("world_see", ". ".join(bits)[:360]) if bits else None
    if REMEMBER_RX.search(question):
        notable = [r for r in recs
                   if r.get("type") in ("build", "lineage")
                   or (r.get("type") == "act" and "named" in str(r.get("content", "")))][-4:]
        if not notable:
            return None
        bits = []
        for r in notable:
            if r.get("type") == "build":
                bits.append(f"{r.get('actor')} raised a {r.get('kind','work')}")
            elif r.get("type") == "lineage":
                bits.append(f"{r.get('actor')} came to be ({r.get('verb')})")
            else:
                bits.append(f"{r.get('actor')} said: {str(r.get('content',''))[:60]}")
        return ("world_remember", "the record remembers: " + "; ".join(bits))
    if MAKE_RX.search(question):
        census = {}
        for r in recs:
            if r.get("type") == "build" and r.get("kind"):
                census[r["kind"]] = census.get(r["kind"], 0) + 1
        if not census:
            return None
        common = sorted(census.items(), key=lambda x: -x[1])[:3]
        absent = [k for k in KNOWN_KINDS if k not in census][:3]
        text = ("the record shows " + ", ".join(f"{n} {k}s" for k, n in common))
        if absent:
            text += ". none yet stand of: " + ", ".join(absent)
        return ("world_scarcity", text[:360])
    return None


class Handler(BaseHTTPRequestHandler):
    runtime = None
    MAX_BODY = 20_000

    def _json_out(self, code, obj):
        try:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass                      # client vanished mid-response: not an event

    def do_GET(self):  # noqa: N802
        if self.path.rstrip("/").endswith("selftest"):
            report = {"thread": __import__("threading").current_thread().name}
            try:
                import stage5m13e7_benchfold_induction_v1 as bench_mod
                report["bench_db"] = str(bench_mod.DB)
                try:
                    pid = Handler.runtime.bench_query.page_id("the cell cycle")
                    report["bench_page_id"] = pid
                except Exception as e:
                    report["bench_error"] = f"{type(e).__name__}: {e}"
                with LOCK:
                    r = Handler.runtime.chat("Summarize the cell cycle.",
                                             session_id="selftest")
                report["chat_status"] = r.get("status")
                report["chat_head"] = str(r.get("response", ""))[:90]
            except Exception as e:
                report["error"] = f"{type(e).__name__}: {e}"
            self._json_out(200, report)
            return
        if self.path.rstrip("/").endswith("health"):
            anchors = 0
            try:
                anchors = len(Handler.runtime.anchors.title_to_page)
            except Exception:
                pass
            self._json_out(200, {"ok": True, "runtime": RUNTIME_NAME,
                                 "anchors": anchors,
                                 "wikipedia_build": os.environ.get("ORACLE_WIKIPEDIA_BUILD", "default"),
                                 "souls_seen": len(SOULS)})
        else:
            self._json_out(404, {"error": "POST /think"})

    def _ledger_query(self, rec):
        try:
            with QUERY_LEDGER.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def do_POST(self):  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > self.MAX_BODY:
                raise ValueError("too large")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if self.path.rstrip("/").endswith("/query"):
                prompt = str(payload.get("prompt", ""))[:800]
                m = QUESTION_RX.search(prompt)
                question = (m.group("q").strip() if m else prompt.strip())[:400]
                t0 = time.perf_counter()
                wr = world_route(question)
                if wr is None and PLACE_RX.search(question):
                    fm = FRAME_RX.search(prompt)
                    if fm:
                        recs = world_recs()
                        near = [r for r in recs if r.get("type") == "build"][-2:]
                        txt = f"this place is the {fm.group('place')} at {fm.group('phase')}"
                        if near:
                            txt += ". near stand " + " and ".join(
                                f"a {b.get('kind','work')} by {b.get('actor','someone')}"
                                for b in near)
                        wr = ("world_place", txt[:300] + ".")
                if wr is None:
                    dc = _decline_cache.get(question)
                    if dc and time.time() - dc < DECLINE_TTL:
                        self._ledger_query({"ts": int(time.time()), "q": question[:160],
                                            "status": "declined_cached", "served": False,
                                            "route": "decline_cache", "ms": 0.1})
                        self._json_out(200, {"text": ""})
                        return
                if wr is not None:
                    route, text = wr
                    entry = {"ts": int(time.time()), "q": question[:160],
                             "status": "answered", "served": True, "route": route,
                             "ms": round(1000 * (time.perf_counter() - t0), 1)}
                    if route == "world_scarcity" and "none yet stand of:" in text:
                        entry["absent"] = [k.strip() for k in
                                           text.split("none yet stand of:")[-1].split(",")]
                    self._ledger_query(entry)
                    self._json_out(200, {"text": text})
                    return
                with LOCK:
                    result = Handler.runtime.chat(question, session_id="world_query")
                status = str(result.get("status"))
                text = ""
                # identity guard: a soul asked "who are you" answers as ITSELF (runner
                # reflex), never by relaying the chain's autobiography into soul speech.
                if str(result.get("path", "")).startswith("act:about"):
                    status = "identity_excluded"
                if status == "answered":
                    text = CITE_STRIP.sub("", str(result.get("response", ""))).strip()
                    limit = max(60, int(payload.get("max_tokens", 32)) * 6)
                    text = text[:limit]
                if not text:
                    _decline_cache[question] = time.time()
                    if len(_decline_cache) > 500:
                        _decline_cache.pop(next(iter(_decline_cache)))
                self._ledger_query({"ts": int(time.time()), "q": question[:160],
                                    "status": status, "served": bool(text), "route": "chain",
                                    "ms": round(1000 * (time.perf_counter() - t0), 1)})
                self._json_out(200, {"text": text})
                return
            soul = "".join(c for c in str(payload.get("soul", "anon"))[:24]
                           if c.isalnum() or c in "-_") or "anon"
            text = str(payload.get("text", ""))[:800]
            SOULS.add(soul)
            t0 = time.perf_counter()
            with LOCK:
                result = Handler.runtime.chat(text, session_id=f"soul_{soul}")
            witness = None
            try:
                recs = Handler.runtime.path(f"soul_{soul}")
                if recs:
                    w = recs[-1]
                    witness = {"operator": w.get("operator"),
                               "out_status": w.get("out_status"),
                               "continuity": bool(w.get("continuity")),
                               "residual": w.get("residual")}
            except Exception:
                pass
            self._json_out(200, {
                "status": result.get("status"), "path": result.get("path"),
                "response": str(result.get("response", ""))[:1200],
                "evidential": result.get("evidential"),
                "witness": witness,
                "latency_ms": round(1000.0 * (time.perf_counter() - t0), 1)})
        except Exception as err:  # noqa: BLE001
            self._json_out(200, {"status": "error",
                                 "error": type(err).__name__})

    def log_message(self, *args):
        pass


def main() -> int:
    print("loading the latest admitted runtime...", flush=True)
    Handler.runtime = _RT_CLS(
        state_root=Path(os.environ.get("SOUL_STATE_ROOT",
                                       str(PHASE / "soul_cognition_state"))),
        wikipedia_build=Path(os.environ.get(
            "ORACLE_WIKIPEDIA_BUILD", str(PHASE / "m13e5_simplewiki_build_a_v1"))))
    try:
        import sqlite3
        reopened = 0

        def _walk(o, depth=0, seen=None):
            nonlocal reopened
            seen = seen if seen is not None else set()
            if id(o) in seen or depth > 5:
                return
            seen.add(id(o))
            d = getattr(o, "__dict__", None)
            if not isinstance(d, dict):
                return
            for k, v in list(d.items()):
                if isinstance(v, sqlite3.Connection):
                    try:
                        rows = v.execute("PRAGMA database_list").fetchall()
                        path = next((r[2] for r in rows if r[1] == "main" and r[2]), None)
                        if path:
                            uri = Path(path).resolve().as_uri() + "?mode=ro&immutable=1"
                            d[k] = sqlite3.connect(uri, uri=True,
                                                   check_same_thread=False)
                            reopened += 1
                    except Exception:
                        pass
                else:
                    _walk(v, depth + 1, seen)

        _walk(Handler.runtime)
        print(f"sqlite connections reopened thread-safe: {reopened}", flush=True)
    except Exception as e:
        print(f"connection walk failed: {type(e).__name__}: {e}", flush=True)
    port = int(os.environ.get("PORT", "8802"))
    host = os.environ.get("BIND_HOST", "127.0.0.1")
    print(f"soul cognition server v3 ({RUNTIME_NAME}) — /think + /query + world-evidence routes on {host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
