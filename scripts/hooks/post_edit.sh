#!/usr/bin/env bash
# PostToolUse hook (Write|Edit): format + lint the file Claude just edited.
# Input: hook JSON on stdin. Exit 2 = report unfixable lint errors back to Claude.
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
NODE22_BIN="${HOME}/.nvm/versions/node/v$(cat "$ROOT/.nvmrc")/bin"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT/.cache/uv}"
export npm_config_cache="${npm_config_cache:-$ROOT/.cache/npm}"

file="$(jq -r '.tool_input.file_path // .tool_response.filePath // empty')"
[[ -z "$file" || ! -f "$file" ]] && exit 0
file="$(realpath -- "$file")" || exit 0   # resolve .. and symlinks before the repo check
case "$file" in "$ROOT"/*) ;; *) exit 0 ;; esac   # only files inside this repo
rel="${file#"$ROOT"/}"

report() { printf '%s\n' "$1" >&2; exit 2; }

case "$rel" in
  *.py)
    cd "$ROOT" || exit 0
    uv run --quiet ruff format --quiet -- "$rel"
    out="$(uv run --quiet ruff check --fix --quiet -- "$rel" 2>&1)" || report "ruff found issues in $rel:"$'\n'"$out"
    ;;
  web/node_modules/*|web/dist/*|web/coverage/*) ;;
  web/*.ts|web/*.tsx|web/*.js|web/*.css|web/*.json)
    cd "$ROOT/web" || exit 0
    target="${rel#web/}"
    PATH="$NODE22_BIN:$PATH" ./node_modules/.bin/prettier --write --log-level warn -- "$target" >/dev/null
    case "$target" in
      *.ts|*.tsx|*.js)
        out="$(PATH="$NODE22_BIN:$PATH" ./node_modules/.bin/eslint --fix -- "$target" 2>&1)" || report "eslint found issues in $rel:"$'\n'"$out"
        ;;
    esac
    ;;
esac
exit 0
