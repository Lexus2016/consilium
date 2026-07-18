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


def _require_int(name: str, value: Any, lo: int) -> int:
    """A numeric config knob must be a JSON integer (not bool, float, or string)
    and within range. Silently coercing a float/bool/string (int(1.9)->1,
    int(True)->1, int("5")->5) would change behavior, so reject it loudly."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{name} must be an integer, got {type(value).__name__}")
    if value < lo:
        raise ConfigError(f"{name} must be >= {lo}, got {value}")
    return value


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
    recipe = d.get("recipe", "parallel")
    if recipe not in VALID_RECIPES:
        raise ConfigError(f"profile {name!r}: unknown recipe {recipe!r} "
                          f"(expected one of {sorted(VALID_RECIPES)})")
    panel = d.get("panel", [])
    reviewers = d.get("reviewers", [])
    # A bare string is iterable, so `list("claude")` would silently become
    # ['c','l',...]; a dict would become a list of its keys. Require real lists.
    if not isinstance(panel, list) or not isinstance(reviewers, list):
        raise ConfigError(f"profile {name!r}: 'panel'/'reviewers' must be lists")
    if not all(isinstance(x, str) for x in panel) or not all(isinstance(x, str) for x in reviewers):
        raise ConfigError(f"profile {name!r}: 'panel'/'reviewers' entries must be agent-name strings")
    # member_timeout_seconds flows all the way to subprocess.communicate(timeout=...)
    # and panel_size reaches roster resolution; validate them now (a non-int would
    # raise mid-run, a bad range would silently degrade) so the config fails cleanly
    # before any paid process.
    mts = d.get("member_timeout_seconds")
    if mts is not None:
        mts = _require_int(f"profile {name!r}: 'member_timeout_seconds'", mts, 0)
    # synthesizer/drafter are used as agent names (a non-string would raise a raw
    # TypeError at spawn); code_access must be a real bool (bool("false") is True,
    # a silent footgun). Validate the remaining scalar fields strictly.
    synthesizer = d.get("synthesizer", "")
    if not isinstance(synthesizer, str):
        raise ConfigError(f"profile {name!r}: 'synthesizer' must be a string")
    drafter = d.get("drafter")
    if drafter is not None and not isinstance(drafter, str):
        raise ConfigError(f"profile {name!r}: 'drafter' must be a string")
    code_access = d.get("code_access", False)
    if not isinstance(code_access, bool):
        raise ConfigError(f"profile {name!r}: 'code_access' must be true or false")
    return Profile(
        name=name,
        recipe=recipe,
        panel=list(panel),
        synthesizer=synthesizer,
        code_access=code_access,
        drafter=drafter,
        reviewers=list(reviewers),
        member_timeout_seconds=mts,
        panel_size=_require_int(f"profile {name!r}: 'panel_size'", d.get("panel_size", 3), 1),
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
    if not isinstance(profiles_raw, dict):
        raise ConfigError(f"'profiles' must be a JSON object, got {type(profiles_raw).__name__}")
    profiles = {name: _profile_from_dict(name, d) for name, d in profiles_raw.items()}

    # A bare string/dict is iterable, so list("abc") would silently become
    # ['a','b','c']; require a real list for strip_patterns.
    strip_raw = raw.get("strip_patterns", [])
    if not isinstance(strip_raw, list):
        raise ConfigError(f"'strip_patterns' must be a list, got {type(strip_raw).__name__}")
    working_dir = raw.get("working_dir", ".")
    if not isinstance(working_dir, str):
        raise ConfigError(f"'working_dir' must be a string, got {type(working_dir).__name__}")
    host = raw.get("host", "127.0.0.1")
    if not isinstance(host, str):
        raise ConfigError(f"'host' must be a string, got {type(host).__name__}")

    # Numeric knobs are strictly validated (int-only, in range) BEFORE any paid
    # process so a float/bool/negative fails cleanly here, not mid-run.
    cfg = Config(
        working_dir=working_dir,
        host=host,
        port=_require_int("'port'", raw.get("port", 11435), 1),
        max_concurrent_panels=_require_int("'max_concurrent_panels'", raw.get("max_concurrent_panels", 2), 1),
        member_timeout_seconds=_require_int("'member_timeout_seconds'", raw.get("member_timeout_seconds", 900), 0),
        heartbeat_seconds=_require_int("'heartbeat_seconds'", raw.get("heartbeat_seconds", 10), 0),
        max_embedded_lines=_require_int("'max_embedded_lines'", raw.get("max_embedded_lines", 6000), 1),
        max_synth_chars=_require_int("'max_synth_chars'", raw.get("max_synth_chars", 6000), 1),
        strip_patterns=list(strip_raw),
        profiles=profiles,
    )
    # Validate strip_patterns eagerly so a bad regex (or non-string entry) fails
    # HERE (exit 2), not with a traceback after the panel has run and been paid for.
    for p in cfg.strip_patterns:
        try:
            re.compile(p)
        except (re.error, TypeError) as e:
            raise ConfigError(f"invalid strip_patterns entry {p!r}: {e}")
    return cfg


def validate_config(cfg: Config) -> list[str]:
    problems: list[str] = []
    if not cfg.profiles:
        problems.append("no profiles defined")
    for prof in cfg.profiles.values():
        problems.extend(prof.validate())
    return problems
