#!/bin/bash
# Verify GPT Researcher installation, config, API keys, and profile readiness.
# Usage: bash health.sh
set -euo pipefail

VENV="$HOME/.local/share/gpt-researcher/venv/bin/python3"

if [ ! -f "$VENV" ]; then
  echo "FAIL: Venv not found at $VENV"
  echo "Fix: bash ~/.claude/skills/gpt-researcher/scripts/setup.sh"
  exit 1
fi

# Load API keys
set -a
[ -f "$HOME/cc/.env" ] && source "$HOME/cc/.env"
set +a

"$VENV" -c "
import os
import sys

print('=== GPT Researcher Health Check ===')
print()

# 1. Package import
try:
    from gpt_researcher import GPTResearcher
    print('Package import: OK')
except ImportError as e:
    print(f'Package import: FAIL ({e})')
    sys.exit(1)

# 2. Config
try:
    from gpt_researcher.config.config import Config
    config_path = os.path.expanduser('~/.config/gpt-researcher/config.json')
    if os.path.exists(config_path):
        c = Config(config_path)
        print(f'Config loaded: OK ({config_path})')
    else:
        c = Config()
        print(f'Config: using defaults (no config.json found)')
    print(f'  Smart LLM:    {c.smart_llm_provider}:{c.smart_llm_model}')
    print(f'  Fast LLM:     {c.fast_llm_provider}:{c.fast_llm_model}')
    print(f'  Strategic LLM: {c.strategic_llm_provider}:{c.strategic_llm_model}')
    print(f'  Retrievers:   {c.retrievers}')
    print(f'  Embedding:    {c.embedding_provider}:{c.embedding_model}')
    print(f'  Deep Research: breadth={c.deep_research_breadth}, depth={c.deep_research_depth}, concurrency={c.deep_research_concurrency}')
    print(f'  Total words:  {c.total_words}')
except Exception as e:
    print(f'Config: FAIL ({e})')

# 3. Required API key
print()
api_key = os.getenv('OPENAI_API_KEY', '')
print(f'OPENAI_API_KEY: {\"SET (\" + api_key[:8] + \"...)\" if api_key else \"MISSING - REQUIRED\"}')

# 4. Premium retriever keys
print()
print('Premium retrievers:')

premium_keys = {
    'TAVILY_API_KEY': ('Tavily', 'tavily.com', 'thorough/government'),
    'EXA_API_KEY': ('Exa', 'exa.ai', 'thorough/government'),
    'SERPER_API_KEY': ('Serper', 'serper.dev', 'government'),
    'BING_API_KEY': ('Bing', 'Azure portal', 'government'),
}

premium_set = 0
premium_missing = []
for env_var, (name, signup, profiles) in premium_keys.items():
    val = os.getenv(env_var, '')
    if val:
        print(f'  {name + \":\":12s} SET ({signup})        <- will use in {profiles}')
        premium_set += 1
    else:
        print(f'  {name + \":\":12s} MISSING              <- {profiles} profile degraded')
        premium_missing.append(name)

# 5. Optional keys
print()
github_token = os.getenv('GITHUB_TOKEN', '')
print(f'GITHUB_TOKEN:   {\"SET\" if github_token else \"not set (optional)\"}')

# 6. Deep research skill
try:
    from gpt_researcher.skills.deep_research import DeepResearchSkill
    print()
    print('Deep research skill: OK')
except ImportError as e:
    print(f'Deep research skill: FAIL ({e})')

# 7. Multi-agent system
try:
    sys.path.insert(0, os.path.expanduser('~/cc/vendor/gpt-researcher'))
    from multi_agents.agents import ChiefEditorAgent
    print('Multi-agent system: OK')
except ImportError:
    print('Multi-agent system: SKIP (needs to run from vendor dir)')

# 8. Retriever availability
print()
print('Retriever backends:')
try:
    from gpt_researcher.retrievers import (
        Duckduckgo, TavilySearch, GoogleSearch, BingSearch,
        ArxivSearch, SemanticScholarSearch, PubMedCentralSearch, ExaSearch
    )
    tavily_key = os.getenv('TAVILY_API_KEY', '')
    exa_key = os.getenv('EXA_API_KEY', '')
    serper_key = os.getenv('SERPER_API_KEY', '')
    bing_key = os.getenv('BING_API_KEY', '')
    print('  DuckDuckGo:       OK (free, no key)')
    print(f'  Tavily:           {\"OK\" if tavily_key else \"needs TAVILY_API_KEY\"}')
    print(f'  Exa:              {\"OK\" if exa_key else \"needs EXA_API_KEY\"}')
    print(f'  Serper (Google):  {\"OK\" if serper_key else \"needs SERPER_API_KEY\"}')
    print(f'  Bing:             {\"OK\" if bing_key else \"needs BING_API_KEY\"}')
    print(f'  arXiv:            OK (free, no key)')
    print(f'  Semantic Scholar: OK (free, no key)')
    print(f'  PubMed Central:   OK (free, no key)')
except ImportError as e:
    print(f'  Retriever import error: {e}')

# 9. Profile readiness
print()
config_dir = os.path.expanduser('~/.config/gpt-researcher')
profiles = {
    'quick': [],
    'standard': [],
    'thorough': ['TAVILY_API_KEY', 'EXA_API_KEY'],
    'government': ['TAVILY_API_KEY', 'EXA_API_KEY', 'SERPER_API_KEY', 'BING_API_KEY'],
}

print('Profile readiness:')
for profile_name, required_keys in profiles.items():
    profile_path = os.path.join(config_dir, f'{profile_name}.json')
    if not os.path.exists(profile_path):
        print(f'  {profile_name:12s} MISSING (run enhance.sh)')
        continue
    missing = [k for k in required_keys if not os.getenv(k, '')]
    if missing:
        print(f'  {profile_name:12s} DEGRADED (missing: {\", \".join(missing)})')
    else:
        print(f'  {profile_name:12s} READY')

print()
print('=== Health check complete ===')
if premium_missing:
    print(f'Note: {len(premium_missing)} premium key(s) missing: {\", \".join(premium_missing)}')
    print('Profiles auto-degrade gracefully (fewer search indexes, still works).')
    print('Sign up: tavily.com, exa.ai, serper.dev, Azure portal')
"
