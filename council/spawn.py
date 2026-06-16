"""Thin wrapper around the `consult` CLI from the consilium project.

Each panel member is a separate `consult <agent> ...` subprocess. consult prints
the agent's answer to STDOUT and its transcript path to STDERR, so capturing
stdout alone yields the clean answer with no bookkeeping noise.

A FAKE mode (env COUNCIL_FAKE=1) returns canned answers instantly so the whole
HTTP / streaming / synthesis pipeline can be exercised end-to-end without
spending a cent on real agent calls.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from dataclasses import dataclass


CONSULT_BIN = os.environ.get("COUNCIL_CONSULT_BIN", "consult")

# Neutral working dir for members without an explicit --code dir. Spawning in an
# empty dir stops agents (notably agy/Antigravity) from "listing the workspace"
# instead of answering the code-in-text question. Created lazily.
_SCRATCH_DIR = os.path.join(os.path.expanduser("~"), ".consilium", "council-scratch")


def _scratch_cwd() -> str:
    os.makedirs(_SCRATCH_DIR, exist_ok=True)
    return _SCRATCH_DIR


def fake_mode() -> bool:
    return os.environ.get("COUNCIL_FAKE", "") not in ("", "0", "false", "False")


@dataclass
class MemberResult:
    agent: str
    role: str            # "panel" | "draft" | "review" | "synth"
    ok: bool
    answer: str
    wall_seconds: float
    error: str = ""


class ProcessRegistry:
    """Tracks live child processes for one HTTP request so they can all be
    terminated if the client disconnects (otherwise children keep running and
    keep charging)."""

    def __init__(self) -> None:
        self._procs: set[subprocess.Popen] = set()
        self._lock = threading.Lock()
        self._cancelled = False

    def add(self, proc: subprocess.Popen) -> None:
        with self._lock:
            if self._cancelled:
                # Already cancelled: don't let a late spawn linger.
                _terminate(proc)
            else:
                self._procs.add(proc)

    def remove(self, proc: subprocess.Popen) -> None:
        with self._lock:
            self._procs.discard(proc)

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel_all(self) -> None:
        with self._lock:
            self._cancelled = True
            procs = list(self._procs)
            self._procs.clear()
        for proc in procs:
            _terminate(proc)


def _terminate(proc: subprocess.Popen) -> None:
    try:
        proc.terminate()
    except Exception:
        pass
    # Best-effort reap so a cancelled child is not left as a zombie.
    try:
        proc.wait(timeout=2)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _child_env() -> dict[str, str]:
    """Environment for spawned members, with a recursion-guard marker.

    If a panel member is itself an agent that could be pointed back at this
    Quorum, this marker is the cheap in-band signal that we are already inside a
    council run. (A member must still be configured to use a REAL provider, not
    this Quorum's base_url — see docs/setup.md. There is no perfect guard.)
    """
    env = dict(os.environ)
    env["COUNCIL_INTERNAL"] = "1"
    return env


# --------------------------------------------------------------------------- #
# Real invocation
# --------------------------------------------------------------------------- #

def run_agent(
    agent: str,
    question: str,
    *,
    role: str = "panel",
    context_file: str | None = None,
    code_dir: str | None = None,
    review: bool = False,
    timeout_seconds: int = 600,
    registry: ProcessRegistry | None = None,
) -> MemberResult:
    """Run one `consult` invocation and return its answer.

    Never raises for an agent-side failure; failures are reported in the
    MemberResult so a partial panel can still be synthesized.
    """
    if fake_mode():
        return _fake_run(agent, question, role=role, review=review)

    cmd = [CONSULT_BIN, agent, "--no-log"]
    if review:
        cmd.append("--review")
    if context_file:
        cmd += ["--context", context_file]
    if code_dir:
        cmd += ["--code", code_dir]
    cmd += ["--", question]

    env = _child_env()
    # Belt-and-suspenders: consult honors CONSILIUM_TIMEOUT (wraps with timeout),
    # and we also enforce a Python-side wait timeout below.
    env["CONSILIUM_TIMEOUT"] = str(timeout_seconds)

    start = time.monotonic()
    if registry is not None and registry.cancelled:
        return MemberResult(agent, role, False, "", 0.0, error="cancelled before start")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=env,
            cwd=code_dir or _scratch_cwd(),
        )
    except FileNotFoundError:
        return MemberResult(
            agent, role, False, "", time.monotonic() - start,
            error=f"`{CONSULT_BIN}` not found on PATH",
        )
    except OSError as e:
        return MemberResult(
            agent, role, False, "", time.monotonic() - start,
            error=f"failed to spawn `{CONSULT_BIN}`: {e}",
        )

    if registry is not None:
        registry.add(proc)
    try:
        # +30s grace over the consult-internal timeout so the agent's own
        # timeout fires first and we don't double-kill prematurely.
        out, _ = proc.communicate(timeout=timeout_seconds + 30)
        wall = time.monotonic() - start
        if registry is not None and registry.cancelled:
            return MemberResult(agent, role, False, "", wall, error="cancelled")
        if proc.returncode != 0:
            return MemberResult(
                agent, role, False, (out or "").strip(), wall,
                error=f"exit code {proc.returncode}",
            )
        answer = (out or "").strip()
        if not answer:
            return MemberResult(agent, role, False, "", wall, error="empty answer")
        return MemberResult(agent, role, True, answer, wall)
    except subprocess.TimeoutExpired:
        # Kill, then drain the pipes so the child is reaped and no zombie /
        # open-fd is left behind (terminate() alone does not reap).
        proc.kill()
        try:
            proc.communicate(timeout=5)
        except Exception:  # noqa: BLE001
            pass
        return MemberResult(
            agent, role, False, "", time.monotonic() - start,
            error=f"timed out after {timeout_seconds}s",
        )
    finally:
        if registry is not None:
            registry.remove(proc)


# --------------------------------------------------------------------------- #
# Fake mode (for cost-free end-to-end testing)
# --------------------------------------------------------------------------- #

def _fake_run(agent: str, question: str, *, role: str, review: bool) -> MemberResult:
    time.sleep(0.2)  # simulate a little work so heartbeats have something to do
    short = question.strip().splitlines()[0][:80] if question.strip() else "(empty)"
    if review:
        body = (
            f"[FAKE review by {agent}] Checked the draft against the task "
            f"({short!r}). One edge case is under-specified.\n"
            "VERDICT: PASS"
        )
    elif role == "synth":
        body = (
            f"[FAKE synthesis by {agent}] Reconciled the panel answers for "
            f"task {short!r}. Final recommendation: proceed with the simplest "
            "option; no blocking disagreements remained."
        )
    else:
        body = (
            f"[FAKE answer by {agent}] On {short!r}: here is my independent take "
            "— the straightforward approach is correct and safe."
        )
    return MemberResult(agent, role, True, body, 0.2)
