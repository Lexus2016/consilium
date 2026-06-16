"""Dynamic roster resolution.

A profile is a POLICY (recipe, code_access, panel_size). The concrete roster —
who answers, who synthesizes — is resolved at runtime from the agents actually
available right now, with cross-provider diversity. Profiles no longer hard-code
agent names, so the council adapts to whatever is installed instead of breaking
when an agent is missing or not logged in.

Availability comes from `consult --list` (installed/not-found only — no login
state). Not-logged-in members that slip through are absorbed downstream by the
member-fail path in recipes (one retry + partial panel).
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import replace

from .config import AGENT_PROVIDERS, AGENTS_WITH_CODE_ACCESS, Profile
from .spawn import CONSULT_BIN

_AVAIL_CACHE: list[str] | None = None
_LINE_RE = re.compile(r"^\s*([A-Za-z0-9_-]+)\s+installed\b")

# Agents excluded from councils by default. `claude` is excluded because the
# orchestrator is typically Claude itself (a same-provider member is
# self-consultation, not a second opinion) AND claude inherits this machine's
# CLAUDE.md the way agy inherited GEMINI.md (unfixed). Override via the env var
# COUNCIL_EXCLUDE_AGENTS (comma-separated; set to "" to allow everything).
_EXCLUDE = {
    a.strip()
    for a in os.environ.get("COUNCIL_EXCLUDE_AGENTS", "claude").split(",")
    if a.strip()
}


def list_available_agents(timeout: int = 15, *, refresh: bool = False) -> list[str]:
    """Agent names reported `installed` by `consult --list`. Cached per process."""
    global _AVAIL_CACHE
    if _AVAIL_CACHE is not None and not refresh:
        return _AVAIL_CACHE
    try:
        proc = subprocess.run(
            [CONSULT_BIN, "--list"], capture_output=True, text=True, timeout=timeout,
        )
        out = proc.stdout
    except Exception:  # noqa: BLE001 — binary missing / timeout: degrade to empty
        _AVAIL_CACHE = []
        return _AVAIL_CACHE
    agents = [
        m.group(1)
        for line in out.splitlines()
        if (m := _LINE_RE.match(line)) and m.group(1) not in _EXCLUDE
    ]
    _AVAIL_CACHE = agents
    return agents


def _dedup_by_provider(agents: list[str]) -> list[str]:
    """Keep the first agent of each provider — two same-provider members are fake
    independence, not a real second opinion."""
    seen: set[str] = set()
    out: list[str] = []
    for a in agents:
        provider = AGENT_PROVIDERS.get(a, a)
        if provider not in seen:
            seen.add(provider)
            out.append(a)
    return out


def resolve_roster(
    policy: Profile, available: list[str]
) -> tuple[Profile | None, str | None, str]:
    """Fill a policy profile's roster from `available` agents.

    Returns (concrete_profile, single_agent, note):
      - council  -> (Profile, None,   note)   caller runs run_recipe(concrete)
      - single   -> (None,    agent,  note)   caller runs that one agent directly
      - none     -> (None,    None,   note)   no usable agent; caller errors with note
    """
    # Legacy / explicit roster: a profile that already names its members is used as-is.
    if policy.panel and policy.synthesizer:
        return policy, None, f"explicit roster: panel={policy.panel} synth={policy.synthesizer}"

    pool = (
        [a for a in available if a in AGENTS_WITH_CODE_ACCESS]
        if policy.code_access
        else list(available)
    )
    diverse = _dedup_by_provider(pool)

    if not diverse:
        return None, None, (
            f"no available agents for {policy.name!r} "
            f"(code_access={policy.code_access}, available={available})"
        )
    if len(diverse) == 1:
        return None, diverse[0], (
            f"single-agent fallback: only {diverse[0]} usable for {policy.name!r}; "
            "a council needs >=2 distinct providers"
        )

    synth = diverse[0]
    answerers = diverse[1: 1 + max(1, policy.panel_size)]

    if policy.recipe == "verify" and len(answerers) >= 2:
        concrete = replace(
            policy, panel=answerers, synthesizer=synth,
            drafter=answerers[0], reviewers=answerers[1:],
        )
        note = f"resolved {policy.name!r} (verify): synth={synth}, draft={answerers[0]}, reviewers={answerers[1:]}"
    else:
        # parallel, or verify with too few answerers to have a separate critic.
        degraded = policy.recipe == "verify"
        concrete = replace(policy, recipe="parallel", panel=answerers, synthesizer=synth)
        note = (
            f"resolved {policy.name!r}: synth={synth}, panel={answerers}"
            + (" (verify degraded to parallel: <2 answerers)" if degraded else "")
        )
    return concrete, None, note
