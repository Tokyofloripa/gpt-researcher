#!/bin/bash
# enhance.sh — One-shot setup: create all config profiles, install extras, verify.
# Usage: bash ~/.claude/skills/gpt-researcher/scripts/enhance.sh
# Idempotent: safe to run multiple times.
set -euo pipefail

CONFIG_DIR="$HOME/.config/gpt-researcher"
VENV_PIP="$HOME/.local/share/gpt-researcher/venv/bin/pip"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== GPT Researcher Enhancement Setup ==="
echo ""

# 1. Verify venv exists
if [ ! -f "$VENV_PIP" ]; then
  echo "ERROR: Venv not found. Run setup.sh first:"
  echo "  bash ~/.claude/skills/gpt-researcher/scripts/setup.sh"
  exit 1
fi

# 2. Create config directory
mkdir -p "$CONFIG_DIR"

# 3. Write profile configs (always overwrite to pick up latest specs)
echo "Creating config profiles..."

cat > "$CONFIG_DIR/quick.json" << 'EOF'
{
  "RETRIEVER": "duckduckgo",
  "SMART_LLM": "openai:gpt-4o-mini",
  "FAST_LLM": "openai:gpt-4o-mini",
  "STRATEGIC_LLM": "openai:gpt-4o-mini",
  "EMBEDDING": "openai:text-embedding-3-small",
  "MAX_SEARCH_RESULTS_PER_QUERY": 3,
  "TOTAL_WORDS": 1000,
  "DEEP_RESEARCH_BREADTH": 2,
  "DEEP_RESEARCH_DEPTH": 1,
  "DEEP_RESEARCH_CONCURRENCY": 2,
  "MAX_SCRAPER_WORKERS": 10,
  "CURATE_SOURCES": false,
  "REPORT_FORMAT": "APA",
  "VERBOSE": true
}
EOF
echo "  quick.json      — smoke test (~\$0.10, 30s)"

cat > "$CONFIG_DIR/standard.json" << 'EOF'
{
  "RETRIEVER": "duckduckgo,arxiv,semantic_scholar,pubmed_central",
  "SMART_LLM": "openai:gpt-4.1",
  "FAST_LLM": "openai:gpt-4o-mini",
  "STRATEGIC_LLM": "openai:o4-mini",
  "EMBEDDING": "openai:text-embedding-3-small",
  "MAX_SEARCH_RESULTS_PER_QUERY": 8,
  "TOTAL_WORDS": 2000,
  "DEEP_RESEARCH_BREADTH": 4,
  "DEEP_RESEARCH_DEPTH": 2,
  "DEEP_RESEARCH_CONCURRENCY": 4,
  "MAX_SCRAPER_WORKERS": 15,
  "CURATE_SOURCES": true,
  "REPORT_FORMAT": "APA",
  "VERBOSE": true
}
EOF
echo "  standard.json   — regular research (~\$0.50, 2min)"

cat > "$CONFIG_DIR/thorough.json" << 'EOF'
{
  "RETRIEVER": "duckduckgo,tavily,exa,arxiv,semantic_scholar,pubmed_central",
  "SMART_LLM": "openai:gpt-4.1",
  "FAST_LLM": "openai:gpt-4o-mini",
  "STRATEGIC_LLM": "openai:o4-mini",
  "EMBEDDING": "openai:text-embedding-3-small",
  "MAX_SEARCH_RESULTS_PER_QUERY": 15,
  "TOTAL_WORDS": 4000,
  "SMART_TOKEN_LIMIT": 8000,
  "DEEP_RESEARCH_BREADTH": 6,
  "DEEP_RESEARCH_DEPTH": 3,
  "DEEP_RESEARCH_CONCURRENCY": 6,
  "MAX_SCRAPER_WORKERS": 30,
  "CURATE_SOURCES": true,
  "REPORT_FORMAT": "APA",
  "VERBOSE": true
}
EOF
echo "  thorough.json   — important work (~\$3, 10min)"

cat > "$CONFIG_DIR/government.json" << 'EOF'
{
  "RETRIEVER": "duckduckgo,tavily,exa,serper,bing,arxiv,semantic_scholar,pubmed_central",
  "SMART_LLM": "openai:gpt-4.1",
  "FAST_LLM": "openai:gpt-4o-mini",
  "STRATEGIC_LLM": "openai:o4-mini",
  "EMBEDDING": "openai:text-embedding-3-small",
  "MAX_SEARCH_RESULTS_PER_QUERY": 20,
  "TOTAL_WORDS": 6000,
  "SMART_TOKEN_LIMIT": 12000,
  "FAST_TOKEN_LIMIT": 4000,
  "DEEP_RESEARCH_BREADTH": 8,
  "DEEP_RESEARCH_DEPTH": 4,
  "DEEP_RESEARCH_CONCURRENCY": 8,
  "MAX_SCRAPER_WORKERS": 50,
  "CURATE_SOURCES": true,
  "REPORT_FORMAT": "APA",
  "VERBOSE": true
}
EOF
echo "  government.json — maximum coverage (~\$10-20, 30min+)"

# 4. Install extra pip deps (idempotent)
echo ""
echo "Checking extra dependencies..."
"$VENV_PIP" install -q -U ddgs 2>/dev/null && echo "  ddgs: OK" || echo "  ddgs: already installed"

# 5. Run health check
echo ""
echo "Running health check..."
bash "$SCRIPT_DIR/health.sh"

echo ""
echo "=== Enhancement Complete ==="
echo "Profiles available: quick, standard, thorough, government"
echo "Usage: bash ~/.claude/skills/gpt-researcher/scripts/research.sh \"query\" deep --profile government"
