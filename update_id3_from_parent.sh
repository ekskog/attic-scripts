#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 [--apply] [--pattern '<glob>'] [--tag artist|album|title]

Defaults:
  --pattern '*.mp3'
  --tag artist    # sets the ID3 `artist` from the parent directory name

Options:
  --apply         Actually modify files. Omit for a dry-run.
  --pattern       Glob pattern passed to find (quote it).
  --tag           Which tag to set: artist (default), album, or title.

Examples:
  # dry-run (default)
  $0

  # apply changes
  $0 --apply

  # dry-run for all mp3s in repo matching pattern
  $0 --pattern '*.mp3'
EOF
}

APPLY=0
PATTERN='*.mp3'
TAG='artist'

while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --pattern) PATTERN="$2"; shift 2 ;;
    --tag) TAG="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [ "$TAG" != "artist" ] && [ "$TAG" != "album" ] && [ "$TAG" != "title" ]; then
  echo "Invalid tag: $TAG" >&2
  exit 2
fi

if [ "$APPLY" -eq 1 ] && ! command -v eyeD3 >/dev/null 2>&1; then
  echo "eyeD3 not found. Install it first (apt/pip)." >&2
  exit 2
fi

find . -type f -name "$PATTERN" -print0 | while IFS= read -r -d '' f; do
  case "$TAG" in
    artist)
      value=$(basename "$(dirname "$f")")
      ;;
    album)
      value=$(basename "$(dirname "$(dirname "$f")")")
      if [ -z "$value" ] || [ "$value" = "." ]; then
        value=$(basename "$(dirname "$f")")
      fi
      ;;
    title)
      value="$(basename "$f" .mp3)"
      ;;
  esac

  if [ "$APPLY" -eq 0 ]; then
    printf "DRY: would set %s='%s' for %s\n" "$TAG" "$value" "$f"
  else
    printf "APPLY: setting %s='%s' for %s\n" "$TAG" "$value" "$f"
    echo "eyeD3 --${TAG} \"${value}\" \"${f}\""
    eyeD3 --${TAG} "${value}" "${f}"
  fi
done

exit 0
