---
name: gpt-researcher
description: GPT Researcher is an autonomous deep research agent that conducts web and local research, producing detailed reports with citations. Use this skill when helping developers understand, extend, debug, or integrate with GPT Researcher - including adding features, understanding the architecture, working with the API, customizing research workflows, adding new retrievers, integrating MCP data sources, or troubleshooting research pipelines.
---

## Running Research (Usage)

### Prerequisites
- Venv: `~/.local/share/gpt-researcher/venv/` (run `setup.sh` if missing)
- Config: `~/.config/gpt-researcher/config.json`
- API key: `OPENAI_API_KEY` must be set in `~/cc/.env`
- First-time setup: `bash ~/.claude/skills/gpt-researcher/scripts/setup.sh`
- Enhancement (profiles): `bash ~/.claude/skills/gpt-researcher/scripts/enhance.sh`

### Research Profiles

| Profile | Retrievers | Deep (BxD) | Sources | Cost | Time |
|---------|-----------|------------|---------|------|------|
| quick | 1 free | 2x1 | 10-15 | ~$0.10 | 30s |
| standard | 4 free | 4x2 | 30-50 | ~$0.50 | 2min |
| thorough | 4 free + 2 premium | 6x3 | 80-150 | ~$3 | 10min |
| government | 4 free + 4 premium | 8x4 | 200-500 | ~$10-20 | 30min+ |

Profiles auto-degrade: if a premium key is missing, that retriever is skipped.

### Commands

**Standard Research Report (~2 min)**
```
bash ~/.claude/skills/gpt-researcher/scripts/research.sh "QUERY" research_report
```

**Deep Research with profile (~varies)**
```
bash ~/.claude/skills/gpt-researcher/scripts/research.sh "QUERY" deep --profile standard
bash ~/.claude/skills/gpt-researcher/scripts/research.sh "QUERY" deep --profile thorough
bash ~/.claude/skills/gpt-researcher/scripts/research.sh "QUERY" deep --profile government
```

**Quick smoke test (~30s, ~$0.10)**
```
bash ~/.claude/skills/gpt-researcher/scripts/research.sh "QUERY" research_report --profile quick
```

**Multi-Agent Research (7-agent LangGraph pipeline, magazine-quality reports)**
```
# Autonomous mode — runs all 7 agents end-to-end
bash ~/.claude/skills/gpt-researcher/scripts/research.sh "QUERY" multi --profile standard

# Human review mode — pauses after outline for approval
bash ~/.claude/skills/gpt-researcher/scripts/research.sh "QUERY" multi --profile thorough --review

# Quick smoke test (~3-5 min, ~$0.50)
bash ~/.claude/skills/gpt-researcher/scripts/research.sh "QUERY" multi --profile quick
```

**Multi-agent profiles:**

| Profile    | Sections | Model       | Guidelines | Time     | Cost    |
|------------|----------|-------------|------------|----------|---------|
| quick      | 3        | gpt-4o-mini | off        | 3-5 min  | ~$0.50  |
| standard   | 5        | gpt-4.1     | APA + refs | 8-15 min | ~$2-4   |
| thorough   | 7        | gpt-4.1     | APA + refs + cross-ref | 15-30 min | ~$5-10 |
| government | 9        | gpt-4.1     | full       | 30-60 min | ~$10-20 |

Output: `~/cc/output/research/<date>-<slug>/` with report.md, metadata.json, and optionally report.pdf/docx.

Pipeline: Browser → Planner → [Human Review] → Parallel Researchers → Reviewer/Reviser → Writer → Publisher.

**All report types:** research_report, detailed_report, deep, outline_report, resource_report, multi

### Output Format (JSON)
All scripts output JSON to stdout:
```json
{
  "report": "# Full markdown report with citations...",
  "sources": ["https://...", "https://..."],
  "source_count": 23,
  "costs_usd": 0.12,
  "elapsed_seconds": 145.3,
  "report_type": "research_report",
  "query": "original query",
  "profile": "standard",
  "config_path": "/path/to/profile.json"
}
```

