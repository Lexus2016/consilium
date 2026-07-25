# consilium-setup Bootstrap Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a `consilium-setup` bootstrap skill (install / update / verify / repair consilium) that `install.sh --clients` syncs into agents' skill directories.

**Architecture:** One new SKILL.md under `clients/bootstrap/consilium-setup/` — a thin state machine over existing commands (`install.sh --clients`, `consult --list`), no duplicated install logic. `install.sh` gains a guarded copy loop into `~/.agents/skills/` and `~/.claude/skills/`. `clients/README.md` gains one short section.

**Tech Stack:** Markdown (SKILL.md format), POSIX-ish bash (`install.sh`), no new dependencies.

**Spec:** `docs/superpowers/specs/2026-07-25-consilium-setup-skill-design.md`

## Global Constraints

- The skill is **thin**: it delegates all real work to `./install.sh --clients` and `consult --list`; it never duplicates manual install steps from `README.md`.
- The skill's boundary: it ends at a verified working install. Day-to-day *use* of `consult` belongs to `consult-peer` — say so explicitly in the skill.
- `install.sh` must **never create** an agent's skills root (`~/.agents/skills`, `~/.claude/skills`); it copies only into roots that already exist, else prints a skip message — same pattern as the existing `consult-peer` sync.
- No changes to `bin/consult`. No sync of `consult-peer` into `~/.agents/skills` (out of scope).
- The repo has no shell test harness; `install.sh` changes are verified by exact manual runs in a temporary `HOME` with expected output (steps below).
- Language: skill and docs are in English, matching the repo.

---

### Task 1: Create the `consilium-setup` skill

**Files:**
- Create: `clients/bootstrap/consilium-setup/SKILL.md`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `clients/bootstrap/consilium-setup/SKILL.md` — the path Task 2's installer sync copies from (`setup_src="$repo_dir/clients/bootstrap/consilium-setup"`).

- [ ] **Step 1: Write the skill file**

Create `clients/bootstrap/consilium-setup/SKILL.md` with exactly this content:

```markdown
---
name: consilium-setup
description: Install, update, verify, or repair consilium — the `consult` command that lets one AI agent ask a DIFFERENT AI for a second opinion. Covers cloning the repo, running install.sh, PATH fixes, advisor sign-in problems, and python3/council availability. NOT for getting a second opinion itself — that is the consult-peer skill.
---

# consilium-setup

consilium adds a `consult` command that lets your agent phone a *different* AI
for a second opinion. This skill gets `consult` installed, updated, and verified
on a machine. Using `consult` day-to-day is the `consult-peer` skill's job —
stop here once the install is verified.

Repo: https://github.com/Lexus2016/consilium

## 1. Check current state

```sh
command -v consult && consult --list
```

- `consult` not found → **Fresh install**.
- Found, and the user asked to update or re-sync → **Update**.
- Found but something is broken → **Diagnostics**.

## 2. Fresh install

If the user already has a clone of the repo, use it instead of re-cloning.

```sh
git clone https://github.com/Lexus2016/consilium
cd consilium
./install.sh --clients
```

`install.sh` symlinks `bin/consult` into `~/.local/bin` (override with
`CONSILIUM_BIN`); `--clients` also syncs the hub instruction block into the
user's agents and copies the consilium skills into their skill directories.

Read the installer's output. If it warns that the bin dir is not on PATH, fix
that (see **Diagnostics**) before calling the install done.

Native Windows: there is no shell installer — use WSL / Git Bash for
`./install.sh`, or wire `bin/consult.ps1` into the user's PowerShell profile as
`clients/README.md` describes.

## 3. Update

From the existing clone:

```sh
git pull && ./install.sh --clients
```

## 4. Verify

```sh
consult --list
```

It must list **at least two** agents — consilium only makes sense with one
agent that asks and a *different* one that answers. Two caveats to tell the
user:

- `--list` checks *installation* only, not sign-in — a listed advisor may still
  need a login in its own CLI.
- `consult council` (multi-agent audit) needs `python3`; core `consult` works
  without it.

Done. From here, how to *use* `consult` is the `consult-peer` skill.

## 5. Diagnostics

| Symptom | Action |
|---|---|
| `consult: command not found` after install | The bin dir is not on PATH. Add `export PATH="$HOME/.local/bin:$PATH"` (or `"$CONSILIUM_BIN"`) to the user's shell profile, then open a fresh shell and re-verify. |
| `install.sh: ... refusing to overwrite` | An unrelated `consult` occupies the target. Remove it by hand or set `CONSILIUM_BIN` to a different bin dir, then re-run `./install.sh --clients`. |
| `consult council` unavailable | Install `python3`. Also: `--copy` installs never include the council — symlink-install (`./install.sh`) or run it from the repo checkout. |
| Advisor listed, but calls fail with auth errors | Sign in to that advisor's own CLI; `consult --list` cannot check sign-in. |
| Native Windows | No shell installer: WSL/Git Bash, or `bin/consult.ps1` per `clients/README.md`. |

Never edit agents' global instruction files (`AGENTS.md`, `GEMINI.md`) by hand —
that is `install.sh --clients`'s job. For anything beyond setup, point at the
repo docs: `docs/usage.md` and `docs/consulting-guide.md`.
```

