"""Tests for verify recipe behavior in council.recipes.

Stdlib only (unittest + mock); no runtime dependency. Run from the repo root:

    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from council import recipes  # noqa: E402
from council.config import Profile  # noqa: E402

S = types.SimpleNamespace


def _member(agent, role="panel", ok=True, answer="x"):
    return S(ok=ok, agent=agent, role=role, answer=answer, wall_seconds=1.0, error="")


class VerifyDegradation(unittest.TestCase):
    def test_failed_draft_degrades_to_parallel_with_max_synth_chars(self):
        """If the drafter fails, _run_verify degrades to _run_parallel and must
        preserve the configured max_synth_chars cap.
        """
        captured: dict[str, int | None] = {}

        def fake_run_member(agent, question, *, role, context_file, code_dir,
                            review=False, timeout_seconds, registry):
            if role == "draft":
                return _member(agent, role=role, ok=False, answer="")
            return _member(agent, role=role)

        def fake_run_parallel(*args, **kwargs):
            captured["max_synth_chars"] = kwargs.get("max_synth_chars")
            return recipes.CouncilResult(
                final_text="degraded", model="v", members=[], note="degraded"
            )

        profile = Profile(
            name="v",
            recipe="verify",
            panel=["a", "b"],
            drafter="d",
            reviewers=["r1", "r2"],
            synthesizer="s",
        )
        registry = S(cancelled=False)

        with mock.patch.object(recipes, "_run_member", fake_run_member), \
             mock.patch.object(recipes, "_run_parallel", fake_run_parallel):
            result = recipes.run_recipe(
                profile, "Q", "",
                working_dir=".", code_access=False,
                member_timeout=10, registry=registry,
                progress=lambda _s: None,
                max_synth_chars=1234,
            )

        self.assertEqual(captured.get("max_synth_chars"), 1234)
        self.assertEqual(result.final_text, "degraded")


if __name__ == "__main__":
    unittest.main(verbosity=2)
