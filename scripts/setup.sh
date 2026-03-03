#!/bin/bash
# One-time setup: create venv, install deps, create config
# Usage: bash ~/.claude/skills/gpt-researcher/scripts/setup.sh
set -euo pipefail

VENV_DIR="$HOME/.local/share/gpt-researcher/venv"
VENDOR_DIR="$HOME/cc/vendor/gpt-researcher"
CONFIG_DIR="$HOME/.config/gpt-researcher"

echo "=== GPT Researcher Setup ==="

# 1. Verify vendor dir exists
if [ ! -d "$VENDOR_DIR" ]; then
  echo "ERROR: Vendor dir not found at $VENDOR_DIR"
  echo "Run: cd ~/cc && git submodule add https://github.com/Tokyofloripa/gpt-researcher.git vendor/gpt-researcher"
  exit 1
fi

# 2. Create venv if missing
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtualenv at $VENV_DIR..."
  python3 -m venv "$VENV_DIR"
else
  echo "Venv exists at $VENV_DIR"
fi

# 3. Install gpt-researcher (editable)
echo "Installing gpt-researcher (editable from vendor)..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -e "$VENDOR_DIR"
"$VENV_DIR/bin/pip" install -U ddgs  # DuckDuckGo search (not auto-installed)

# 4. Create config dir + default config if missing
mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_DIR/config.json" ]; then
  echo "Creating default config at $CONFIG_DIR/config.json..."
  cat > "$CONFIG_DIR/config.json" << 'CONF'
{
  "RETRIEVER": "duckduckgo",
  "SMART_LLM": "openai:gpt-4.1",
  "FAST_LLM": "openai:gpt-4o-mini",
  "STRATEGIC_LLM": "openai:o4-mini",
  "EMBEDDING": "openai:text-embedding-3-small",
  "TOTAL_WORDS": 2000,
  "DEEP_RESEARCH_BREADTH": 4,
  "DEEP_RESEARCH_DEPTH": 2,
  "DEEP_RESEARCH_CONCURRENCY": 4,
  "REPORT_FORMAT": "APA",
  "IMAGE_GENERATION_ENABLED": false,
  "VERBOSE": true
}
CONF
else
  echo "Config exists at $CONFIG_DIR/config.json"
fi

# 5. Make scripts executable
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
chmod +x "$SCRIPT_DIR"/*.sh 2>/dev/null || true

# 6. Verify
echo ""
echo "=== Verification ==="
"$VENV_DIR/bin/python3" -c "
from gpt_researcher import GPTResearcher
print('  gpt-researcher package: OK')
from gpt_researcher.config.config import Config
print('  Config system: OK')
from gpt_researcher.skills.deep_research import DeepResearchSkill
print('  Deep research: OK')
try:
    from multi_agents.agents import ChiefEditorAgent
    print('  Multi-agent system: OK')
except ImportError:
    print('  Multi-agent system: SKIP (run from vendor dir)')
"

echo ""
echo "=== Setup Complete ==="
echo "Run health check: bash ~/.claude/skills/gpt-researcher/scripts/health.sh"
