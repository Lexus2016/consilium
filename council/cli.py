"""Command-line entry point: `python -m council ...` (also reached as `consult council`).

Subcommands:
  check   validate the config and print the resolved profiles/policies
  audit   run the council on code (embedded as text) and verify SOURCEs
"""

from __future__ import annotations

import argparse
import os

from .config import load_config, validate_config


def _add_common(p: argparse.ArgumentParser):
    default_cfg = (
        os.environ.get("COUNCIL_CONFIG")
        or os.environ.get("QUORUM_CONFIG")  # back-compat
        or "config/council.json"
    )
    p.add_argument("--config", "-c", default=default_cfg,
                   help="path to JSON config (default: config/council.json)")


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
    from .orchestrator import run_audit

    res = run_audit(args.file, args.question, profile_name=args.profile,
                    config_path=args.config)
    print(res.final_text)

    bad_sources = sum(1 for s in res.sources if not s.ok)
    total_sources = len(res.sources)

    print("\n" + "=" * 60)
    print("SOURCE VERIFICATION")
    print("=" * 60)
    if not res.sources:
        print("  (no SOURCE: citations found in the answer)")
    else:
        for s in res.sources:
            mark = "OK " if s.ok else "BAD"
            extra = "" if s.ok else f"  <- {s.reason}"
            print(f"  [{mark}] {s.path}:{s.line}{extra}")
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
    complete = bool(ok_members) and bad_sources == 0
    if complete:
        status = "COMPLETE"
    else:
        reasons = []
        if not ok_members:
            reasons.append("no member produced an answer")
        if bad_sources:
            reasons.append(f"{bad_sources}/{total_sources} sources unverified")
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
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
