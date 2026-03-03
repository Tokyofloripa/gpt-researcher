#!/bin/bash
# Run GPT Researcher from the isolated venv.
# Usage: research.sh "query" [report_type] [--profile NAME] [config_path]
#   report_type: research_report | detailed_report | deep | outline_report | resource_report
#   --profile NAME: use ~/.config/gpt-researcher/NAME.json (quick|standard|thorough|government)
#   config_path: explicit path to config JSON (overrides --profile)
#
# Output: JSON to stdout
# Examples:
#   bash research.sh "latest AI developments" deep
#   bash research.sh "latest AI developments" deep --profile government
#   bash research.sh "quick validation" research_report --profile quick
set -euo pipefail

VENV="$HOME/.local/share/gpt-researcher/venv/bin/python3"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$HOME/.config/gpt-researcher"

if [ ! -f "$VENV" ]; then
  echo '{"error": "Venv not found. Run: bash ~/.claude/skills/gpt-researcher/scripts/setup.sh"}' >&2
  exit 1
fi

# Parse arguments
QUERY="${1:?Usage: research.sh \"query\" [report_type] [--profile NAME]}"
REPORT_TYPE="${2:-research_report}"
CONFIG=""
REVIEW_FLAG=""

# Scan remaining args for --profile
shift 2 2>/dev/null || true
while [ $# -gt 0 ]; do
  case "$1" in
    --profile)
      PROFILE_NAME="${2:?--profile requires a name (quick|standard|thorough|government)}"
      PROFILE_PATH="$CONFIG_DIR/$PROFILE_NAME.json"
      if [ -f "$PROFILE_PATH" ]; then
        CONFIG="$PROFILE_PATH"
        echo "Using profile: $PROFILE_NAME ($PROFILE_PATH)" >&2
      else
        echo "WARNING: Profile '$PROFILE_NAME' not found. Available: quick, standard, thorough, government. Falling back to default." >&2
        CONFIG="$CONFIG_DIR/config.json"
      fi
      shift 2
      ;;
    --review)
      REVIEW_FLAG="--review"
      shift
      ;;
    --review-approved)
      REVIEW_FLAG="--review-approved"
      shift
      ;;
    *)
      # Treat as explicit config path (backwards compat)
      CONFIG="$1"
      shift
      ;;
  esac
done

# Default to config.json if no profile or explicit path given
CONFIG="${CONFIG:-$CONFIG_DIR/config.json}"

# Load API keys
set -a
[ -f "$HOME/cc/.env" ] && source "$HOME/cc/.env"
set +a

# Route: multi -> multi_research.py, everything else -> research.py
if [ "$REPORT_TYPE" = "multi" ]; then
  exec "$VENV" "$SCRIPT_DIR/multi_research.py" "$QUERY" "$CONFIG" ${REVIEW_FLAG:+"$REVIEW_FLAG"}
else
  exec "$VENV" "$SCRIPT_DIR/research.py" "$QUERY" "$REPORT_TYPE" "$CONFIG"
fi
