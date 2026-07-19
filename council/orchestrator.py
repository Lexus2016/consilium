"""Audit orchestrator: the proven shape for running the council on code.

The panel reads the code FROM THE QUESTION (numbered lines embedded as text),
NOT via ``--code`` — because ``consult`` cannot feed a working dir to
``opencode``/``hermes`` (their dispatch entries ignore it), and giving the
synthesizer ``--code`` made it spawn its own read loop and hang. With the code
in the prompt, every panel member is a code-reader.

Every finding must carry a ``SOURCE: <path>:<line>`` line; we then re-check each
citation against the real files (``verify_sources``). A path we never sent, or a
line past EOF, is flagged — which is exactly how a hallucination becomes visible.
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import sys
import tempfile
import threading
import time
from dataclasses import dataclass

from .config import load_config, ConfigError
from .spawn import ProcessRegistry
from .recipes import run_recipe, _run_member
from .roster import list_available_agents, resolve_roster

# Default budget of embedded code lines across all files. Over this, extra files
# are dropped with a VISIBLE marker. The actual cap is configurable via
# `max_embedded_lines` in config/council.json.
DEFAULT_MAX_EMBEDDED_LINES = 6000


@dataclass
class SourceCheck:
    path: str
    line: int | None  # None = a SOURCE-shaped line we could not parse
    ok: bool
    reason: str = ""


@dataclass
class AuditResult:
    final_text: str
    members: list  # list[MemberResult]
    sources: list  # list[SourceCheck]
    note: str = ""


# Machine sentinel a member/synthesizer emits when a review found NOTHING to
# report. Without it, an answer with zero citations is ambiguous — "made claims
# but cited nothing" looks identical to "correctly had nothing to cite". The
# verifier treats a zero-citation answer as INCOMPLETE UNLESS this token is present.
NO_FINDINGS_TOKEN = "NO_FINDINGS"
_NO_FINDINGS_RE = re.compile(r"(?m)^\s*NO_FINDINGS\s*$")


def has_clean_audit_token(final_text: str) -> bool:
    """True iff the ENTIRE answer is the clean-audit sentinel and nothing else.
    A clean audit is exactly ``NO_FINDINGS`` — any other content means the answer
    is making claims and must cite them (or it is INCOMPLETE). Matching the token
    merely *somewhere* would let ``NO_FINDINGS`` + an uncited claim pass as COMPLETE."""
    return final_text.strip() == NO_FINDINGS_TOKEN


def mentions_no_findings(final_text: str) -> bool:
    """True iff a standalone ``NO_FINDINGS`` line appears anywhere. Used to detect
    the contradiction of emitting it ALONGSIDE other content or real findings."""
    return bool(_NO_FINDINGS_RE.search(final_text))


SOURCE_RULE = (
    "OUTPUT RULES (mandatory):\n"
    "- For EVERY finding, end it with a line exactly like:\n"
    "    SOURCE: <absolute file path>:<line> (function <name>)\n"
    "- Use the EXACT line numbers shown in the left margin of the code below.\n"
    "  Do NOT invent or approximate line numbers.\n"
    "- Cite ONLY the file paths shown below. If you cannot point to a specific\n"
    "  line in the given code, DROP the finding.\n"
    f"- If you find NO issues to report, output exactly one line: {NO_FINDINGS_TOKEN}\n"
    "  (and nothing else). Do NOT output it together with any finding.\n"
    "- Output ONLY your findings. Do NOT echo the code, the prompt, or these rules."
)


def _norm(path: str) -> str:
    """Single canonical path form used everywhere: the FILE header shown to
    advisors, the embedded-file set, and citation checking. Consistency here is
    what makes a citation match what the advisor actually saw (expanduser +
    realpath, so ``~/x`` and symlink aliases resolve to one form on both sides)."""
    return os.path.realpath(os.path.expanduser(str(path)))


def _line_count(path: str) -> int:
    """Count lines the SAME way _number_file numbers them (splitlines), so a
    citation to the last shown line never reads as out-of-range near EOF."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return len(f.read().splitlines())
    except OSError:
        return 0


