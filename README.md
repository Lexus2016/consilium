# consilium

**English** · [Українська](README.uk.md) · [Русский](README.ru.md)

> Let your AI ask a different AI when it isn't sure.

Your coding assistant is good, but it has the same problem the rest of us do: it
can't always tell when it's wrong. It will convince itself a migration is safe,
miss a race condition, or keep hammering a broken approach instead of stopping to
check. consilium gives it a way to stop and check. It hands the same code to a
different model (Claude, GPT, or Gemini) and asks what that one thinks. The other
AI only answers. It never changes your files.

> Still early, but I reach for it most days.

## When it's worth asking

A second read pays off in moments like these.

You're about to run a database migration and you're not sure it's safe if it runs
twice. Ask before you hit enter, not after.

A retry loop passes every test and still falls over in production once a day.
Another model reads the back-off logic and spots the off-by-one you'd stopped
noticing.

You and your assistant have spent an hour on one bug, each fix breaking the last.
Bring in something that wasn't around for the first fifty-nine minutes.

The auth check looks right. But you wrote it, so of course it does. Send it to a
different model and ask the one question that counts: can this be bypassed?

Release is minutes away and something about backwards compatibility nags at you,
though you can't name it yet. Two minutes now is cheaper than a rollback at
midnight.

## Install it (just ask your AI)

Paste this to your assistant (Claude Code, Codex, OpenCode, or Antigravity):

> Install consilium from https://github.com/Lexus2016/consilium for me: clone it,
> run its `install.sh`, and set yourself up to ask other AIs for a second opinion
> the way its `clients/README.md` describes.

That's it. You only need the assistants you actually plan to ask.

## Use it

Just say what you want, in plain words:

> "Before we continue, get a second opinion from codex on this."

> "Ask another AI whether this change is safe."

> "I'm stuck. Check this with agy."

It runs the request, shows you the reply, and tells you whether it agrees. What
happens next is your call.

If you'd rather run it yourself, it's one line: who you're asking, then the
question.

```
consult codex -- "Is it safe to do it this way?"
```

## Good to know

- The other AI advises, it doesn't act. consilium won't let it skip safety checks,
  and it answers without editing your files.
- The assistants you want to ask have to be installed and signed in first. Run
  `consult --list` to see who's ready.
- It runs in your current project folder, so your code is already in front of it.
- Ask a different model than the one you're using. A second Claude mostly agrees
  with the first.
- Every call is a real request to another model, so save it for the things that
  matter.
- Don't put passwords or keys in the question.

## Read more

- Real situations, in plain language: [`docs/examples.md`](docs/examples.md)
- A short guide for you: [`docs/usage.md`](docs/usage.md)
- The playbook your assistant follows: [`docs/consulting-guide.md`](docs/consulting-guide.md)
- How it's built, if you're curious: [`docs/architecture.md`](docs/architecture.md)

## License

[MIT](LICENSE)
