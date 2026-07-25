# Consilium — Adversarial Audit Report

**Date:** 2026-07-18
**Scope:** `bin/consult`, `bin/consult.ps1`, `install.sh`, `council/*.py`, `config/council.json`, `clients/`, `tests/`, all user-facing docs (EN/RU/UK).
**Method:** Four independent reviewer tracks (shell core, Python council, docs-vs-code, clients/tests/UX) plus a self-audit by Consilium's own council (`agy` + `opencode` panel, `hermes` synthesis; `COUNCIL STATUS: COMPLETE`, 51/51 citations verified). Code is the single source of truth: every HIGH finding was confirmed by two independent tracks or reproduced directly.

**How to read this:** each finding has severity, exact locations, evidence/repro, and a recommended fix. Findings are independent — pick them off in any order, but the suggested fix order is at the bottom.

---

## HIGH

### H1. Zero or malformed citations produce `COUNCIL STATUS: COMPLETE`
**Where:** `council/cli.py:83`, `council/orchestrator.py:106`
**Problem:** `complete = bool(ok_members) and bad_sources == 0`. An answer with **no** `SOURCE:` lines has `bad_sources == 0` → COMPLETE, exit 0. Malformed citations don't count as BAD — they vanish: `_SOURCE_RE = re.compile(r"SOURCE:\s*(\S+?):(\d+)")` silently ignores `SOURCE: x.py:-5` and any path containing a space. A synthesizer that drops/garbles citations converts INCOMPLETE into COMPLETE — the opposite of the tool's "verification-first" contract (`cli.py:78-82`).
**Reproduced:** `verify_sources("trust me, no citations", {…})` → `[]` → COMPLETE.
**Fix:**
- Treat `total_sources == 0` as INCOMPLETE ("no verifiable citations").
- Treat citations that *look like* SOURCE lines but fail to parse as BAD, not invisible (e.g. a second, looser regex whose matches are flagged "unparseable citation").
- Support `expanduser`/realpath and quoted paths with spaces, or document the citation grammar strictly in `SOURCE_RULE`.

### H2. Citations to files omitted by the embed budget verify as OK
**Where:** `council/orchestrator.py:81-83` (omission), `:117-122,171` (verification set)
**Problem:** `gather_code` drops over-budget files with a `[TRUNCATED]` marker, but `run_audit` passes **all** input files to `verify_sources`. A citation to a file the advisor never saw — a guaranteed hallucination — passes as `[OK]`.
**Reproduced:** 500-line file omitted at `max_lines=10`; `SOURCE: <omitted>:250` → `ok=True`.
**Fix:** `gather_code` should return the set of actually-embedded files; `run_audit` must pass exactly that set to `verify_sources`. A citation to a `[TRUNCATED]` file should be flagged "file not shown to advisors".

### H3. Killing consilium does not kill advisors — orphaned paid processes
**Where:** `council/spawn.py:153` (plain `Popen`), `:83-95` (`_terminate` signals only the direct child), `bin/consult:298-308` (panel children, no trap/setsid), `bin/consult:584` (agent runs as a *grandchild* behind `timeout … | tee`), `bin/consult:551-553` (`timeout` absent on stock macOS → unbounded run)
**Problem:** On client disconnect, Python timeout, or Ctrl-C, only the `consult` shell is signalled; the real advisor process survives and keeps billing. The only backstop (`timeout`/`gtimeout`) does not exist on a default macOS install, where the orphan runs *forever*.
**Fix:**
- `spawn.py`: `Popen(..., start_new_session=True)`; on kill/terminate use `os.killpg(proc.pid, sig)`.
- `bin/consult`: spawn advisors via `setsid` where available and `trap … EXIT INT TERM` to kill the panel's process group; add `timeout --kill-after`.
- After `proc.kill()`, always `proc.wait()` to reap (`spawn.py:93,194-199` currently leaves zombies and swallows the drain timeout).

### H4. Ctrl-C hangs for up to ~31 minutes; cancel path never fires
**Where:** `council/recipes.py:174-179`, `council/orchestrator.py:201-203`
**Problem:** `with ThreadPoolExecutor … ex.map` — on `KeyboardInterrupt`, `__exit__` calls `shutdown(wait=True)` and blocks until workers return (member timeout 900s + 30s grace, doubled by the retry). `run_audit`'s `except BaseException: registry.cancel_all()` cannot run until shutdown returns, so children are never killed on interrupt.
**Fix:** use `executor.shutdown(wait=False, cancel_futures=True)` on interrupt (or avoid the context manager and shut down explicitly in `except`/`finally`), call `registry.cancel_all()` *before* waiting on workers.

