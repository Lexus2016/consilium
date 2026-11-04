# consilium

**English** · [Українська](README.uk.md) · [Русский](README.ru.md)

**Get a second opinion from the coding agents already installed on your machine.**

`consult` is a local CLI for one advisor, an independent panel, or a code-audit
council. It uses the agents' existing sign-ins and model settings.

[Install](#install-it-just-ask-your-ai) · [Usage](docs/usage.md) · [Contribute](CONTRIBUTING.md) · [Report a bug](https://github.com/Lexus2016/consilium/issues/new/choose)

## What this is, in one breath

There's a kind of AI that lives in your terminal and writes code *with* you — it
reads your files, edits them, runs commands. Claude Code, Codex, Gemini's `agy`,
and OpenCode are all this kind of tool. People call them coding assistants, or
just "agents."

They're good. But like anyone working alone, an agent can't always tell when it's
wrong. It will talk itself into a risky change, miss a bug it wrote two minutes
ago, and keep retrying the same broken fix long after it should have stopped.

**consilium adds one command, `consult`, that lets your agent phone a _different_
AI for a second opinion.** Your agent hands the same code or question to a model
from another company and asks: *what do you think?* The other AI reads it and
answers in plain text. It advises; it doesn't act for you.

```
consult codex -- "Is it safe to run this migration twice?"
```

You — or your agent — type that. A different AI reads the question, looks at the
code in your current folder, and prints back what it thinks. You decide what to do
with the answer.

> Still early, but I reach for it most days.

## Why ask a *different* AI, and not just ask the same one again

Think of it like checking your own homework. Re-read your own answer and you see
what you *meant* to write, not what's actually on the page. Hand it to someone from
a different class — who studied from different notes and has no reason to agree
with you — and they spot the mistake in five seconds.

A separate review can reveal assumptions the first pass missed. Using another
model or provider may give you a different perspective, but it does not guarantee
independence, disagreement or correctness. Verify advice against the original code
and tests.

So the rule is short: **ask someone other than the AI you're already working
with.**

## Who you can ask

Run `consult --list` to see which of these are installed on your machine (it checks
installation only, not sign-in). Type the name in the left column; the reply comes
from the model on the right.

| You type   | Reply comes from               | Built by      |
|------------|--------------------------------|---------------|
| `claude`   | Claude                         | Anthropic     |
| `codex`    | GPT                            | OpenAI        |
| `agy`      | Gemini                         | Google        |
| `opencode` | OpenCode (the model you set)   | open source   |
| `hermes`   | Hermes                         | Nous Research |
| `grok`     | Grok                           | xAI           |
| `pi`       | Pi (the model you set)         | pi.dev        |
| `cursor`   | Cursor (the model you set)     | Cursor        |
| `kilo`     | Kilo Code (the model you set)  | Kilo          |
| `cline`    | Cline (the model you set)      | Cline         |
| `goose`    | Goose (the model you set)      | Block         |
| `kimi`     | Kimi                           | Moonshot AI   |

Choose the actual model and provider deliberately. Different CLI names can still
use the same underlying model; `consult --list` does not prove provider diversity.

## When a second opinion is worth it

A second read pays off in moments like these.

You're about to run a database migration and you're not sure it's safe if it runs
twice. Ask before you hit enter, not after.

A retry loop passes every test and still falls over in production once a day.
Another model reads the back-off logic and spots the off-by-one you'd stopped
noticing.

You and your assistant have spent an hour on one bug, each fix breaking the last.
Time to bring in a model that wasn't there for the first fifty-nine minutes.

The auth check looks right. But you wrote it, so of course it does. Send it to a
different model and ask the one question that counts: can this be bypassed?

Release is minutes away and something about backwards compatibility nags at you,
though you can't name it yet. Two minutes now is cheaper than a rollback at
midnight.

## What you need first

For a direct `consult <agent>` call, you need that advisor CLI installed and
signed in. To have one coding agent ask another, install and sign in to both.
Agent-assisted use does not require a separate consilium API key.

The shell launcher targets macOS, Linux, WSL and Git Bash. The optional council
requires Python 3.10+. Native PowerShell has a separate `bin/consult.ps1` launcher;
see [usage](docs/usage.md).

## Install it (just ask your AI)

Paste this to your assistant (Claude Code, Codex, OpenCode, or Antigravity):

> Install consilium from https://github.com/Lexus2016/consilium for me: clone it,
> run its `install.sh`, and set yourself up to ask other AIs for a second opinion
> the way its `clients/README.md` describes.

That's it. You only need the assistants you actually plan to ask.

Prefer to do it by hand? Clone and inspect the installer, then install the CLI:

```sh
git clone https://github.com/Lexus2016/consilium.git
cd consilium
./install.sh
export PATH="$HOME/.local/bin:$PATH"  # default install location, current shell
consult --help
consult --list
```

The default installation symlinks to this checkout, so keep it in place.
`--list` checks installed executables, not authentication or live model access.

To opt into agent integration, review [clients/README.md](clients/README.md), then
run `./install.sh --clients`. This also writes managed instructions and skills to
supported agent directories. A fresh agent session may be needed to load them.

For updates, review the incoming changes, run `git pull --ff-only` from this
checkout, and rerun the installer with the same options you chose initially.
Real consultations send context to the selected provider and can incur charges.

## Use it — three ways

**Your agent does it on its own.** Once it knows about `consult` (the consult-peer
skill, or the hub block in `AGENTS.md` / `GEMINI.md`), it offers a second opinion by itself
when it's stuck or about to do something hard to undo. You read the result and
decide.

**You ask for it in plain words.** This is the one you'll use most:

> "Before we continue, get a second opinion from codex on this."

> "Ask another AI whether this change is safe."

> "I'm stuck. Check this with agy."

Your agent gathers the context, runs `consult`, shows you the reply next to its own
read, and says whether it agrees. What happens next is your call.

**You run it yourself.** `consult` is an ordinary command — who you're asking, then
the question:

```
consult codex -- "Is it safe to do it this way?"
```

**Three handy shortcuts.** Ask several advisors at once, hand work straight in, or
have a finished result checked against the task:

```
consult --panel codex,agy -- "Is this migration safe to run twice?"
git diff | consult codex -- "Review these changes for bugs"
git diff | consult --panel codex,agy --review -- "Task: add rate limiting to login"
```

`--panel` asks several advisors **in parallel and independently** — they don't see
each other's answers (that's the point; you weigh them yourself). A pipe hands your
work in as the thing to look at. `--review` asks them to hunt for where a finished
result doesn't match the task and to end with a clear **PASS or FAIL** — handy right
before you call something done.

