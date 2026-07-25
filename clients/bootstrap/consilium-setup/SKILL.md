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
- Not found, but the user believes consilium is already installed → almost
  certainly a PATH problem, not a missing install — go to **Diagnostics**;
  don't re-clone over an existing install.
- Found, and the user asked to update or re-sync → **Update**.
- Found but something is broken → **Diagnostics**.

## 2. Fresh install

Look for an existing clone first. On a symlink install,
`readlink "$(command -v consult)"` prints `<repo>/bin/consult`, so the repo is
two dirs up from that — or the user may just tell you where it is. If you find
a clone, `cd` into it and `git pull`, then skip to the `install.sh` line below.

No clone anywhere: clone *outside* the user's project, not into their working
directory —

```sh
git clone https://github.com/Lexus2016/consilium ~/consilium   # unless the user picked a location
cd ~/consilium
```

If the target dir already holds a clone, `cd` into it and `git pull` instead of
cloning. If it exists but is not a git clone of consilium (no `.git`, or a
different project), pick a different directory — never `git pull` a stranger's
folder. Then, either way:

```sh
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

Find the clone first. On a symlink install:

```sh
readlink "$(command -v consult)"   # prints <repo>/bin/consult — the repo is two dirs up
```

If the user knows where the clone is, use that instead. Then:

```sh
cd <repo> && git pull && ./install.sh --clients
```

If `readlink` shows `consult` is *not* a symlink into a repo, the install used
`--copy` — keep it a copy, don't let the update silently turn it into a
symlink: from the clone, `git pull && ./install.sh --copy --clients` instead.
(The council stays unavailable under `--copy` — see **Diagnostics**.)

No clone to be found (`--copy` install, or the repo was deleted) → fall back to
**Fresh install** above.

## 4. Verify

```sh
consult --list | grep -c installed
```

Must print **2 or more** — count only the `installed` rows, because `--list`
also prints `not found` rows for agents that aren't there. consilium only makes
sense with one agent that asks and a *different* one that answers. Two caveats
to tell the user:

- `--list` checks *installation* only, not sign-in — a listed advisor may still
  need a login in its own CLI.
- `consult council` (multi-agent audit) needs `python3`; core `consult` works
  without it.

Done. From here, how to *use* `consult` is the `consult-peer` skill.

## 5. Diagnostics

| Symptom | Action |
|---|---|
| `consult: command not found` after install | The bin dir is not on PATH. Add `export PATH="$HOME/.local/bin:$PATH"` to the user's shell profile — write the *resolved* directory (the actual `CONSILIUM_BIN` value if one was set), never the literal `$CONSILIUM_BIN`. Then run the same `export` in your current shell (or call `consult` by full path) and re-verify right away; the profile line covers future shells. If a custom `CONSILIUM_BIN` was used and its value is forgotten: the installer prints the bin dir it used in its `installed: <dir>/consult` line at install time, and the shell profile may already carry a `CONSILIUM_BIN` line — check both. |
| `install.sh: ... refusing to overwrite` | An unrelated `consult` occupies the target. Remove it by hand or set `CONSILIUM_BIN` to a different bin dir, then re-run `./install.sh --clients`. |
| `consult council` unavailable | Install `python3`. Also: `--copy` installs never include the council — symlink-install (`./install.sh`) or run it from the repo checkout. |
| Advisor listed, but calls fail with auth errors | Sign in to that advisor's own CLI; `consult --list` cannot check sign-in. |
| Native Windows | No shell installer: WSL/Git Bash, or `bin/consult.ps1` per `clients/README.md`. |

Don't hand-write or hand-maintain the hub block in agents' global instruction
files (`AGENTS.md`, `GEMINI.md`) — keeping it current is `install.sh
--clients`'s job. But if the installer prints a WARN about unbalanced,
out-of-order, or legacy markers, follow its own advice: fix or remove the
markers by hand, then re-run. For anything beyond setup, point at the repo
docs: `docs/usage.md` and `docs/consulting-guide.md`.
