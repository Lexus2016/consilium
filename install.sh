#!/usr/bin/env bash
#
# install.sh — put the consilium `consult` command on your PATH.
#
# Works on macOS, Linux, WSL, and Git Bash. By default it symlinks bin/consult
# into your bin directory (so `git pull` keeps `consult` current); pass --copy to
# copy the file instead.
#
# Pass --clients to also sync the consult-peer hub block into the agents you
# already use (codex / opencode / agy) and copy the Claude skill. This is the
# one command to run after `git pull` to push a new release everywhere:
#   git pull && ./install.sh --clients
#
# Windows, native PowerShell: there is no shell installer — point your PATH at
# bin/consult.ps1 (see the README).

set -euo pipefail

mode="symlink"
do_clients=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --copy)    mode="copy"; shift ;;
    --clients) do_clients=1; shift ;;
    -h|--help)
      cat <<EOF
usage: ./install.sh [--copy] [--clients]

Install the 'consult' command into a bin directory.

  --copy      copy the script instead of symlinking (default: symlink)
  --clients   also sync the consult-peer hub block into installed agents
              (codex/opencode/agy) and copy the Claude skill

env:
  CONSILIUM_BIN   target bin directory (default: ~/.local/bin)
EOF
      exit 0 ;;
    *) echo "install.sh: unknown argument: $1" >&2; exit 2 ;;
  esac
done

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

# ----- optional council (Python) availability --------------------------------
if command -v python3 >/dev/null 2>&1; then
  echo "council ok: \`consult council\` is available (python3 found)"
else
  echo
  echo "note: \`consult council\` (multi-agent code audit) needs python3."
  echo "      Core \`consult\` works without it; install python3 to enable council."
fi

# ----- optional: sync hub block + skill into installed agents ----------------

if [ "$do_clients" -eq 1 ]; then
  block_file="$repo_dir/clients/hub-block.txt"
  if [ ! -f "$block_file" ]; then
    echo "install.sh: cannot find $block_file" >&2
    exit 1
  fi

  # Replace the consilium block (between START/END markers) in a target file,
  # or append it if the file exists without the block. Never creates files —
  # only touches agents you already use. The block carries no agent list, so it
  # never needs re-syncing when a new advisor is added; `consult --list` is the
  # source of truth at runtime.
  sync_block() {
    target="$1"
    if [ ! -f "$target" ]; then
      echo "  skip (not present): $target"
      return
    fi
    has_start=$(grep -c "consilium:consult-peer START" "$target" 2>/dev/null || true)
    has_end=$(grep -c "consilium:consult-peer END" "$target" 2>/dev/null || true)
    tmp="$target.consilium.tmp"
    trap 'rm -f "$tmp"' RETURN
    # Require EXACTLY one of each marker. With -ge 1 an unbalanced file (e.g.
    # two START + one END) would still take the awk branch, whose state machine
    # then deletes everything after the second START to EOF — silent data loss.
    if [ "${has_start:-0}" -eq 1 ] && [ "${has_end:-0}" -eq 1 ]; then
      awk '/consilium:consult-peer START/{s=1} s==0{print} /consilium:consult-peer END/{s=0; next}' "$target" > "$tmp"
      printf '\n' >> "$tmp"
      cat "$block_file" >> "$tmp"
      # Write through the file (cat >), not mv, so a dotfiles symlink at $target
      # keeps pointing at its real file instead of being replaced by a plain file.
      cat "$tmp" > "$target"
      echo "  updated block: $target"
    elif [ "${has_start:-0}" -ge 1 ] || [ "${has_end:-0}" -ge 1 ]; then
      echo "  WARN: unbalanced or duplicate consult-peer markers in $target — fix manually; skipping" >&2
    elif grep -q "Consulting a peer AI (consilium)" "$target"; then
      # Legacy block pasted before markers existed: don't silently duplicate it.
      echo "  WARN: $target has an unmarked legacy block — remove it by hand, then re-run; skipping" >&2
    else
      printf '\n' >> "$target"
      cat "$block_file" >> "$target"
      echo "  added block:   $target"
    fi
  }

  echo
  echo "syncing consult-peer hub block into installed agents:"
  sync_block "$HOME/.codex/AGENTS.md"
  sync_block "$HOME/.config/opencode/AGENTS.md"

  # agy (Antigravity / Gemini) reads ~/.gemini/GEMINI.md. Nothing else creates
  # that file, so seed it when agy is installed, then keep it in sync on later
  # runs. Harmless to other tools — the block is generic hub guidance.
  gemini_md="$HOME/.gemini/GEMINI.md"
  if [ -f "$gemini_md" ]; then
    sync_block "$gemini_md"
  elif command -v agy >/dev/null 2>&1; then
    mkdir -p "$HOME/.gemini"
    printf '# Global agent instructions\n\n' > "$gemini_md"
    cat "$block_file" >> "$gemini_md"
    echo "  created block: $gemini_md (read by agy)"
  fi

  # hermes (Nous) has no dedicated dotfile like ~/.codex/AGENTS.md; it reads a
  # home-level ~/AGENTS.md as global user instructions. Nothing else creates that
  # file, so seed it (with the block) when hermes is installed, then keep it in
  # sync on later runs. Harmless to other tools — the block is generic hub guidance.
  home_agents="$HOME/AGENTS.md"
  if [ -f "$home_agents" ]; then
    sync_block "$home_agents"
  elif command -v hermes >/dev/null 2>&1; then
    printf '# Global agent instructions\n' > "$home_agents"
    cat "$block_file" >> "$home_agents"
    echo "  created block: $home_agents (home-global; read by hermes)"
  fi

  skill_src="$repo_dir/clients/claude-code/consult-peer/SKILL.md"
  skill_dir="$HOME/.claude/skills/consult-peer"
  if [ -d "$HOME/.claude/skills" ] && [ -f "$skill_src" ]; then
    mkdir -p "$skill_dir"
    cp "$skill_src" "$skill_dir/SKILL.md"
    echo "  skill synced:  $skill_dir/SKILL.md"
  else
    echo "  skip skill (~/.claude/skills not present)"
  fi
fi

echo
echo "try: consult --list"