### Parallel with last60days
For maximum research coverage, dispatch both skills as parallel Task agents:
- **Task 1**: GPT Researcher deep mode (deep web research, academic sources, 50+ sources)
- **Task 2**: /last60days (engagement-scored social signals: Reddit, X, HN, GitHub, YouTube)
Synthesize both outputs — they provide complementary perspectives.

### Operational Commands

**Health check** (imports, config, keys, profile readiness):
```
bash ~/.claude/skills/gpt-researcher/scripts/health.sh
```

**Enhancement setup** (create profiles, install extras):
```
bash ~/.claude/skills/gpt-researcher/scripts/enhance.sh
```

**Sync upstream** (merge upstream changes safely):
```
bash ~/.claude/skills/gpt-researcher/scripts/sync-upstream.sh
```

### Premium Retrievers

| Retriever | Env Var | Used In | Sign-up |
|-----------|---------|---------|---------|
| Tavily | `TAVILY_API_KEY` | thorough, government | tavily.com |
| Exa | `EXA_API_KEY` | thorough, government | exa.ai |
| Serper | `SERPER_API_KEY` | government | serper.dev |
| Bing | `BING_API_KEY` | government | Azure portal |

Add keys to `~/cc/.env`. Run `health.sh` to verify.

---

# GPT Researcher Development Skill

GPT Researcher is an LLM-based autonomous agent using a planner-executor-publisher pattern with parallelized agent work for speed and reliability.

## Quick Start

### Basic Python Usage

```python
from gpt_researcher import GPTResearcher
import asyncio

async def main():
    researcher = GPTResearcher(
        query="What are the latest AI developments?",
        report_type="research_report",  # or detailed_report, deep, outline_report
        report_source="web",            # or local, hybrid
    )
    await researcher.conduct_research()
    report = await researcher.write_report()
    print(report)

asyncio.run(main())
```

### Run Servers

```bash
# Backend
python -m uvicorn backend.server.server:app --reload --port 8000

# Frontend
cd frontend/nextjs && npm install && npm run dev
```

---

## Key File Locations

| Need | Primary File | Key Classes |
|------|--------------|-------------|
| Main orchestrator | `gpt_researcher/agent.py` | `GPTResearcher` |
| Research logic | `gpt_researcher/skills/researcher.py` | `ResearchConductor` |
| Report writing | `gpt_researcher/skills/writer.py` | `ReportGenerator` |
| All prompts | `gpt_researcher/prompts.py` | `PromptFamily` |
| Configuration | `gpt_researcher/config/config.py` | `Config` |
| Config defaults | `gpt_researcher/config/variables/default.py` | `DEFAULT_CONFIG` |
| API server | `backend/server/app.py` | FastAPI `app` |
| Search engines | `gpt_researcher/retrievers/` | Various retrievers |

---

## Architecture Overview

```
User Query → GPTResearcher.__init__()
                │
                ▼
         choose_agent() → (agent_type, role_prompt)
                │
                ▼
         ResearchConductor.conduct_research()
           ├── plan_research() → sub_queries
           ├── For each sub_query:
           │     └── _process_sub_query() → context
           └── Aggregate contexts
                │
                ▼
         [Optional] ImageGenerator.plan_and_generate_images()
                │
                ▼
         ReportGenerator.write_report() → Markdown report
```

**For detailed architecture diagrams**: See [references/architecture.md](references/architecture.md)

---

## Core Patterns

### Adding a New Feature (8-Step Pattern)

1. **Config** → Add to `gpt_researcher/config/variables/default.py`
2. **Provider** → Create in `gpt_researcher/llm_provider/my_feature/`
3. **Skill** → Create in `gpt_researcher/skills/my_feature.py`
4. **Agent** → Integrate in `gpt_researcher/agent.py`
5. **Prompts** → Update `gpt_researcher/prompts.py`
6. **WebSocket** → Events via `stream_output()`
7. **Frontend** → Handle events in `useWebSocket.ts`
8. **Docs** → Create `docs/docs/gpt-researcher/gptr/my_feature.md`

