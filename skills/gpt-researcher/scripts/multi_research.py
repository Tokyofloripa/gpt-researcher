"""Multi-agent research wrapper: query -> ChiefEditorAgent -> structured output.

Usage: python3 multi_research.py "query" config_path [--review|--review-approved]

Invoked by research.sh when report_type=multi. Creates task.json from profile,
runs the 7-agent LangGraph pipeline, copies outputs to structured dirs.
"""
import asyncio
import json
import os
import re
import shutil
import sys
import time
from datetime import date

# Load API keys from ~/cc/.env
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

# ---------------------------------------------------------------------------
# Profile configuration
# ---------------------------------------------------------------------------

MULTI_PROFILES = {
    "quick": {
        "max_sections": 3,
        "model": "gpt-4o-mini",
        "follow_guidelines": False,
        "guidelines": [],
    },
    "standard": {
        "max_sections": 5,
        "model": "gpt-4.1",
        "follow_guidelines": True,
        "guidelines": [
            "Use APA citation format",
            "All factual claims must include hyperlinked source references",
        ],
    },
    "thorough": {
        "max_sections": 7,
        "model": "gpt-4.1",
        "follow_guidelines": True,
        "guidelines": [
            "Use APA citation format",
            "All factual claims must include hyperlinked source references",
            "Cross-reference claims across multiple sources for accuracy",
        ],
    },
    "government": {
        "max_sections": 9,
        "model": "gpt-4.1",
        "follow_guidelines": True,
        "guidelines": [
            "Use APA citation format",
            "All factual claims must include hyperlinked source references",
            "Cross-reference claims across multiple sources for accuracy",
            "Present balanced perspectives including counterarguments",
        ],
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def detect_profile_name(config_path: str) -> str:
    """Extract profile name from config path, or 'default' if config.json."""
    name = os.path.splitext(os.path.basename(config_path))[0]
    return "default" if name == "config" else name


def make_slug(query: str, max_words: int = 5) -> str:
    """Convert query to a filesystem-safe slug."""
    words = re.sub(r"[^a-zA-Z0-9\s]", "", query).lower().split()
    return "-".join(words[:max_words]) or "research"


def make_output_dir(query: str) -> str:
    """Build structured output path: ~/cc/output/research/date-slug/"""
    today = date.today().isoformat()
    slug = make_slug(query)
    return os.path.expanduser(f"~/cc/output/research/{today}-{slug}")


def check_deps() -> None:
    """Verify LangGraph and multi_agents are importable."""
    vendor = os.path.expanduser("~/cc/vendor/gpt-researcher")
    if vendor not in sys.path:
        sys.path.insert(0, vendor)
    try:
        from multi_agents.agents.orchestrator import ChiefEditorAgent  # noqa: F401
    except ImportError as e:
        print(json.dumps({
            "error": f"Multi-agent dependencies missing: {e}",
            "fix": f"cd {vendor} && pip install -e .",
        }), file=sys.stderr)
        sys.exit(1)


def check_optional_formats() -> tuple:
    """Check for PDF/DOCX export dependencies. Returns (pdf_ok, docx_ok)."""
    pdf_ok = False
    docx_ok = False
    try:
        import weasyprint  # noqa: F401
        pdf_ok = True
    except (ImportError, OSError):
        print("INFO: weasyprint not available — PDF export disabled", file=sys.stderr)
    try:
        import docx  # noqa: F401
        docx_ok = True
    except (ImportError, OSError):
        print("INFO: python-docx not available — DOCX export disabled", file=sys.stderr)
    return pdf_ok, docx_ok


def copy_outputs(chief_output_dir: str, target_dir: str) -> list:
    """Copy publisher output files to our structured directory. Returns artifact list."""
    artifacts = []
    if not os.path.isdir(chief_output_dir):
        return artifacts

    os.makedirs(target_dir, exist_ok=True)
    for fname in os.listdir(chief_output_dir):
        src = os.path.join(chief_output_dir, fname)
        if not os.path.isfile(src):
            continue
        ext = os.path.splitext(fname)[1].lower()
        friendly = {".md": "report.md", ".pdf": "report.pdf", ".docx": "report.docx"}.get(
            ext, fname
        )
        dst = os.path.join(target_dir, friendly)
        shutil.copy2(src, dst)
        artifacts.append(friendly)

    # Clean up vendor output dir
    shutil.rmtree(chief_output_dir, ignore_errors=True)
    return artifacts

# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def run(query: str, config_path: str, review_mode: str = "") -> dict:
    """Run the 7-agent LangGraph pipeline.

    review_mode: "" (autonomous), "--review" (pause at outline),
                 "--review-approved" (resume with feedback from stdin)
    """
    start = time.time()
    profile_name = detect_profile_name(config_path)
    profile = MULTI_PROFILES.get(profile_name, MULTI_PROFILES["standard"])
    pdf_ok, docx_ok = check_optional_formats()

    # Build task config
    task_config = {
        "query": query,
        "max_sections": profile["max_sections"],
        "publish_formats": {"markdown": True, "pdf": pdf_ok, "docx": docx_ok},
        "include_human_feedback": False,  # We handle review ourselves (Task 4)
        "follow_guidelines": profile["follow_guidelines"],
        "model": profile["model"],
        "guidelines": profile["guidelines"],
        "verbose": True,
    }

    # Handle review modes
    if review_mode == "--review":
        task_config["include_human_feedback"] = True
        print("REVIEW MODE: Pipeline will pause after outline for your feedback.", file=sys.stderr)
        print("Type your feedback to revise, or 'no' to accept and continue.", file=sys.stderr)
    elif review_mode == "--review-approved":
        feedback = ""
        if not sys.stdin.isatty():
            raw = sys.stdin.read().strip()
            if raw:
                try:
                    data = json.loads(raw)
                    feedback = data.get("feedback", "")
                except json.JSONDecodeError:
                    feedback = raw
        if feedback:
            task_config["include_human_feedback"] = True
            print(f"REVIEW-APPROVED: Injecting feedback: {feedback[:100]}...", file=sys.stderr)
        else:
            print("REVIEW-APPROVED: No feedback provided, running autonomously.", file=sys.stderr)

    # Dependency check + import
    check_deps()
    vendor = os.path.expanduser("~/cc/vendor/gpt-researcher")
    if vendor not in sys.path:
        sys.path.insert(0, vendor)

    from multi_agents.agents.orchestrator import ChiefEditorAgent

    # Run from vendor dir (required for relative imports in multi_agents/)
    original_cwd = os.getcwd()
    os.chdir(vendor)

    try:
        chief = ChiefEditorAgent(task_config)
        result_state = await chief.run_research_task()
        # Resolve to absolute path while still in vendor dir (chief.output_dir is relative)
        chief_output_abs = os.path.abspath(chief.output_dir)
    finally:
        os.chdir(original_cwd)

    elapsed = time.time() - start

    # Build output directory, copy files
    output_dir = make_output_dir(query)

    # Save outline to drafts/ for reference (review modes)
    if review_mode in ("--review", "--review-approved"):
        drafts_dir = os.path.join(output_dir, "drafts")
        os.makedirs(drafts_dir, exist_ok=True)
        outline = {
            "title": result_state.get("title", ""),
            "sections": result_state.get("sections", []),
            "human_feedback": result_state.get("human_feedback", ""),
        }
        with open(os.path.join(drafts_dir, "outline.json"), "w") as f:
            json.dump(outline, f, ensure_ascii=False, indent=2)

    artifacts = copy_outputs(chief_output_abs, output_dir)

    # Extract results from state
    report = result_state.get("report", "")
    sources = result_state.get("sources", [])

    result = {
        "report": report,
        "sources": sources,
        "source_count": len(sources),
        "costs_usd": None,  # ChiefEditorAgent doesn't surface costs
        "elapsed_seconds": round(elapsed, 1),
        "report_type": "multi",
        "query": query,
        "profile": profile_name,
        "config_path": config_path,
        "output_dir": output_dir,
        "max_sections": profile["max_sections"],
        "follow_guidelines": profile["follow_guidelines"],
        "human_review": review_mode in ("--review", "--review-approved"),
        "artifacts": artifacts,
    }

    # Write metadata.json
    meta_path = os.path.join(output_dir, "metadata.json")
    os.makedirs(output_dir, exist_ok=True)
    with open(meta_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    if "metadata.json" not in artifacts:
        artifacts.append("metadata.json")

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python3 multi_research.py 'query' [config_path] [--review|--review-approved]",
            file=sys.stderr,
        )
        sys.exit(1)

    query = sys.argv[1]
    config_path = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser(
        "~/.config/gpt-researcher/config.json"
    )
    review_mode = sys.argv[3] if len(sys.argv) > 3 else ""

    result = asyncio.run(run(query, config_path, review_mode))
    print(json.dumps(result, ensure_ascii=False))
