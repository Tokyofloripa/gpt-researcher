"""GPT Researcher wrapper: query -> GPTResearcher -> structured JSON output.

Usage: python3 research.py "query" report_type config_path
  report_type: research_report | detailed_report | deep | outline_report | resource_report
  config_path: path to config.json or profile JSON

Output: JSON to stdout with keys: report, sources, source_count, costs_usd, elapsed_seconds, profile
"""
import asyncio
import json
import os
import sys
import time

# Load API keys from ~/cc/.env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.expanduser("~/cc/.env"))
except ImportError:
    # python-dotenv may not be installed; fall back to manual loading
    env_path = os.path.expanduser("~/cc/.env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value:
                        os.environ.setdefault(key, value)

from gpt_researcher import GPTResearcher
from gpt_researcher.utils.enum import Tone


def detect_profile_name(config_path: str) -> str:
    """Extract profile name from config path, or 'default' if config.json."""
    basename = os.path.basename(config_path)
    name = os.path.splitext(basename)[0]
    if name == "config":
        return "default"
    return name


async def main(query: str, report_type: str, config_path: str):
    start = time.time()
    profile_name = detect_profile_name(config_path)

    researcher = GPTResearcher(
        query=query,
        report_type=report_type,
        config_path=config_path,
        tone=Tone.Objective,
        verbose=True,
    )

    # Conduct research (search, scrape, filter, summarize)
    await researcher.conduct_research()

    # Generate report from collected context
    report = await researcher.write_report()

    elapsed = time.time() - start

    result = {
        "report": report,
        "sources": list(researcher.get_source_urls()),
        "source_count": len(researcher.get_source_urls()),
        "costs_usd": round(researcher.get_costs(), 4),
        "elapsed_seconds": round(elapsed, 1),
        "report_type": report_type,
        "query": query,
        "profile": profile_name,
        "config_path": config_path,
    }

    # Output JSON to stdout
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 research.py 'query' [report_type] [config_path]", file=sys.stderr)
        sys.exit(1)

    query = sys.argv[1]
    report_type = sys.argv[2] if len(sys.argv) > 2 else "research_report"
    config_path = sys.argv[3] if len(sys.argv) > 3 else os.path.expanduser(
        "~/.config/gpt-researcher/config.json"
    )

    asyncio.run(main(query, report_type, config_path))
