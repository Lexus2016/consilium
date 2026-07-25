# Consilium — Audit Verification & Remediation Plan

**Date:** 2026-07-18
**Verifies:** `AUDIT.md` (third-party adversarial audit, 2026-07-18)
**Method:** Four independent read-only verification tracks (Python verifier core /
process-lifecycle & concurrency / shell safety / docs-install-hook). Every finding
checked against the *current* source by content, not by trusting the audit's line
numbers. Code quoted per finding. `python3 -m pytest -q` → **16 passed** (baseline, no
files modified during verification).

## Release status — v0.7.0 (shipped)

Remediation shipped as tagged release **v0.7.0** (commits `fa85985` verifier · `8125fc1`
hook · `bf685a7` lifecycle · `a59a965` config · `eafc7f5` docs · `6a48b86` release).
Every code change was peer-reviewed via `consult --panel`/`--review` and covered by
tests (**16 → 46**; ruff + bash -n clean).

- **HIGH — all 10 fixed:** H1 H2 H3 H4 H5 H6 H7 H8 H9 H10.
- **MEDIUM:** fixed M2 M3 M4 M5 M6(trailer slice) M7(partial) M8 M9 M11; M1 refuted (no-op + hardening).
- **LOW/NIT:** fixed L2 L6 L7 L8 L13 L14 L15 N2 N3 N4 N5; N1 no-op.
- **Stock-macOS lifecycle residual — NOW CLOSED.** macOS ships no `setsid`/`timeout`, but
  it does ship `perl`. `bin/consult` now uses a `perl` fallback for BOTH: (a) the runner
  (`perl` setsid+alarm gives the same timeout + whole-process-group SIGTERM/-KILL, exit 124),
  so a hung/orphaned advisor is bounded by `CONSILIUM_TIMEOUT` even without coreutils; and
  (b) the panel children (`perl` setsid makes each child a group leader), so the trap kills
  the advisor grandchild on a non-interactive `SIGTERM`. Verified on macOS with stub advisors
  (hang→bounded, panel-SIGTERM→advisor dead, normal path unregressed).
- **Deferred follow-ups (documented, tracked):** M6 full untrusted-output wrapper; M10 M12
  M13 L1 L3 L4 L5 L9-cleanup L10 L11 L12; shell exit-code tests. L5 (agy auth symlinks)
  deliberately skipped — LOW nitpick on credentials, poor risk/reward.
- **Known verifier limitation (design, not a bug):** verification is citation-EXISTENCE
  based. It cannot enforce that *every* finding carries its own citation, so an answer that
  MIXES a cited finding with an uncited claim still reads COMPLETE (the zero-citation and
  omitted-file false-greens ARE closed). Per-finding enforcement needs a structured
  `FINDING:/SOURCE:` output contract — a v0.8 design item, not bolted on as a brittle heuristic.
- **Convergence loop (self-check ×N, `consult --panel codex,grok --review`):** the whole
  release diff was run through a loop of adversarial panel reviews, fixing every real finding
  and re-reviewing until a clean pass. It converged at **VERDICT: PASS — publishable** (no
  real crash / security / data-loss / correctness blocker). Fixes the loop surfaced beyond
  the original plan: SOURCE citation line-anchoring (an in-diff `SOURCE:` no longer false-fails
  a valid answer) + `file:line:col` tolerance; a `--copy`+council clean error; install.sh
  refuses to clobber an unrelated *symlinked* tool; **strict, exhaustive config validation** —
  every field type/range-checked (`_require_int` rejects bool/float/string; `recipe` enum;
  `panel`/`reviewers` lists-of-strings; `synthesizer`/`drafter`/`working_dir`/`host` strings;
  `code_access` bool; dead `min_panel` removed) and `run_audit` now runs `profile.validate()`
  before any paid member; and **ps1 parity** (`--model` guard, forced `GOOSE_MODE=approve`,
  chmod 700/600 transcripts on non-Windows). Tests 16 → 50.
