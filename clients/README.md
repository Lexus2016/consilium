# Wiring consilium into your agent (hub setup)

`consult` works the moment it's on your `PATH` (see [`../README.md`](../README.md)
for install). This folder shows each agent how to set itself up as a *hub*: how to
teach itself when and how to consult a peer, using that agent's own mechanism.

Every agent needs the same two steps.

1. **Install the command.** Run `./install.sh` from the repo root (on native
   Windows, see [Windows](#windows) below). After that, `consult --list` works in
   any shell.
2. **Install the guidance.** Drop the **Hub instruction block** (bottom of this
   file, canonical copy in
   [`../docs/consulting-guide.md`](../docs/consulting-guide.md)) where your agent
   reads its instructions, so it reaches for `consult` on its own.

The guidance is the same everywhere; only its location changes per agent. The full
playbook (when to consult, how to build context, how to read the reply) lives in
[`../docs/consulting-guide.md`](../docs/consulting-guide.md).

---

## Claude Code

**Install the skill** into your skills folder:

```sh
cp -r clients/claude-code/consult-peer ~/.claude/skills/
```

(or into a project's `.claude/skills/`). Start a new session so it's discovered.

**Use it.** Work normally. When you're stuck or facing a decision that's hard to
undo, the `consult-peer` skill nudges Claude to run `consult <agent> -- "..."`. You
can also ask outright: *"get a second opinion from codex on this plan."*

---

## Codex

Codex reads `AGENTS.md`.

**Install.** Append the Hub instruction block to `~/.codex/AGENTS.md` (global) or a
project-level `AGENTS.md`.

**Use it.** Ask Codex to sanity-check something; it runs `consult <agent> -- "..."`
as a shell command and folds the reply back in. Pick a non-OpenAI advisor
(`claude` or `agy`) for an independent view.

---

## OpenCode

OpenCode reads `AGENTS.md`.

**Install.** Append the Hub instruction block to `~/.config/opencode/AGENTS.md`
(global) or a project `AGENTS.md`. You can also define a dedicated consulting agent
with `opencode agent`.

**Use it.** Ask OpenCode to consult a peer; it runs `consult` as a shell command.

---

## Antigravity (`agy`)

`agy` is Gemini-based and reads `GEMINI.md`.

**Install.** Append the Hub instruction block to `~/.gemini/GEMINI.md`, or add a
custom command under `~/.gemini/commands/`. `agy` can also import a Claude/Gemini
plugin via `agy plugin import` if you package the skill that way, though the
instruction-file path above is the simplest and doesn't depend on a plugin format.

**Use it.** Ask `agy` to get a second opinion; it runs `consult` as a shell command.

---

## Hermes (`hermes`)

Hermes (Nous) has no dedicated global dotfile like `~/.codex/AGENTS.md`; it reads a
home-level `~/AGENTS.md` as global user instructions (alongside any project-level
`AGENTS.md`).

**Install.** `./install.sh --clients` seeds `~/AGENTS.md` with the Hub instruction
block when `hermes` is installed, and keeps it in sync on later runs. To do it by
hand, append the block from [`hub-block.txt`](hub-block.txt) to `~/AGENTS.md`.

**Use it.** Ask Hermes to consult a peer; it runs `consult` as a shell command.
Pick a non-Hermes advisor for an independent view.

---

## Windows

No shell installer for native Windows yet. Two options:

- **WSL or Git Bash.** `./install.sh` works there just like on macOS/Linux.
- **Native PowerShell 7+.** Use `bin/consult.ps1`. Add the repo's `bin` folder to
  your `PATH`, or put this in your PowerShell profile:

  ```powershell
  function consult { pwsh -NoProfile -File C:\path\to\consilium\bin\consult.ps1 @args }
  ```

---

## Hub instruction block

The canonical block lives in [`hub-block.txt`](hub-block.txt). The easiest way to
install or update it is:

    ./install.sh --clients

That syncs the block into the agents you already use (codex/opencode/agy), seeds
`~/AGENTS.md` for hermes, and copies the Claude skill. To paste it by hand instead,
copy the contents of
[`hub-block.txt`](hub-block.txt) into your agent's instruction file
(`AGENTS.md`, `GEMINI.md`, …).

The block carries no agent list — `consult --list` is the runtime source of truth.
It also points agents at `consult council` — the multi-agent code-audit mode — for
high-stakes questions (that mode needs `python3`; core `consult` does not).
