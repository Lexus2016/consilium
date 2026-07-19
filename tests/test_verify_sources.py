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

    def test_build_question_is_adversarial_cites_and_has_no_subagent_line(self):
        from council.orchestrator import build_question, AUDIT_PREAMBLE, NO_FINDINGS_TOKEN
        q = build_question("    1\tsome code", "find bugs")
        self.assertIn(AUDIT_PREAMBLE, q)          # adversarial framing is present
        self.assertIn("ADVERSARIAL", q)
        self.assertIn("find bugs", q)             # the caller's question
        self.assertIn("SOURCE:", q)               # the citation rule (anti-hallucination guard)
        self.assertIn(NO_FINDINGS_TOKEN, q)       # the clean-audit token rule
        self.assertIn("some code", q)             # the embedded code
        # must NOT tell headless advisors to spawn subagents / explore (tool-loop hang)
        self.assertNotIn("subagent", q.lower())

    # --- M1: markdown-formatted citations must not evade the verifier ----------
    def test_markdown_prefixed_source_is_checked_not_invisible(self):
        p = self._mk("a.py", 10)
        for prefix in ("- ", "* ", "> ", "1. ", "1) ", "**"):
            checks = verify_sources(f"{prefix}SOURCE: /nope/ghost.py:9999", {_norm(p)})
            self.assertEqual(len(checks), 1, f"{prefix!r}SOURCE must be checked, not ignored")
            self.assertFalse(checks[0].ok)
            self.assertIn("not in audited set", checks[0].reason)

    def test_valid_bulleted_citation_verifies_ok(self):
        p = self._mk("a.py", 10)
        checks = verify_sources(f"- SOURCE: {p}:3", {_norm(p)})
        self.assertEqual(len(checks), 1)
        self.assertTrue(checks[0].ok)

    def test_bold_wrapped_citation_verifies_ok(self):
        # `**SOURCE:** p:3` (bold label) and a fully-bold `**SOURCE: p:3**` are valid
        # citations; the wrapping markdown must not flag them (regression caught in
        # the pre-release panel review).
        p = self._mk("a.py", 10)
        for form in (f"**SOURCE:** {p}:3", f"**SOURCE: {p}:3**"):
            checks = verify_sources(form, {_norm(p)})
            self.assertEqual(len(checks), 1, f"{form!r} must parse to one check")
            self.assertTrue(checks[0].ok, f"{form!r} is a valid citation, not malformed")
            self.assertEqual(checks[0].line, 3)

    def test_lowercase_source_in_prose_is_not_a_citation(self):
        # A lowercase 'source:' is prose, not the mandated uppercase citation; matching
        # it would falsely flag ordinary sentences as malformed citations.
        p = self._mk("a.py", 10)
        self.assertEqual(verify_sources("source: the auth module looks fine", {_norm(p)}), [])

    # --- L: trailing punctuation must not falsely flag a valid citation --------
    def test_trailing_punctuation_does_not_falsely_flag(self):
        p = self._mk("a.py", 10)
        for suffix in (".", ")", ",", ";"):
            checks = verify_sources(f"SOURCE: {p}:3{suffix}", {_norm(p)})
            self.assertEqual(len(checks), 1)
            self.assertTrue(checks[0].ok, f"trailing {suffix!r} must not flag a valid citation")
            self.assertEqual(checks[0].line, 3)

    # --- M2: a NUL byte in a citation path must be flagged, not crash the audit -
    def test_nul_byte_in_citation_is_flagged_not_crashing(self):
        p = self._mk("a.py", 10)
        checks = verify_sources("SOURCE: /evil\x00.py:3", {_norm(p)})
        self.assertEqual(len(checks), 1)
        self.assertFalse(checks[0].ok)
        self.assertIn("unparseable path", checks[0].reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
