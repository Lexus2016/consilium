# Examples: real situations

A few everyday moments where a second opinion helps. The easy way is to ask your
agent in plain words (shown in quotes) and let it work out the rest. Each one also
shows the bare `consult` command, in case you'd rather run it yourself.

New here? The [README](../README.md) explains what `consult` is and why you'd ask a
different AI.

## Before a risky change

You're about to change the database and you're worried it could lose data.

> "Before we run this change, ask codex whether it could lose data."

For a short, self-contained question like this, you can also ask it yourself in one
line — the name of who you're asking, then the question:

```
consult codex -- "Could this database change lose data if it runs twice?"
```

## A fresh look at your code

You wrote a tricky bit and want another set of eyes on it.

> "Get a second opinion from agy on this login code before we move on."

Your agent shares the code with the other AI for you. You don't have to.

## Check a plan

You've got a plan and want to know what could go wrong with it.

> "Ask another AI what could break in this plan."

## When you and your agent disagree

You're not convinced your agent's idea is the right one.

> "I'm not sold on this. Get an independent opinion from codex."

## A high-stakes code audit

A security-sensitive file is about to ship, and one opinion isn't enough.

> "Run the council on src/auth.js — find security bugs and race conditions."

Your agent runs `consult council -f src/auth.js -q "…"`: several AIs on different
providers audit the code independently, one synthesizes the result, and every
finding is verified against its `file:line` before you see it. It's expensive — a
few minutes and several paid calls — but it's for the things that have to be right.

## What happens every time

The other AI answers, your agent shows you the reply and says what it makes of it,
and you decide. Nothing in your files changes unless you say so.
