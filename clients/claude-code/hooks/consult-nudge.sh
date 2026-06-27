#!/usr/bin/env bash
# consult-nudge — non-blocking PreToolUse(Bash) reminders to get an independent
# second opinion (consilium `consult`) at two moments. NEVER blocks; stays silent
# unless a branch matches. Destructive ops are already hard-DENIED in
# ~/.claude/settings.json, so this does not duplicate them.
#
#   Branch 1 — about to run an allowed-but-hard-to-reverse command
#              (git push/merge/rebase, DB migrations, infra apply): nudge to
#              consult the underlying DECISION first.
#   Branch 2 — about to `git commit` CODE (not docs): nudge a finished-work AUDIT
#              with `--review` before sealing it. Doc-only / nothing-staged commits
#              stay silent, so the nudge fires on real code, not every commit.
set -euo pipefail

cmd=""
if command -v jq >/dev/null 2>&1; then
  cmd=$(jq -r '.tool_input.command // ""' 2>/dev/null || true)
elif command -v python3 >/dev/null 2>&1; then
  cmd=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null || true)
fi
# If neither jq nor python3 is available we cannot parse the hook input;
# stay silent and non-blocking rather than emitting a malformed context.

# Branch 1: hard-to-reverse action.
if printf '%s' "$cmd" | grep -qiE 'git (push|merge|rebase)|alembic (upgrade|downgrade)|flyway (migrate|clean)|prisma migrate|db:migrate|artisan migrate|terraform apply|kubectl apply'; then
  jq -nc '{hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:"This step is hard to reverse. If you have NOT already gotten an independent second opinion on the underlying decision, run `consult <agent>` with a tight question (pick a DIFFERENT provider; `consult --list` for the roster), or a `--panel` cross-check, BEFORE proceeding. Skip only if this is routine, trivially reversible, or already reviewed."}}'
  exit 0
fi

# Branch 2: committing CODE -> nudge a finished-work audit. Skip when only docs /
# nothing is staged, so this does not fire on every commit.
if printf '%s' "$cmd" | grep -qiE 'git commit'; then
  staged=$(git diff --cached --name-only 2>/dev/null || true)
  if printf '%s' "$staged" | grep -qiE '\.(py|ts|tsx|js|jsx|mjs|cjs|go|rs|rb|java|kt|swift|c|h|cc|cpp|hpp|cs|php|scala|sh|bash|zsh|sql)$'; then
    jq -nc '{hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:"You are about to commit CODE. If this is a substantial change and you have NOT verified it against what was asked, pipe the diff to `consult --panel <a,b> --review` with a one-line Task statement (advisors return VERDICT: PASS/FAIL plus the mismatches) BEFORE sealing it. Skip for trivial or obvious changes."}}'
  fi
  exit 0
fi

exit 0
