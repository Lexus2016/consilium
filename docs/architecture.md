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

**Layer 2 — per-client ergonomic wrappers** (verified mechanisms; see `clients/`).
All share one playbook (`docs/consulting-guide.md`); each agent stores it where it
reads instructions:
- Claude Code → a **skill** (`clients/claude-code/consult-peer`): when to seek a
  second opinion, how to build context, how to read the reply. Built.
- `codex` → the **Hub instruction block** in `~/.codex/AGENTS.md` (codex reads
  `AGENTS.md`). A codex plugin / MCP server is a heavier alternative.
- `opencode` → the block in `~/.config/opencode/AGENTS.md`, or an `opencode agent`.
- `agy` → the block in `~/.gemini/GEMINI.md` (agy is Gemini-based), or a command
  under `~/.gemini/commands/`, or `agy plugin import` of a Claude/Gemini plugin.

A deeper Phase-2 path exists via **MCP** (codex can *be* an MCP server, opencode
manages MCP/ACP). More structured but heavier. The CLI adapter is the universal
base because it is the only thing all four share with zero extra processes.

## `consult` command spec

```
consult <agent> [options] -- <question...>
consult <agent> [options] "<question>"
consult --panel <a,b,c> [options] -- <question...>
<command> | consult <agent> [options] -- <question...>

agents:  claude | agy | hermes | opencode | codex
options:
  --panel LIST     fan the question out to several advisors in parallel; print
                   all answers back-to-back (independent, never a debate)
  --context FILE   inline a context file into the prompt
  --code DIR       give the agent a working directory for code context
  --model NAME     override the model
  --continue       continue the agent's previous session
  --review         swap in an adversarial review preamble (RESULT vs TASK,
                   ends with VERDICT: PASS/FAIL)
  --raw            send the question as-is (no advisor preamble)
  --no-log         do not write a transcript
  --list           list agents + whether installed
  -h, --help / --version
stdin:  piped input is appended to the prompt under `## Input`; the advisor's own
        stdin is closed (only the hub reads the pipe). Read only from a real pipe
        or redirected file, never a bare/empty stdin (would hang on EOF).
env:
  CONSILIUM_LOG_DIR   transcript dir (default ~/.consilium/log)
  CONSILIUM_TIMEOUT   per-call timeout if `timeout`/`gtimeout` present
  CONSILIUM_MAX_DEPTH consultation-chain depth limit (default 3; loop guard)
  CONSILIUM_LOG_KEEP  keep only the newest N transcripts (default 200; 0 = all)
```

**Panel** (`--panel a,b,c`) is a thin orchestration layer, not a new transport:
the hub re-invokes `consult` once per advisor in parallel (bash: backgrounded
self-calls + `wait`; PowerShell: child `pwsh -File` processes), each reusing the
full single-advisor dispatch/timeout/logging path and writing its own transcript.
Answers print under `===== <agent> =====` separators. Advisors are **independent**
— none sees another's reply — and the hub synthesizes. This is a deliberate star
topology, not a debate mesh: letting advisors see each other anchors them into a
confident-but-not-better consensus, the exact false signal a verification tool
must avoid. Children inherit `CONSILIUM_CALL_DEPTH+1`, so the loop guard still
bounds any onward consulting; unknown/uninstalled names are warned and skipped,
duplicates collapsed.

**Dispatch table:**

| agent | command built |
|---|---|
| claude | `claude -p [-c] [--model M] [--add-dir DIR] "<prompt>"` |
| agy | `agy -p [-c] [--add-dir DIR] "<prompt>"` |
| hermes | `hermes chat [--model M] [-c] -q "<prompt>"` (no `--add-dir`) |
| opencode | `opencode run [-c] [-m M] "<prompt>"` |
| codex | `codex exec --sandbox read-only [-m M] [-C DIR] "<prompt>"` |

**Prompt assembly (unless `--raw`):** advisor preamble + optional `## Context`
(file contents) + optional `## Input` (piped stdin) + `## Question`. The default
preamble instructs the advisor: *"You are a peer AI advisor consulted by another
agent. Give honest, direct analysis. Advice only — do not modify, create, or
delete files."* With `--review`, that preamble is replaced by an adversarial one:
the advisor is told to find where the RESULT (the `## Input`/`--code` material)
fails the TASK (the question + `## Context`), not to "assess quality" (which
invites a rubber stamp), and to end with `VERDICT: PASS`/`VERDICT: FAIL`. `--raw`
sends the question verbatim and ignores `--review`.