- **macOS lifecycle CLOSED + a correct signal state machine.** A later loop closed the
  stock-macOS residual with a `perl` fallback (portable timeout + setsid/process-group kill).
  Two bugs in that `perl` were then found and fixed: an `EINTR` `waitpid` that exited before
  the `KILL` grace (a `TERM`-ignoring advisor would orphan), and external `TERM`/`INT`
  handlers that didn't arm the grace (a signal-ignoring advisor would hang forever) with
  non-signal-appropriate exit codes. The final state machine (timeout→124; external
  TERM/INT→128+sig; grace→`KILL`; EINTR-safe reap loop; race-correct) was **empirically
  reproduced and confirmed** by the panel (codex ran 124/143/137/130/137 + race cases) and
  by local stub tests. Convergence reached **VERDICT: PASS — publishable**.

## Headline

The audit is exceptionally accurate. Of 43 findings:

- **39 CONFIRMED** — real, reproducible defects.
- **3 PARTIAL** — real but narrower/less severe than stated (M10, L9, L11).
- **1 REFUTED** — the described defect does not exist (M1).

All **10 HIGH** findings are fully confirmed. No HIGH was over-stated on existence
(one, H6, is better classified as a documentation-honesty bug than privilege
escalation — see below).

---

## Corrections to the audit (where it was wrong or overstated)

- **M1 (Cancellation race) — REFUTED (registration race), with a residual.** The
  specific race the audit describes is closed: `spawn.py` `Registry.add()` re-checks
  `_cancelled` *under the same lock* as `cancel_all()` and terminates a late spawn
  inline. An independent codex+grok panel confirmed the refutation but flagged that
  "never orphaned" is too absolute: (a) a `KeyboardInterrupt` landing between `Popen`
  returning and `registry.add()` (narrow; main-thread synth / single-agent paths) would
  orphan an unregistered child; (b) even a *terminated* registered proc can leave the
  real advisor alive because `_terminate` signals only the direct child (H3's grandchild
  gap). Both are covered by the Group 2 H3 fix; also add a small exception-safe
  `Popen`→`add` guard there. Do **not** re-open M1 as the audit's registration race.
- **M10 (verify→parallel degradation) — PARTIAL.** True: degradation iterates
  `profile.panel`, not the verify participants. The audit's "*empty* panel" is
  unreachable via shipped config/resolution (`panel == [drafter]+reviewers`, len ≥ 2).
  The real residual (both advisors) is a *wrong non-empty* roster: a pinned/explicit
  verify profile whose `panel` ≠ `drafter+reviewers` degrades to the wrong set of
  agents. Fix framing = degrade over `[drafter]+reviewers`, not "guard against empty".
- **L9 — PARTIAL.** `COUNCIL_INTERNAL` is indeed dead (set in `spawn.py`, read
  nowhere). But `QUORUM_CONFIG` is **not** dead — `cli.py` reads it as a live
  back-compat config-path fallback. Do **not** remove it.
- **L11 — PARTIAL.** The audit-trail gap is real (council members run `--no-log`,
  no per-member transcript). But the cited "contradiction" of `SKILL.md:67` is weak —
  that line is scoped to the single-advisor flow, which *does* log; the council section
  makes no transcript promise. Treat as a gap to fill, not a contradiction to fix.
- **Severity softened (still real):** M8, M12, L4, L7, N2 are minor/narrow-trigger.
  N1 (`_finalize` picks longest answer) is a defensible fallback-of-a-fallback heuristic
  with no clean drop-in fix.
- **H6 nuance:** `--raw`/`--model` flag injection is a doc-accuracy defect, not
  privilege escalation — the caller who writes such a command line could run the vendor
  CLI directly. The load-bearing fix is the leading-`-` guard + honest README wording.

---

## Verdict table

