"""Lifecycle tests for the council spawn/cancel path: the fixes that stop
orphaned paid advisor processes (H3) and the ~31-minute Ctrl-C hang (H4).

These use REAL short-lived subprocesses (a `sleep` grandchild) — no advisor
calls, no cost. Stdlib only. POSIX only (process groups); skipped elsewhere.

    python3 -m unittest tests.test_lifecycle
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from council import recipes  # noqa: E402
from council.spawn import _terminate, ProcessRegistry, MemberResult  # noqa: E402


@unittest.skipUnless(hasattr(os, "killpg"), "process groups are POSIX-only")
class TerminateKillsTree(unittest.TestCase):
    def test_terminate_kills_the_whole_process_group(self):
        # `sh` (direct child) spawns a `sleep 60` grandchild; both share the new
        # session's process group. Signalling only the direct child would leave
        # the grandchild — the exact orphaned-advisor leak H3 is about.
        with tempfile.TemporaryDirectory() as d:
            pidfile = os.path.join(d, "child.pid")
            proc = subprocess.Popen(
                ["sh", "-c", f"sleep 60 & echo $! > {pidfile}; wait"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                child_pid = None
                for _ in range(100):
                    try:
                        s = open(pidfile).read().strip()
                        if s:
                            child_pid = int(s)
                            break
                    except (OSError, ValueError):
                        pass
                    time.sleep(0.05)
                self.assertIsNotNone(child_pid, "grandchild pid was never recorded")
                os.kill(child_pid, 0)  # grandchild is alive (no exception)

                _terminate(proc)

                gone = False
                for _ in range(100):
                    try:
                        os.kill(child_pid, 0)
                        time.sleep(0.05)
                    except ProcessLookupError:
                        gone = True
                        break
                self.assertTrue(gone, "grandchild must be killed by the group signal")
                self.assertIsNotNone(proc.poll(), "direct child must be reaped")
            finally:
                try:
                    os.killpg(os.getpgid(proc.pid), 9)
                except Exception:
                    pass


class ParallelMapCancellation(unittest.TestCase):
    def test_worker_failure_triggers_cancel_all_and_reraises(self):
        # On any error escaping a worker, the paid children are cancelled at once
        # (cancel_all) rather than the pool blocking on shutdown(wait=True) — the
        # mechanism that turns the ~31-min Ctrl-C hang into a prompt cancel.
        class FakeReg:
            def __init__(self):
                self.cancelled = False

            def cancel_all(self):
                self.cancelled = True

        reg = FakeReg()

        def fn(a):
            if a == "boom":
                raise RuntimeError("worker died")
            time.sleep(0.05)
            return a

        with self.assertRaises(RuntimeError):
            recipes._parallel_map(["ok", "boom", "ok2"], fn, registry=reg)
        self.assertTrue(reg.cancelled, "cancel_all must fire so children are killed promptly")

    def test_preserves_order(self):
        def fn(a):
            time.sleep(0.02 if a == 1 else 0.0)
            return a * 10

        self.assertEqual(recipes._parallel_map([1, 2, 3], fn), [10, 20, 30])

    def test_empty_is_noop(self):
        self.assertEqual(recipes._parallel_map([], lambda a: a), [])


class RunDirPruning(unittest.TestCase):
    def test_prunes_stale_runs_but_never_a_recent_or_active_one(self):
        from council.orchestrator import _new_run_dir
        with tempfile.TemporaryDirectory() as base:
            stale = os.path.join(base, "old-run")
            os.makedirs(stale)
            with open(os.path.join(stale, "01-panel-x.md"), "w") as f:
                f.write("old paid answer")
            two_days_ago = time.time() - 2 * 86400
            os.utime(stale, (two_days_ago, two_days_ago))

            active = os.path.join(base, "active-run")
            os.makedirs(active)
            with open(os.path.join(active, "01-panel-y.md"), "w") as f:
                f.write("live paid answer")

            new = _new_run_dir(base=base)  # triggers the prune

            self.assertFalse(os.path.exists(stale), "a run untouched for >1 day is pruned")
            self.assertTrue(os.path.exists(active),
                            "a recent/active run's preserved answers are NEVER pruned")
            self.assertTrue(os.path.isdir(new))


class ResultPersistence(unittest.TestCase):
    """A member's answer is saved the moment it lands, so a later kill/timeout of
    the whole council never discards an already-paid consultation."""

    def test_registry_persists_any_nonempty_answer_with_status(self):
        with tempfile.TemporaryDirectory() as d:
            reg = ProcessRegistry(results_dir=d)
            reg.record(MemberResult("codex", "panel", True, "the real answer", 12.0))
            # ok=False but with TEXT (printed output, then exited non-zero) -> still paid, still saved
            reg.record(MemberResult("opencode", "panel", False, "partial paid answer", 8.0, error="exit 1"))
            # a pure failure with no answer -> nothing to save
            reg.record(MemberResult("agy", "panel", False, "", 5.0, error="timeout"))
            files = sorted(os.listdir(d))
            self.assertEqual(len(files), 2, "both non-empty answers saved; the empty failure skipped")
            joined = "\n".join(open(os.path.join(d, f)).read() for f in files)
            self.assertIn("the real answer", joined)
            self.assertIn("partial paid answer", joined)
            self.assertIn("FAILED", joined)  # the non-zero-exit member is marked, not silently dropped

    def test_registry_without_dir_is_noop(self):
        # no results_dir configured -> record() must not raise
        ProcessRegistry().record(MemberResult("codex", "panel", True, "x", 1.0))

    def test_run_member_records_each_attempt_not_just_the_retry(self):
        # A first attempt that printed paid text then failed must be saved BEFORE the
        # retry overwrites it — otherwise an interrupted retry loses paid output.
        calls = {"n": 0}

        def fake_run_agent(agent, question, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                return MemberResult(agent, "panel", False, "paid partial answer", 3.0, error="exit 1")
            return MemberResult(agent, "panel", True, "successful retry answer", 4.0)

        with tempfile.TemporaryDirectory() as d:
            reg = ProcessRegistry(results_dir=d)
            orig = recipes.run_agent
            recipes.run_agent = fake_run_agent
            try:
                res = recipes._run_member("codex", "q", role="panel", context_file=None,
                                          code_dir=None, timeout_seconds=10, registry=reg)
            finally:
                recipes.run_agent = orig
            self.assertTrue(res.ok, "the final result is the successful retry")
            files = sorted(os.listdir(d))
            self.assertEqual(len(files), 2, "both the failed-with-text first attempt AND the retry are saved")
            joined = "\n".join(open(os.path.join(d, f)).read() for f in files)
            self.assertIn("paid partial answer", joined)
            self.assertIn("successful retry answer", joined)


class RunAgentPreservesPaidOutput(unittest.TestCase):
    """H1/R1: run_agent must NOT discard an already-received paid answer when the run
    is cancelled or the member times out — record() persists only a non-empty answer,
    so nulling `out` on these paths silently loses a paid consultation."""

    class _FakePopen:
        def __init__(self, *, out="", timeout_first=False):
            self.pid = 2_000_000_000  # not a real pid; _signal_group is stubbed out
            self.returncode = 0
            self._out = out
            self._timeout_first = timeout_first
            self._n = 0

        def communicate(self, timeout=None):
            self._n += 1
            if self._timeout_first and self._n == 1:
                raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout)
            return (self._out, "")

    def test_timeout_preserves_streamed_paid_answer(self):
        from council import spawn
        fake = self._FakePopen(out="PAID PARTIAL", timeout_first=True)
        orig_popen, orig_sig = spawn.subprocess.Popen, spawn._signal_group
        spawn.subprocess.Popen = lambda *a, **k: fake
        spawn._signal_group = lambda proc, sig: None
        try:
            m = spawn.run_agent("codex", "q", timeout_seconds=0, registry=None)
        finally:
            spawn.subprocess.Popen, spawn._signal_group = orig_popen, orig_sig
        self.assertFalse(m.ok)
        self.assertIn("timed out", m.error)
        self.assertEqual(m.answer, "PAID PARTIAL", "timed-out member's paid stdout must be kept")

    def test_cancel_preserves_already_received_paid_answer(self):
        from council import spawn

        class _FlipReg:
            results_dir = None

            def __init__(self):
                self._n = 0

            @property
            def cancelled(self):
                self._n += 1
                return self._n > 1  # False at the pre-spawn check, True post-communicate

            def add(self, p):
                pass

            def remove(self, p):
                pass

        fake = self._FakePopen(out="PAID ANSWER")
        orig_popen = spawn.subprocess.Popen
        spawn.subprocess.Popen = lambda *a, **k: fake
        try:
            m = spawn.run_agent("codex", "q", timeout_seconds=5, registry=_FlipReg())
        finally:
            spawn.subprocess.Popen = orig_popen
        self.assertFalse(m.ok)
        self.assertEqual(m.error, "cancelled")
        self.assertEqual(m.answer, "PAID ANSWER", "cancelled member's received answer must be kept")


if __name__ == "__main__":
    unittest.main(verbosity=2)
