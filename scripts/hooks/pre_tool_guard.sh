#!/usr/bin/env bash
# PreToolUse guard: protect secrets and the $5-per-key API budget.
#   - deny : reading/writing/searching real .env files (secrets); .env.example is fine
#   - ask  : anything that enables or triggers live (paid) API calls
# Fails closed: if the hook input can't be parsed, the tool call is denied.
set -uo pipefail

deny_raw() {  # used before jq is known to work
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$1"
  exit 0
}
command -v jq >/dev/null 2>&1 || deny_raw "Guard unavailable: jq is not installed."

input="$(cat)"
tool="$(jq -er '.tool_name' <<<"$input" 2>/dev/null)" || deny_raw "Guard could not parse the tool call."

decide() {  # $1 = deny|ask, $2 = reason
  jq -n --arg d "$1" --arg r "$2" \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: $d, permissionDecisionReason: $r}}'
  exit 0
}

# A real dotenv file: .env or .env.<anything> except .env.example (case-insensitive).
SECRET_ENV_RE='(^|[^A-Za-z0-9_])\.env(\.[A-Za-z0-9_-]+)?([^A-Za-z0-9_.-]|$)'
EXAMPLE_ONLY_RE='\.env\.example'

mentions_secret_env() {  # $1 = text; true if it references a dotenv file other than .env.example
  local text="${1//$'\n'/ }"
  local stripped
  stripped="$(sed -E "s/${EXAMPLE_ONLY_RE}//Ig" <<<"$text")"
  grep -Eiq "$SECRET_ENV_RE" <<<"$stripped"
}

case "$tool" in
  Read|Edit|MultiEdit|Write|NotebookEdit)
    path="$(jq -r '.tool_input.file_path // .tool_input.notebook_path // empty' <<<"$input")"
    if [[ -n "$path" ]] && mentions_secret_env "$path"; then
      decide deny "Blocked: $path holds API keys. Ask the presenter to edit it directly."
    fi
    ;;
  Grep|Glob)
    target="$(jq -r '[.tool_input.path, .tool_input.glob, .tool_input.pattern] | map(select(. != null)) | join(" ")' <<<"$input")"
    if mentions_secret_env "$target"; then
      decide deny "Blocked: searching dotenv files would expose API keys."
    fi
    ;;
  Bash)
    cmd="$(jq -r '.tool_input.command // empty' <<<"$input")"
    if mentions_secret_env "$cmd" || grep -Eiq '(^|[^A-Za-z0-9_])(printenv|dotenv)([^A-Za-z0-9_]|$)' <<<"$cmd"; then
      decide deny "Blocked: command touches a dotenv file or dumps environment variables that hold API keys."
    fi
    if grep -Eiq 'LIVE_ENABLED["'\'' ]*=["'\'' ]*(1|true|yes|on)|jev[ ._-]*(cli)?[^|;&]*[ ._-](record|live)([^A-Za-z]|$)|api\.openai\.com|api\.typesafe\.ai' <<<"$cmd"; then
      decide ask "This command enables or makes live API calls that spend from the \$5-per-key budget. Approve only if intended."
    fi
    ;;
esac
exit 0
