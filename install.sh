#!/usr/bin/env bash
#
# install.sh — put the consilium `consult` command on your PATH.
#
# Works on macOS, Linux, WSL, and Git Bash. By default it symlinks bin/consult
# into your bin directory (so `git pull` keeps `consult` current); pass --copy to
# copy the file instead.
#
# Windows, native PowerShell: there is no shell installer — point your PATH at
# bin/consult.ps1 (see the README).

set -euo pipefail

mode="symlink"
case "${1:-}" in
  --copy) mode="copy" ;;
  -h|--help)
    cat <<EOF
usage: ./install.sh [--copy]

Install the 'consult' command into a bin directory.

  --copy   copy the script instead of symlinking (default: symlink)

env:
  CONSILIUM_BIN   target bin directory (default: ~/.local/bin)
EOF
    exit 0 ;;
  "") ;;
  *) echo "install.sh: unknown argument: $1" >&2; exit 2 ;;
esac

repo_dir="$(cd "$(dirname "$0")" && pwd)"
src="$repo_dir/bin/consult"
bin_dir="${CONSILIUM_BIN:-$HOME/.local/bin}"
dest="$bin_dir/consult"

if [ ! -f "$src" ]; then
  echo "install.sh: cannot find $src" >&2
  exit 1
fi

mkdir -p "$bin_dir"
chmod +x "$src"

rm -f "$dest" 2>/dev/null || true
if [ "$mode" = "copy" ]; then
  cp "$src" "$dest"
else
  ln -s "$src" "$dest"
fi
chmod +x "$dest" 2>/dev/null || true

echo "installed: $dest ($mode of $src)"

case ":$PATH:" in
  *":$bin_dir:"*)
    echo "PATH ok: $bin_dir is on your PATH"
    ;;
  *)
    echo
    echo "note: $bin_dir is not on your PATH. Add this to your shell profile:"
    echo "  export PATH=\"$bin_dir:\$PATH\""
    ;;
esac

echo
echo "try: consult --list"
