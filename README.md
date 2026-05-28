# consilium

> Cross-agent consultation bus for AI coding CLIs.

**consilium** lets one AI agent — your *hub* — consult another AI agent in
headless mode: ask a question, get an independent second opinion, fold it back
into your work, and continue. It is symmetric: Claude Code, Antigravity (`agy`),
OpenCode and Codex can each be the hub *or* the advisor.

The everyday command is `consult`:

```sh
consult codex    -- "Is a read-only sandbox enough to make a consultant safe?"
consult opencode --context design.md -- "Any race conditions in this plan?"
consult claude   --code . -- "Spot bugs in the auth flow"
```

## Why

One model has blind spots. A second, independent agent — a different provider,
a fresh context — catches what the first one missed. consilium turns that second
opinion into a single command, from inside whatever agent you already work in.

## Status

Early work in progress. The full design lives in
[`docs/architecture.md`](docs/architecture.md). Multilingual docs (EN / UK / RU)
and real-world examples are on the roadmap.

## License

[MIT](LICENSE)
