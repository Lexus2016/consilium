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
