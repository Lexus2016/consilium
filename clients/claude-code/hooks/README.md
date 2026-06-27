# Proactive consult hook (Claude Code, optional)

`consult-nudge.sh` is a **non-blocking** Claude Code `PreToolUse(Bash)` hook that
reminds the agent to get an independent second opinion (`consult`) at two moments:

- **Branch 1 — hard-to-reverse action:** about to run `git push` / `merge` / `rebase`,
  a DB migration (`alembic`, `flyway`, `prisma migrate`, `db:migrate`, `artisan migrate`),
  or `terraform apply` / `kubectl apply` → nudges to consult the *decision* first.
- **Branch 2 — committing finished CODE:** on `git commit`, if a source file is staged
  (`.py`, `.ts`, `.go`, `.rs`, `.sh`, `.sql`, …) → nudges a *finished-work audit*
  (`git diff | consult --panel … --review`). Doc-only / nothing-staged commits stay
  silent, so it fires on real code, not every commit.

It **never blocks** a command and stays silent unless a branch matches. It does not
duplicate destructive ops you already hard-deny in `settings.json`. Requires `jq`
(preferred) or `python3` (fallback).

## Enable it (two manual steps — by design)

We do **not** auto-edit your `~/.claude/settings.json`: a malformed merge silently
disables *all* your settings, so wiring the hook is left to you.

1. Copy the script and make it executable:

   ```sh
   mkdir -p ~/.claude/hooks
   cp clients/claude-code/hooks/consult-nudge.sh ~/.claude/hooks/
   chmod +x ~/.claude/hooks/consult-nudge.sh
   ```

2. Add this entry to the `PreToolUse` array in `~/.claude/settings.json`
   (**merge** into the existing array — do not replace it):

   ```json
   {
     "matcher": "Bash",
     "hooks": [
       { "type": "command", "command": "bash ~/.claude/hooks/consult-nudge.sh", "timeout": 5 }
     ]
   }
   ```

Open `/hooks` once (or restart) so the running session picks it up; new sessions load
it automatically. Tune the trigger patterns directly in the script — e.g. drop
`git push` if it fires too often, or narrow the staged-code extensions.
