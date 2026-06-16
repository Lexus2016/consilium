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
import sys
from dataclasses import dataclass

from .config import load_config
from .spawn import ProcessRegistry, run_agent
from .recipes import run_recipe
from .roster import list_available_agents, resolve_roster

# Total budget of embedded code lines across all files. Over this, extra files
# are dropped with a VISIBLE marker (never a silent cap).
MAX_LINES = 6000


@dataclass
class SourceCheck:
    path: str
    line: int
    ok: bool
    reason: str = ""


@dataclass
class AuditResult:
    final_text: str
    members: list  # list[MemberResult]
    sources: list  # list[SourceCheck]
    note: str = ""


SOURCE_RULE = (
    "OUTPUT RULES (mandatory):\n"
    "- For EVERY finding, end it with a line exactly like:\n"
    "    SOURCE: <absolute file path>:<line> (function <name>)\n"
    "- Use the EXACT line numbers shown in the left margin of the code below.\n"
    "  Do NOT invent or approximate line numbers.\n"
    "- Cite ONLY the file paths shown below. If you cannot point to a specific\n"
    "  line in the given code, DROP the finding.\n"
    "- Output ONLY your findings. Do NOT echo the code, the prompt, or these rules."
)


def _number_file(abs_path: str) -> tuple[str, int]:
    """Return (a FILE-headed, line-numbered block, line count)."""
    with open(abs_path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    body = "\n".join(f"{i + 1:>5}\t{ln}" for i, ln in enumerate(lines))
    return f"// FILE: {abs_path}\n{body}", len(lines)


def gather_code(files: list[str]) -> str:
    """Read, number and concatenate ``files`` within ``MAX_LINES``.

    The first file is always included even if it alone exceeds the budget;
    subsequent over-budget files are dropped with a visible ``[TRUNCATED ...]``
    marker so the omission is never silent.
    """
    blocks: list[str] = []
    omitted: list[tuple[str, int]] = []
    used = 0
    for path in files:
        ap = os.path.abspath(path)
        block, n = _number_file(ap)
        if blocks and used + n > MAX_LINES:
            omitted.append((ap, n))
            continue
        blocks.append(block)
        used += n
    text = "\n\n".join(blocks)
    if omitted:
        marker = "\n".join(
            f"[TRUNCATED: omitted {p} ({n} lines) — over the {MAX_LINES}-line "
            f"budget; audit it in a separate run]"
            for p, n in omitted
        )
        text = f"{text}\n\n{marker}"
    return text


def build_question(code_block: str, user_question: str) -> str:
    return (
        f"{user_question.strip()}\n\n"
        f"{SOURCE_RULE}\n\n"
        "The code is shown WITH line numbers (number<TAB>code):\n\n"
        f"```\n{code_block}\n```"
    )


_SOURCE_RE = re.compile(r"SOURCE:\s*(\S+?):(\d+)")


def verify_sources(final_text: str, abs_files: set[str]) -> list[SourceCheck]:
    """Parse every ``SOURCE: <path>:<line>`` and check it against the real files.

    A citation is ``ok`` iff its path is one we actually sent AND the line is
    within that file. Everything else (unknown path, line past EOF) is a flagged
    miss — the mechanical hallucination check.
    """
    counts: dict[str, int] = {}
    for p in abs_files:
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                counts[p] = sum(1 for _ in f)
        except OSError:
            counts[p] = 0

    checks: list[SourceCheck] = []
    for m in _SOURCE_RE.finditer(final_text):
        raw_path, line = m.group(1), int(m.group(2))
        ap = os.path.abspath(raw_path)
        if ap not in abs_files:
            checks.append(SourceCheck(raw_path, line, False, "path not in audited set"))
        elif not (1 <= line <= counts[ap]):
            checks.append(SourceCheck(raw_path, line, False,
                                      f"line out of range (file has {counts[ap]})"))
        else:
            checks.append(SourceCheck(raw_path, line, True))
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
        raise SystemExit(f"unknown profile {profile_name!r}; have {sorted(cfg.profiles)}")
    profile = cfg.profiles[profile_name]
    abs_files = {os.path.abspath(f) for f in files}

    code_block = gather_code(files)
    question = build_question(code_block, user_question)
    member_timeout = profile.member_timeout_seconds or cfg.member_timeout_seconds

    # Resolve the POLICY profile into a concrete roster from live availability.
    # Fewer agents -> smaller council; one agent -> run it directly; none -> error.
    concrete, single_agent, roster_note = resolve_roster(profile, list_available_agents())
    print(f"[quorum] {roster_note}", file=sys.stderr)

    registry = ProcessRegistry()
    try:
        if concrete is not None:
            result = run_recipe(
                concrete, question, "",
                working_dir=cfg.working_dir_abs, code_access=False,
                member_timeout=member_timeout, registry=registry,
                progress=lambda msg: print(f"[quorum] {msg}", file=sys.stderr),
            )
            raw_text, members, run_note = result.final_text, result.members, result.note
        elif single_agent is not None:
            m = run_agent(
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
    sources = verify_sources(final, abs_files)
    note = " | ".join(x for x in (roster_note, run_note) if x)
    return AuditResult(final, members, sources, note)