- [ ] **Step 2: Verify the file and its front matter**

Run: `head -5 clients/bootstrap/consilium-setup/SKILL.md`
Expected output starts with:

```
---
name: consilium-setup
description: Install, update, verify, or repair consilium
```

Also confirm no tab characters in front matter (YAML forbids them):
Run: `grep -P '\t' clients/bootstrap/consilium-setup/SKILL.md || echo "no tabs"`
Expected: `no tabs`

- [ ] **Step 3: Commit**

```bash
git add clients/bootstrap/consilium-setup/SKILL.md
git commit -m "feat: add consilium-setup bootstrap skill"
```

---

### Task 2: Sync the skill from `install.sh --clients`

**Files:**
- Modify: `install.sh` (the `--clients` section, after the existing `consult-peer` skill copy, currently lines 201–209)

**Interfaces:**
- Consumes: `clients/bootstrap/consilium-setup/SKILL.md` from Task 1.
- Produces: on machines with `~/.agents/skills` or `~/.claude/skills`, a synced `$skills_root/consilium-setup/SKILL.md` and an echoed `skill synced:` / `skip consilium-setup (...)` line.

- [ ] **Step 1: Run the pre-change verification (shows the gap)**

Run:

```bash
tmp=$(mktemp -d)
mkdir -p "$tmp/.agents/skills" "$tmp/.claude/skills"
HOME="$tmp" CONSILIUM_BIN="$tmp/bin" ./install.sh --clients
ls "$tmp/.agents/skills" "$tmp/.claude/skills"
echo "$tmp"
```

Expected: both skill dirs are **empty** (no `consilium-setup/` yet) — this is
the gap the change closes. Keep the printed `$tmp` path for Step 3.

- [ ] **Step 2: Add the sync block to `install.sh`**

In `install.sh`, immediately after the existing block

```sh
  skill_src="$repo_dir/clients/claude-code/consult-peer/SKILL.md"
  skill_dir="$HOME/.claude/skills/consult-peer"
  if [ -d "$HOME/.claude/skills" ] && [ -f "$skill_src" ]; then
    mkdir -p "$skill_dir"
    cp "$skill_src" "$skill_dir/SKILL.md"
    echo "  skill synced:  $skill_dir/SKILL.md"
  else
    echo "  skip skill (~/.claude/skills not present)"
  fi
```

insert:

```sh

  # consilium-setup bootstrap skill: sync into every skills root the user
  # already has (~/.agents/skills for Kimi Code and compatible agents,
  # ~/.claude/skills for Claude Code). Never creates an agent's skills root —
  # only copies into one that already exists.
  setup_src="$repo_dir/clients/bootstrap/consilium-setup"
  for skills_root in "$HOME/.agents/skills" "$HOME/.claude/skills"; do
    if [ -d "$skills_root" ] && [ -f "$setup_src/SKILL.md" ]; then
      mkdir -p "$skills_root/consilium-setup"
      cp "$setup_src/SKILL.md" "$skills_root/consilium-setup/SKILL.md"
      echo "  skill synced:  $skills_root/consilium-setup/SKILL.md"
    else
      echo "  skip consilium-setup ($skills_root not present or skill missing)"
    fi
  done
```

- [ ] **Step 3: Verify — roots present**

Run (same `$tmp` from Step 1, or make a fresh one the same way):

