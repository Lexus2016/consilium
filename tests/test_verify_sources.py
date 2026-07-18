"""Unit tests for the verifier core (``council.orchestrator``): the citation
parser, the embed-budget set, path normalization and the clean-audit token.

These lock the H1/H2/H1b/M8/N2 fixes and would have caught the original bugs
(a garbled citation vanishing; a cite to an over-budget file passing as OK).

Stdlib only. Run from the repo root:

    python3 -m unittest tests.test_verify_sources
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from council.orchestrator import (  # noqa: E402
    gather_code,
    has_clean_audit_token,
    mentions_no_findings,
    verify_sources,
    _norm,
)


class VerifierCore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _mk(self, name: str, nlines: int) -> str:
        p = os.path.join(self.dir, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(f"line {i}" for i in range(1, nlines + 1)))
        return p

    # --- H1: zero / malformed citations ------------------------------------
    def test_zero_citations_returns_empty(self):
        p = self._mk("a.py", 10)
        self.assertEqual(verify_sources("prose with no citations", {_norm(p)}), [])

    def test_malformed_negative_line_is_flagged_not_vanished(self):
        p = self._mk("a.py", 10)
        checks = verify_sources(f"SOURCE: {p}:-5", {_norm(p)})
        self.assertEqual(len(checks), 1, "a SOURCE-shaped line must NOT vanish")
        self.assertFalse(checks[0].ok)
        self.assertIsNone(checks[0].line)
        self.assertIn("unparseable", checks[0].reason)

    def test_missing_line_number_is_flagged(self):
        p = self._mk("a.py", 10)
        checks = verify_sources(f"SOURCE: {p}", {_norm(p)})
        self.assertEqual(len(checks), 1)
        self.assertFalse(checks[0].ok)
        self.assertIn("unparseable", checks[0].reason)

    # --- happy path + range -------------------------------------------------
    def test_in_range_ok(self):
        p = self._mk("a.py", 10)
        checks = verify_sources(f"finding\nSOURCE: {p}:3 (function f)", {_norm(p)})
        self.assertEqual(len(checks), 1)
        self.assertTrue(checks[0].ok)
        self.assertEqual(checks[0].line, 3)

    def test_out_of_range_bad(self):
        p = self._mk("a.py", 10)
        checks = verify_sources(f"SOURCE: {p}:99", {_norm(p)})
        self.assertFalse(checks[0].ok)
        self.assertIn("out of range", checks[0].reason)

    # --- H1b: paths with spaces --------------------------------------------
    def test_path_with_spaces_parses(self):
        p = self._mk("my file.py", 5)
        checks = verify_sources(f"SOURCE: {p}:2", {_norm(p)})
        self.assertEqual(len(checks), 1)
        self.assertTrue(checks[0].ok, "a path containing spaces must still parse")

    def test_file_line_col_citation_parses(self):
        # Some advisors emit file:line:col; the trailing :col must not make the
        # path read as "<file>:<line>" (which would falsely flag it BAD).
        p = self._mk("a.py", 10)
        checks = verify_sources(f"SOURCE: {p}:3:15 (function f)", {_norm(p)})
        self.assertEqual(len(checks), 1)
        self.assertTrue(checks[0].ok)
        self.assertEqual(checks[0].line, 3)

    def test_source_inside_diff_is_ignored(self):
        # A `SOURCE:` appearing mid-line inside a suggested diff / quoted code must
        # NOT create a spurious malformed citation and wrongly fail a valid answer;
        # only a real line-anchored citation counts.
        p = self._mk("a.py", 10)
        ans = 'Finding.\n```diff\n+LOG_PREFIX = "SOURCE: x"\n```\nSOURCE: %s:3\n' % p
        checks = verify_sources(ans, {_norm(p)})
        self.assertEqual(len(checks), 1, "the in-diff SOURCE: must be ignored")
        self.assertTrue(checks[0].ok)

    # --- H2: budget-omitted file is a guaranteed hallucination -------------
    def test_omitted_file_flagged_not_shown(self):
        shown = self._mk("shown.py", 10)
        hidden = self._mk("hidden.py", 500)
        checks = verify_sources(
            f"SOURCE: {hidden}:250",
            embedded_files={_norm(shown)},
            input_files={_norm(shown), _norm(hidden)},
        )
        self.assertFalse(checks[0].ok)
        self.assertIn("not shown", checks[0].reason)

    def test_unknown_path_bad(self):
        p = self._mk("a.py", 10)
        checks = verify_sources("SOURCE: /nope/ghost.py:1", {_norm(p)})
        self.assertFalse(checks[0].ok)
        self.assertIn("not in audited set", checks[0].reason)

    # --- N2: expanduser / symlink normalization ----------------------------
    def test_symlink_alias_resolves_to_embedded_path(self):
        real = self._mk("real.py", 4)
        link = os.path.join(self.dir, "alias.py")
        os.symlink(real, link)
        checks = verify_sources(f"SOURCE: {link}:2", {_norm(real)})
        self.assertTrue(checks[0].ok, "a symlink alias must resolve to the real embedded path")

    # --- M8: numbering and counting use the same splitter ------------------
    def test_formfeed_line_count_matches_numbering(self):
        p = os.path.join(self.dir, "ff.py")
        # splitlines() treats \x0c (form feed) as a break -> 4 lines; the OLD
        # verifier counted only \n -> 3, so a cite to line 4 wrongly failed.
        with open(p, "w", encoding="utf-8") as f:
            f.write("a\nb\x0cc\nd")
        checks = verify_sources(f"SOURCE: {p}:4", {_norm(p)})
        self.assertTrue(checks[0].ok, "last splitlines() line must verify OK")

    # --- H2 / L8: gather_code contract -------------------------------------
    def test_gather_code_returns_embedded_set(self):
        a = self._mk("a.py", 10)
        b = self._mk("b.py", 10)
        text, embedded = gather_code([a, b], max_lines=5)  # b is over budget
        self.assertIn(_norm(a), embedded)
        self.assertNotIn(_norm(b), embedded)
        self.assertIn("TRUNCATED", text)

    def test_gather_code_dedups_paths(self):
        a = self._mk("a.py", 3)
        text, embedded = gather_code([a, a], max_lines=6000)
        self.assertEqual(text.count("// FILE:"), 1, "a duplicate -f must not embed twice")
        self.assertEqual(len(embedded), 1)

    # --- clean-audit token --------------------------------------------------
    def test_clean_audit_token_must_be_whole_answer(self):
        # A clean audit is EXACTLY the sentinel; the token buried in other prose
        # (or alongside a fabricated claim) must NOT count — else it re-opens a
        # false-COMPLETE path (the exact bypass the review caught).
        self.assertTrue(has_clean_audit_token("NO_FINDINGS"))
        self.assertTrue(has_clean_audit_token("  NO_FINDINGS\n"))
        self.assertFalse(has_clean_audit_token("summary\nNO_FINDINGS\n"))
        self.assertFalse(has_clean_audit_token("NO_FINDINGS\nbut this uncited claim should not pass"))
        self.assertFalse(has_clean_audit_token("there are no findings here"))
        self.assertFalse(has_clean_audit_token("NO_FINDINGS_YET is not it"))

    def test_mentions_no_findings_detects_standalone_line(self):
        self.assertTrue(mentions_no_findings("finding\nNO_FINDINGS\nmore"))
        self.assertTrue(mentions_no_findings("NO_FINDINGS"))
        self.assertFalse(mentions_no_findings("NO_FINDINGS_YET"))
        self.assertFalse(mentions_no_findings("no findings at all"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
