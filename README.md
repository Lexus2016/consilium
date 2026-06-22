# consilium

**English** · [Українська](README.uk.md) · [Русский](README.ru.md)

> Let one AI ask a different AI when it isn't sure.

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

An AI has the same blind spot. Ask the same model to "double-check," and it mostly
nods along with itself. Ask a *rival* model from another company — trained
differently, with no stake in the first answer — and it actually pushes back. That
pushback is the whole point. It's where the useful catches come from.

So the rule is short: **ask someone other than the AI you're already working
with.**

## Who you can ask

Run `consult --list` to see which of these are installed and signed in on your
machine. Type the name in the left column; the reply comes from the model on the
right.

| You type   | Reply comes from               | Built by      |
|------------|--------------------------------|---------------|
| `claude`   | Claude                         | Anthropic     |
| `codex`    | GPT                            | OpenAI        |
| `agy`      | Gemini                         | Google        |
| `opencode` | OpenCode (the model you set)   | open source   |
| `hermes`   | Hermes                         | Nous Research |

Pick a row that *isn't* the AI you're already using. A second Claude mostly agrees
with the first.

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

consilium is an add-on, not an app you open on its own. Before it's any use you
need **two terminal coding agents** installed and signed in: one that *asks*, and a
different one that *answers*. Claude Code, Codex, `agy`, and OpenCode all qualify.

Never used a terminal coding agent? Start there first — consilium only makes sense
once you have two of them, because the whole idea is one asking the other.

## Install it (just ask your AI)

Paste this to your assistant (Claude Code, Codex, OpenCode, or Antigravity):

> Install consilium from https://github.com/Lexus2016/consilium for me: clone it,
> run its `install.sh`, and set yourself up to ask other AIs for a second opinion
> the way its `clients/README.md` describes.

That's it. You only need the assistants you actually plan to ask.

Prefer to do it by hand? Two commands:

```sh
./install.sh                                     # puts `consult` on your PATH
cp -r clients/claude-code/consult-peer ~/.claude/skills/   # teach Claude to use it
```

Then open a fresh session and run `consult --list` to confirm it's there. Already
installed? From your clone, `git pull && ./install.sh --clients` pulls the latest
and re-syncs everything.

## Use it — three ways

**Your agent does it on its own.** Once it knows about `consult` (the Claude skill,
or the hub block in `AGENTS.md` / `GEMINI.md`), it offers a second opinion by itself
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
every finding is **mechanically verified against its `file:line`** — a fabricated or
out-of-range citation is flagged, so hallucinations don't slip through.

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

## How it compares — consilium vs Fugu vs OpenRouter Fusion

Fugu and OpenRouter Fusion are hosted services that hide a panel of models behind one
paid endpoint. consilium keeps the panel in **your** hands — local, transparent, and
verifiable, using the AI tools you already have.

| | **consilium** (this project) | **Sakana Fugu** | **OpenRouter Fusion** |
|---|---|---|---|
| What it is | A local CLI for a second opinion from a *different* AI | A hosted orchestrator **model** | A hosted multi-model **API** |
| Where it runs | Your machine, your own signed-in AI CLIs | Vendor cloud, one endpoint | Vendor cloud, one endpoint |
| Models per question | You choose: one, or an independent panel | A pool the model picks (hidden) | 3–5 models in parallel |
| Who synthesizes | **You / your agent** (the hub), with full task context | The trained model, internally | A judge model returns structured analysis; your model writes the final answer |
| Transparency | Open — you can read each advisor's own answer | Hidden machinery; one answer out | Panel answers + a structured judge report |
| Verifies findings against your code | Yes — every finding checked against `file:line` | Internal / unspecified | No |
| Touches your files | Read-only advice; never edits | Text API | Text API |
| Dependencies | Zero-dependency shell core (+ `python3` for the council) | Vendor API | Vendor API (OpenAI-compatible) |
| Cost | Only the model calls you already pay for — no markup | Premium, metered | Sum of every panel call + the judge (~3× a single call) |
| Best for | Code/design review where you stay in control and verify | One-call hidden orchestration | High-stakes research/critique via API |

The short version: Fugu and Fusion sell **convenience** (one endpoint, hidden machinery,
their bill); consilium gives **control** (your machine, your providers, every answer
visible, findings checked against the real code).

## Good to know

- The other AI advises, it doesn't act. codex runs hard-sandboxed read-only; the
  others answer without editing unless you grant permission, and consilium never
  passes them permission-granting flags. Either way, your edits stay yours.
- The assistants you want to ask have to be installed and signed in first. Run
  `consult --list` to see who's ready.
- It runs in your current project folder, so your code is already in front of it.
- Every call is a real request to another model, so save it for the things that
  matter, not trivia.
- Don't put passwords or keys in the question.

## Read more

- Real situations, in plain language: [`docs/examples.md`](docs/examples.md)
- A short guide for you: [`docs/usage.md`](docs/usage.md)
- The playbook your assistant follows: [`docs/consulting-guide.md`](docs/consulting-guide.md)
- How it's built, if you're curious: [`docs/architecture.md`](docs/architecture.md)

## License

[MIT](LICENSE)
