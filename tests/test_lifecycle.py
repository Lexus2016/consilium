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
from council.spawn import _terminate  # noqa: E402


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
