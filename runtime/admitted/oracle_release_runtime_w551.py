#!/usr/bin/env python3
"""Untrusted cross-check against the packaged veri7vn kernels.

The entire displayed answer is compared, retaining units, labels, every number
and explanatory text. Exact text/numeric-format agreement is recorded as a
kernel_check, never as proof of the English answer. The kernel's theorem names
are declarations: this Python adapter does not check their premises or question
recognition. Different templates and uncertain rounding remain unsupported;
only comparable contradictory displays withhold the original answer.

The manifest binds each Linux x86-64 executable to its SHA256. A missing kernel,
bad manifest, malformed reply, refusal or timeout leaves the original unchanged.
The manifest and installation are trusted configuration, not signed attestations.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, ROUND_HALF_UP, localcontext
import hashlib
import json
import os
import platform
import re
import selectors
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

from oracle_release_runtime_w548 import OracleReleaseRuntimeW548 as _Base

PROVED = os.environ.get("ORACLE7_ROOT", "/opt/oracle-clm") + "/specialists/_proved"
# Deliberately do not erase commas, punctuation, Unicode unit symbols or words.
# ASCII numbers only; an unfamiliar representation is unsupported, not agreement.
NUM = re.compile(r"(?<![\w.])[-+\N{MINUS SIGN}]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:[eE][-+]?[0-9]+)?(?![\w.])")
YESNO = re.compile(r"\s*(yes|no)[.!]?\s*", re.I)
SPEC = re.compile(r"\bspecialist:([a-z0-9][a-z0-9-]*)")
TIMEOUT_S = 5.0
MAX_REQUEST_BYTES = 64 * 1024
MAX_REPLY_BYTES = 256 * 1024
_LOCK = threading.Lock()
_PROCS: dict = {}
_SCOPE = ("Untrusted full-output comparison; question recognition and theorem "
          "premises are not checked. Provenance is declared by the kernel.")


def _load_map():
    # Small manifest: reread so an update cannot leave an old process identity
    # cached under the new installation. Failed reads can recover on a later call.
    try:
        with open(os.path.join(PROVED, "PROVED.json"), encoding="utf-8") as f:
            m = json.load(f)
        if isinstance(m, dict) and isinstance(m.get("specialists"), dict) and isinstance(m.get("binaries"), dict):
            return m
    except (OSError, ValueError):
        pass
    return {}


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _runnable(binary, digest):
    """Verify the source and any executable copy against this manifest entry."""
    if not isinstance(binary, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", binary):
        return None
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        return None
    tmp = None
    try:
        p = os.path.join(PROVED, "bin", binary)
        if _sha256(p) != digest:
            return None
        if os.access(p, os.X_OK):
            return p
        d = os.path.join(os.environ.get("ORACLE7_STATE", os.path.expanduser("~/.oracle7")), "proved_bin")
        os.makedirs(d, exist_ok=True)
        q = os.path.join(d, binary + "-" + digest)
        if not os.path.isfile(q) or _sha256(q) != digest:
            fd, tmp = tempfile.mkstemp(prefix=binary + "-", dir=d)
            os.close(fd)
            shutil.copyfile(p, tmp)
            if _sha256(tmp) != digest:
                return None
            os.chmod(tmp, 0o755)
            os.replace(tmp, q)
            tmp = None
        os.chmod(q, 0o755)
        return q
    except OSError:
        return None
    finally:
        if tmp is not None:
            os.unlink(tmp)


def _stop(key):
    p = _PROCS.pop(key, None)
    if p is not None:
        try:
            if p.poll() is None:
                p.kill()
            p.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            pass
        for stream in (p.stdin, p.stdout):
            if stream is not None:
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass


def _exchange(p, payload, request_id):
    """Bound both pipe directions under one deadline; no background I/O survives."""
    deadline = time.monotonic() + TIMEOUT_S
    sent = 0
    received = bytearray()
    os.set_blocking(p.stdin.fileno(), False)
    os.set_blocking(p.stdout.fileno(), False)
    with selectors.DefaultSelector() as selector:
        selector.register(p.stdin, selectors.EVENT_WRITE)
        selector.register(p.stdout, selectors.EVENT_READ)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            for event, _ in selector.select(remaining):
                try:
                    if event.fileobj is p.stdin:
                        n = os.write(p.stdin.fileno(), payload[sent:])
                        if not n:
                            return None
                        sent += n
                        if sent == len(payload):
                            selector.unregister(p.stdin)
                    else:
                        chunk = os.read(p.stdout.fileno(), min(65536, MAX_REPLY_BYTES + 1 - len(received)))
                        if not chunk:
                            return None
                        received.extend(chunk)
                        if len(received) > MAX_REPLY_BYTES:
                            return None
                        if b"\n" in received:
                            # Exactly one JSONL reply. Reject unsolicited output;
                            # a delayed extra line will fail the next unique ID.
                            if sent != len(payload) or received.find(b"\n") != len(received) - 1:
                                return None
                            reply = json.loads(received.decode("utf-8"))
                            if not isinstance(reply, dict) or reply.get("id") != request_id:
                                return None
                            return reply
                except BlockingIOError:
                    continue


def _ask(sid, text):
    """One serialized JSONL request, or None when no trustworthy check ran."""
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64"):
        return None
    if not isinstance(text, str) or len(text) > MAX_REQUEST_BYTES:
        return None
    request_id = "w551-" + uuid.uuid4().hex
    try:
        payload = (json.dumps({"id": request_id, "q": text}, ensure_ascii=False) + "\n").encode("utf-8")
    except UnicodeError:
        return None
    if len(payload) > MAX_REQUEST_BYTES:
        return None
    m = _load_map()
    ent = m.get("specialists", {}).get(sid)
    if not isinstance(ent, dict):
        return None
    binary = ent.get("binary")
    if not isinstance(binary, str):
        return None
    digest = m.get("binaries", {}).get(binary)
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        return None
    if not isinstance(ent.get("flag", True), bool):
        return None
    identity = (os.path.abspath(PROVED), binary, sid if ent.get("flag", True) else "")
    key = identity + (digest,)
    with _LOCK:
        for old in list(_PROCS):
            if old[:3] == identity and old != key:
                _stop(old)
        p = _PROCS.get(key)
        if p is None or p.poll() is not None:
            _stop(key)
            exe = _runnable(binary, digest)
            if not exe:
                return None
            argv = [exe] + (["--specialist", sid] if ent.get("flag", True) else [])
            try:
                p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, bufsize=0)
            except OSError:
                return None
            _PROCS[key] = p
        try:
            reply = _exchange(p, payload, request_id)
            if reply is None:
                _stop(key)
                return None
            reply["kernel_binary"] = {"name": binary, "sha256": digest}
            return reply
        except (OSError, ValueError, RecursionError):
            _stop(key)
            return None


def _numbers(text):
    matches = list(NUM.finditer(text))
    if not matches:
        return None
    values = []
    for match in matches:
        token = match.group().replace("\N{MINUS SIGN}", "-")
        if len(token) > 100:
            return None
        try:
            value = Decimal(token)
        except InvalidOperation:
            return None
        if not value.is_finite() or abs(value.as_tuple().exponent) > 1000:
            return None
        values.append(value)
    return NUM.split(text), values


def _rounds_to(a, b):
    """Compatibility only: rounding a finer display is not the exact result."""
    ea, eb = a.as_tuple().exponent, b.as_tuple().exponent
    if not eb < ea < 0:
        return False
    with localcontext() as ctx:
        ctx.prec = 2200
        unit = Decimal(1).scaleb(ea)
        return any(b.quantize(unit, rounding=mode) == a for mode in (ROUND_HALF_EVEN, ROUND_HALF_UP))


def compare(reply_text, kernel_text):
    """Return (comparison, method), without claiming semantic proof.

    Only literal text or every decimal value with identical intervening text
    agrees. All words/units/list delimiters must match. Display rounding is
    explicitly unsupported, not a licence to prove a nearby number.
    """
    if not isinstance(reply_text, str) or not isinstance(kernel_text, str) or not reply_text or not kernel_text:
        return "unsupported", "missing_text"
    if reply_text == kernel_text:
        return "agreement", "exact_text"
    a, b = YESNO.fullmatch(reply_text), YESNO.fullmatch(kernel_text)
    if a and b:
        return ("agreement" if a.group(1).lower() == b.group(1).lower() else "disagreement"), "boolean"
    a, b = _numbers(reply_text), _numbers(kernel_text)
    if a is None or b is None or a[0] != b[0]:
        return "unsupported", "unmatched_text"
    pairs = list(zip(a[1], b[1]))
    if all(x == y for x, y in pairs):
        return "agreement", "numeric_format"
    if all(x == y or _rounds_to(x, y) or _rounds_to(y, x) for x, y in pairs):
        return "unsupported", "display_rounding"
    return "disagreement", "numeric_template"


def agrees(reply_text, kernel_text):
    """Compatibility helper: nearby numbers and matching prefixes do not agree."""
    return compare(reply_text, kernel_text)[0] == "agreement"


def _provenance(k):
    p = k.get("provenance")
    if not isinstance(p, dict) or p.get("taken") is not True:
        return None
    if any(not isinstance(p.get(key), str) or not p[key].strip() for key in ("kernel", "session")):
        return None
    thms = p.get("theorems")
    if not isinstance(thms, list) or not thms or any(not isinstance(t, str) or not t.strip() for t in thms):
        return None
    return p


class OracleReleaseRuntimeW551(_Base):
    def chat(self, text: str, session_id: str = "default") -> dict:
        r = super().chat(text, session_id)
        if not isinstance(r, dict) or r.get("status") != "answered":
            return r
        path = str(r.get("path", ""))
        ids = SPEC.findall(path)
        if len(set(ids)) != 1 or path.startswith("network"):
            return r
        k = _ask(ids[0], text)
        if not isinstance(k, dict) or k.get("status") != "answered" or k.get("error"):
            return r
        prov = _provenance(k)
        if prov is None or not isinstance(k.get("response"), str) or not k["response"]:
            return r
        comparison, method = compare(r.get("response"), k["response"])
        out = dict(r)
        out["kernel_check"] = {"comparison": comparison, "method": method,
                               "terminal": comparison == "disagreement",
                               "reply": k,
                               "response": k["response"], "provenance": prov, "scope": _SCOPE}
        if "kernel_binary" in k:
            out["kernel_check"]["binary"] = k["kernel_binary"]
        if comparison == "disagreement":
            for field in ("value", "kind", "proved"):
                out.pop(field, None)
            out.update(status="withheld", path="proved_check:disagree>" + path,
                       response="The specialist and its veri7vn cross-check returned different values for the same answer format, so I won't give either as the answer.")
        return out
