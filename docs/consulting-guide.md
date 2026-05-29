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

## Pick an independent advisor

The value comes from *independence*, so consult an agent that is **not the same
model family as you**. A second instance of yourself mostly agrees with itself.

| Advisor | Provider | Good for |
|---|---|---|
| `claude` | Anthropic | reasoning about design, code review, careful analysis |
| `codex` | OpenAI | code-heavy questions, alternative implementation takes |
| `opencode` | model-agnostic (your configured model) | a third independent voice |
| `agy` | Google (Gemini) | another provider's perspective |

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
- Strip secrets from any context file before you pass it. The advisor is another
  process, possibly another provider.

## Hub instruction block

This is the compact version to drop into a client's instruction file (`AGENTS.md`,
`GEMINI.md`, a Claude skill, etc.). Keep it in sync with the rules above.

```text
You can consult a peer AI for a second opinion with the `consult` command:

    consult <agent> [--context FILE] [--code DIR] -- "<question>"

agents: claude | agy | opencode | codex  (pick a different provider than yourself)

Consult when you are stuck after repeated attempts, before a hard-to-reverse
decision, or to get a blind-spot check on a plan. Write the relevant context to a
temp file and pass it with --context; ask one sharp question. The advisor only
returns text — it never edits files. Read its reply as advice, then decide. Set
CONSILIUM_TIMEOUT to bound the call. Run `consult --list` to see installed agents.
```