### H5. Transcripts persist full prompts (incl. piped diffs/secrets) world-readable
**Where:** `bin/consult:614-625,631` (also `consult.ps1:609-629`)
**Problem:** The full prompt — question + piped `git diff` + `--context` contents — is written to `$LOG_DIR/*.md` with default umask (typically 022 → readable by other local users), 200 files kept. The README discloses the `ps`/argv exposure (`README.md:232-235`) but not the on-disk one.
**Fix:** `umask 077` (or `chmod 600 "$logfile"`) around log writes in both ports; document the transcript directory and its permissions in README "Good to know".

### H6. `--raw` (and `--model`) allow flag injection into advisor CLIs
**Where:** `bin/consult:337,399` and all dispatch branches; `--model` passthrough at `:397,420,436,…`
**Problem:** With `--raw` the verbatim question is the trailing argv token: `consult --raw claude -- "--dangerously-skip-permissions"` execs `claude -p --dangerously-skip-permissions`. This undermines the headline claim "consilium never passes them permission-granting flags" (`README.md:224-225`). The dispatch table itself is clean — the hole is caller-supplied input.
**Fix:** reject question/`--model` values beginning with `-` (or insert `--` where each vendor CLI supports it); reword the README claim to "consilium's own flags never grant permissions" and document the `--raw` risk.

