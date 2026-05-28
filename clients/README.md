# Wiring consilium into your agent (hub setup)

`consult` works the moment it is on your `PATH` (see [`../README.md`](../README.md)
for install). This directory tells each agent how to set itself up as a *hub* —
how to teach itself *when and how* to consult a peer — using that agent's own
mechanism.

Every agent needs the same two steps:

1. **Install the command** — `./install.sh` from the repo root (on native
   Windows, see [Windows](#windows) below). After this, `consult --list` works in
   any shell.
2. **Install the guidance** — store the **Hub instruction block** (bottom of this
   file, canonical copy in [`../docs/consulting-guide.md`](../docs/consulting-guide.md))
   where your agent reads its instructions, so it reaches for `consult` on its own.

The guidance is identical everywhere; only its location differs per agent. The
full playbook (when to consult, how to build context, how to read the reply) is
[`../docs/consulting-guide.md`](../docs/consulting-guide.md).

---

## Claude Code

**Install the skill** into your skills directory:

```sh
cp -r clients/claude-code/consult-peer ~/.claude/skills/
```

(or into a project's `.claude/skills/`). Start a new session so it is discovered.

**Use.** Work normally. When you are stuck or facing a hard-to-reverse decision,
the `consult-peer` skill prompts Claude to run `consult <agent> -- "..."`. You can
also ask explicitly: *"get a second opinion from codex on this plan."*

---

## Codex

Codex reads `AGENTS.md`.

**Install.** Append the Hub instruction block to `~/.codex/AGENTS.md` (global) or
a project-level `AGENTS.md`.

**Use.** Ask Codex to sanity-check something; it runs `consult <agent> -- "..."`
as a shell command and folds the reply back in. Pick a non-OpenAI advisor
(`claude` or `agy`) for an independent view.

---

## OpenCode

OpenCode reads `AGENTS.md`.

**Install.** Append the Hub instruction block to `~/.config/opencode/AGENTS.md`
(global) or a project `AGENTS.md`. Optionally define a dedicated consulting agent
with `opencode agent`.

**Use.** Ask OpenCode to consult a peer; it runs `consult` as a shell command.

---

## Antigravity (`agy`)

`agy` is Gemini-based and reads `GEMINI.md`.

**Install.** Append the Hub instruction block to `~/.gemini/GEMINI.md`, or add a
custom command under `~/.gemini/commands/`. `agy` can also import a Claude/Gemini
plugin via `agy plugin import` if you package the skill that way — but the
instruction-file path above is the simplest and does not depend on a plugin
format.

**Use.** Ask `agy` to get a second opinion; it runs `consult` as a shell command.

---

## Windows

There is no shell installer for native Windows yet. Two options:

- **WSL or Git Bash** — `./install.sh` works there just like on macOS/Linux.
- **Native PowerShell 7+** — use `bin/consult.ps1`. Add the repo's `bin` folder to
  your `PATH`, or put this in your PowerShell profile:

  ```powershell
  function consult { pwsh -NoProfile -File C:\path\to\consilium\bin\consult.ps1 @args }
  ```

---

## Hub instruction block

Paste this into the file named for your agent above. Canonical copy:
[`../docs/consulting-guide.md`](../docs/consulting-guide.md).

```text
You can consult a peer AI for a second opinion with the `consult` command:

    consult <agent> [--context FILE] [--code DIR] -- "<question>"

agents: claude | agy | opencode | codex  (pick a different provider than yourself)

Consult when you are stuck after repeated attempts, before a hard-to-reverse
decision, or to get a blind-spot check on a plan. Write the relevant context to a
temp file and pass it with --context; ask one sharp question. The advisor only
returns text — it never edits files. Read its reply as advice, then decide. Set
CONSILIUM_TIMEOUT to bound the call. Run `consult --list` to see installed agents.
```
