#!/usr/bin/env bash
# ai-test-runner.sh — "Log Firewall" (Headroom-inspired)
#
# Wraps any test/build command, strips noise, returns ≤15 high-signal lines
# with project file path, line number, and error message.
#
# Usage:
#   ~/.agent-template/scripts/ai-test-runner.sh npm run build
#   ~/.agent-template/scripts/ai-test-runner.sh npx playwright test
#   ~/.agent-template/scripts/ai-test-runner.sh --max 10 npm test
#
# Env:
#   AI_TEST_MAX_LINES      default max lines (default 15)
#   AI_TEST_PROJECT_ROOT   project root for context header (default: cwd)

set -uo pipefail

MAX_LINES="${AI_TEST_MAX_LINES:-15}"
PROJECT_ROOT="${AI_TEST_PROJECT_ROOT:-$(pwd)}"

if [[ "${1:-}" == "--max" ]]; then
  MAX_LINES="${2:-15}"
  shift 2
fi

if [[ $# -lt 1 ]]; then
  echo "Usage: ai-test-runner.sh [--max N] <command> [args...]" >&2
  exit 2
fi

strip_ansi() {
  sed -E $'s/\x1B\\[[0-9;?]*[a-zA-Z]//g; s/\x1B\\][^\x07]*\x07//g; s/\x1B\\([A-Z]//g'
}

is_noise_line() {
  local line="$1"
  [[ -z "${line//[[:space:]]/}" ]] && return 0
  case "$line" in
    */node_modules/*|*'\\node_modules\\'*|*node:internal/*) return 0 ;;
    *'at Module._compile'*|*'at Object.<anonymous>'*|*'at Module.load'*) return 0 ;;
    *'at Function.Module'*|*'at TracingChannel'*|*'at processTicksAndRejections'*) return 0 ;;
    *'DeprecationWarning'*|*'ExperimentalWarning'*|*'npm warn'*|*'npm notice'*) return 0 ;;
    *'[dotenv'*|*'webpack compiled'*|*'Compiled successfully'*) return 0 ;;
  esac
  # Passing checkmarks / green PASS noise
  [[ "$line" == *"✓ "* || "$line" == *"√ "* || "$line" == *"✔ "* ]] && return 0
  [[ "$line" == PASS\ * ]] && return 0
  return 1
}

score_line() {
  local line="$1"
  local score=0

  echo "$line" | grep -qiE '(^|[^a-zA-Z])(error|fail(ed|ure)?|exception|assert|panic|fatal)([^a-zA-Z]|$)' \
    && score=$((score + 50))
  echo "$line" | grep -qiE 'TypeError|ReferenceError|SyntaxError|RangeError|ENOENT|EADDRINUSE' \
    && score=$((score + 40))
  echo "$line" | grep -qiE 'Expected|Received|AssertionError' && score=$((score + 30))
  echo "$line" | grep -qE 'TS[0-9]{4}' && score=$((score + 35))
  echo "$line" | grep -qiE '(^|[^a-zA-Z])warn(ing)?([^a-zA-Z]|$)' && score=$((score + 10))

  if echo "$line" | grep -qE '(src|app|lib|tests?|e2e|pages|components|server|api|config|core|models|scrapers|aggregator)[/\\][^[:space:](:]+\.(py|[jt]sx?)[:\(][0-9]+'; then
    score=$((score + 45))
  elif echo "$line" | grep -qE '\.(ts|tsx|js|jsx|mjs|cjs)[:\(][0-9]+'; then
    if echo "$line" | grep -qvE 'node_modules'; then
      score=$((score + 25))
    fi
  fi

  if echo "$line" | grep -qE '^[[:space:]]*at '; then
    if echo "$line" | grep -qvE 'node_modules|node:internal'; then
      score=$((score + 20))
    else
      score=$((score - 100))
    fi
  fi

  printf '%s' "$score"
}

extract_focus() {
  local line="$1"
  local focus
  focus=$(printf '%s' "$line" \
    | grep -oE '(src|app|lib|tests?|e2e|pages|components|server|api|config|core|models|scrapers|aggregator)[/\\][^[:space:](:]+\.(py|[jt]sx?)(:[0-9]+(:[0-9]+)?|\([0-9]+(,[0-9]+)?\))?' \
    | head -1 || true)
  printf '%s' "$focus"
}

# --- capture once -------------------------------------------------------
OUT_FILE=$(mktemp "${TMPDIR:-/tmp}/ai-test-runner.XXXXXX")
trap 'rm -f "$OUT_FILE"' EXIT

set +e
"$@" >"$OUT_FILE" 2>&1
STATUS=$?
set -e

# --- filter & rank ------------------------------------------------------
RANK_FILE=$(mktemp "${TMPDIR:-/tmp}/ai-test-rank.XXXXXX")
trap 'rm -f "$OUT_FILE" "$RANK_FILE"' EXIT

LINE_NO=0
while IFS= read -r raw || [[ -n "$raw" ]]; do
  LINE_NO=$((LINE_NO + 1))
  line=$(printf '%s' "$raw" | strip_ansi)
  is_noise_line "$line" && continue
  sc=$(score_line "$line")
  [[ "$sc" -le 0 ]] && continue
  # score \t original_order \t line  (stable secondary sort)
  printf '%s\t%06d\t%s\n' "$sc" "$LINE_NO" "$line" >>"$RANK_FILE"
done <"$OUT_FILE"

echo "=== ai-test-runner: max ${MAX_LINES} lines (exit ${STATUS}) ==="
echo "cwd: ${PROJECT_ROOT}"
echo "cmd: $*"
echo "---"

COUNT=0
declare -A SEEN=()

if [[ -s "$RANK_FILE" ]]; then
  # Sort by score desc, then original order asc
  while IFS=$'\t' read -r sc ord line; do
    focus=$(extract_focus "$line")
    key="${focus}|${line:0:160}"
    [[ -n "${SEEN[$key]+x}" ]] && continue
    SEEN[$key]=1

    if [[ -n "$focus" ]]; then
      printf '[%s] %s\n' "$focus" "$line"
    else
      printf '%s\n' "$line"
    fi
    COUNT=$((COUNT + 1))
    [[ "$COUNT" -ge "$MAX_LINES" ]] && break
  done < <(sort -t$'\t' -k1,1nr -k2,2n "$RANK_FILE")
fi

if [[ "$COUNT" -eq 0 ]]; then
  if [[ "$STATUS" -eq 0 ]]; then
    echo "(ok — no errors after firewall)"
  else
    echo "(firewall: no ranked lines; last raw tail)"
    strip_ansi <"$OUT_FILE" | grep -vE 'node_modules|node:internal' | tail -n "$MAX_LINES"
  fi
fi

echo "---"
echo "exit: ${STATUS}"
exit "$STATUS"
