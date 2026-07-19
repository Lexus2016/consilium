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
import signal
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
    return os.environ.get("COUNCIL_FAKE", "").lower() not in ("", "0", "false")


@dataclass
class MemberResult:
    agent: str
    role: str            # "panel" | "draft" | "review" | "synth"
    ok: bool
    answer: str
    wall_seconds: float
    error: str = ""


class ProcessRegistry:
    """Tracks live child processes so they can all be terminated if the client
    disconnects or the run is interrupted (otherwise children keep charging).

    Also PERSISTS each member's answer to ``results_dir`` the moment it arrives, so
    a killed or timed-out council never discards an already-paid consultation."""

    def __init__(self, results_dir: str | None = None) -> None:
        self._procs: set[subprocess.Popen] = set()
        self._lock = threading.Lock()
        self._cancelled = False
        self._results_dir = results_dir
        self._n = 0

    @property
    def results_dir(self) -> str | None:
        return self._results_dir

    def record(self, result: "MemberResult") -> None:
        """Write a member's ANSWER to ``results_dir`` immediately, so it survives a
        later kill/timeout of the whole council. Saves ANY non-empty answer and
        marks its status — a member that printed output but then exited non-zero
        (ok=False with text) produced paid content too, and must not be lost.
        Members with no answer at all are skipped. Best-effort; never breaks a run."""
        answer = getattr(result, "answer", "") or ""
        if not self._results_dir or not answer.strip():
            return
        with self._lock:
            self._n += 1
            n = self._n
        status = "ok" if getattr(result, "ok", False) else \
            f"FAILED: {getattr(result, 'error', '') or 'non-zero exit'}"
        path = os.path.join(self._results_dir, f"{n:02d}-{result.role}-{result.agent}.md")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# {result.role} — {result.agent} "
                        f"({result.wall_seconds:.0f}s) [{status}]\n\n{answer}\n")
            os.chmod(path, 0o600)
        except OSError:
            pass

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


def _signal_group(proc: subprocess.Popen, sig: int) -> None:
    """Signal the child's WHOLE process group, not just the direct child.

    Members are spawned with ``start_new_session=True``, so ``consult`` is a group
    leader and the real advisor (a ``timeout … | tee`` grandchild) shares its
    group. Signalling only ``proc`` would leave that paid grandchild running.
    Falls back to signalling the direct child if the group is already gone."""
    try:
        os.killpg(os.getpgid(proc.pid), sig)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.send_signal(sig)
        except Exception:
            pass


def _terminate(proc: subprocess.Popen) -> None:
    _signal_group(proc, signal.SIGTERM)
    # Best-effort reap so a cancelled child (and its group) is not left behind.
    try:
        proc.wait(timeout=2)
    except Exception:
        _signal_group(proc, signal.SIGKILL)
        try:
            proc.wait(timeout=2)
        except Exception:
            pass


def _child_env() -> dict[str, str]:
    """Environment for spawned members, with a recursion-guard marker.

    COUNCIL_INTERNAL signals a member that it is already running inside a council,
    so an agent that could itself invoke `consult council` knows not to recurse.
    (Best-effort: members are spawned as `consult agy|opencode|hermes`, never
    `consult council`, so recursion needs a member explicitly wired to call it.)
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
    # Actively REMOVE CONSILIUM_TIMEOUT from the child env — it is often exported in
    # the parent shell, and merely not setting it is not enough. If `consult` sees
    # it, it wraps the advisor in the `timeout` binary, which puts the advisor in
    # its OWN process group; our os.killpg() on the consult session group
    # (cancel_all, and the Python-side timeout below) would then MISS the advisor
    # and leave a paid orphan. With no inner timeout the advisor stays in the consult
    # group, and communicate(timeout) + os.killpg bound AND reap it.
    env.pop("CONSILIUM_TIMEOUT", None)

    start = time.monotonic()
    if registry is not None and registry.cancelled:
        return MemberResult(agent, role, False, "", 0.0, error="cancelled before start")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=code_dir or _scratch_cwd(),
            start_new_session=True,  # own process group -> kill the whole tree
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

    try:
        # Register INSIDE the try: if a KeyboardInterrupt lands right after the
        # spawn, the `except BaseException` below terminates the child so it is
        # never orphaned (the pre-add window the audit's M1 worried about).
        if registry is not None:
            registry.add(proc)
        # +30s grace over the consult-internal timeout so the agent's own
        # timeout fires first and we don't double-kill prematurely.
        out, stderr_text = proc.communicate(timeout=timeout_seconds + 30)
        wall = time.monotonic() - start
        if registry is not None and registry.cancelled:
            return MemberResult(agent, role, False, "", wall, error="cancelled")
        stderr_part = (stderr_text or "").strip()
        if proc.returncode != 0:
            return MemberResult(
                agent, role, False, (out or "").strip(), wall,
                error=f"exit code {proc.returncode}{((': ' + stderr_part) if stderr_part else '')}",
            )
        answer = (out or "").strip()
        if not answer:
            return MemberResult(agent, role, False, "", wall, error="empty answer")
        return MemberResult(agent, role, True, answer, wall)
    except subprocess.TimeoutExpired:
        # Kill the WHOLE group (the advisor is a grandchild), then drain the pipes
        # so the child is reaped and no zombie / open-fd is left behind.
        _signal_group(proc, signal.SIGKILL)
        stderr_part = ""
        try:
            _, stderr_text = proc.communicate(timeout=5)
            stderr_part = (stderr_text or "").strip()
        except Exception:  # noqa: BLE001
            pass
        return MemberResult(
            agent, role, False, "", time.monotonic() - start,
            error=f"timed out after {timeout_seconds}s + 30s grace{((': ' + stderr_part) if stderr_part else '')}",
        )
    except BaseException:
        # KeyboardInterrupt / cancellation mid-run: make sure the child and its
        # whole process group die rather than lingering as paid orphans.
        _terminate(proc)
        raise
    finally:
        if registry is not None:
            registry.remove(proc)


# --------------------------------------------------------------------------- #
# Fake mode (for cost-free end-to-end testing)
# --------------------------------------------------------------------------- #

def _fake_run(agent: str, question: str, *, role: str, review: bool) -> MemberResult:
    # COUNCIL_FAKE_DELAY lets a test make a fake member slow enough to interrupt.
    try:
        _delay = float(os.environ.get("COUNCIL_FAKE_DELAY", "0.2"))
    except ValueError:
        _delay = 0.2
    time.sleep(_delay)  # simulate a little work so heartbeats have something to do
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