### H7. The "never edits / permission-gated" safety claim is false for `pi`, voidable for `goose`, config-dependent for `claude`
**Where:** `bin/consult:464-473` (pi: only `-p`, **no permission gate at all**), `:516` (`GOOSE_MODE="${GOOSE_MODE:-approve}"` honors a preset `GOOSE_MODE=auto`), `:394-399` (`claude -p` inherits the user's own permission config)
**Problem:** `README.md:223-225`, `clients/hub-block.txt:4-5` ("never touches your files", absolute), `README.md:206`. The project's own architecture doc admits pi is "WEAKEST" (`docs/architecture.md:175`) — the user-facing docs contradict it.
**Fix:** override `GOOSE_MODE=approve` unconditionally; add per-advisor caveats to README + hub-block (pi: no gate; claude/kimi/kilo/cursor: gate depends on user config); soften hub-block wording to match `clients/claude-code/consult-peer/SKILL.md:90-92` (which is accurate).

### H8. Flagship hook hard-errors on machines without `jq`
**Where:** `clients/claude-code/hooks/consult-nudge.sh:16-20` (python3 fallback for parsing) vs `:26,35` (output still via `jq -nc`)
**Problem:** With python3 present but jq absent, any `git push`/`git commit` kills the hook: `jq: command not found`, exit 127 under `set -euo pipefail`. The hook README advertises the python3 fallback.
**Reproduced** on a jq-less PATH.
**Fix:** emit the JSON with python3 too, or build it with `printf` (context strings are static — escaping is trivial).

### H9. Missing config is silently ignored; `check` reports "OK"
**Where:** `council/config.py:194` (`if path and os.path.exists(path)`), `council/cli.py:20` (default config path is CWD-relative), `config/council.json:4` (`working_dir: "."` resolves to caller's CWD)
**Problem:** A typo'd `--config`, or running `consult council` outside the repo root, silently yields built-in defaults; `council check` then prints "OK: config is valid" for a file never read. With `install.sh --copy`, council mode fails entirely (`No module named council`) with no actionable message.
**Fix:** error out when an explicitly-passed `--config`/`COUNCIL_CONFIG` path doesn't exist; print a warning when the *default* path is missing and defaults are used; resolve the default config relative to the consult script's repo root; make `--copy` installs detect the missing `council` package and say so.

### H10. The self-declared SSoT (`docs/architecture.md`) documents the wrong argv
**Where:** `docs/architecture.md:106,111,114` vs `bin/consult:402-406,418,472,504`
**Problem:** The dispatch table shows flags *after* `-p` for agy/pi — the exact shape the code comment says is parsed as prompt text — omits agy's always-passed `--gemini_dir`, and omits cline's `--auto-approve false` (the one flag that makes cline safe; the doc's own safety table at `:178` contradicts its dispatch table).
**Fix:** regenerate the dispatch table from `bin/consult` verbatim; add a doc test or a `--print-cmd` debug flag to keep them in sync.

---

## MEDIUM

| # | Where | Problem | Fix |
|---|-------|---------|-----|
| M1 | `spawn.py:153→173` | Cancellation race: `Popen` succeeds, cancel fires before `registry.add` → child never registered, never killed | Register under a spawn-lock, or re-check `cancelled` immediately after `Popen` and terminate |
| M2 | `bin/consult:161`, `spawn.py:21`, `roster.py:45` | `COUNCIL_CONSULT_BIN` not propagated: `./bin/consult council` without `consult` on PATH → "no available agents" | Export `COUNCIL_CONSULT_BIN="$resolved_self"` when exec'ing the council module |
| M3 | `orchestrator.py:62`, `config.py:196,182`, `orchestrator.py:143` | Raw tracebacks for user errors: nonexistent `-f` file, malformed JSON, bad `strip_patterns` regex; crash exit-1 indistinguishable from INCOMPLETE exit-1 | Catch, print one-line errors, exit 2 (usage error) |
| M4 | `bin/consult:438,445,471,484,520` vs `docs/usage.md:127` | `--code` ignored by 5 of 12 advisors (hermes, opencode, pi, cursor, goose just warn); where honored it is not "read-only" except codex | Document the per-advisor matrix; drop "read-only" wording |
| M5 | `bin/consult:108-117` vs `README.md:50-51` | `--list` checks installation only, not "signed in"; councils burn two attempts per signed-out member | Reword docs; optionally probe auth cheaply per agent |
| M6 | `bin/consult:584`, `cli.py:50` | Advisor output fed back to the hub agent raw — no delimiters/untrusted-output framing; a buggy/malicious advisor can inject instructions or forge `VERDICT: PASS` | Wrap output in explicit untrusted-content markers; say so in SKILL.md/hub-block |
| M7 | `tests/` | Zero coverage on the riskiest code: `bin/consult` (637 lines), `consult.ps1`, `verify_sources`, `gather_code`, `roster.resolve_roster`, `spawn.run_agent`. `COUNCIL_FAKE` exists but no test uses it. `test_config.py:34-37` is near-tautological | Add fake-mode end-to-end `run_audit` test; unit tests for `verify_sources` edge cases (would have caught H1/H2); shell tests for exit-code contract |
| M8 | `orchestrator.py:63` vs `:120` | `_number_file` uses `splitlines()` (splits on `\v \f \u2028`), verifier counts `\n` — citation off-by-skew near EOF | Count lines the same way in both places |
| M9 | `install.sh:57,114-115` | `rm -f "$dest"` deletes a pre-existing unrelated `consult` and can't remove a directory (silent broken install); `sync_block` checks marker count but not order — reversed markers delete everything from START to EOF | Refuse to overwrite non-consilium binaries; check `[ -d ]` explicitly; validate marker order |
| M10 | `recipes.py:271-279`, `config.py:91-96` | `verify`→`parallel` degradation uses `profile.panel`, which "may differ from who really runs" — legacy explicit verify rosters degrade to an empty panel | Degrade using drafter+reviewers, or resolve the concrete roster once and reuse it |
| M11 | `orchestrator.py:194-197` | Single-agent fallback calls `run_agent` directly — skips the transient-failure retry the panel gets | Route it through `_run_member` |
| M12 | `bin/consult:200-205 → 354` | TOCTOU: `--context`/`--code` check-then-use; file swappable for symlink/FIFO in the window | Open-and-fstat, or document as accepted local-trust risk |
| M13 | `recipes.py:255` | Synthesizer sees only successful answers — cannot reason about a half-failed panel (failures only in `note` for the caller) | Include a one-line "member X failed: reason" preamble in the synth input |

## LOW / NITPICKS

- **L1** `bin/consult:264` vs `consult.ps1:248-251`: stdin read diverges — bash `cat` can hang forever; ps1 caps at 10 s but *silently drops* slow piped input (advisor answers without the material). Pick one behavior; never lose context silently.
- **L2** `bin/consult:548`: `timeout` without `--kill-after`; a TERM-ignoring agent hangs past `CONSILIUM_TIMEOUT`.
- **L3** `bin/consult:135-139`: panel prefers `consult` from PATH over `$0` — a newer clone fans out to a stale installed binary.
- **L4** `bin/consult:216`: unquoted `$(…)` in `--panel` parsing permits globbing.
- **L5** `bin/consult:412-417`: agy auth symlinks — two files gated on one; dangling `ln -sf` masked by `|| true`; `CONSILIUM_AGY_DIR` redirects where symlinks to Google credentials are written.
- **L6** `config.py:176,198`: `panel: "claude"` (string) becomes `['c','l','a','u','d','e']`; `profiles: {}` is falsy → silently replaced by defaults. Dead fields: `min_panel`, `heartbeat_seconds`, `max_concurrent_panels` parsed but never used.
- **L7** `spawn.py:203,177`: timeout message says "after {N}s" but waited N+30; `member_timeout_seconds: 0` is falsy → silently falls back (`orchestrator.py:175`).
- **L8** `orchestrator.py:62,80`: whole file read into memory before the budget check (multi-GB `-f` input); duplicate `-f` args embedded twice.
- **L9** `spawn.py:107`: `COUNCIL_INTERNAL` set but read nowhere — the documented recursion guard doesn't exist; `cli.py:19` `QUORUM_CONFIG` is a dead rename leftover.
- **L10** Exit codes 2/3/4/127 and `council check` are undocumented in usage text and `docs/`; env vars `CONSILIUM_AGY_DIR`, `CONSILIUM_BIN`, `COUNCIL_FAKE`, `COUNCIL_CONSULT_BIN`, `COUNCIL_EXCLUDE_AGENTS` undocumented.
- **L11** Council members run with `--no-log` (`spawn.py:134`) — no audit trail of what (possibly secret-bearing) code went to which third-party provider; contradicts `clients/claude-code/consult-peer/SKILL.md:67`.
- **L12** `pyproject.toml`: no `[build-system]`, no entry points — `pip install .` produces a package that can't work without the repo-rooted config and separately-installed `consult`.
- **L13** `roster.py`/`config.py:24`: provider diversity is per-frontend, not per-model — `goose`+`cline` both on Claude count as "diverse"; hermes is bucketed `openrouter/moonshot`, so a "cross-provider" council can hit Moonshot twice. Disclose in README.
- **L14** `consulting-guide.md:32` says hallucinated citations are "dropped" — nothing is dropped; the full answer prints verbatim before the verification trailer (`cli.py:50`).
- **L15** `install.sh:115-117,124`: block-replace awk relocates the block to EOF if content followed the END marker; legacy-block grep matches the old heading ("Consulting a peer AI") but not the current one ("Consulting peer AIs") → possible duplicated block.
- **N1** `_finalize` fallback picks the *longest* member answer (`recipes.py:378`) — verbosity ≠ quality; it's labeled, fine, but consider first-ok instead.
- **N2** `verify_sources` doesn't `expanduser`/`realpath` citation paths while config does — advisor citing `~/x.py` or a symlink alias is flagged BAD (safe direction, but noisy).
- **N3** `README.uk.md:187-188` mid-word line wrap ("shell-\nінструментом").
- **N4** `docs/architecture.md:16-25` "verified locally" table shows only the original 4 agents; its codex "continue" column documents `codex resume --last`, which the dispatch explicitly does not support (`bin/consult:450`).
- **N5** `config/council.json:39` `_doc` says the frontier pool is "(agy/claude/codex)" — actual pool is agy/codex/grok/kilo/cline/kimi (claude excluded by default).

---

## Verified TRUE — do not "fix" these

- No shell injection/eval bugs: argv construction is quoted correctly; agent names whitelisted (`bin/consult:233`); `mktemp` used properly.
- Exit-code fidelity: 127/3/4/124 semantics, `PIPESTATUS` snapshot (`bin/consult:583-587`), retry-on-empty — all as documented.
- The dispatch table itself grants no permissions (all 12 branches checked; cline forced `--auto-approve false`, goose `GOOSE_MODE=approve`, codex `--sandbox read-only`).
- Roster provider-dedup (`roster.py:61-71,111-112`): the synthesizer can never share a provider with a panel member.
- `--panel` parallelism/isolation works as documented; `install.sh --clients` re-sync works; README RU/UK translations are structurally in sync with EN (including — unfortunately — the oversold claims: any claim fix must be mirrored to all three).
- The council's synthesizer behaved correctly on the self-audit: it dropped two unsubstantiated member claims and merged overlapping ones with sound reasoning.

## Suggested fix order

1. **Verifier integrity** (H1, H2, M8, N2) — the product's core promise; small diff, add tests first (M7).
2. **Process lifecycle** (H3, H4, M1, L2) — real money leaks on stock macOS.
3. **Secret hygiene** (H5, H6, H7, L5) — `chmod 600`, leading-dash guard, unconditional `GOOSE_MODE=approve`.
4. **Hook fix** (H8) — one line, currently breaking the flagship "non-blocking" promise.
5. **Config honesty** (H9, M3, L6) — fail loudly, actionable messages.
6. **Docs realignment** (H10, M4, M5, L13, L14, N4, N5) — regenerate `architecture.md` dispatch tables from code; qualify safety claims in README×3 + hub-block; fix "dropped" wording.
7. **Resilience polish** (M2, M10, M11, M13, L1, L7, L8).

---

*Methodology note for the team: this audit was itself partly produced by `consult council` running on this repository (panel: agy, opencode; synth: hermes — COMPLETE, 51/51 citations verified). Findings H1/H2 mean that very run would have passed with fabricated or omitted citations; the human auditor re-verified all load-bearing claims against the code. Treat accordingly.*
