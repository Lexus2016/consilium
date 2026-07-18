# Consulting playbook

> The single source of truth for *how to be a hub*. Client-agnostic, written to be
> read by an agent. Each client wrapper (`clients/`) points back here.

You have a command, `consult`, that asks a different AI agent for a second opinion.
You stay in control: the other agent only returns text. You read it, decide, and
keep working. This file covers when to reach for it and how.

## When to consult

Reach for a second opinion when an independent read is worth more than another lap
on your own:

- You're stuck. Two or more attempts at the same problem have failed.
- The decision is hard to reverse: a schema change, an API contract, a security
  boundary, a release.
- You want a blind-spot check on a plan or design before you commit to it.
- You're reviewing your own output and want eyes that have no stake in it.
- The stakes justify the latency and cost of a second model call.

Don't consult for trivial or easily-reversible steps. A second opinion on
`git status` is just noise.

## A cookbook: 10 concrete triggers

Quick recipes — *when* it fires, the *command shape*, and *what to expect back*. The
advisor only returns text; apply nothing it says without judging it yourself.

1. **Before a DB migration** — `consult --panel agy,codex -- "safe to run twice? where could it lose data?"` → independent idempotency/rollback reads + concrete data-loss risks.
2. **Changing a public API or signature** — `consult codex --code . -- "what breaks in callers; backward-compat path?"` → the break points + a compatibility strategy.
3. **Touching auth / crypto / permissions** — `consult council -f auth.py -q "security bugs and authz gaps"` → findings verified against their `file:line` (hallucinated citations dropped).
4. **Stuck after 2+ failed attempts** — `git diff | consult agy -- "why does this still fail after these attempts?"` → a different hypothesis / the root cause you tunnelled past.
5. **Before push/merge to main** — `git diff | consult --panel codex,agy --review -- "Task: <what you were asked>"` → `VERDICT: PASS/FAIL` + mismatches against the task.
6. **Claiming a task is done** — `consult --panel agy,codex --review -- "Task: <requirements>"` → PASS/FAIL + a ranked list of gaps between result and requirements.
7. **An architecture/design choice with 2+ valid approaches** — `consult --panel agy,codex,hermes --context plan.md -- "blind spots; which approach and why?"` → independent critiques + a recommended approach with rationale.
8. **A deploy or infra `apply`** — `consult codex --context plan.txt -- "risk in this apply; ordering and idempotency?"` → a risk list + a safer sequence.
9. **Reviewing a risky diff or a complex function** — `git diff | consult agy -- "race conditions / edge cases here?"` (escalate to `council` if high-stakes) → concrete bugs + missed edge cases.
10. **Cross-checking a strong claim — yours or one advisor's** — `consult --panel <two different providers> -- "<the claim>"` → where two independent models agree vs disagree, so you synthesize and decide on the merits.

The through-line: every trigger is a **hard-to-reverse or uncertain** step (a decision,
a boundary, a publish, a verification). Skip it for trivial, easily-reversible steps.

## Pick an independent advisor

The value comes from *independence*, so consult an agent that is **not the same
model family as you**. A second instance of yourself mostly agrees with itself.

| Advisor | Provider | Good for |
|---|---|---|
| `claude` | Anthropic | reasoning about design, code review, careful analysis |
| `codex` | OpenAI | code-heavy questions, alternative implementation takes |
| `opencode` | model-agnostic (your configured model) | a third independent voice |
| `agy` | Google (Gemini) | another provider's perspective |
| `hermes` | Nous Research (Hermes) | a self-improving agent's independent take |
| `grok` | xAI (Grok) | another frontier provider's take; can read `--code` |
| `pi` | model-agnostic (provider/model you set) | a configurable extra voice |
| `cursor` | Cursor (your configured model) | an editor-based agent's independent take (edits stay approval-gated) |
| `kilo` | model-agnostic (provider/model you set) | another configurable voice, can read `--code` |
| `cline` | model-agnostic (needs `cline auth`) | a configurable voice, can read `--code` |
| `goose` | model-agnostic (provider/model you set) | Block's agent as an independent voice |
| `kimi` | Moonshot AI (Kimi K2) | another frontier provider's take; can read `--code` |

If you're Claude, prefer `codex` or `agy`. If you're Codex, prefer `claude`.

## Build a sharp question

The advisor has none of your *conversation*, but it runs in your current working
directory, so it already shares your project's cwd-scoped context (the files here,
and the same `tqmemory` project memory if it has that configured). Don't re-explain
the layout. Give it the specific slice it needs, no more:

