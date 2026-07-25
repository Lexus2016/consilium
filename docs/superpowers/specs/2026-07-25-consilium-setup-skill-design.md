# consilium-setup bootstrap skill — design

Date: 2026-07-25
Status: approved approach (option 1), pending spec review

## Problem

consilium already ships a *usage* skill (`clients/claude-code/consult-peer/SKILL.md`)
that teaches an agent when and how to ask a peer AI for a second opinion. It assumes
`consult` is already installed. What is missing is a *bootstrap* skill: a
self-contained playbook an agent can be handed so it can install consilium from
scratch, update it, verify the install, and diagnose common problems — without
improvising from `README.md` + `clients/README.md`.

Today an agent told "install consilium" usually copes, but non-deterministically:
it may skip `--clients`, forget the PATH check, or skip verification.

## Decisions (from brainstorming)

- **Scenario:** a new, separate bootstrap skill. `consult-peer` stays the daily-usage
  skill; the two do not overlap.
- **Distribution:** the skill lives in the repo and `install.sh --clients` copies it
  into the skill directories of agents that support the SKILL.md format
  (`~/.agents/skills/` for Kimi Code and compatible agents, `~/.claude/skills/` for
  Claude Code) — same pattern as the existing Claude skill sync.
- **Scope:** full lifecycle — fresh install, update, verification, diagnostics of
  common problems. Usage guidance stays out (that is `consult-peer`'s job).

## Non-goals

- No changes to `bin/consult` (a `--doctor` flag was considered and deferred; may be
  added later if prose diagnostics prove fragile).
- No sync of `consult-peer` into `~/.agents/skills/` (out of scope; can be a
  follow-up).
- No Windows-native installer work (skill documents the existing WSL/Git Bash and
  `consult.ps1` paths as-is).
- No automated tests for the skill markdown itself.

## Design

### New file: `clients/bootstrap/consilium-setup/SKILL.md`

Front matter:

- `name: consilium-setup`
- `description:` triggers on install / update / repair / "set up consilium" requests
  — explicitly *not* on "get a second opinion" (that is `consult-peer`). The
  description must mention: install consilium, update it, verify, troubleshoot PATH
  / sign-in / python3-council issues.

Body — a state machine, thin over existing commands (no duplicated manual steps;
`install.sh` remains the single source of truth for installation):

1. **Check current state.** `command -v consult`, then `consult --list`. If `consult`
   is missing → install. If present → check whether the user asked for update or
   repair.
2. **Fresh install.** Clone `https://github.com/Lexus2016/consilium` (respect an
   existing clone if the user points at one) → run `./install.sh --clients` →
   verify `consult` is on PATH (installer prints a PATH warning; act on it).
3. **Update.** From the clone: `git pull && ./install.sh --clients`.
4. **Verify.** `consult --list` must show ≥2 agents; remind that *installed* ≠
   *signed in* — a listed agent may still need a login, and the skill cannot check
   that. `consult council` needs `python3`; core `consult` works without it.
5. **Diagnostics.** Symptom → action table:
   - `consult: command not found` after install → PATH missing the bin dir; add
     `export PATH="$HOME/.local/bin:$PATH"` (or `$CONSILIUM_BIN`) to the shell
     profile, open a fresh shell.
   - `install.sh: refusing to overwrite` → an unrelated `consult` sits at the
     target; remove it or set `CONSILIUM_BIN`.
   - Council unavailable → install `python3`; note `--copy` installs never get the
     council (symlink install or run from the repo checkout).
   - Advisor listed but errors on auth → sign in to that advisor's own CLI;
     `consult --list` checks installation only.
   - Native Windows → no shell installer; use WSL/Git Bash or wire
     `bin/consult.ps1` per `clients/README.md`.
6. **Boundary.** One closing line: how to *use* `consult` day-to-day is the
   `consult-peer` skill's job; this skill ends at a verified working install.

Style: short imperative steps, copy-pasteable commands, no duplicated prose from
`README.md` — reference the repo docs (`docs/usage.md`, `docs/consulting-guide.md`)
instead of restating them.

### Modified: `install.sh`

In the `--clients` section, next to the existing Claude skill copy, add a guarded
copy of the new skill:

- If `~/.agents/skills/` exists → copy `clients/bootstrap/consilium-setup/` to
  `~/.agents/skills/consilium-setup/`, echo `skill synced: ...`.
- Also copy it to `~/.claude/skills/consilium-setup/` under the existing
  `~/.claude/skills` guard (same `if [ -d ... ]` pattern already used there).
- Missing target dirs are skipped with a message, exactly like the current
  `consult-peer` sync — the installer never creates an agent's skills root.

### Modified: `clients/README.md`

One short section: what `consilium-setup` is, when an agent picks it up
(install/update/repair vs. daily use), and that `./install.sh --clients` syncs it.

## Error handling / edge cases

- Installer must not create `~/.agents/skills` or `~/.claude/skills` if absent
  (matches existing behavior — only touches environments the user already has).
- Skill must handle "user already has a clone somewhere" — prefer it over
  re-cloning.
- Skill must not instruct the agent to edit global instruction files by hand; that
  is `install.sh --clients`'s job.

## Testing

- No automated tests for the markdown skill.
- `install.sh` change: manual run in a temporary `HOME` with and without
  `~/.agents/skills` / `~/.claude/skills` present; verify copy happens iff the
  target root exists, and that output messages are correct.
- Acceptance walkthrough: in a fresh agent session, ask "install consilium" with
  the skill loaded → agent reaches a verified `consult --list` without human
  hints.