**Behavior:** answer printed to stdout; a transcript (prompt + answer) saved to
`~/.consilium/log/<ts>-<agent>-<pid>.md` unless `--no-log` (the PID suffix avoids
same-second filename collisions). The advisor is spawned in the hub's working
directory, so it shares cwd-scoped context: `tqmemory` keys memory by cwd, and
project `AGENTS.md`/`GEMINI.md`/`CLAUDE.md` resolve from there. The PowerShell port
sets the child's working directory explicitly, since .NET's `CurrentDirectory`
does not track `$PWD`. The bash adapter targets
macOS bash 3.2 (avoid empty-array expansion under `set -u`) and stays portable to
Linux/WSL/Git Bash. The PowerShell port targets pwsh 7+ and implements the
timeout natively (no external `timeout`/`gtimeout`). Both close the advisor's
stdin to avoid TTY hangs — codex reads stdin in addition to its prompt arg.

## Safety defaults

A consultant **advises, never acts** — but how strongly that is *enforced*
differs per agent, so be honest about it:

| Agent | What keeps it from editing files |
|---|---|
| codex | enforced: runs under `--sandbox read-only` |
| claude | does not edit in `-p` answer mode without granted permission |
| agy | does not edit in `-p` answer mode without granted permission (its `--sandbox` flag stalls headless calls, so we don't pass it) |
| opencode | no read-only flag exists; relies on its default behaviour + the preamble |

Guaranteed for all four: consilium never passes
`--dangerously-skip-permissions` (or any equivalent), and the advisor preamble
tells the advisor to advise only — do not create, modify, or delete files. All
real edits stay with the hub.

To stop runaway `A -> B -> A` consultation loops, each call increments
`CONSILIUM_CALL_DEPTH` in the advisor's environment and aborts (exit 3) once it
reaches `CONSILIUM_MAX_DEPTH` (default 3).

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
- **Hardening from the first dogfood (we consulted `agy` about consilium):** a
  recursion depth guard (`CONSILIUM_CALL_DEPTH` / `CONSILIUM_MAX_DEPTH`),
  PID-suffixed transcript names, and spawning the advisor in the hub's working
  directory so cwd-scoped context (notably `tqmemory`) is shared. Rejected from
  the same review: `--map` / code-stripping (those belong to the hub building
  context at Layer 2, not the transport) and dropping `--model`/`--continue`
  (cheap, useful pass-throughs).
- **Panel + pipe + review (multi-advisor feedback), from a dogfood design review
  (`agy` + `opencode`, two independent non-Claude advisors, both consulted via
  consilium itself):** add `--panel` (parallel independent fan-out), stdin →
  `## Input`, and `--review` (adversarial PASS/FAIL preamble). Explicitly
  **rejected: advisor-vs-advisor debate** (advisors seeing and rebutting each
  other). Both reviewers converged: debate destroys the independence that is the
  tool's entire value (anchoring/sycophancy → confident-but-wrong consensus) and
  opens a prompt-injection propagation path (A's injected output becomes B's
  context). The chosen shape keeps the star topology — independent advisors fan
  out, the hub synthesizes — and stays "just a shell command": `--panel` is a thin
  self-re-invoking layer, `--review` is only a preamble swap, stdin is read once
  in the hub. Also rejected: a stateful "collaboration mode" / `--synthesize`
  transport step (a second synthesis pass is just another plain `consult`, so it
  needs no new flag or state).

## Roadmap

1. ~~Scaffold local project.~~ Done.
2. ~~`bin/consult` (the universal adapter)~~ + a native PowerShell port
   (`bin/consult.ps1`). Done.
3. ~~Verify a live cross-agent call.~~ Done (codex, opencode, agy).
4. ~~Claude Code skill `consult-peer`~~ + per-agent hub setup (`clients/`). Done.
5. ~~Multilingual docs (README EN/UK/RU) + real-world examples.~~ Done.
6. ~~Per-client hub setup via each tool's instruction file~~ (skill / `AGENTS.md`
   / `GEMINI.md`). Done. Native plugins remain optional.
7. ~~`install.sh` (Unix) + publish to GitHub.~~ Done. A native Windows installer
   and a tagged release remain.
8. Open: minimal tests for both adapters; `install.ps1` for Windows.

## Resuming in a fresh session

1. Open a Claude Code session with **this directory as cwd**
   (`/Users/admin/_Projects/consilium`).
2. First actions: read this file; run `tqmemory semantic_search` (now scoped to
   consilium); `index_paths` if not indexed.
3. Next task: implement `bin/consult` per the spec above, then run a live test.