```bash
tmp=$(mktemp -d)
mkdir -p "$tmp/.agents/skills" "$tmp/.claude/skills"
HOME="$tmp" CONSILIUM_BIN="$tmp/bin" ./install.sh --clients
diff "$tmp/.agents/skills/consilium-setup/SKILL.md" clients/bootstrap/consilium-setup/SKILL.md && echo AGENTS-OK
diff "$tmp/.claude/skills/consilium-setup/SKILL.md" clients/bootstrap/consilium-setup/SKILL.md && echo CLAUDE-OK
```

Expected: installer output contains two `skill synced:  .../consilium-setup/SKILL.md`
lines, and the two `diff` runs print `AGENTS-OK` and `CLAUDE-OK`.

- [ ] **Step 4: Verify — roots absent (no creation, clean skip)**

Run:

```bash
tmp2=$(mktemp -d)
HOME="$tmp2" CONSILIUM_BIN="$tmp2/bin" ./install.sh --clients
ls -A "$tmp2"
```

Expected: output contains a `skip consilium-setup (<tmp2>/.agents/skills not present or skill missing)`
line (with `<tmp2>` expanded to the real path), **no** `.agents` or `.claude` directories were created
under `$tmp2` (`ls -A` shows only `bin`), and the installer still exits 0.

- [ ] **Step 5: Commit**

```bash
git add install.sh
git commit -m "feat: sync consilium-setup skill in install.sh --clients"
```

---

### Task 3: Document the skill in `clients/README.md`

**Files:**
- Modify: `clients/README.md` (append a section after the final `## Hub instruction block` section, i.e. at end of file)

**Interfaces:**
- Consumes: Tasks 1–2 (describes behavior they shipped).
- Produces: user-facing documentation of the new skill.

- [ ] **Step 1: Append the section**

Append to `clients/README.md`:

```markdown
---

## The consilium-setup skill (install / update / repair)

[`bootstrap/consilium-setup/`](bootstrap/consilium-setup/) is a
[SKILL.md](bootstrap/consilium-setup/SKILL.md)-format skill that teaches an
agent how to **install, update, verify, and repair** consilium itself — as
opposed to `consult-peer`, which covers day-to-day *use* of `consult`.

`./install.sh --clients` copies it into `~/.agents/skills/` (Kimi Code and
compatible agents) and `~/.claude/skills/` (Claude Code) when those directories
already exist. Hand it to any agent that supports the SKILL.md format when you
want consilium set up on a new machine — the agent clones, installs, syncs the
hub block, and verifies with `consult --list` on its own.
```

- [ ] **Step 2: Verify the relative links resolve**

Run:

```bash
cd clients && ls bootstrap/consilium-setup/SKILL.md && cd ..
```

Expected: the path prints, no "No such file or directory".

- [ ] **Step 3: Commit**

```bash
git add clients/README.md
git commit -m "docs: document consilium-setup skill in clients/README"
```

---

### Task 4: Acceptance walkthrough

**Files:**
- None (verification only).

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: confirmation the whole flow works end to end.

- [ ] **Step 1: Full clean-HOME run**

Run:

```bash
tmp=$(mktemp -d)
mkdir -p "$tmp/.agents/skills"
HOME="$tmp" CONSILIUM_BIN="$tmp/bin" ./install.sh --clients
PATH="$tmp/bin:$PATH" consult --list
```

Expected: installer ends with `try: consult --list`; `consult --list` runs and
prints the advisor table (which advisors are listed depends on the host — any
output that is not "command not found" passes). `consilium-setup/SKILL.md`
exists under `$tmp/.agents/skills/`.

- [ ] **Step 2: Update path (idempotent re-run)**

Run the same `HOME="$tmp" ... ./install.sh --clients` command again.
Expected: exits 0, re-syncs the skill without errors (this is the
`git pull && ./install.sh --clients` update path, minus the pull).

- [ ] **Step 3: Clean up temp dirs**

```bash
rm -rf "$tmp" "$tmp2" 2>/dev/null || true
```

(Only the `mktemp -d` directories created by this plan — nothing else.)

- [ ] **Step 4: Report**

Summarize to the user: skill created, installer syncs it, docs updated, both
verification runs green. Suggest the real-world acceptance test — in a fresh
agent session with the skill present, ask "install consilium" and watch the
agent reach a verified `consult --list` without hints.