**For complete feature addition guide with Image Generation case study**: See [references/adding-features.md](references/adding-features.md)

### Adding a New Retriever

```python
# 1. Create: gpt_researcher/retrievers/my_retriever/my_retriever.py
class MyRetriever:
    def __init__(self, query: str, headers: dict = None):
        self.query = query
    
    async def search(self, max_results: int = 10) -> list[dict]:
        # Return: [{"title": str, "href": str, "body": str}]
        pass

# 2. Register in gpt_researcher/actions/retriever.py
case "my_retriever":
    from gpt_researcher.retrievers.my_retriever import MyRetriever
    return MyRetriever

# 3. Export in gpt_researcher/retrievers/__init__.py
```

**For complete retriever documentation**: See [references/retrievers.md](references/retrievers.md)

---

## Configuration

Config keys are **lowercased** when accessed:

```python
# In default.py: "SMART_LLM": "gpt-4o"
# Access as: self.cfg.smart_llm  # lowercase!
```

Priority: Environment Variables → JSON Config File → Default Values

**For complete configuration reference**: See [references/config-reference.md](references/config-reference.md)

---

## Common Integration Points

### WebSocket Streaming

```python
class WebSocketHandler:
    async def send_json(self, data):
        print(f"[{data['type']}] {data.get('output', '')}")

researcher = GPTResearcher(query="...", websocket=WebSocketHandler())
```

### MCP Data Sources

```python
researcher = GPTResearcher(
    query="Open source AI projects",
    mcp_configs=[{
        "name": "github",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_TOKEN": os.getenv("GITHUB_TOKEN")}
    }],
    mcp_strategy="deep",  # or "fast", "disabled"
)
```

**For MCP integration details**: See [references/mcp.md](references/mcp.md)

### Deep Research Mode

```python
researcher = GPTResearcher(
    query="Comprehensive analysis of quantum computing",
    report_type="deep",  # Triggers recursive tree-like exploration
)
```

**For deep research configuration**: See [references/deep-research.md](references/deep-research.md)

---

## Error Handling

Always use graceful degradation in skills:

```python
async def execute(self, ...):
    if not self.is_enabled():
        return []  # Don't crash
    
    try:
        result = await self.provider.execute(...)
        return result
    except Exception as e:
        await stream_output("logs", "error", f"⚠️ {e}", self.websocket)
        return []  # Graceful degradation
```

---

## Critical Gotchas

| ❌ Mistake | ✅ Correct |
|-----------|-----------|
| `config.MY_VAR` | `config.my_var` (lowercased) |
| Editing pip-installed package | `pip install -e .` |
| Forgetting async/await | All research methods are async |
| `websocket.send_json()` on None | Check `if websocket:` first |
| Not registering retriever | Add to `retriever.py` match statement |

---

## Reference Documentation

| Topic | File |
|-------|------|
| System architecture & diagrams | [references/architecture.md](references/architecture.md) |
| Core components & signatures | [references/components.md](references/components.md) |
| Research flow & data flow | [references/flows.md](references/flows.md) |
| Prompt system | [references/prompts.md](references/prompts.md) |
| Retriever system | [references/retrievers.md](references/retrievers.md) |
| MCP integration | [references/mcp.md](references/mcp.md) |
| Deep research mode | [references/deep-research.md](references/deep-research.md) |
| Multi-agent system | [references/multi-agents.md](references/multi-agents.md) |
| Adding features guide | [references/adding-features.md](references/adding-features.md) |
| Advanced patterns | [references/advanced-patterns.md](references/advanced-patterns.md) |
| REST & WebSocket API | [references/api-reference.md](references/api-reference.md) |
| Configuration variables | [references/config-reference.md](references/config-reference.md) |