Legend: ✅ CONFIRMED · 🟡 CONFIRMED-MINOR (real, low severity/narrow) · 🟠 PARTIAL · ❌ REFUTED

### HIGH

| ID | Verdict | Note |
|----|---------|------|
| H1 | ✅ | `complete = bool(ok_members) and bad_sources==0`; no/garbled `SOURCE:` → `bad_sources==0` → COMPLETE. Malformed lines vanish (regex `\S+?:\d+` drops `x.py:-5`, spaces). |
| H2 | ✅ | `verify_sources` checks all input `abs_files`, ignorant of `gather_code`'s `[TRUNCATED]` omission → cite an unseen file, still `[OK]`. |
| H3 | ✅ | All 5 sub-claims: plain `Popen` (no new session); `_terminate` uses `proc.kill()` not `os.killpg`; no `trap`/`setsid` in `bin/consult`; advisor is a `timeout … | tee` grandchild; stock macOS lacks `timeout` → orphan unbounded. |
| H4 | ✅ | `ex.map` inside `with ThreadPoolExecutor` → `shutdown(wait=True)` blocks on 930 s × 2-retry workers before `cancel_all` can run (~31 min). |
| H5 | ✅ | Log write has no `umask`/`chmod` (bash & ps1); full prompt incl. `--context` + piped diff persisted 0644, 200 kept. README discloses only ps/argv exposure. |
| H6 | ✅ | `--raw` sets `prompt=$question` passed as trailing argv, no leading-`-` guard / no `--` sentinel. Doc-honesty bug (not escalation). |
| H7 | ✅ | pi: no gate at all; goose: `${GOOSE_MODE:-approve}` honors preset `auto`; claude: inherits user config. Contradicts absolute "never touches your files". |
| H8 | ✅ | Hook parses with python3 fallback but still emits via `jq -nc` (2 sites) → exit 127 under `set -euo pipefail` when jq absent. |
| H9 | ✅ | Missing/typo config silently → defaults; `check` prints "OK" for a file never read; `install.sh --copy` → `No module named council`. |
| H10 | ✅ | `architecture.md` dispatch table wrong: `-p` shown first for agy/pi (code puts it last), omits agy `--gemini_dir` and cline `--auto-approve false`. |

### MEDIUM

| ID | Verdict | Note |
|----|---------|------|
| M1 | ❌ | `add()` re-checks `_cancelled` under the lock and terminates a late spawn — the audit's registration race is closed (residual orphan windows are H3's, not M1's). |
| M2 | ✅ | council exec omits `COUNCIL_CONSULT_BIN`; `spawn.py` defaults to bare `consult` → "no available agents" when not on PATH. |
| M3 | ✅ | Missing `-f` / bad JSON / bad `strip_patterns` regex → uncaught traceback exit-1, indistinguishable from INCOMPLETE. |
| M4 | ✅ | `--code` warn-and-ignored by 5/12 (hermes, opencode, pi, cursor, goose); read-only only for codex. `usage.md` says "read-only" universally. |
| M5 | ✅ | `--list` is `command -v` only (not signed-in); `_run_member` retries once → two attempts per signed-out member. |
| M6 | ✅ | Advisor stdout `tee`'d back to hub raw, no untrusted-content framing → injection / forged `VERDICT: PASS` surface. |
| M7 | ✅ | No tests touch `consult`/`roster`/`spawn.run_agent`/`verify_sources`/`gather_code`; `COUNCIL_FAKE` unused; `test_config` near-tautological. |
| M8 | 🟡 | `_number_file` uses `splitlines()`, verifier counts `\n` iteration — skews only on `\v`/`\f`/unicode separators. |
| M9 | ✅ | `rm -f "$dest"` clobbers unrelated `consult` / can't rmdir; `sync_block` checks marker *count* not *order* → reversed markers delete START→EOF. |
| M10 | 🟠 | Degradation reads `profile.panel` (true); "empty panel" unreachable in default/resolved path. |
| M11 | ✅ | Single-agent fallback calls `run_agent` directly, bypassing `_run_member`'s one-retry. |
| M12 | 🟡 | Real TOCTOU on `--context`/`--code`, but caller-controlled local-trust path. |
| M13 | ✅ | Synthesizer sees only `ok` answers; failures only in caller `note` (largely by-design). |

