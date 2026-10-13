#!/bin/bash
set -euo pipefail
editor_package_dir="$(cd "$(dirname "$0")" && pwd)"
editor_codex_dir="${CODEX_HOME:-$HOME/.codex}"
editor_skill_source="$editor_package_dir/skills/auto-video-editor"
if [ ! -f "$editor_skill_source/SKILL.md" ]; then
  echo "Skill source missing: $editor_skill_source" >&2
  exit 1
fi
mkdir -p "$editor_codex_dir/skills/auto-video-editor"
cp -R "$editor_skill_source/." "$editor_codex_dir/skills/auto-video-editor/"
echo "Installed auto-video-editor skill: $editor_codex_dir/skills/auto-video-editor"
echo "Use the CLI at /Applications/AutoVideoEditor.app/Contents/MacOS/auto-edit."
