"""M3: cross-provider diversity is DISCLOSED as best-effort, not hardcoded.

A panel whose members' real provider the map cannot pin (a model-agnostic front-end,
or an agent whose configured model varies like `hermes`) must carry a note saying
independence is best-effort — instead of silently claiming distinct providers, or
hardcoding a merge the CLI does not actually pin.

    python3 -m unittest tests.test_roster
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from council.config import Profile  # noqa: E402
from council.roster import resolve_roster  # noqa: E402


def _policy():
    return Profile(name="p", recipe="parallel", code_access=False, panel_size=3)


class RosterDiscloses(unittest.TestCase):
    def test_panel_with_unverifiable_provider_agent_is_disclosed(self):
        # hermes runs a user-configured model, so it may share a provider (e.g.
        # Moonshot) with kimi; the note must SAY independence is best-effort.
        _concrete, single, note = resolve_roster(_policy(), ["codex", "hermes", "kimi"])
        self.assertIsNone(single, "3 agents -> a real council, not single-agent")
        self.assertIn("best-effort", note)
        self.assertIn("hermes", note)

    def test_all_vendor_locked_panel_has_no_caveat(self):
        # codex/agy/grok are vendor-locked CLIs; no unverifiable-provider caveat.
        _concrete, _single, note = resolve_roster(_policy(), ["codex", "agy", "grok"])
        self.assertNotIn("best-effort", note)


if __name__ == "__main__":
    unittest.main(verbosity=2)
