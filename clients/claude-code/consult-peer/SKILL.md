---
name: consult-peer
description: Use regularly during work for an independent second opinion from a DIFFERENT AI provider — when stuck after repeated tries, before a hard-to-reverse decision (schema/API/security/release), for a blind-spot check on a plan or a diff, and to VERIFY a finished task against what was asked (advisors hunt for mismatches and return PASS/FAIL). Supports asking several advisors in parallel (`--panel`) and piping a diff straight in. A habit, not a last resort. Runs via the `consult` command from the consilium project.
---

# consult-peer

You can ask a different AI agent for a second opinion with the `consult` command
(from the [consilium](https://github.com/Lexus2016/consilium) project). The other
agent advises in text — it doesn't act on your files. You read its reply and decide.

Treat this as a **regular working habit, not a last resort.** A different model,
trained differently and with no stake in your answer, is the cheapest way to catch
the mistakes you can't see in your own work. Reach for it across the whole task,
not just when you're stuck.

## When to reach for this

- **While building** — you're unsure, or you've tried the same thing 2+ times and
  it still fails, or you just want a review of a diff or function before moving on.
- **Before deciding** — the next step is hard to reverse: a migration, an API
  contract, a security boundary, a release. Pressure-test it first.
- **Checking a plan or design** — a blind-spot check before you commit to it.
- **After finishing a task** — verify the result against what was actually asked,
  before you call it done. This is the highest-value moment: an independent
  reviewer catches "works, but not what was requested" and bugs you wrote minutes
  ago and can no longer see.

Skip it only for trivial, easily-reversible steps — a second opinion there is noise.

## How to consult

1. **Pick an independent advisor.** Consult a *different provider* than yourself.
   You are Claude, so prefer a different provider — e.g. `codex`, `agy`, or
   `hermes`; run `consult --list` for the full set. A second Claude mostly
   agrees with itself.

2. **Build a sharp question.** The advisor has none of your conversation.
   - Write the relevant slice to a temp file and pass `--context FILE`, or pipe
     it in (`git diff | consult …`) — piped text is shown to the advisor under
     `## Input`. Keep it tight: the function and its callers, the plan, the diff.
   - For a repo question, pass `--code .` so the advisor reads the tree read-only.
   - Ask one specific question, not "review this".

   ```sh
   consult codex --context /tmp/plan.md -- "Does this migration lose data if it runs twice?"
   git diff | consult agy -- "Spot bugs in these changes"
   ```

3. **Ask several at once, and verify finished work.**
   - `--panel a,b,c` fans the question out to several advisors **in parallel**.
     They answer independently (never seeing each other — that independence is the
     value; debate just makes models anchor and agree). You read all replies and
     synthesize.
   - `--review` swaps in an adversarial preamble: the advisor is told to find
     where the RESULT fails the TASK and to end with `VERDICT: PASS`/`FAIL`. Use it
     to check finished work against its spec.

   ```sh
   consult --panel codex,agy,opencode -- "Is this lock ordering deadlock-free?"
   git diff | consult --panel codex,agy --review -- "Task: add rate limiting to the login route"
   ```

4. **Read the reply as advice, not orders.** It is one opinion.
   - If it disagrees, decide on the merits — do not apply a fix you cannot justify.
   - If it agrees, that is signal, not proof; two models can share a blind spot.
   - All edits stay with you. The transcript is saved under `~/.consilium/log/`.

## The council — for high-stakes code audits

One advisor gives a second opinion; the **council** runs a whole panel for an
audit you must get right. `consult council` embeds the code as text, fans it to
several agents on different providers, synthesizes one answer, and **verifies
every finding against its `file:line`** — a fabricated or out-of-range citation is
flagged, so hallucinated findings don't slip through.

```sh
consult council -f src/auth.js -q "find security bugs and race conditions"
consult council -f a.js -f b.js -q "is this retry logic correct"
```

It is **expensive** (a multi-agent run takes minutes and several paid calls), so
reserve it for questions that earn it: a subtle bug, migration safety, a security
boundary. Read the `SOURCE VERIFICATION` block — apply only `[OK]` findings;
`[BAD]` is a hallucinated citation. The council never edits files; you apply the
fixes. Needs `python3` (the core `consult` stays a zero-dependency shell tool).

## Safety

The advisor is meant to advise, not act: codex runs hard-sandboxed under
`--sandbox read-only`, while the others answer without editing unless you grant
permission, and consilium never passes them permission-skipping flags. Strip
secrets from any context file or piped input before passing it — the advisor is
another process, often another provider. Bound a call with `CONSILIUM_TIMEOUT`.

The full playbook lives in the project's `docs/consulting-guide.md`.
