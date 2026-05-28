# consilium — architecture & design

> Single source of truth for the project. Read this first when resuming work.

## Purpose

`consilium` is a **cross-agent consultation bus** for AI coding CLIs. It lets
one agent (the *hub*) ask another agent (the *advisor*) a question in headless
mode, capture the answer as text, and continue working. Symmetric by design:
each agent can be hub or advisor.

Goal: any user can install it into any of the supported clients and immediately
start consulting the others.

## The agents (verified locally)

| Agent | Version | Headless call | Continue session | Plugins |
|---|---|---|---|---|
| `claude` (Claude Code) | — | `claude -p "Q"` | `claude -c -p` | skills |
| `agy` (Antigravity) | 1.0.2 | `agy -p "Q"` | `agy -c -p` / `--conversation ID` | `agy plugin` |
| `opencode` | 1.15.10 | `opencode run "Q"` | `opencode run -c` / `-s ID` | `opencode plugin`, MCP, ACP |
| `codex` (OpenAI) | 0.134.0 | `codex exec "Q"` | `codex resume --last` | `codex plugin`, can be MCP server |

Shared extras: `--add-dir` / `-C` (give a working dir as context), `-m`/`--model`,
sandbox / approval controls (codex: `--sandbox read-only -a never`).

## Architecture — 3 layers

**Layer 0 — common primitive (already exists).** Every agent has a
"prompt in → text out" headless mode. This is the foundation; nothing to build.

**Layer 1 — the universal adapter: `consult`.** One interface over all four
agents. Because it is just a shell command, *any* agent can call it — that is
what makes the system symmetric without any daemons. Two implementations share
one CLI grammar and dispatch table:
- `bin/consult` — bash (macOS bash 3.2+, Linux, and Windows via WSL/Git Bash),
  installed to `~/.local/bin`.
- `bin/consult.ps1` — native PowerShell port (pwsh 7+) for Windows cmd/PowerShell
  where bash is absent.

**Layer 2 — per-client ergonomic wrappers.**
- Claude Code → a **skill** (`consult-peer`): when to seek a second opinion,
  how to build context (via `cheap extract` to a temp file), how to analyze the
  reply and continue.
- `agy` → a **plugin** exposing a `/consult` command.
- `opencode` → a **plugin** or agent definition.
- `codex` → a **plugin** or config instruction + shell tool.

A deeper Phase-2 path exists via **MCP** (codex can *be* an MCP server, opencode
manages MCP/ACP). More structured but heavier. The CLI adapter is the universal
base because it is the only thing all four share with zero extra processes.

## `consult` command spec (to implement)

```
consult <agent> [options] -- <question...>
consult <agent> [options] "<question>"

agents:  claude | agy | opencode | codex
options:
  --context FILE   inline a context file into the prompt
  --code DIR       give the agent a working directory for code context
  --model NAME     override the model
  --continue       continue the agent's previous session
  --raw            send the question as-is (no advisor preamble)
  --no-log         do not write a transcript
  --list           list agents + whether installed
  -h, --help / --version
env:
  CONSILIUM_LOG_DIR   transcript dir (default ~/.consilium/log)
  CONSILIUM_TIMEOUT   per-call timeout if `timeout`/`gtimeout` present
```

**Dispatch table:**

| agent | command built |
|---|---|
| claude | `claude -p [-c] [--model M] [--add-dir DIR] "<prompt>"` |
| agy | `agy -p [-c] [--add-dir DIR] "<prompt>"` |
| opencode | `opencode run [-c] [-m M] "<prompt>"` |
| codex | `codex exec --sandbox read-only [-m M] [-C DIR] "<prompt>"` |

**Prompt assembly (unless `--raw`):** advisor preamble + optional `## Context`
(file contents) + `## Question`. Preamble instructs the advisor: *"You are a peer
AI advisor consulted by another agent. Give honest, direct analysis. Advice only
— do not modify, create, or delete files."*

**Behavior:** answer printed to stdout; a transcript (prompt + answer) saved to
`~/.consilium/log/<ts>-<agent>.md` unless `--no-log`. The bash adapter targets
macOS bash 3.2 (avoid empty-array expansion under `set -u`) and stays portable to
Linux/WSL/Git Bash. The PowerShell port targets pwsh 7+ and implements the
timeout natively (no external `timeout`/`gtimeout`). Both close the advisor's
stdin to avoid TTY hangs — codex reads stdin in addition to its prompt arg.

## Safety defaults

A consultant **advises, never acts**. Read-only by default (codex
`--sandbox read-only`; never pass `--dangerously-skip-permissions`). All file
edits stay with the hub. The advisor preamble reinforces this in-prompt.

## Decisions log

- **Name:** project `consilium`, command `consult` (like ripgrep → rg). Latin
  "council/consultation"; neutral across EN/UK/RU; not generic-AI-sounding.
- **Read-only consultants** by default (safety).
- **Local-first:** build & verify locally; GitHub remote is a later, confirmed
  step (name/visibility to confirm before push).
- **Memory scoping:** `tqmemory` keys memory by cwd. Project memory must be
  written from a session whose cwd is this directory, so it stays separate from
  other projects. Do not write consilium notes from unrelated cwds.
- **Cross-platform target (Windows / Linux / macOS):** the bash adapter covers
  macOS / Linux / WSL / Git Bash; a native PowerShell port (`bin/consult.ps1`,
  pwsh 7+) covers Windows cmd/PowerShell. Two implementations, one shared CLI
  grammar and dispatch table — kept in sync by hand.

## Roadmap

1. Scaffold local project (done: dir, git, README, LICENSE, .gitignore, docs).
2. Implement `bin/consult` (the universal adapter).
3. Verify a live cross-agent call (trivial question + timeout; record who is
   authenticated / working).
4. Claude Code skill `consult-peer`.
5. Multilingual docs (README EN/UK/RU) + real-world examples.
6. Per-client adapters (agy / opencode / codex plugins) for full symmetry.
7. `install.sh` + publish to GitHub.

## Resuming in a fresh session

1. Open a Claude Code session with **this directory as cwd**
   (`/Users/admin/_Projects/consilium`).
2. First actions: read this file; run `tqmemory semantic_search` (now scoped to
   consilium); `index_paths` if not indexed.
3. Next task: implement `bin/consult` per the spec above, then run a live test.
