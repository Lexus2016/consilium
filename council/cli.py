"""Command-line entry point: `python -m council ...` (also reached as `consult council`).

Subcommands:
  check   validate the config and print the resolved profiles/policies
  audit   run the council on code (embedded as text) and verify SOURCEs
"""

from __future__ import annotations

import argparse
import sys

from .config import load_config, validate_config, ConfigError

# The tool's authoritative verdict line. A synthesizer/advisor must not be able to
# forge it inside its own (untrusted) answer, so EVERY occurrence of the token in the
# body is neutralized before printing (cmd_audit) — regardless of line position or
# exotic line breaks (\r \f \v U+2028 U+0085) that a line-anchored regex would miss,
# and rewriting the token itself so a bare substring match on it also fails. The real
# trailer is emitted separately by this module.
_CONTROL_TOKEN = "COUNCIL STATUS:"


def _neutralize_control(text: str) -> str:
    return text.replace(_CONTROL_TOKEN, "COUNCIL STATUS (from advisor):")


def _add_common(p: argparse.ArgumentParser):
    # default=None (not the path string) so load_config can tell an EXPLICIT
    # --config from the built-in default: a typo'd explicit path fails loudly,
    # a missing default just warns and uses built-in profiles.
    p.add_argument("--config", "-c", default=None,
                   help="path to JSON config (default: the repo's config/council.json, "
                        "or $COUNCIL_CONFIG)")


def cmd_check(args) -> int:
    cfg = load_config(args.config)
    problems = validate_config(cfg)
    print(f"working_dir : {cfg.working_dir_abs}")
    print(f"concurrency : {cfg.max_concurrent_panels}")
    print(f"member t/o  : {cfg.member_timeout_seconds}s")
    print("profiles    :")
    for name, prof in cfg.profiles.items():
        print(f"  - {name}: recipe={prof.recipe} panel_size={prof.panel_size} "
              f"code={prof.code_access}")
    if problems:
        print("\nproblems:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nOK: config is valid")
    return 0


def cmd_audit(args) -> int:
    from .orchestrator import run_audit, has_clean_audit_token, mentions_no_findings

    res = run_audit(args.file, args.question, profile_name=args.profile,
                    config_path=args.config)
    # Print the (untrusted) answer, but neutralize any forged occurrence of this
    # tool's own COUNCIL STATUS token; the caller must key on the real one below.
    print(_neutralize_control(res.final_text))

    bad_sources = sum(1 for s in res.sources if not s.ok)
    total_sources = len(res.sources)
    # A clean audit is EXACTLY the NO_FINDINGS sentinel. The token appearing
    # alongside other content or findings is contradictory, not clean.
    clean_only = has_clean_audit_token(res.final_text)
    token_mixed = mentions_no_findings(res.final_text) and not clean_only

    print("\n" + "=" * 60)
    print("SOURCE VERIFICATION")
    print("=" * 60)
    if not res.sources:
        print("  (no SOURCE: citations found in the answer)")
    else:
        for s in res.sources:
            mark = "OK " if s.ok else "BAD"
            extra = "" if s.ok else f"  <- {s.reason}"
            loc = s.path if s.line is None else f"{s.path}:{s.line}"
            print(f"  [{mark}] {loc}{extra}")
        good = total_sources - bad_sources
        tail = f", {bad_sources} UNVERIFIED" if bad_sources else ""
        print(f"\n  {good}/{total_sources} sources verified{tail}")

    print("\n[members]")
    ok_members = 0
    for m in res.members:
        print(f"  {m.role} {m.agent} ok={m.ok} {m.wall_seconds:.0f}s {m.error or ''}".rstrip())
        if m.ok:
            ok_members += 1
    if res.note:
        print(f"[note] {res.note}")

    # COUNCIL STATUS: one stable line the calling agent can branch on without
    # re-parsing the blocks above. consilium is verification-first, so an answer
    # with unverified citations (or no surviving member) is INCOMPLETE, not a
    # silent exit-0 success. Reports STATE only -- the caller, which holds the
    # task context consilium lacks, decides whether to re-consult.
    # An answer with ZERO citations is COMPLETE only when it IS the clean-audit
    # sentinel (exactly NO_FINDINGS). Otherwise "claims without citations" is
    # indistinguishable from a dropped/garbled citation set — the exact false-green
    # H1 guarded against — so it is INCOMPLETE. Emitting NO_FINDINGS together with
    # any other content or finding is contradictory and likewise INCOMPLETE.
    no_citations = total_sources == 0
    complete = (
        bool(ok_members)
        and bad_sources == 0
        and not token_mixed
        and (not no_citations or clean_only)
    )
    if complete:
        status = "COMPLETE"
    else:
        reasons = []
        if not ok_members:
            reasons.append("no member produced an answer")
        if bad_sources:
            reasons.append(f"{bad_sources}/{total_sources} sources unverified")
        if token_mixed:
            reasons.append("NO_FINDINGS emitted alongside other content or findings "
                           "(contradictory answer)")
        elif no_citations and not clean_only and ok_members:
            reasons.append("no citations and no NO_FINDINGS signal "
                           "(claims without citations, or the clean-audit token was dropped)")
        status = "INCOMPLETE -- " + "; ".join(reasons)
    print(f"\nCOUNCIL STATUS: {status}")

    return 0 if complete else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="council", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="validate config")
    _add_common(c)
    c.set_defaults(func=cmd_check)

    a = sub.add_parser("audit", help="audit code via the council (code embedded as text)")
    _add_common(a)
    a.add_argument("--file", "-f", action="append", required=True, metavar="PATH",
                   help="file to audit (repeatable)")
    a.add_argument("--question", "-q", required=True, help="audit task / question")
    a.add_argument("--profile", default="consilium-budget",
                   help="profile name (default: consilium-budget)")
    a.set_defaults(func=cmd_audit)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as e:
        # A user/config error (bad path, malformed JSON, bad regex, unknown
        # profile): one clean line and exit 2 — distinct from INCOMPLETE (exit 1).
        print(f"council: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
