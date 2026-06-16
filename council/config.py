"""Configuration loading and validation for council.

Config is plain JSON (stdlib only, works on any Python 3) so there is nothing to
install and the format is obvious. A profile maps an OpenAI "model" name to a
council policy: which agents sit on the panel, which recipe runs, and who
synthesizes the final answer.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any


# Which provider each agent CLI talks to. Used to enforce cross-provider
# diversity in a panel: two members on the SAME provider give fake independence,
# which is exactly the failure mode that makes a council pointless.
AGENT_PROVIDERS: dict[str, str] = {
    "claude": "anthropic",
    "codex": "openai",
    "agy": "google",
    "hermes": "openrouter/moonshot",
    "opencode": "zhipu/glm",
}

# Agents whose `consult` dispatch actually passes the working directory through
# to the model (claude/agy via --add-dir, codex via -C). hermes/opencode ignore
# --code, so they must NOT be chosen as the synthesizer when code access matters.
AGENTS_WITH_CODE_ACCESS = {"claude", "agy", "codex"}

VALID_RECIPES = {"parallel", "verify"}


@dataclass
class Profile:
    """One routing policy, exposed to clients as an OpenAI 'model' name."""

    name: str
    recipe: str                       # "parallel" | "verify"
    # Roster: empty in a POLICY profile (resolved at runtime by roster.py from the
    # agents actually available); may be set explicitly in a legacy profile and is
    # then used as-is.
    panel: list[str] = field(default_factory=list)  # independent answerers / draft+review
    synthesizer: str = ""             # separate agent that reconciles the final answer
    code_access: bool = False         # pass working_dir to members that support it
    drafter: str | None = None        # verify recipe: who writes the first draft
    reviewers: list[str] = field(default_factory=list)  # verify recipe: adversarial critics
    member_timeout_seconds: int | None = None  # per-member override
    panel_size: int = 3               # POLICY: target number of independent answerers
    min_panel: int = 1                # POLICY: below this, degrade toward single-agent

    def validate(self) -> list[str]:
        """Return a list of human-readable problems (empty = OK)."""
        problems: list[str] = []
        if self.recipe not in VALID_RECIPES:
            problems.append(f"{self.name}: unknown recipe {self.recipe!r}")
        # POLICY profile (no explicit panel): the roster is resolved at runtime, so
        # only policy fields are checked here. Cross-provider diversity and
        # code-access are enforced by roster.resolve_roster against live availability.
        if not self.panel:
            if self.panel_size < 1:
                problems.append(f"{self.name}: panel_size must be >= 1")
            return problems
        if self.recipe == "verify":
            if not self.drafter:
                problems.append(f"{self.name}: verify recipe needs a 'drafter'")
            if not self.reviewers:
                problems.append(f"{self.name}: verify recipe needs 'reviewers'")
        # Cross-provider diversity check on the agents that actually give
        # INDEPENDENT answers: the panel for 'parallel', but drafter+reviewers
        # for 'verify' (where profile.panel may differ from who really runs).
        if self.recipe == "verify":
            answering = ([self.drafter] if self.drafter else []) + self.reviewers
        else:
            answering = self.panel
        providers = [AGENT_PROVIDERS.get(a, a) for a in answering]
        dupes = {p for p in providers if providers.count(p) > 1}
        if dupes:
            problems.append(
                f"{self.name}: independent answerers share provider(s) {sorted(dupes)} "
                "— that is fake independence; use distinct providers"
            )
        if self.code_access and self.synthesizer not in AGENTS_WITH_CODE_ACCESS:
            problems.append(
                f"{self.name}: synthesizer {self.synthesizer!r} cannot read code "
                f"(code_access=true). Use one of {sorted(AGENTS_WITH_CODE_ACCESS)}"
            )
        if self.code_access and self.recipe == "parallel":
            blind = [a for a in self.panel if a not in AGENTS_WITH_CODE_ACCESS]
            if blind:
                problems.append(
                    f"{self.name}: parallel panel member(s) {blind} ignore --code "
                    f"(code_access=true) — they answer blind. Use readers "
                    f"{sorted(AGENTS_WITH_CODE_ACCESS)}, or set code_access=false and "
                    "pass code in the question (the orchestrator path)."
                )
        return problems


@dataclass
class Config:
    working_dir: str = "."
    host: str = "127.0.0.1"
    port: int = 11435
    max_concurrent_panels: int = 2
    member_timeout_seconds: int = 900
    heartbeat_seconds: int = 10
    # Regexes (matched at the START of an answer) used to strip environment-
    # specific boilerplate that advisor agents prepend — e.g. activation tokens
    # or SSoT lines injected by a user's global agent instructions. Empty by
    # default so the tool stays general.
    strip_patterns: list[str] = field(default_factory=list)
    profiles: dict[str, Profile] = field(default_factory=dict)

    @property
    def working_dir_abs(self) -> str:
        return os.path.abspath(os.path.expanduser(self.working_dir))


DEFAULT_PROFILES: dict[str, dict[str, Any]] = {
    # Default for serious work: draft -> adversarial review -> synthesize.
    # Code is not averageable; a critic told to "find where this fails" catches
    # bugs that a naive merge of independent answers does not.
    "consilium-verify": {
        "recipe": "verify",
        "panel": ["agy", "opencode", "hermes"],
        "drafter": "agy",
        "reviewers": ["opencode", "hermes"],
        "synthesizer": "agy",
        "code_access": True,
    },
    # Cheap/fast: independent answers + synthesis. Good for "give me options".
    "consilium-budget": {
        "recipe": "parallel",
        "panel": ["opencode", "hermes"],
        "synthesizer": "agy",
        "code_access": False,
    },
    # Strongest panel, independent + synthesis, with code access.
    "consilium-frontier": {
        "recipe": "parallel",
        "panel": ["agy", "codex", "opencode"],
        "synthesizer": "agy",
        "code_access": True,
    },
}


def _profile_from_dict(name: str, d: dict[str, Any]) -> Profile:
    return Profile(
        name=name,
        recipe=d.get("recipe", "parallel"),
        panel=list(d.get("panel", [])),
        synthesizer=d.get("synthesizer", ""),
        code_access=bool(d.get("code_access", False)),
        drafter=d.get("drafter"),
        reviewers=list(d.get("reviewers", [])),
        member_timeout_seconds=d.get("member_timeout_seconds"),
        panel_size=int(d.get("panel_size", 3)),
        min_panel=int(d.get("min_panel", 1)),
    )


def load_config(path: str | None) -> Config:
    """Load config from JSON, falling back to built-in defaults.

    Explicit fields in the file override defaults; if no 'profiles' key is given,
    the three built-in profiles are used so the council works out of the box.
    """
    raw: dict[str, Any] = {}
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

    profiles_raw = raw.get("profiles") or DEFAULT_PROFILES
    profiles = {name: _profile_from_dict(name, d) for name, d in profiles_raw.items()}

    cfg = Config(
        working_dir=raw.get("working_dir", "."),
        host=raw.get("host", "127.0.0.1"),
        port=int(raw.get("port", 11435)),
        max_concurrent_panels=int(raw.get("max_concurrent_panels", 2)),
        member_timeout_seconds=int(raw.get("member_timeout_seconds", 900)),
        heartbeat_seconds=int(raw.get("heartbeat_seconds", 10)),
        strip_patterns=list(raw.get("strip_patterns", [])),
        profiles=profiles,
    )
    return cfg


def validate_config(cfg: Config) -> list[str]:
    problems: list[str] = []
    if not cfg.profiles:
        problems.append("no profiles defined")
    for prof in cfg.profiles.values():
        problems.extend(prof.validate())
    return problems
