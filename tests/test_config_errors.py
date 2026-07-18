"""Config-honesty tests (H9/M3/L6): a typo'd config, malformed JSON, a string
`panel`, a bad strip regex, or a missing audit file must fail LOUDLY with a
clean message and exit 2 — never a silent default or a raw traceback.

Stdlib only.  python3 -m unittest tests.test_config_errors
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from council import cli  # noqa: E402
from council.config import load_config, _profile_from_dict, ConfigError  # noqa: E402


def _write(obj_or_text) -> str:
    fd, p = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        f.write(obj_or_text if isinstance(obj_or_text, str) else json.dumps(obj_or_text))
    return p


class ConfigErrors(unittest.TestCase):
    def test_explicit_missing_config_is_hard_error(self):
        with self.assertRaises(ConfigError):
            load_config("/no/such/dir/council.json")

    def test_malformed_json_is_config_error(self):
        p = _write("{ this is not valid json ")
        try:
            with self.assertRaises(ConfigError):
                load_config(p)
        finally:
            os.unlink(p)

    def test_string_panel_is_rejected(self):
        # list("claude") would silently become ['c','l',...]; must be refused.
        with self.assertRaises(ConfigError):
            _profile_from_dict("bad", {"recipe": "parallel", "panel": "claude"})

    def test_bad_strip_regex_is_config_error(self):
        p = _write({"strip_patterns": ["("]})  # unbalanced group
        try:
            with self.assertRaises(ConfigError):
                load_config(p)
        finally:
            os.unlink(p)

    def test_wrong_typed_fields_are_config_errors_not_tracebacks(self):
        # profiles as a list, a non-numeric timeout, and a non-list strip_patterns
        # must all raise ConfigError (clean exit 2), never a raw AttributeError /
        # ValueError / TypeError traceback.
        for bad in (
            {"profiles": []},
            {"member_timeout_seconds": "abc"},
            {"strip_patterns": 5},
            {"strip_patterns": "abc"},                       # str is iterable -> would become ['a','b','c']
            {"profiles": {"p": {"recipe": "parallel", "panel_size": "abc"}}},
            {"profiles": {"p": {"recipe": "parallel", "panel": {"claude": True}}}},  # dict panel
            {"profiles": {"p": {"recipe": "parallel", "panel": ["codex"],
                                "member_timeout_seconds": "abc"}}},  # profile-level non-int timeout
            {"working_dir": 5},                                       # non-string working_dir
            {"member_timeout_seconds": -40},                         # negative timeout
            {"max_synth_chars": 0},                                  # zero synth budget
            {"max_embedded_lines": -1},                              # negative embed budget
            {"profiles": {"p": {"recipe": "parallel", "panel": [5]}}},  # non-string agent name
            {"profiles": {"p": {"recipe": "parallel", "panel_size": -5}}},  # panel_size < 1
            {"profiles": {"p": {"recipe": "typo", "panel": ["codex"]}}},    # unknown recipe enum
            {"profiles": {"p": {"recipe": "parallel", "panel_size": 1.9}}},  # float, not int
            {"member_timeout_seconds": True},                               # bool, not int
            {"max_synth_chars": 1.9},                                       # float, not int
            {"profiles": {"p": {"recipe": "parallel", "synthesizer": 5}}},  # non-string synthesizer
            {"profiles": {"p": {"recipe": "verify", "drafter": 5, "reviewers": ["a"]}}},  # non-string drafter
            {"profiles": {"p": {"recipe": "parallel", "code_access": "false"}}},  # non-bool code_access
            {"host": 5},                                                    # non-string host
        ):
            p = _write(bad)
            try:
                with self.assertRaises(ConfigError):
                    load_config(p)
            finally:
                os.unlink(p)

    def test_explicit_empty_profiles_not_silently_defaulted(self):
        p = _write({"profiles": {}})
        try:
            cfg = load_config(p)
            self.assertEqual(cfg.profiles, {}, "explicit {} must stay empty, not become the defaults")
        finally:
            os.unlink(p)

    def test_missing_default_config_warns_and_uses_defaults(self):
        # No path, no env: a missing default must NOT raise — it warns and ships
        # the built-in profiles. Point the default resolver at a nonexistent file.
        env_snapshot = {k: os.environ.get(k) for k in ("COUNCIL_CONFIG", "QUORUM_CONFIG")}
        for k in env_snapshot:
            os.environ.pop(k, None)
        try:
            import council.config as cfgmod
            orig = cfgmod._default_config_path
            cfgmod._default_config_path = lambda: "/no/such/default/council.json"
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                cfg = load_config(None)
            self.assertTrue(cfg.profiles, "built-in profiles should be used")
            self.assertIn("using built-in defaults", buf.getvalue())
        finally:
            cfgmod._default_config_path = orig
            for k, v in env_snapshot.items():
                if v is not None:
                    os.environ[k] = v

    def test_missing_audit_file_exits_2_not_traceback(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            rc = cli.main(["audit", "-f", "/nope/ghost_xyz_123.py", "-q", "find bugs"])
        self.assertEqual(rc, 2, "a user error must exit 2, not crash or exit 1")
        self.assertIn("council:", buf.getvalue())

    def test_semantically_invalid_profile_fails_before_paid_run(self):
        # A verify profile with no drafter/reviewers passes per-field load_config but
        # must be rejected (Profile.validate) at exit 2 by the AUDIT path too, before
        # any paid member runs — not crash mid-run passing None as an agent.
        p = _write({"profiles": {"bad": {"recipe": "verify",
                                         "panel": ["codex", "agy"],
                                         "synthesizer": "opencode"}}})
        try:
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                rc = cli.main(["audit", "-f", "/nope/x.py", "-q", "q",
                               "--profile", "bad", "--config", p])
            self.assertEqual(rc, 2)
            self.assertIn("drafter", buf.getvalue())
        finally:
            os.unlink(p)


if __name__ == "__main__":
    unittest.main(verbosity=2)
