---
name: consult-peer
description: Use when stuck after repeated attempts, before a hard-to-reverse decision (schema/API/security/release), or when you want an independent blind-spot check on a plan or your own output — gets a second opinion from a different AI provider via the `consult` command and folds it back into your work.
---

# consult-peer

You can ask a different AI agent for a second opinion with the `consult` command
(from the [consilium](https://github.com/Lexus2016/consilium) project). The other
agent advises in text — it doesn't act on your files. You read its reply and decide.

## When to reach for this

- You have tried the same thing two or more times and it still fails.
- The next step is hard to reverse: a migration, an API contract, a security
  boundary, a release.
- You want a blind-spot check on a plan or design before committing.
- You are reviewing your own output and want eyes with no stake in it.

Skip it for trivial, easily-reversible steps — a second opinion there is noise.

## How to consult

1. **Pick an independent advisor.** Consult a *different provider* than yourself.
   You are Claude, so prefer a different provider — e.g. `codex`, `agy`, or
   `hermes`; run `consult --list` for the full set. A second Claude mostly
   agrees with itself.

2. **Build a sharp question.** The advisor has none of your context.
   - Write the relevant slice to a temp file and pass `--context FILE`. Keep it
     tight: the function and its callers, the plan, the diff — not the whole repo.
   - For a repo question, pass `--code .` so the advisor reads the tree read-only.
   - Ask one specific question, not "review this".

   ```sh
   consult codex --context /tmp/plan.md -- "Does this migration lose data if it runs twice?"
   consult agy   --code .               -- "Spot the bug in the retry/backoff loop"
   ```

   Bound the call with `CONSILIUM_TIMEOUT` (seconds) so a hung advisor cannot
   stall you. Run `consult --list` to see which agents are installed.

3. **Read the reply as advice, not orders.** It is one opinion.
   - If it disagrees, decide on the merits — do not apply a fix you cannot justify.
   - If it agrees, that is signal, not proof; two models can share a blind spot.
   - All edits stay with you. The transcript is saved under `~/.consilium/log/`.

## Safety

The advisor is meant to advise, not act: codex runs hard-sandboxed under
`--sandbox read-only`, while the others answer without editing unless you grant
permission, and consilium never passes them permission-skipping flags. Strip
secrets from any context file before passing it — the advisor is another process,
often another provider.

The full playbook lives in the project's `docs/consulting-guide.md`.
