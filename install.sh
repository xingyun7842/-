#!/usr/bin/env bash
set -euo pipefail

repo="https://github.com/xingyun7842/-.git"
skill_dir="${HOME}/.codex/skills/weread-optimizer"

mkdir -p "$(dirname "$skill_dir")"

if [ -d "$skill_dir/.git" ]; then
  echo "Updating existing skill at $skill_dir"
  git -C "$skill_dir" pull --ff-only
elif [ -e "$skill_dir" ]; then
  echo "Path exists but is not a git repo: $skill_dir" >&2
  exit 1
else
  echo "Installing skill to $skill_dir"
  git clone "$repo" "$skill_dir"
fi

echo "Installed weread-optimizer"
