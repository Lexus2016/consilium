"""Tests for the perspective-diverse audit lens in council.recipes.

Stdlib only (unittest + mock); no runtime dependency. Run from the repo root:

    python3 -m unittest discover -s tests

Locks two guarantees of the perspective-diverse panel:
  * distinct members of a multi-member panel get DISTINCT lenses (more coverage);
  * a single-member panel is NOT lensed (a lone auditor stays full-spectrum).
"""

from __future__ import annotations

import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from council import recipes  # noqa: E402
from council.recipes import AUDIT_LENSES, _with_lens  # noqa: E402

S = types.SimpleNamespace


def _member(agent, role="panel"):
    return S(ok=True, agent=agent, role=role, answer="x", wall_seconds=1.0, error="")


class AuditLensHelper(unittest.TestCase):
    def test_distinct_index_distinct_lens(self):
        self.assertNotEqual(_with_lens("Q", 0), _with_lens("Q", 1))

    def test_preserves_the_prompt(self):
        self.assertIn("Q-BODY", _with_lens("Q-BODY", 0))

    def test_cycles_past_the_list(self):
        self.assertEqual(_with_lens("Q", 0), _with_lens("Q", len(AUDIT_LENSES)))

    def test_enough_distinct_lenses(self):
        self.assertGreaterEqual(len(set(AUDIT_LENSES)), 3)


class ParallelLensAssignment(unittest.TestCase):
    def _run(self, panel):
        """Run _run_parallel with run_member/synthesize/finalize stubbed; return
        the list of prompts each member actually received."""
        prompts = []

        def fake_member(agent, prompt, **kw):
            prompts.append(prompt)
            return _member(agent)

        profile = S(panel=list(panel), name="p", synthesizer="s")
        registry = S(cancelled=False)
        with mock.patch.object(recipes, "_run_member", fake_member), \
             mock.patch.object(recipes, "_synthesize",
                               lambda *a, **k: _member("s", role="synth")), \
             mock.patch.object(recipes, "_finalize",
                               lambda profile, synth, ok, members, wd:
                               recipes.CouncilResult(synth.answer, profile.name, members)):
            recipes._run_parallel(profile, "BASE-Q", None, None, ".", 10,
                                  registry, lambda _s: None)
        return prompts

    def test_multi_member_panel_gets_distinct_lenses(self):
        prompts = self._run(["a", "b", "c"])
        self.assertEqual(len(prompts), 3)
        self.assertEqual(len(set(prompts)), 3, "each member must get a distinct lensed prompt")
        for p in prompts:
            self.assertIn("BASE-Q", p)
            self.assertIn("PRIMARY AUDIT LENS", p)

    def test_single_member_panel_is_not_lensed(self):
        prompts = self._run(["solo"])
        self.assertEqual(prompts, ["BASE-Q"])
        self.assertNotIn("PRIMARY AUDIT LENS", prompts[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
