# Using consilium as a human (from Claude Code)

> For people. How you actually work with the consultant day to day from inside
> Claude Code. The agent-facing playbook is [`consulting-guide.md`](consulting-guide.md).

## One-time setup

```sh
./install.sh                                   # puts `consult` on your PATH
cp -r clients/claude-code/consult-peer ~/.claude/skills/   # install the skill
```

Start a new Claude Code session so the skill is picked up. Check the command:

```sh
consult --list        # shows which agents are installed
```

## Three ways you use it

**1. Claude decides on its own.** With the `consult-peer` skill installed, Claude
will offer a second opinion by itself when it is stuck, facing a hard-to-reverse
step, or wants a blind-spot check. You just read the result and decide.

**2. You ask Claude (the usual way for you).** Say it in plain language:

- "Before we commit, ask codex to review the auth flow for bugs."
- "Get an independent opinion from agy: can this lock ordering deadlock?"
- "I'm not sure about this approach — consult opencode and compare."

Claude assembles the context, runs `consult`, shows you the reply and its own
take, and proposes how to proceed.

**3. You run it yourself.** `consult` is a normal shell command — use it in your
terminal anytime, with no agent involved:

```sh
consult codex -- "Is a read-only sandbox enough to make a consultant safe?"
```

## What a typical exchange looks like

1. You're working with Claude and reach a decision point.
2. Claude consults on its own, or you say "double-check this with codex."
3. Claude writes the relevant context to a temp file and runs
   `consult <agent> --context … -- "question"`. **The first time, Claude Code asks
   permission to run the command — you approve** (once, or always).
4. The advisor's answer prints; Claude summarises it and says whether it agrees.
5. **You decide:** accept, push back, or ask a different agent.
6. The exchange is saved to `~/.consilium/log/<timestamp>-<agent>-<pid>.md`.

## What the advisor actually sees

The advisor has **none of your Claude conversation**. It does run in your current
working directory, so it shares cwd-scoped context — the project files here, and
the same `tqmemory` project memory if it has that configured. For the specific
question, it decides on what the hub hands it:

```
<fixed preamble: "you are a peer advisor… advice only, don't touch files">

## Context        ← the file you passed with --context, inlined verbatim
<that file's contents>

## Question
<your question>
```

Two ways to feed it:

- `--context FILE` — the file's text is **pasted into** the prompt. Use it for a
  tight slice: the function and its callers, a plan, a diff, an error log.
- `--code DIR` — gives the advisor **read-only access** to a directory so it can
  look around the repo itself (it is not pasted into the prompt).

So the quality of the second opinion depends entirely on how good that slice is.
Garbage in, garbage out.

## Keep in mind

- **You stay in control.** The advisor returns text and answers without changing
  your files — codex is sandboxed read-only, and consilium never lets any advisor
  skip safety checks. Every change stays with you and Claude.
- **Use an independent advisor.** Pick a different provider than Claude — `codex`
  (OpenAI) or `agy` (Gemini). A second Claude mostly agrees with itself.
- **It costs a real model call** on the advisor's account, so use it for decisions
  that matter, not trivia.
- **Strip secrets** from anything you put in a `--context` file — the advisor is
  another process, often another provider.
- **Bound slow calls** with `CONSILIUM_TIMEOUT` (seconds) if an advisor hangs.