### LOW / NITPICKS

| ID | Verdict | Note |
|----|---------|------|
| L1 | ✅ | bash `cat` can hang forever; ps1 `.Wait(10000)` silently drops slow piped input. |
| L2 | ✅ | bash `timeout` without `-k`/`--kill-after`; TERM-ignoring agent outlives `CONSILIUM_TIMEOUT` (bash-only; ps1 hard-kills). |
| L3 | ✅ | Panel prefers `consult` on PATH over `$0`; newer clone fans out to stale installed binary. |
| L4 | 🟡 | Unquoted `$(...)` in `--panel` globs, but `is_known_agent` whitelist neutralizes it. |
| L5 | ✅ | agy symlinks: guard checks 1 of 2 files; `ln -sf` dangling masked by `|| true`; `CONSILIUM_AGY_DIR` steers credential-symlink location unvalidated. |
| L6 | ✅ | `panel:"claude"` → char list; `profiles:{}` falsy → defaults; `min_panel`/`heartbeat_seconds` dead (`max_concurrent_panels` is printed by `check`). |
| L7 | 🟡 | Timeout msg says "after {N}s" but waited N+30; `member_timeout_seconds: 0` coerced to default 900 by `or`. |
| L8 | ✅ | Whole file read before budget check; duplicate `-f` embedded twice. |
| L9 | 🟠 | `COUNCIL_INTERNAL` dead (true); `QUORUM_CONFIG` is a LIVE back-compat alias (refuted). |
| L10 | ✅ | Exit 2/4/127 + `council check` + 4 env vars undocumented (`CONSILIUM_BIN` only in `install.sh --help`). |
| L11 | 🟠 | council `--no-log` = no audit trail (true); SKILL.md:67 "contradiction" is weak (single-consult scope). |
| L12 | ✅ | No `[build-system]`, no entry points → `pip install .` yields nothing runnable. |
| L13 | ✅ | Provider diversity keyed per front-end not model; hermes+kimi both Moonshot count as "diverse" (documented in comments). |
| L14 | ✅ | `consulting-guide.md` says citations "dropped" — nothing dropped; full answer prints verbatim, BAD only flagged. |
| L15 | ✅ | awk relocates block to EOF when content follows END; legacy grep string ≠ current heading → duplicate-block risk. |
| N1 | 🟡 | `_finalize` fallback picks longest answer — defensible fallback-of-fallback; no clean fix. |
| N2 | 🟡 | Citation paths not `expanduser`/`realpath`'d while config is → `~/x.py`/symlink alias flagged BAD (narrow: advisor echoes abspath). |
| N3 | ✅ | `README.uk.md` wraps `shell-`/`інструментом` mid-compound. |
| N4 | ✅ | "verified locally" table lists 4/12 agents; codex `resume --last` cell not supported by dispatch. |
| N5 | ✅ | `council.json` `_doc` frontier "(agy/claude/codex)" stale; real pool agy/codex/grok/kilo/cline/kimi (claude excluded by default). |

---

## Remediation plan (prioritized)

Ordering follows the audit's suggested order, adjusted for the verification results
(M1 dropped; M10/L9/L11 rescoped). Each group is an independent, shippable unit.
**Tests first for Group 1** — the `verify_sources`/`gather_code` unit tests would have
caught H1/H2 and guard the fix.