## When one opinion isn't enough — the council

`consult <agent>` gives you one second opinion. For a high-stakes **code audit**,
`consult council` runs a whole panel: several agents on different providers each
audit the code independently, a separate agent reconciles them into one answer, and
each emitted `SOURCE:` citation is **checked against the files and line ranges
actually supplied to the panel**. Unknown paths, omitted files, invalid line ranges
and malformed citations are flagged. A valid location does not prove the finding
is correct, and this check does not catch every hallucination. ("Different
providers" means different CLI front-ends, not guaranteed-different models: two
Claude-backed CLIs — or `hermes` and `kimi` both routed to Moonshot — still count as
diverse, so pick advisors you know run on different models.)

**You ask for it in plain words** — the agent convenes the council itself:

> "This touches auth — convene the council before I merge."

> "Have a panel of different AIs audit this migration for data loss."

> "I keep flip-flopping on this lock ordering — put it to the council."

**Or run it yourself** — one or more files, then the question:

```
consult council -f src/auth.js -q "find security bugs and race conditions"
consult council -f a.js -f b.js -q "is this retry logic correct"
```

It's **expensive** — a multi-agent run takes minutes and several paid calls — so
save it for questions that earn it: a subtle bug, migration safety, a security
boundary. It returns located, verified findings; you apply them (it never edits
files). It ends with a single `COUNCIL STATUS: COMPLETE | INCOMPLETE` line — and a matching exit code — so your assistant sees at a glance whether to act on the answer or come back with a follow-up. The council needs `python3`; the core `consult` stays a zero-dependency
shell tool, so this is opt-in.

## Where this fits

consilium is useful when you want to choose your advisors, inspect their separate
answers and keep edits in your main workflow. It does not automatically choose the
cheapest model, guarantee different providers, or establish that a finding is true.
The CLI runs locally; the selected advisors can still send your context to remote
model providers. Their normal billing and data-handling policies apply.

## Good to know

- The other AI advises, it doesn't act — and since v0.8.0 that is *enforced* by a
  real mechanism per advisor, not just asked for in the prompt. `codex` is
  hard-sandboxed (`--sandbox read-only`), `cursor` runs its read-only `ask` mode,
  `opencode` its read-only `plan` agent, `hermes` gets a toolset list with no file
  or terminal tools, `grok` gets explicit deny rules, `claude` a consilium-owned
  deny list; `agy`'s tools are auto-denied headless. All seven were checked by
  asking them outright to create a file, with the "advice only" preamble removed —
  none did. `pi`, `kilo`, `cline` and `kimi` have not been checked that way, so
  keep sensitive files out of their working folder. consilium's *own* flags never
  grant permissions — but `--raw` sends your question to the advisor verbatim and
  `--model` forwards its value as a token (a value beginning with `-` is
  rejected), so those two are your responsibility. Either way, your edits stay yours.
- The assistants you want to ask have to be installed and signed in first.
  `consult --list` shows which are *installed* — it can't check sign-in, so a listed
  agent may still need a login.
- Every consult saves a transcript (the full prompt + the answer) to
  `~/.consilium/log/`, kept owner-private (files `chmod 600`); the newest 200 are
  retained.
- It runs in your current project folder, so your code is already in front of it.
- Every call is a real request to another model, so save it for the things that
  matter, not trivia.
- Don't put passwords or keys in the question.
- Anything passed through `--context` or a pipe is inlined into the prompt, and the
  prompt is passed to the advisor as a command-line argument. On a multi-user host
  this text can show up in `ps` / `/proc` listings. Strip secrets from context files
  and diffs, not just from the question itself.

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) covers offline checks and the boundaries of live
advisor tests. Use the [issue forms](https://github.com/Lexus2016/consilium/issues/new/choose)
for reproducible bugs and focused feature requests. Remove credentials, proprietary
code and session content before sharing logs.

## Read more

- Real situations, in plain language: [`docs/examples.md`](docs/examples.md)
- A short guide for you: [`docs/usage.md`](docs/usage.md)
- The playbook your assistant follows: [`docs/consulting-guide.md`](docs/consulting-guide.md)
- How it's built, if you're curious: [`docs/architecture.md`](docs/architecture.md)

## License

[MIT](LICENSE)
