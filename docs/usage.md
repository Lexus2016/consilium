# Using consilium (for people)

> Written for you, not for the AI. How you actually work with a second opinion
> day to day from Claude Code. The version your assistant reads is
> [`consulting-guide.md`](consulting-guide.md).

## Set it up once

```sh
./install.sh                                   # puts `consult` on your PATH
cp -r clients/claude-code/consult-peer ~/.claude/skills/   # install the skill
```

Open a fresh Claude Code session so it picks up the skill, then check the command
is there:

```sh
consult --list        # shows which assistants are installed
```

## Three ways it gets used

**Claude does it on its own.** With the `consult-peer` skill installed, Claude
offers a second opinion by itself when it's stuck, about to do something hard to
undo, or wants a check on its own blind spots. You read the result and decide.

**You ask Claude for it.** This is the one you'll use most. Say it plainly:

- "Before we commit, ask codex to review the auth flow for bugs."
- "Get an independent opinion from agy: can this lock ordering deadlock?"
- "I'm not sure about this approach. Consult opencode and compare."

Claude gathers the context, runs `consult`, shows you the reply next to its own
read, and suggests how to move.

**You run it yourself.** `consult` is an ordinary shell command. Use it in your
terminal whenever you like, no assistant involved:

```sh
consult codex -- "Is a read-only sandbox enough to make a consultant safe?"
```

## How an exchange usually goes

1. You're working with Claude and hit a decision point.
2. Claude consults on its own, or you say "double-check this with codex."
3. Claude writes the relevant context to a temp file and runs
   `consult <agent> --context … -- "question"`. The first time, Claude Code asks
   permission to run the command. You approve it once, or for always.
4. The other AI's answer prints. Claude sums it up and says whether it agrees.
5. You decide: take it, push back, or ask someone else.
6. The whole exchange is saved to `~/.consilium/log/<timestamp>-<agent>-<pid>.md`.

## What the other AI actually sees

It gets none of your Claude conversation. It does run in your current working
directory, so it shares whatever lives there: the project files, and the same
`tqmemory` project memory if that's set up. For the question itself, it works from
what the hub hands it:

```
<fixed preamble: "you are a peer advisor… advice only, don't touch files">

## Context        ← the file you passed with --context, inlined verbatim
<that file's contents>

## Question
<your question>
```

Two ways to feed it:

- `--context FILE` pastes the file's text straight into the prompt. Use it for a
  tight slice: a function and its callers, a plan, a diff, an error log.
- `--code DIR` gives the other AI read-only access to a directory so it can look
  around the repo itself. That directory isn't pasted into the prompt.

The answer is only as good as the slice you hand it. Give it a mess and you'll get
a vague reply back.

## Worth keeping in mind

- **You stay in control.** The other AI returns text and answers without changing
  your files. codex runs read-only, and consilium never lets any advisor skip
  safety checks. Every edit stays between you and Claude.
- **Pick an independent one.** Choose a different provider than Claude, like
  `codex` (OpenAI) or `agy` (Gemini). A second Claude mostly agrees with itself.
- **It costs a real model call** on the other account, so use it for decisions
  that matter, not trivia.
- **Strip secrets** from anything you put in a `--context` file. The other AI is a
  separate process, often a separate provider.
- **Cap slow calls** with `CONSILIUM_TIMEOUT` (in seconds) if an advisor hangs.
