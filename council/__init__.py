"""council — a multi-agent code-audit council (reached as `consult council`).

You give it source files + a question; it embeds the code as text, fans the audit
out to several independent coding-agent CLIs (via the `consult` tool) on distinct
providers, a separate synthesizer reconciles their findings into one answer, and
every finding is mechanically verified against its cited file:line.

Positioning (decided after an independent 3-AI review): an explicit, long-running
ADVISORY ORACLE for expensive / high-stakes code questions — not a transparent
drop-in for every step of an agent loop. The consumer applies the findings; the
council never edits files.
"""

__version__ = "0.1.0"
