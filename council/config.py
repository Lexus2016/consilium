"""Configuration loading and validation for council.

Config is plain JSON (stdlib only, works on any Python 3) so there is nothing to
install and the format is obvious. A profile maps an OpenAI "model" name to a
council policy: which agents sit on the panel, which recipe runs, and who
synthesizes the final answer.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any


class ConfigError(Exception):
    """A user-facing configuration or usage error. cli.main maps it to exit 2 so
    it is distinguishable from an INCOMPLETE audit (exit 1) and never surfaces as
    a raw traceback."""


# Which provider each agent CLI talks to. Used to enforce cross-provider
# diversity in a panel: two members on the SAME provider give fake independence,
# which is exactly the failure mode that makes a council pointless.
AGENT_PROVIDERS: dict[str, str] = {
    "claude": "anthropic",
    "codex": "openai",
    "agy": "google",
    "hermes": "openrouter/moonshot",
    "grok": "xai",
    # Kimi Code talks to Moonshot's own Kimi models (K2), so it is a NAMED provider,
    # not a model-agnostic front-end. Bucketed as "moonshot". (hermes is tagged
    # "openrouter/moonshot"; kept as a distinct bucket because hermes's configured
    # model varies — a user who runs hermes on Moonshot too should merge the two.)
    "kimi": "moonshot",
    # `opencode`, `pi`, `cursor`, `kilo`, `cline`, and `goose` are model-agnostic
    # front-ends: the real provider is whatever the user configured, so we cannot
    # assign one reliably. Bucketing each under its own name means the cross-
    # provider diversity check treats two `opencode` (or two `goose`) instances as
    # the same provider — fake independence — while still allowing, say, `goose`
    # and `cline` on one panel. Users who want a guaranteed provider should pick a
    # named-provider advisor (claude/codex/agy/hermes/grok) or override this map.
    "opencode": "opencode",
    "pi": "pi",
    "cursor": "cursor",
    "kilo": "kilo",
    "cline": "cline",
    "goose": "goose",
}

# Agents whose `consult` dispatch actually passes the working directory through
# to the model (claude/agy/kimi via --add-dir, codex via -C, grok via --cwd, kilo
# via --dir, cline via --cwd). hermes/opencode/pi/cursor/goose ignore --code, so
# they must NOT be chosen as the synthesizer when code access matters.
AGENTS_WITH_CODE_ACCESS = {"claude", "agy", "codex", "grok", "kilo", "cline", "kimi"}

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
    # Total lines of code embedded into a council question. Over this, extra
    # files are dropped with a visible [TRUNCATED] marker.
    max_embedded_lines: int = 6000
    # Per-member answer cap fed into the synthesizer. Over this, the answer is
    # truncated with a visible marker so one verbose member can't blow the
    # synthesizer's input budget.
    max_synth_chars: int = 6000
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
    # The concrete roster is resolved at runtime from the agents `consult --list`
    # reports as available, with cross-provider diversity.
    "consilium-verify": {
        "recipe": "verify",
        "code_access": True,
        "panel_size": 3,
    },
    # Cheap/fast: independent answers + synthesis. Good for "give me options".
    "consilium-budget": {
        "recipe": "parallel",
        "code_access": False,
        "panel_size": 2,
    },
    # Strongest panel, independent + synthesis, with code access.
    "consilium-frontier": {
        "recipe": "parallel",
        "code_access": True,
        "panel_size": 3,
    },
}


def _profile_from_dict(name: str, d: dict[str, Any]) -> Profile:
    if not isinstance(d, dict):
        raise ConfigError(f"profile {name!r} must be a JSON object")
    panel = d.get("panel", [])
    reviewers = d.get("reviewers", [])
    # A bare string is iterable, so `list("claude")` would silently become
    # ['c','l','a','u','d','e']. Reject it instead of building a nonsense roster.
    if isinstance(panel, str) or isinstance(reviewers, str):
        raise ConfigError(f"profile {name!r}: 'panel'/'reviewers' must be lists, not strings")
    return Profile(
        name=name,
        recipe=d.get("recipe", "parallel"),
        panel=list(panel),
        synthesizer=d.get("synthesizer", ""),
        code_access=bool(d.get("code_access", False)),
        drafter=d.get("drafter"),
        reviewers=list(reviewers),
        member_timeout_seconds=d.get("member_timeout_seconds"),
        panel_size=int(d.get("panel_size", 3)),
        min_panel=int(d.get("min_panel", 1)),
    )


def _default_config_path() -> str:
    """The config shipped with the repo, resolved relative to THIS package rather
    than the caller's CWD — so `python3 -m council` works from any directory."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(repo_root, "config", "council.json")


def load_config(path: str | None) -> Config:
    """Load config from JSON, falling back to built-in defaults.

    An EXPLICITLY-passed path (``--config`` / ``$COUNCIL_CONFIG`` / ``$QUORUM_CONFIG``)
    that does not exist is a hard error — a typo must fail loudly, not silently use
    defaults. A missing DEFAULT config warns and uses the built-in profiles so the
    council still works out of the box.
    """
    env_path = os.environ.get("COUNCIL_CONFIG") or os.environ.get("QUORUM_CONFIG")
    explicit = path is not None or env_path is not None
    resolved = path or env_path or _default_config_path()

    raw: dict[str, Any] = {}
    if os.path.exists(resolved):
        try:
            with open(resolved, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise ConfigError(f"cannot read config {resolved}: {e}")
        if not isinstance(raw, dict):
            raise ConfigError(f"config {resolved} must be a JSON object")
    elif explicit:
        raise ConfigError(f"config file not found: {resolved}")
    else:
        print(f"[council] no config at {resolved}; using built-in defaults", file=sys.stderr)

    # An explicit {"profiles": {}} means "no profiles" (a mistake to surface), NOT
    # "use the defaults": distinguish a missing key from an empty value.
    profiles_raw = raw["profiles"] if "profiles" in raw else DEFAULT_PROFILES
    profiles = {name: _profile_from_dict(name, d) for name, d in profiles_raw.items()}

    cfg = Config(
        working_dir=raw.get("working_dir", "."),
        host=raw.get("host", "127.0.0.1"),
        port=int(raw.get("port", 11435)),
        max_concurrent_panels=int(raw.get("max_concurrent_panels", 2)),
        member_timeout_seconds=int(raw.get("member_timeout_seconds", 900)),
        heartbeat_seconds=int(raw.get("heartbeat_seconds", 10)),
        max_embedded_lines=int(raw.get("max_embedded_lines", 6000)),
        max_synth_chars=int(raw.get("max_synth_chars", 6000)),
        strip_patterns=list(raw.get("strip_patterns", [])),
        profiles=profiles,
    )
    # Validate strip_patterns eagerly so a bad regex fails HERE (exit 2), not with a
    # traceback after the panel has already run and been paid for.
    for p in cfg.strip_patterns:
        try:
            re.compile(p)
        except re.error as e:
            raise ConfigError(f"invalid strip_patterns regex {p!r}: {e}")
    return cfg


def validate_config(cfg: Config) -> list[str]:
    problems: list[str] = []
    if not cfg.profiles:
        problems.append("no profiles defined")
    for prof in cfg.profiles.values():
        problems.extend(prof.validate())
    return problems
