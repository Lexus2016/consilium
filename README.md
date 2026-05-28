# consilium

**English** · [Українська](README.uk.md) · [Русский](README.ru.md)

> Ask another AI for a second opinion — from inside the AI you already work with.

When you work with an AI coding assistant, it sometimes misses things or talks
itself into a bad idea. **consilium** lets it quietly ask a *different* AI to check
the work, then carry on. The other AI only gives an opinion — it never changes
your files.

> Early work, but it already works day to day.

## Install it — just ask your AI

Copy this and paste it to your AI assistant (Claude Code, Codex, OpenCode, or
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

It asks the other AI, shows you the answer, and tells you what it thinks. **You
always decide what to do next.**

If you'd rather do it yourself, it's one line in your terminal — the name of who
you're asking, then your question:

```
consult codex -- "Is it safe to do it this way?"
```

## A few things worth knowing

- The other AI is there to **advise, not act** — consilium never lets it skip
  safety checks, and it answers without changing your files.
- The assistants you want to ask must be **installed and signed in** first. Run
  `consult --list` to see which are ready.
- It looks at the same project folder you're in, so it understands your work.
- Ask a *different* AI than the one you're using — a fresh pair of eyes helps more.
- It's a real request to another AI, so use it for things that matter, not trifles.
- Don't put passwords or secret keys in your question.

## Want more?

- Everyday examples: [`docs/examples.md`](docs/examples.md)
- A short guide for people: [`docs/usage.md`](docs/usage.md)
- The how-to your assistant follows: [`docs/consulting-guide.md`](docs/consulting-guide.md)
- How it's built, for the curious: [`docs/architecture.md`](docs/architecture.md)

## License

[MIT](LICENSE)
