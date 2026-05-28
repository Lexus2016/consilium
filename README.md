# consilium

> Cross-agent consultation bus for AI coding CLIs.

**consilium** lets one AI coding agent — your *hub* — ask a different agent for a
second opinion, mid-task, without you leaving the tool you already work in. The
hub poses a question in headless mode, gets back plain text, and folds the answer
into its work. It is symmetric: Claude Code, Antigravity (`agy`), OpenCode and
Codex can each be the hub *or* the advisor.

The everyday command is `consult`:

```sh
consult codex    -- "Is a read-only sandbox enough to make a consultant safe?"
consult opencode --context design.md -- "Any race conditions in this plan?"
consult claude   --code . -- "Spot bugs in the auth flow"
```

> **Status: early work in progress.** The command interface above is the design
> target, not a shipped feature yet. The single source of truth for the design is
> [`docs/architecture.md`](docs/architecture.md) — read it first when resuming
> work. See [Roadmap](#roadmap) for what exists today.

## Why a second agent

One model has blind spots. It anchors on its first reading of a problem, misses
the edge case it didn't think to look for, and agrees with itself. A second agent
— a different provider, a fresh context, no stake in the first answer — catches
what the first one missed. consilium turns that second opinion into one command
you can run from inside whatever agent you already have open.

This is not a router or an ensemble. The hub stays in charge. The advisor only
talks.

## How it works

Three layers, each thin:

- **Layer 0 — the shared primitive.** Every supported CLI already has a
  "prompt in, text out" headless mode. Nothing to build here; consilium stands on
  top of it.
- **Layer 1 — `consult`, the universal adapter.** A single bash script
  (`bin/consult`, installed to `~/.local/bin`) that puts one interface over all
  four agents. Because it is just a shell command, *any* agent can call it — that
  is what makes the bus symmetric, with no daemon and no background process.
- **Layer 2 — per-client ergonomics.** Optional wrappers that make `consult`
  feel native in each host: a Claude Code skill, an `agy` plugin, an OpenCode
  plugin/agent, a Codex plugin or shell-tool config.

## Supported agents

| Agent | Command | Headless call | Continue a session |
|---|---|---|---|
| Claude Code | `claude` | `claude -p "Q"` | `claude -c -p` |
| Antigravity | `agy` | `agy -p "Q"` | `agy -c -p` |
| OpenCode | `opencode` | `opencode run "Q"` | `opencode run -c` |
| Codex | `codex` | `codex exec "Q"` | `codex resume --last` |

You only need the agents you actually want to consult installed and
authenticated. `consult --list` will show which ones are present.

## The `consult` command

```
consult <agent> [options] -- <question...>
consult <agent> [options] "<question>"

agents:  claude | agy | opencode | codex

options:
  --context FILE   inline a context file into the prompt
  --code DIR       give the advisor a working directory for code context
  --model NAME     override the model
  --continue       continue the advisor's previous session
  --raw            send the question as-is, with no advisor preamble
  --no-log         do not write a transcript
  --list           list agents and whether each is installed
  -h, --help
  --version

env:
  CONSILIUM_LOG_DIR   transcript directory (default: ~/.consilium/log)
  CONSILIUM_TIMEOUT   per-call timeout, if `timeout`/`gtimeout` is available
```

Unless you pass `--raw`, the question is wrapped with a short preamble that tells
the advisor it is a peer being consulted: give honest, direct analysis, and
advise only — do not touch files. The answer prints to stdout and, by default, a
transcript of the exchange is saved under `~/.consilium/log`.

## Safety

A consultant **advises, never acts**:

- Read-only by default. Codex runs under `--sandbox read-only`; consilium never
  passes `--dangerously-skip-permissions` or any equivalent.
- All file edits stay with the hub. The advisor returns text, nothing else.
- The preamble repeats this constraint in-prompt, so the advisor is told not to
  create, modify, or delete files even if it could.

## Roadmap

1. ~~Scaffold the project (repo, README, license, design doc).~~ Done.
2. Implement `bin/consult` — the universal adapter.
3. Verify a live cross-agent call (trivial question, with a timeout).
4. Claude Code skill: `consult-peer`.
5. Multilingual docs (README in EN / UK / RU) and real-world examples.
6. Per-client adapters (`agy` / `opencode` / `codex` plugins) for full symmetry.
7. `install.sh` and a tagged release.

A heavier Phase-2 path via MCP is possible (Codex can *be* an MCP server,
OpenCode manages MCP/ACP). The CLI adapter comes first because it is the one
thing all four agents share with zero extra processes.

## Installation

Not packaged yet — see the roadmap. Once `bin/consult` lands, install will be a
one-liner that drops the script into `~/.local/bin`.

## Contributing

The project is local-first and pre-release; the design may still shift. If you
want to follow along or weigh in, open an issue. Please read
[`docs/architecture.md`](docs/architecture.md) first — it is the source of truth
for scope and decisions.

## License

[MIT](LICENSE)
