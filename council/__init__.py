"""quorum — a local OpenAI-compatible endpoint backed by a council of AI agents.

The "model" name a client picks selects a routing POLICY (which panel of agents
and which synthesis recipe), not a real model. The Quorum fans the task out to
several independent coding-agent CLIs (via the `consult` tool), then a separate
synthesizer agent reconciles their answers into one peer-verified reply that is
returned in the normal OpenAI response shape.

Positioning (decided after an independent 3-AI review): this is an explicit,
long-running ADVISORY ORACLE for expensive / high-stakes questions — not a
transparent drop-in for every call of an agent loop.
"""

__version__ = "0.1.0"