- Write the relevant slice of context to a temp file and pass `--context FILE`.
  Keep it tight: the relevant function and its callers, not the whole repo.
- For a code question about a project, pass `--code DIR` so the advisor can read
  the tree (read-only).
- Ask one specific question. "Any race conditions in this lock ordering?" beats
  "review this."

```sh
consult codex --context /tmp/plan.md -- "Does this migration lose data if it runs twice?"
consult agy   --code .               -- "Spot the bug in the retry/backoff loop"
```

## Ask several at once, pipe in work, and review

Three shapes for richer feedback — all still "just a shell command", no daemon,
no shared state between advisors.

**Panel — independent voices in parallel.** `--panel` fans the same question out
to several advisors at once. They answer *independently* and never see each
other's replies — that independence is the whole point. You read all the answers
and synthesize. Prefer this over any scheme where advisors debate each other:
debate makes models anchor on the first argument and converge on a
confident-but-not-better consensus, which is exactly the false signal a
verification tool must avoid.

```sh
consult --panel codex,agy,opencode -- "Is this lock ordering deadlock-free?"
```

**Pipe in the material.** Anything you pipe to `consult` is added to the prompt
under `## Input`, so the advisor reviews it directly — no temp file needed.

```sh
git diff | consult codex -- "Review these changes for bugs"
```

**Review mode.** `--review` swaps the preamble for an adversarial one: the advisor
is told to find where the RESULT fails the TASK (not to "assess quality", which
invites a rubber stamp) and to end with `VERDICT: PASS` or `VERDICT: FAIL`. Use it
to check finished work against its spec. Combine all three for an independent,
cross-checked review:

```sh
git diff | consult --panel codex,agy --review -- "Task: add rate limiting to the login route"
```

You stay the moderator: independent advisors fan out, you weigh and synthesize.
Star topology, never a debate mesh.

## The council — when one read isn't enough

For a code audit you must get right, escalate from one advisor to the council:

    consult council -f <file> [-f <file>...] -q "<question>"

It hands the code (as text) to several agents on distinct providers, has each
audit independently, synthesizes one answer, and verifies every finding against
its cited `file:line` — apply only the `[OK]`-verified ones, drop any `[BAD]`
(hallucinated) citation. It is expensive (minutes, several paid calls), so reserve
it for high-stakes questions: a subtle bug, migration safety, a security boundary.
It never edits files; you apply the fixes. Needs `python3` (core `consult` does not).

## Read the reply as advice, not orders

What comes back is one opinion. Weigh it:

- The advisor is meant to **advise, not act**. It returns text, and every edit
  stays with you. (codex is sandboxed read-only; the others answer without editing
  unless you grant permission, and the preamble tells them to advise only.)
- If it disagrees with you, decide on the merits. Don't apply a suggestion you
  can't justify yourself.
- If it agrees, that's signal but not proof. Two models can share a blind spot.

The exchange is saved to `~/.consilium/log/<timestamp>-<agent>-<pid>.md`, so you
can revisit the reasoning later.

## Etiquette

- A consult is a real model call. Bound it: set `CONSILIUM_TIMEOUT` (seconds) so a
  hung advisor can't stall you.
- One well-formed question is worth more than five vague ones.
- Strip secrets from any context file or piped diff before you pass it. The advisor
  is another process, possibly another provider, and the prompt is passed as a
  command-line argument (visible in process listings on multi-user hosts).

## `agy` and `grok` are agentic (occasionally slow / empty)

Both run an internal tool/exploration loop in headless mode, so they are slower
(often 15–60 s, sometimes minutes) and can occasionally end a turn with **no
answer at all** (exit 0, empty output) — agy's read-only `command` tool is
auto-denied by the closed stdin, and grok wanders off exploring. `consult` handles
this for you: it nudges these two to answer from the provided context as text, and
**retries once** on a blank answer (`CONSILIUM_RETRY_EMPTY`, default 1). Still, for
heavy `--code`/`--review` work prefer embedding the slice via `--context` / a pipe,
raise `CONSILIUM_TIMEOUT` (≥300), or reach for a non-agentic advisor
(`claude`/`codex`/`hermes`) when you need a guaranteed, fast reply.

## Hub instruction block

This is the compact block to drop into a client's instruction file (`AGENTS.md`,
`GEMINI.md`, a Claude skill, etc.). The canonical text lives in
[`../clients/hub-block.txt`](../clients/hub-block.txt) and is installed or updated
automatically by `./install.sh --clients` — no manual copy needed.

The block deliberately carries **no agent list**: `consult --list` is the runtime
source of truth, so adding a new advisor never requires re-syncing client blocks.