### Group 1 — Verifier integrity (core product promise) · HIGH · ✅ DONE (tests 16→35, ruff clean, panel-reviewed)
Files: `council/orchestrator.py`, `council/cli.py`, `council/recipes.py`, `tests/`
Implemented H1 (clean-audit NO_FINDINGS contract), H1b, H2, M8, N2, L8, M6-trailer +
member/synth prompt updates. A `consult --panel codex,grok --review` pass caught 3
issues (token-not-whole-answer bypass; token+citations contradiction; indented-trailer
gap) — all fixed and re-tested. M2 (COUNCIL_CONSULT_BIN) still pending (needs `bin/consult`).

### Group 2 — Process lifecycle (real money leaks on stock macOS) · HIGH
Files: `council/spawn.py`, `council/orchestrator.py`, `council/recipes.py`, `bin/consult`
- **H3:** `Popen(..., start_new_session=True)`; `_terminate` → `os.killpg(os.getpgid(pid), sig)`;
  in `bin/consult` add `trap '… kill panel pgroup' EXIT INT TERM`, spawn via `setsid`
  where available, and `timeout --kill-after`.
- **H4:** on `KeyboardInterrupt` call `registry.cancel_all()` *before* joining workers;
  use `executor.shutdown(wait=False, cancel_futures=True)` (drop the plain `with … as ex`
  auto-join), ideally a SIGINT handler.
- **M11:** route the single-agent fallback through `_run_member`.
- **L2:** `timeout -k <grace>` in `bin/consult`.
- **L7:** `member_timeout = profile.x if profile.x is not None else cfg.x`; fix the
  "after {N}s" message to reflect the +30 s grace.
- **Reap:** `proc.wait()` after `proc.kill()` in `_terminate`; surface (don't silently
  swallow) the drain timeout.
- **M1:** the registration race needs no fix (verified safe) — add a comment so the
  re-check isn't "fixed" into a regression. Do add an exception-safe `Popen`→`add`
  guard (try/finally) so a `KeyboardInterrupt` between them can't orphan an unregistered
  child on the main-thread synth / single-agent paths.

### Group 3 — Secret / auth hygiene · HIGH
Files: `bin/consult`, `bin/consult.ps1`, `README.md` ×3, `clients/hub-block.txt`
- **H5:** `umask 077` (or `chmod 600 "$logfile"`) around log writes in both ports;
  document the transcript dir + perms in README "Good to know".
- **H6:** reject `question`/`--model` values beginning with `-` (or insert `--` where the
  vendor CLI supports it); reword the README claim to "consilium's own flags never grant
  permissions" and document the `--raw` risk.
- **H7:** `export GOOSE_MODE=approve` unconditionally; add per-advisor caveats to README +
  hub-block (pi: no gate; claude/kimi/kilo/cursor: gate depends on user config); soften
  the absolute "never touches your files" wording to match the accurate `SKILL.md`.
- **L5:** gate on both agy files; verify symlink target before `ln` (don't mask failures);
  validate/constrain `CONSILIUM_AGY_DIR`.

### Group 4 — Hook fix (one line; unblocks flagship "non-blocking" promise) · HIGH · DO EARLY / PARALLEL
Files: `clients/claude-code/hooks/consult-nudge.sh`
Independent of the verifier/process work; both advisors flagged position-4 as a priority
inversion (it breaks `git commit`/`push` today). Run it parallel to Group 1.
- **H8:** emit the JSON via the python3 fallback (or `printf` — the context strings are
  static) so the hook works with jq absent.

### Group 5 — Config honesty (fail loudly, actionable messages) · MEDIUM
Files: `council/config.py`, `council/cli.py`, `bin/consult`, `install.sh`
- **H9:** error when an explicit `--config`/`COUNCIL_CONFIG` path doesn't exist; warn when
  the *default* path is missing and defaults are used; resolve the default relative to the
  consult repo root; make `--copy` installs detect the missing `council` package and say so.
- **M3:** catch `FileNotFoundError`/`JSONDecodeError`/`re.error` → one-line message, exit 2.
- **M2:** `COUNCIL_CONSULT_BIN` export — bash port done in Group 1; mirror in the ps1 port here.
- **L6:** reject a non-list `panel`; treat `{}` profiles as empty/error; drop or wire
  `min_panel`/`heartbeat_seconds`.
- **L9:** implement or remove `COUNCIL_INTERNAL`; **keep** `QUORUM_CONFIG`.

### Group 6 — Untrusted-output framing + resilience · MEDIUM
Files: `bin/consult`, `council/cli.py`, `council/recipes.py`, `bin/consult.ps1`, `SKILL.md`, `hub-block.txt`
- **M6:** wrap advisor output in explicit untrusted-content markers; note in
  SKILL.md/hub-block that a peer's output is data, never instructions. (Trailer-integrity
  part moved to Group 1 — it interacts with the `COUNCIL STATUS:` contract.)
