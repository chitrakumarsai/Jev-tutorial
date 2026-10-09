#!/usr/bin/env bash
# Runs the web lint, typecheck and format check with the Node version pinned in .nvmrc.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
NODE22_BIN="${HOME}/.nvm/versions/node/v$(cat "$ROOT/.nvmrc")/bin"
npm22() { PATH="$NODE22_BIN:$PATH" npm "$@"; }
npm22 --prefix "$ROOT/web" run --silent lint
npm22 --prefix "$ROOT/web" run --silent typecheck
npm22 --prefix "$ROOT/web" run --silent format:check
