# consilium

**English** · [Українська](README.uk.md) · [Русский](README.ru.md)

> A second AI, reading over your AI's shoulder.

Your coding assistant is sharp, but it has one blind spot: its own. It will talk
itself into a shaky migration, miss a race condition, or keep digging into a dead
end instead of backing out. **consilium** lets it stop and ask a *different* AI —
Claude, GPT, or Gemini — to read the same code and say what it really thinks. The
second AI only gives an opinion. It never touches your files.

> Early days, but it's already part of the daily routine here.

## When you'll actually reach for it

You're about to run a database migration and a small voice asks *what if this runs
twice?* Get another AI to look before you press enter, not after.

The retry loop looks fine and the tests are green, yet it still falls over in
production about once a day. A fresh model reads the back-off math and catches the
off-by-one you've been staring past all week.

You and your assistant have been circling the same bug for an hour, every fix
breaking the last one. That's the moment to bring in someone who wasn't in the room
for the first fifty-nine minutes.

The auth check feels right. "Feels right" isn't the bar for auth — hand the file to
a second AI with one question: *can this be bypassed?*

It's release night, the changelog is long, and you can't shake the feeling you
broke something for people already using it. Two minutes of a second opinion beats
a rollback at 2 a.m.

## Install it — just ask your AI

Copy this and paste it to your assistant (Claude Code, Codex, OpenCode, or
Antigravity):

> Install consilium from https://github.com/Lexus2016/consilium for me: clone it,
> run its `install.sh`, and set yourself up to ask other AIs for a second opinion
> the way its `clients/README.md` describes.

It does the rest. You only need the assistants you actually want to ask.

## Use it — just ask, in plain words

Tell your assistant things like:

> "Get a second opinion from codex on this before we continue."

> "Ask another AI whether this change is safe."

> "I'm stuck — check this with agy."

It asks the other AI, shows you the answer, and tells you what it makes of it. **You
always decide what happens next.**

Prefer to do it yourself? It's one line in the terminal — who you're asking, then
your question:

```
consult codex -- "Is it safe to do it this way?"
```

## Good to know

- The other AI is there to **advise, not act** — consilium never lets it skip
  safety checks, and it answers without changing your files.
- The assistants you want to ask must be **installed and signed in** first. Run
  `consult --list` to see who's ready.
- It works in the same project folder you're in, so it already has your code in
  front of it.
- Ask a *different* AI than the one you're using. A fresh pair of eyes is the whole
  point.
- Each call is a real request to another model, so save it for the decisions that
  matter, not every typo.
- Keep passwords and secret keys out of your question.

## Want the details?

- Real examples, start to finish: [`docs/examples.md`](docs/examples.md)
- A short guide for people: [`docs/usage.md`](docs/usage.md)
- The how-to your assistant follows: [`docs/consulting-guide.md`](docs/consulting-guide.md)
- How it's built, for the curious: [`docs/architecture.md`](docs/architecture.md)

## License

[MIT](LICENSE)
