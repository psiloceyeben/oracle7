"""Focused w551 regression tests; no corpus, model, network or HOL build.

The parent runtime is controlled, but the actual w551 module/chat fold runs.
Mechanics replies follow veri7vn's src/extract/mechanics/main.sml and
Mechanics.thy shapes. Fake executable tests exercise the JSONL/process boundary;
they are portable scripts, not claims to have run the shipped Linux kernels.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch


class Parent:
    def chat(self, text, session_id="default"):
        self.parent_call = (text, session_id)
        return self.parent_reply


def load_fold():
    name = "oracle_release_runtime_w548"
    stub = types.ModuleType(name)
    stub.OracleReleaseRuntimeW548 = Parent
    source = Path(__file__).resolve().parents[1] / "runtime/admitted/oracle_release_runtime_w551.py"
    spec = importlib.util.spec_from_file_location("tested_w551", source)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {name: stub}):
        spec.loader.exec_module(module)
    return module


w551 = load_fold()
PROVENANCE = {"taken": True, "organ": "physics", "specialist_ms": 0.1,
              "kernel": "Mechanics.reply_of", "session": "Veri7vn_Mechanics",
              "theorems": ["kernel_exact_sound", "kernel_approx_sound", "stated_dec_sound"]}
MECHANICS_TEXT = "The kinetic energy is 10 J (KE = 1/2 m v^2 = 1/2 x 5 x 2^2)."


def kernel(text):
    return {"id": "w551", "status": "answered", "path": "specialist:physics>ke",
            "kind": "ke", "value": 10, "response": text, "provenance": copy.deepcopy(PROVENANCE)}


class FoldTests(unittest.TestCase):
    def run_fold(self, original, checked, **fields):
        engine = w551.OracleReleaseRuntimeW551()
        engine.parent_reply = {"status": "answered", "response": original,
                               "path": "specialist_call>specialist:physics>ke", **fields}
        before = copy.deepcopy(engine.parent_reply)
        with patch.object(w551, "_ask", return_value=checked) as ask:
            result = engine.chat("What is the kinetic energy?", "private-session")
        self.assertEqual(engine.parent_reply, before, "must not mutate the parent reply")
        self.assertEqual(engine.parent_call, ("What is the kinetic energy?", "private-session"))
        return result, ask

    def test_real_mechanics_shape_retains_full_evidence_without_proof(self):
        result, ask = self.run_fold(MECHANICS_TEXT, kernel(MECHANICS_TEXT), value=10)
        ask.assert_called_once_with("physics", "What is the kinetic energy?")
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["response"], MECHANICS_TEXT)
        self.assertEqual(result["value"], 10)
        check = result["kernel_check"]
        self.assertEqual(check["comparison"], "agreement")
        self.assertEqual(check["method"], "exact_text")
        self.assertEqual(check["provenance"], PROVENANCE)
        self.assertEqual(check["response"], MECHANICS_TEXT)
        self.assertEqual(check["reply"], kernel(MECHANICS_TEXT))
        self.assertIn("premises are not checked", check["scope"])
        self.assertFalse(check["terminal"])
        self.assertNotIn("proved", result)
        self.assertNotIn(">proved:", result["path"])

    def test_unsupported_cases_do_not_gain_proof_or_withhold(self):
        cases = [("10 kg", "10 m"), ("Paris", "London"),
                 ("Yes, the mass is 10 kg", "Yes, the mass is 10 m"),
                 ("0.68 kg", "0.675 kg"), ("0.675 kg", "0.68 kg"),
                 ("0.66 kg", "0.665 kg"),  # half-even compatible, no proof
                 ("10 µm", "10 um"), ("−10 m", "10 m below zero"),
                 ("[1,234]", "[1234]"), ("10 m²", "10 m³"),
                 ("١٠ m", "10 m"), ("1e10000 m", "10 m"),
                 ("1e99999999999999999999 m", "10 m")]
        for original, checked in cases:
            with self.subTest(original=original, checked=checked):
                result, _ = self.run_fold(original, kernel(checked))
                self.assertEqual(result["status"], "answered")
                self.assertEqual(result["response"], original)
                self.assertEqual(result["kernel_check"]["comparison"], "unsupported")
                self.assertFalse(result["kernel_check"]["terminal"])
                self.assertNotIn("proved", result)
                self.assertFalse(w551.agrees(original, checked))

    def test_contradictions_cover_signs_all_quantities_and_boolean(self):
        cases = [("0", "1"), ("10; second result 5", "10; second result 900"),
                 ("[10, 5] kg", "[10, 900] kg"), ("−10 m", "10 m"),
                 ("-10 m", "+10 m"), ("1e3 m", "1e4 m"),
                 ("Yes", "No"), ("10.00 kg", "10.01 kg"),
                 (MECHANICS_TEXT, MECHANICS_TEXT.replace("x 5 x", "x 6 x"))]
        for original, checked in cases:
            with self.subTest(original=original, checked=checked):
                result, _ = self.run_fold(original, kernel(checked), value=999, kind="old", proved={"old": True})
                self.assertEqual(result["status"], "withheld")
                self.assertTrue(result["path"].startswith("proved_check:disagree>"))
                self.assertEqual(result["kernel_check"]["comparison"], "disagreement")
                self.assertTrue(result["kernel_check"]["terminal"])
                self.assertNotIn("proved", result)
                self.assertNotIn("value", result)
                self.assertNotIn("kind", result)

    def test_format_equivalence_checks_every_number_and_keeps_units(self):
        cases = [("10.00 kg", "10 kg"), ("[+10.0, −5] µm", "[10, -5.00] µm"),
                 ("1e3 m", "1000 m"), ("Yes.", "yes"),
                 ("0.000000000001 m", "1e-12 m")]
        for original, checked in cases:
            with self.subTest(original=original, checked=checked):
                result, _ = self.run_fold(original, kernel(checked))
                self.assertEqual(result["kernel_check"]["comparison"], "agreement")
                self.assertFalse(result["kernel_check"]["terminal"])
                self.assertNotIn("proved", result)
                self.assertTrue(w551.agrees(original, checked))

    def test_malformed_absent_and_declined_kernel_unchanged(self):
        candidates = [None, [], "bad", {}, {"status": "withheld"},
                      {**kernel("10"), "error": "broken"}, {**kernel("10"), "response": 10}]
        for provenance in [None, {}, [], {**PROVENANCE, "taken": False},
                           {**PROVENANCE, "session": ""}, {**PROVENANCE, "kernel": None},
                           {**PROVENANCE, "theorems": []}, {**PROVENANCE, "theorems": "claim"}]:
            candidates.append({**kernel("10"), "provenance": provenance})
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                result, _ = self.run_fold("10", candidate)
                self.assertNotIn("kernel_check", result)
                self.assertNotIn("proved", result)
                self.assertEqual(result["response"], "10")
                self.assertEqual(result["status"], "answered")

    def test_nonanswers_multispecialist_network_not_checked(self):
        cases = [{"status": "withheld"}, {"path": "network>specialist:physics"},
                 {"path": "specialist:physics>specialist:chemistry"}, {"path": "retrieval"}]
        for fields in cases:
            with self.subTest(fields=fields):
                result, ask = self.run_fold("10", kernel("10"), **fields)
                ask.assert_not_called()
                self.assertNotIn("kernel_check", result)


class ExecutableTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.proved = self.base / "proved"
        (self.proved / "bin").mkdir(parents=True)
        self.state = self.base / "state"
        self.patches = [patch.object(w551, "PROVED", str(self.proved)),
                        patch.dict(os.environ, {"ORACLE7_STATE": str(self.state)}),
                        patch.object(w551.platform, "system", return_value="Linux"),
                        patch.object(w551.platform, "machine", return_value="x86_64")]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for key in list(w551._PROCS):
            w551._stop(key)
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def write_binary(self, contents, executable=False):
        binary = self.proved / "bin/k"
        binary.write_bytes(contents)
        binary.chmod(0o755 if executable else 0o644)
        digest = hashlib.sha256(contents).hexdigest()
        manifest = {"specialists": {"physics": {"binary": "k", "flag": False}},
                    "binaries": {"k": digest}}
        (self.proved / "PROVED.json").write_text(json.dumps(manifest))
        return digest

    def script(self, value="NEW", body=None):
        if body is None:
            body = 'print(json.dumps({"id":request["id"], "response":' + repr(value) + '}), flush=True)'
        return ("#!" + sys.executable + "\nimport json, sys, time\nfor line in sys.stdin:\n    request = json.loads(line)\n    " + body + "\n").encode()

    def test_same_size_stale_cache_cannot_replace_new_binary(self):
        digest = self.write_binary(b"NEW")
        cache = self.state / "proved_bin"
        cache.mkdir(parents=True)
        (cache / "k").write_bytes(b"OLD")
        (cache / ("k-" + digest)).write_bytes(b"OLD")
        chosen = Path(w551._runnable("k", digest))
        self.assertEqual(chosen.read_bytes(), b"NEW")
        self.assertTrue(os.access(chosen, os.X_OK))
        self.assertEqual(list(cache.glob("k-*")), [chosen], "temporary copy must be removed")

    def test_manifest_mismatch_rejects_even_executable_source(self):
        self.write_binary(b"NEW", executable=True)
        old = hashlib.sha256(b"OLD").hexdigest()
        self.assertIsNone(w551._runnable("k", old))
        self.assertIsNone(w551._runnable("../k", old))
        self.assertIsNone(w551._runnable("k", "not-a-hash"))

    def test_running_process_digest_changes_after_same_size_upgrade(self):
        old = self.write_binary(self.script("OLD"))
        reply = w551._ask("physics", "q1")
        self.assertEqual(reply["response"], "OLD")
        old_process = next(iter(w551._PROCS.values()))
        new = self.write_binary(self.script("NEW"))
        self.assertNotEqual(old, new)
        reply = w551._ask("physics", "q2")
        self.assertEqual(reply["response"], "NEW")
        self.assertEqual(reply["kernel_binary"], {"name": "k", "sha256": new})
        self.assertIsNotNone(old_process.poll())
        process = next(iter(w551._PROCS.values()))
        self.assertEqual(w551._ask("physics", "q3")["response"], "NEW")
        self.assertIs(next(iter(w551._PROCS.values())), process)

    def test_platform_guard_does_not_try_linux_binary(self):
        for system, arch in [("Darwin", "x86_64"), ("Linux", "arm64")]:
            with self.subTest(system=system, arch=arch), patch.object(w551.platform, "system", return_value=system), patch.object(w551.platform, "machine", return_value=arch), patch.object(w551, "_load_map") as load:
                self.assertIsNone(w551._ask("physics", "q"))
                load.assert_not_called()

    def test_timeout_stops_and_reaps_process(self):
        self.write_binary(self.script(body="time.sleep(10)"))
        started = []
        real_popen = w551.subprocess.Popen
        def start(*args, **kwargs):
            p = real_popen(*args, **kwargs)
            started.append(p)
            return p
        with patch.object(w551, "TIMEOUT_S", 0.05), patch.object(w551.subprocess, "Popen", side_effect=start):
            self.assertIsNone(w551._ask("physics", "q"))
        self.assertFalse(w551._PROCS)
        self.assertEqual(len(started), 1)
        self.assertIsNotNone(started[0].returncode)
        self.assertTrue(started[0].stdin.closed)
        self.assertTrue(started[0].stdout.closed)

    def test_copy_is_checked_before_atomic_install(self):
        digest = self.write_binary(b"NEW")
        def corrupt(source, target):
            Path(target).write_bytes(b"BAD")
        with patch.object(w551.shutil, "copyfile", side_effect=corrupt):
            self.assertIsNone(w551._runnable("k", digest))
        self.assertEqual(list((self.state / "proved_bin").iterdir()), [])

    def assert_bounded_refusal(self, question="q"):
        start = time.monotonic()
        with patch.object(w551, "TIMEOUT_S", 0.15):
            self.assertIsNone(w551._ask("physics", question))
        self.assertLess(time.monotonic() - start, 2.0)
        self.assertFalse(w551._PROCS)

    def test_stuck_writer_and_partial_or_oversized_reply_are_bounded(self):
        # Larger than pipe capacity, but within the test request limit. The
        # executable never reads stdin, so the write itself must time out.
        self.write_binary(("#!" + sys.executable + "\nimport time\ntime.sleep(10)\n").encode())
        with patch.object(w551, "MAX_REQUEST_BYTES", 2 * 1024 * 1024):
            self.assert_bounded_refusal("q" * (1024 * 1024))
        self.write_binary(self.script(body='print(json.dumps({"id":request["id"], "response":"first"}), flush=True); time.sleep(10)'))
        self.assertEqual(w551._ask("physics", "first")["response"], "first")
        with patch.object(w551, "MAX_REQUEST_BYTES", 2 * 1024 * 1024):
            self.assert_bounded_refusal("q" * (1024 * 1024))
        for body in ["sys.stdout.write('{'); sys.stdout.flush(); time.sleep(10)",
                     "sys.stdout.write('x' * 4096); sys.stdout.flush(); time.sleep(10)"]:
            with self.subTest(body=body):
                self.write_binary(self.script(body=body))
                with patch.object(w551, "MAX_REPLY_BYTES", 1024):
                    self.assert_bounded_refusal()

    def test_oversized_request_does_not_spawn(self):
        with patch.object(w551, "_load_map") as load:
            self.assertIsNone(w551._ask("physics", "q" * w551.MAX_REQUEST_BYTES))
            self.assertIsNone(w551._ask("physics", "µ" * (w551.MAX_REQUEST_BYTES // 2)))
            load.assert_not_called()

    def test_delayed_duplicate_reply_cannot_answer_next_question(self):
        body = ('reply = json.dumps({"id":request["id"], "response":"OLD"}); '
                'print(globals().get("previous", reply), flush=True); previous = reply')
        self.write_binary(self.script(body=body))
        first = w551._ask("physics", "first")
        self.assertEqual(first["response"], "OLD")
        # The second request triggers a duplicate with the first ID, which must
        # not become a successful answer to this different request.
        self.assert_bounded_refusal("second")

    def test_immediate_extra_line_is_rejected(self):
        body = ('reply = json.dumps({"id":request["id"], "response":"OLD"}); '
                'sys.stdout.write(reply + "\\n" + reply + "\\n"); sys.stdout.flush()')
        self.write_binary(self.script(body=body))
        self.assert_bounded_refusal()

    def test_bad_json_shape_or_id_does_not_poison_next_request(self):
        for body in ["print('[]', flush=True)", "print('bad json', flush=True)", "print('{\"id\":\"other\"}', flush=True)",
                     "sys.stdout.buffer.write(b'\\xff\\n'); sys.stdout.flush()",
                     "print('[' * 1500 + '0' + ']' * 1500, flush=True)"]:
            with self.subTest(body=body):
                self.write_binary(self.script(body=body))
                self.assertIsNone(w551._ask("physics", "q"))
                self.assertFalse(w551._PROCS)
        self.write_binary(self.script())
        self.assertEqual(w551._ask("physics", "q")["response"], "NEW")

    def test_bad_manifest_can_recover(self):
        self.assertIsNone(w551._ask("physics", "q"))
        (self.proved / "PROVED.json").write_text("[]")
        self.assertIsNone(w551._ask("physics", "q"))
        self.write_binary(self.script())
        self.assertEqual(w551._ask("physics", "q")["response"], "NEW")


if __name__ == "__main__":
    unittest.main()
