# Multi-Agent System Reference

## Table of Contents
- [Overview](#overview)
- [Agent Roles](#agent-roles)
- [Workflow](#workflow)
- [Usage](#usage)

---

## Overview

**Directory:** `multi_agents/`

LangGraph-based system inspired by [STORM paper](https://arxiv.org/abs/2402.14207). Generates 5-6 page reports with multiple agents collaborating.

---

## Agent Roles

| Agent | File | Role |
|-------|------|------|
| Human | - | Oversees and provides feedback |
| Chief Editor | `agents/editor.py` | Master coordinator via LangGraph |
| Researcher | Uses GPTResearcher | Deep research on topics |
| Editor | `agents/editor.py` | Plans outline and structure |
| Reviewer | `agents/reviewer.py` | Validates research correctness |
| Revisor | `agents/revisor.py` | Revises based on feedback |
| Writer | `agents/writer.py` | Compiles final report |
| Publisher | `agents/publisher.py` | Exports to PDF, DOCX, Markdown |

---

## Workflow

```
1. Browser (GPTResearcher) → Initial research
2. Editor → Plans report outline
3. For each outline topic (parallel):
   a. Researcher → In-depth subtopic research
   b. Reviewer → Validates draft
   c. Revisor → Revises until satisfactory
4. Writer → Compiles final report
5. Publisher → Exports to multiple formats
```

---

## Usage

### Via API

```python
report_type = "multi_agents"
```

### Via WebSocket

```json
{
    "task": "Research query",
    "report_type": "multi_agents",
    "tone": "Analytical"
}
```

### Directly in Python

```python
from multi_agents import run_research_task

report = await run_research_task(
    query="Comprehensive analysis of market trends",
    websocket=handler,
    tone=Tone.Analytical,
)
```

### Configuration File

**File:** `multi_agents/task.json`

Configure the multi-agent research task parameters and agent behaviors.

---

## Integration: Claude Code Workflow

### Architecture

`research.sh multi` → `multi_research.py` → `ChiefEditorAgent` → structured output

### Profile → task.json Mapping

| Profile | max_sections | model | follow_guidelines | guidelines |
|---------|-------------|-------|-------------------|------------|
| quick | 3 | gpt-4o-mini | false | none |
| standard | 5 | gpt-4.1 | true | APA + hyperlinks |
| thorough | 7 | gpt-4.1 | true | APA + hyperlinks + cross-ref |
| government | 9 | gpt-4.1 | true | full set |

### Human Review Gate

Two-pass invocation via `--review` / `--review-approved`:
1. `--review`: Pipeline pauses at human node, user provides feedback via input()
2. `--review-approved` with piped stdin: Injects feedback JSON into pipeline

### Output Routing

Publisher writes to `./outputs/run_{id}_{query}/` → `multi_research.py` copies to `~/cc/output/research/<date>-<slug>/` → cleans up vendor dir.

### Troubleshooting

- **Import errors**: Run `cd ~/cc/vendor/gpt-researcher && pip install -e .`
- **PDF fails**: Install system deps: `brew install cairo pango gdk-pixbuf`
- **Timeout on thorough**: 7 sections × full GPTResearcher can take 20+ min. Use quick for validation.
- **weasyprint OSError**: The import raises OSError (not ImportError) if system libs are missing. Already handled.
- **Relative path bug**: `chief.output_dir` is relative; resolved to absolute before os.chdir(original_cwd).
