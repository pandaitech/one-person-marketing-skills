#!/usr/bin/env bash
# Publish a GitHub release with one .zip per skill.
# Usage: scripts/release.sh v1.1 "What changed"
# Stable download links: https://github.com/pandaitech/one-person-marketing-skills/releases/latest/download/<skill>.zip
set -euo pipefail
tag="${1:?usage: scripts/release.sh <tag> [notes]}"
notes="${2:-}"
root="$(cd "$(dirname "$0")/.." && pwd)"
dist="$(mktemp -d)"
trap 'rm -rf "$dist"' EXIT

cd "$root"
for dir in */; do
  skill="${dir%/}"
  [ -f "$skill/SKILL.md" ] || continue
  zip -rq "$dist/$skill.zip" "$skill" -x "*.DS_Store"
done
ls -l "$dist"

git tag "$tag"
git push origin "$tag"
if [ -n "$notes" ]; then note_args=(--notes "$notes"); else note_args=(--generate-notes); fi
gh release create "$tag" "$dist"/*.zip --repo pandaitech/one-person-marketing-skills --title "$tag" "${note_args[@]}"