def _number_file(abs_path: str) -> tuple[str, int]:
    """Return (a FILE-headed, line-numbered block, line count)."""
    with open(abs_path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    body = "\n".join(f"{i + 1:>5}\t{ln}" for i, ln in enumerate(lines))
    return f"// FILE: {abs_path}\n{body}", len(lines)


def gather_code(files: list[str], max_lines: int = DEFAULT_MAX_EMBEDDED_LINES) -> tuple[str, set[str]]:
    """Read, number and concatenate ``files`` within ``max_lines``.

    Returns ``(embedded_text, embedded_paths)`` where ``embedded_paths`` is the
    set of files ACTUALLY shown to the advisors (normalized). The first file is
    always included even if it alone exceeds the budget; subsequent over-budget
    files are dropped with a visible ``[TRUNCATED ...]`` marker so the omission is
    never silent — and, crucially, they are NOT in ``embedded_paths``, so a
    citation to one is flagged rather than passing as verified. Duplicate ``-f``
    paths are collapsed so the same file is never embedded twice.
    """
    blocks: list[str] = []
    omitted: list[tuple[str, int]] = []
    embedded: set[str] = set()
    seen: set[str] = set()
    used = 0
    for path in files:
        ap = _norm(path)
        if ap in seen:
            continue
        seen.add(ap)
        block, n = _number_file(ap)
        if blocks and used + n > max_lines:
            omitted.append((ap, n))
            continue
        blocks.append(block)
        used += n
        embedded.add(ap)
    text = "\n\n".join(blocks)
    if omitted:
        marker = "\n".join(
            f"[TRUNCATED: omitted {p} ({n} lines) — over the {max_lines}-line "
            f"budget; audit it in a separate run]"
            for p, n in omitted
        )
        text = f"{text}\n\n{marker}"
    return text, embedded


# Adversarial framing for the council's code AUDIT (only ever used by build_question,
# i.e. `consult council` — NOT the neutral single-advisor consult). It counters
# sycophancy (an agreeable reviewer rubber-stamps and misses real defects) WITHOUT
# inviting fabrication (the SOURCE_RULE + the mechanical file:line verification are the
# actual anti-hallucination guard). Deliberately does NOT tell the advisor to spawn
# subagents / explore — that is what makes headless agents hang in a tool loop.
AUDIT_PREAMBLE = (
    "You are an ADVERSARIAL code auditor reviewing another team's code. Your job is to "
    "find what is WRONG — real bugs, security holes, race conditions, resource leaks, "
    "broken edge cases, design flaws, and gaps — and prove each one against the code. "
    "Do NOT be agreeable, reassuring, or eager to approve; a reviewer who wants to please "
    "misses real defects. Equally, do NOT invent problems to look thorough: every claim "
    "must be tied to the exact line where it occurs (see the OUTPUT RULES), or it is not a "
    "finding. Reason carefully, be concrete, and challenge the code hard — but only where "
    "the code actually earns it."
)


def build_question(code_block: str, user_question: str) -> str:
    return (
        f"{AUDIT_PREAMBLE}\n\n"
        f"{user_question.strip()}\n\n"
        f"{SOURCE_RULE}\n\n"
        "The code is shown WITH line numbers (number<TAB>code):\n\n"
        f"```\n{code_block}\n```"
    )


# A citation line the advisor is told to emit: `SOURCE: <path>:<line> (function ...)`.
# `_SOURCE_ANY` matches a SOURCE marker only at the START of a line (after optional
# whitespace) so a `SOURCE:` appearing INSIDE prose or a suggested ```diff block
# (e.g. `+LOG = "SOURCE: x"`) does not create a spurious malformed-citation and
# wrongly fail a valid answer. `_CITE` then parses `path:line` from the rest. The
# path is non-greedy so it tolerates spaces AND colons; the line number may carry a
# trailing `:col`; and it must be followed by whitespace, `(`, or end — so `:5`
# inside `/a:5/b.py:10` does not win over the real `:10`. A SOURCE marker whose rest
# fails `_CITE` is a MALFORMED citation: flagged BAD, never silently ignored.
_SOURCE_ANY = re.compile(r"(?m)^[ \t]*SOURCE:[ \t]*([^\n]*)")
_CITE = re.compile(r"^(?P<path>.+?):(?P<line>\d+)(?::\d+)?(?=\s|\(|$)")


def verify_sources(
    final_text: str,
    embedded_files: set[str],
    input_files: set[str] | None = None,
) -> list[SourceCheck]:
    """Parse every ``SOURCE:`` citation and check it against the real files.

    ``embedded_files`` is the set of files ACTUALLY shown to the advisors (from
    ``gather_code``); ``input_files`` (default: the same set) is every file the
    caller passed. A citation is ``ok`` iff its path was embedded AND the line is
    within that file. A citation to an ``input`` file that was dropped by the embed
    budget is flagged "file not shown to advisors" (it is a guaranteed
    hallucination — the advisor never saw it); an unknown path or an out-of-range
    line is likewise flagged; a SOURCE-shaped line that does not parse is flagged
    "unparseable citation" rather than vanishing.
    """
    if input_files is None:
        input_files = embedded_files
    counts = {p: _line_count(p) for p in embedded_files}

    checks: list[SourceCheck] = []
    for m in _SOURCE_ANY.finditer(final_text):
        rest = m.group(1).strip()
        pm = _CITE.match(rest)
        if not pm:
            checks.append(SourceCheck(rest or "(empty)", None, False, "unparseable citation"))
            continue
        raw_path = pm.group("path").strip()
        line = int(pm.group("line"))
        cp = _norm(raw_path)
        if cp in embedded_files:
            n = counts.get(cp, 0)
            if 1 <= line <= n:
                checks.append(SourceCheck(raw_path, line, True))
            else:
                checks.append(SourceCheck(raw_path, line, False,
                                          f"line out of range (file has {n})"))
        elif cp in input_files:
            checks.append(SourceCheck(raw_path, line, False,
                                      "file not shown to advisors (over budget)"))
        else:
            checks.append(SourceCheck(raw_path, line, False, "path not in audited set"))
    return checks


def _strip_boilerplate(text: str, patterns: list[str]) -> str:
    """Drop leading [STATE]/SSoT lines that advisor agents prepend (they inherit
    this machine's global instructions). Same logic as the HTTP server's
    ``_sanitize``, replicated because the orchestrator calls run_recipe directly.
    """
    res = [re.compile(p) for p in patterns]
    changed = True
    while changed:
        changed = False
        for rx in res:
            m = rx.match(text)
            if m and m.end() > 0:
                text = text[m.end():].lstrip("\n")
                changed = True
    return text


def _new_run_dir(base: str | None = None) -> str:
    """An owner-private per-run directory under ~/.consilium/council/ where each
    member's answer is saved as it arrives, so a killed run can be recovered."""
    if base is None:
        base = os.path.join(os.path.expanduser("~"), ".consilium", "council")
    os.makedirs(base, exist_ok=True)
    try:
        os.chmod(base, 0o700)
    except OSError:
        pass
    # Bound accumulation of interrupted runs by pruning ONLY directories untouched
    # for over a day. A concurrent or recent audit (freshly-created, freshly-written
    # dir) is never eligible — a count-based "keep newest N" prune could delete a
    # still-active run's preserved answers out from under it.
    try:
        cutoff = time.time() - 86400
        for name in os.listdir(base):
            p = os.path.join(base, name)
            try:
                if os.path.isdir(p) and os.path.getmtime(p) < cutoff:
                    shutil.rmtree(p, ignore_errors=True)
            except OSError:
                pass
    except OSError:
        pass
    # mkdtemp guarantees a UNIQUE directory (a bare timestamp+pid collides for two
    # run_audit() calls in the same process within one second) and creates it 0700.
    return tempfile.mkdtemp(dir=base, prefix=f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}-")


def _install_interrupt_handler(registry: ProcessRegistry, results_dir: str):
    """On a hard signal (SIGTERM from a launcher/`timeout`, or Ctrl-C) kill the
    child advisors and preserve the answers already saved under ``results_dir``.
    Python does NOT raise on a bare SIGTERM, so without this the cancel path would
    be skipped — leaving orphaned paid advisors and losing the partial answers.
    Only installable from the main thread; returns handlers to restore."""
    def _on_signal(signum, _frame):
        registry.cancel_all()
        print(f"\n[council] interrupted (signal {signum}) — kept the answers already "
              f"received in {results_dir}", file=sys.stderr)
        sys.stderr.flush()
        os._exit(130)

    saved = []
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                saved.append((sig, signal.signal(sig, _on_signal)))
            except (ValueError, OSError):
                pass
    return saved


def _restore_handlers(saved) -> None:
    for sig, old in saved:
        try:
            signal.signal(sig, old)
        except (ValueError, OSError):
            pass


def run_audit(
    files: list[str],
    user_question: str,
    *,
    profile_name: str = "consilium-budget",
    config_path: str | None = None,
) -> AuditResult:
    """Gather ``files`` as numbered text, ask the parallel council, verify SOURCEs.

    ``code_access`` is forced False regardless of the profile: the code is in the
    question, so members must NOT also receive ``--code``.
    """
    cfg = load_config(config_path)
    if profile_name not in cfg.profiles:
        raise ConfigError(f"unknown profile {profile_name!r}; have {sorted(cfg.profiles)}")
    profile = cfg.profiles[profile_name]
    # Enforce the SEMANTIC (cross-field) profile checks — a verify profile missing
    # its drafter/reviewers, an explicit roster sharing a provider, a code synth
    # that can't read code — BEFORE any paid member runs. cmd_check does this too,
    # but the audit path must not skip it.
    problems = profile.validate()
    if problems:
        raise ConfigError(f"invalid profile {profile_name!r}: " + "; ".join(problems))
    missing = [f for f in files if not os.path.exists(_norm(f))]
    if missing:
        raise ConfigError("file(s) to audit not found: " + ", ".join(missing))
    abs_files = {_norm(f) for f in files}

    code_block, embedded_files = gather_code(files, max_lines=cfg.max_embedded_lines)
    question = build_question(code_block, user_question)
    # A configured member_timeout_seconds of 0 must be honored/rejected, not
    # silently coerced to the default by `or` (L7).
    member_timeout = (
        profile.member_timeout_seconds
        if profile.member_timeout_seconds is not None
        else cfg.member_timeout_seconds
    )

    # Resolve the POLICY profile into a concrete roster from live availability.
    # Fewer agents -> smaller council; one agent -> run it directly; none -> error.
    concrete, single_agent, roster_note = resolve_roster(profile, list_available_agents())
    print(f"[council] {roster_note}", file=sys.stderr)

    results_dir = _new_run_dir()
    registry = ProcessRegistry(results_dir=results_dir)
    saved_handlers = _install_interrupt_handler(registry, results_dir)
    success = False
    try:
        try:
            if concrete is not None:
                result = run_recipe(
                    concrete, question, "",
                    working_dir=cfg.working_dir_abs, code_access=False,
                    member_timeout=member_timeout, registry=registry,
                    max_synth_chars=cfg.max_synth_chars,
                    progress=lambda msg: print(f"[council] {msg}", file=sys.stderr),
                )
                raw_text, members, run_note = result.final_text, result.members, result.note
            elif single_agent is not None:
                # Route through _run_member so the lone agent gets the SAME one-retry
                # on a transient failure that panel members get (M11).
                m = _run_member(
                    single_agent, question, role="panel", context_file=None,
                    code_dir=None, timeout_seconds=member_timeout, registry=registry,
                )
                raw_text, members, run_note = m.answer, [m], "single-agent"
            else:
                raise SystemExit(roster_note)
        except BaseException:
            registry.cancel_all()
            raise

        final = _strip_boilerplate(raw_text, cfg.strip_patterns)
        sources = verify_sources(final, embedded_files, input_files=abs_files)
        note = " | ".join(x for x in (roster_note, run_note) if x)
        success = True
        return AuditResult(final, members, sources, note)
    finally:
        _restore_handlers(saved_handlers)
        if success or not (os.path.isdir(results_dir) and os.listdir(results_dir)):
            # clean success (the printed report has everything) OR nothing was saved
            # yet -> drop the per-run copies.
            shutil.rmtree(results_dir, ignore_errors=True)
        else:
            # abnormal exit with answers already received -> keep them and say where.
            print(f"[council] partial answers preserved in {results_dir}", file=sys.stderr)