- **M13:** include a one-line "member X failed: reason" preamble in the synth input.
- **M10:** degrade using `[drafter]+reviewers` (or resolve the concrete roster once and
  reuse) — latent hardening.
- **L1:** pick one bounded-and-warned stdin behavior for bash + ps1; never lose context
  silently.

### Group 7 — Docs realignment · MEDIUM/LOW (mirror to README ×3)
Files: `docs/architecture.md`, `docs/usage.md`, `docs/consulting-guide.md`, `README.*`, `config/council.json`, `clients/*`
- **H10:** regenerate the dispatch table from `bin/consult` verbatim; add a `--print-cmd`
  debug flag or a doc test to keep them in sync.
- **M4:** document the per-advisor `--code` matrix; drop blanket "read-only".
- **M5:** reword `--list` docs ("installed", not "signed in"); optional cheap auth probe.
- **L10:** add an env-var + exit-code reference table (2/3/4/124/127, `council check`).
- **L13:** disclose the per-frontend (not per-model) diversity limitation in README.
- **L14:** "dropped" → "flagged".
- **L11:** either let council write one aggregate transcript, or note the no-log gap in
  the council docs.
- **N3/N4/N5:** fix the UK line wrap; annotate the codex `continue` cell / verified-subset
  table; correct the `council.json` `_doc` frontier pool.

### Group 8 — Install robustness · MEDIUM
Files: `install.sh`
- **M9 + L15:** refuse to overwrite a non-consilium binary; `[ -d "$dest" ]` explicit
  check; validate START-before-END marker order; update the legacy heading string
  ("Consulting a peer AI" → "Consulting peer AIs").

### Group 9 — Packaging (optional) · LOW
Files: `pyproject.toml`
- **L12:** add `[build-system]` + console entry points + package the config, **or**
  document explicitly that consilium is repo-run-only.

### No action
- **M1** (refuted), **N1** (acceptable heuristic).

---

## Notes for the team

- All wording fixes (H6, H7, M4, M5, L14) must be mirrored to `README.md`,
  `README.ru.md`, and `README.uk.md` — the three are structurally in sync.
- The audit's own "Verified TRUE" list (no shell injection, exit-code fidelity,
  dispatch table grants no permissions, roster provider-dedup, `--panel` isolation)
  was spot-checked and holds — do **not** "fix" those.
- Groups are independent; **revised sequence after the codex+grok panel:** H8 (hook)
  runs early/parallel (one-line, breaks commit/push today); M2 + the M6 trailer-integrity
  slice are folded into Group 1 (test enabler + verifier-contract integrity); Groups 1
  and 2 are parallelizable; then secrets (3) → config (5) → resilience (6) → docs (7) →
  install (8) → packaging (9).
- **Independent second opinion:** a `consult --panel codex,grok` run (transcript in
  `~/.consilium/log/`) reviewed the four contested calls (M1/M10/L9) and the Group 1
  design. Both confirmed M1's refutation and L9; both rejected the naive H1a — the
  revised clean-token contract above is the result.
