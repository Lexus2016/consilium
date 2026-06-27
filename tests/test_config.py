"""Regression tests for council config loading and defaults.

Run from the repo root:

    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from council import config  # noqa: E402


class ConfigLoading(unittest.TestCase):
    def test_custom_caps_loaded(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(
                '{"max_embedded_lines": 1234, "max_synth_chars": 5678, "profiles": {}}'
            )
            path = f.name
        try:
            cfg = config.load_config(path)
            self.assertEqual(cfg.max_embedded_lines, 1234)
            self.assertEqual(cfg.max_synth_chars, 5678)
        finally:
            os.unlink(path)

    def test_default_caps_present(self):
        cfg = config.load_config(None)
        self.assertEqual(cfg.max_embedded_lines, 6000)
        self.assertEqual(cfg.max_synth_chars, 6000)


class DefaultProfiles(unittest.TestCase):
    def test_default_profiles_are_policies_not_fixed_rosters(self):
        for name, raw in config.DEFAULT_PROFILES.items():
            with self.subTest(profile=name):
                self.assertNotIn("panel", raw)
                self.assertNotIn("synthesizer", raw)
                self.assertNotIn("drafter", raw)
                self.assertNotIn("reviewers", raw)
                self.assertIn("recipe", raw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
