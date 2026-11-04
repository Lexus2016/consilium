# Contributing to consilium

Start with a small, reproducible problem or a specific use case. Search
[existing issues](https://github.com/Lexus2016/consilium/issues) before opening a new
one. Keep changes focused and include documentation changes when behavior changes.

## Local checks

From a checkout of this repository:

```bash
(
  set -eu
  test_home="$(mktemp -d)"
  trap 'rm -rf -- "$test_home"' EXIT
  env -u CONSILIUM_LIVE_BAIT HOME="$test_home" python3 -m unittest discover -s tests -v
)
bash -n bin/consult
bash -n install.sh
bash -n clients/claude-code/hooks/consult-nudge.sh
# With the dev dependency installed:
ruff check .
```

Python 3.10+ is required for council development. The macOS/Linux test command
above gives the test process a temporary `HOME`, keeping consilium scratch files
separate from your normal home. It stops if `mktemp` fails and cleans that directory
when the subshell exits. It does not sandbox the test process or clear other
credentials from its environment.

The command explicitly unsets `CONSILIUM_LIVE_BAIT`, overriding an inherited
live-test opt-in. The live advisor write-bait runs when that variable is nonempty,
including the value `0`; it invokes installed agents and can spend money. Keep it
unset for routine checks.
CI also parses the PowerShell launcher. A parse check is not a Windows runtime test.
Install the linter in a virtualenv with `python -m pip install 'ruff>=0.5.0'`.

## Bug reports

Use the [issue forms](https://github.com/Lexus2016/consilium/issues/new/choose).
Include the version or commit, operating system, exact command, expected and
actual behavior, and a minimal public or synthetic reproduction. Remove secrets,
private source, personal data and session content from logs before posting.
Do not post exploitable security details or credentials in a public issue.

## Pull requests

- Base your change on current `main` and explain the problem it solves.
- Link the relevant issue when one exists.
- Add a regression test for behavior changes and run the applicable checks.
- State exactly what passed, failed, skipped or was not run.
- Keep generated data, credentials and unrelated formatting changes out of the diff.
- Keep translated documentation consistent when changing shared instructions.
