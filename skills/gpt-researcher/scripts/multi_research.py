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
import tempfile
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


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text (SGR, CSI, and OSC sequences)."""
    return re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07", "", text)


def parse_pipeline_log(raw_log: str) -> dict:
    """Extract structured data from raw ChiefEditorAgent stderr output.

    Parses URLs, costs, scrape failures, phase timing, and initial report
    from the ANSI-colored log output of the 7-agent LangGraph pipeline.

    Returns dict with keys: research_urls, costs, scrape_failures,
    elapsed_breakdown, initial_report.
    """
    clean = strip_ansi(raw_log)
    lines = clean.splitlines()

    # --- URLs ---
    url_pattern = re.compile(r"Added source url to research:\s*(https?://\S+)")
    seen_urls = []
    seen_url_set = set()
    for line in lines:
        m = url_pattern.search(line)
        if m:
            url = m.group(1)
            if url not in seen_url_set:
                seen_urls.append(url)
                seen_url_set.add(url)

    # --- Costs ---
    cost_pattern = re.compile(r"Total Research Costs:\s*\$([0-9.]+)")
    costs_total = 0.0
    cost_found = False
    for line in lines:
        m = cost_pattern.search(line)
        if m:
            costs_total += float(m.group(1))
            cost_found = True

    # --- Scrape failures ---
    fail_pattern = re.compile(r"Content too short or empty for\s*(https?://\S+)")
    seen_fails = []
    seen_fail_set = set()
    for line in lines:
        m = fail_pattern.search(line)
        if m:
            url = m.group(1)
            if url not in seen_fail_set:
                seen_fails.append(url)
                seen_fail_set.add(url)

    # --- Phase timing from INFO timestamps ---
    # Pattern: INFO:     [HH:MM:SS]
    ts_pattern = re.compile(r"INFO:\s+\[(\d{2}):(\d{2}):(\d{2})\]")
    # Phase markers (after ANSI stripping)
    phase_pattern = re.compile(
        r"^(MASTER|EDITOR|RESEARCHER|REVIEWER|WRITER|PUBLISHER):"
    )

    current_phase = None
    phase_first_ts = {}  # phase -> first timestamp in seconds
    phase_last_ts = {}   # phase -> last timestamp in seconds

    for line in lines:
        pm = phase_pattern.match(line)
        if pm:
            current_phase = pm.group(1).lower()

        tm = ts_pattern.search(line)
        if tm and current_phase:
            secs = int(tm.group(1)) * 3600 + int(tm.group(2)) * 60 + int(tm.group(3))
            if current_phase not in phase_first_ts:
                phase_first_ts[current_phase] = secs
            phase_last_ts[current_phase] = secs

    elapsed_breakdown = {}
    for phase in phase_first_ts:
        if phase in phase_last_ts:
            diff = phase_last_ts[phase] - phase_first_ts[phase]
            if diff > 0:  # Skip phases with single timestamp (< 1s)
                elapsed_breakdown[phase] = diff

    # --- Initial report: text between MASTER: Starting... and first EDITOR: ---
    initial_report = ""
    in_master = False
    report_lines = []
    for line in lines:
        if re.match(r"MASTER:\s*Starting", line):
            in_master = True
            continue
        if in_master and re.match(r"EDITOR:", line):
            break
        if in_master:
            report_lines.append(line)

    if report_lines:
        initial_report = "\n".join(report_lines).strip()

    return {
        "research_urls": seen_urls,
        "costs": round(costs_total, 4) if cost_found else None,
        "scrape_failures": seen_fails,
        "elapsed_breakdown": elapsed_breakdown,
        "initial_report": initial_report,
    }


def format_summary(parsed: dict, profile: str, sections: int, cited: int) -> str:
    """Produce a clean multi-line summary from parsed pipeline log data.

    Args:
        parsed: Output of parse_pipeline_log()
        profile: Profile name (quick, standard, thorough, government)
        sections: Number of max_sections in profile
        cited: Number of cited sources in final report
    """
    from urllib.parse import urlparse

    out = []

    # Line 1: Overview
    url_count = len(parsed["research_urls"])
    cost_str = f"${parsed['costs']:.4f}" if parsed["costs"] is not None else "N/A"
    out.append(
        f"[multi] Research complete: {sections} sections, "
        f"{url_count} URLs scraped, {cited} cited, {cost_str}"
    )

    # Line 2: Phase timing
    breakdown = parsed["elapsed_breakdown"]
    if breakdown:
        parts = [f"{phase} {secs}s" for phase, secs in breakdown.items()]
        out.append(f"[multi] Phases: {' | '.join(parts)}")

    # Line 3: Scrape failures
    failures = parsed["scrape_failures"]
    if failures:
        # Extract unique domains
        domains = []
        seen = set()
        for url in failures:
            try:
                domain = urlparse(url).netloc
                if domain and domain not in seen:
                    domains.append(domain)
                    seen.add(domain)
            except Exception:
                pass
        if domains:
            domain_str = ", ".join(domains[:5])
            if len(domains) > 5:
                domain_str += f", +{len(domains) - 5} more"
            out.append(
                f"[multi] Scrape failures: {len(failures)} paywalled "
                f"({domain_str})"
            )

    # Line 4: Review status
    if profile == "quick":
        out.append("[multi] Review: skipped (quick profile)")

    return "\n".join(out)


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
        from md2pdf.core import md2pdf as _  # noqa: F401
        pdf_ok = True
    except (ImportError, OSError):
        print("INFO: md2pdf not available — PDF export disabled (install: brew install pango && pip install md2pdf)", file=sys.stderr)
    try:
        import docx  # noqa: F401
        docx_ok = True
    except (ImportError, OSError):
        print("INFO: python-docx not available — DOCX export disabled", file=sys.stderr)
    return pdf_ok, docx_ok


def copy_outputs(chief_output_dir: str, target_dir: str) -> list:
    """Copy publisher output files to our structured directory. Returns artifact list.

    When multiple files share the same extension, picks the largest (most likely the report).
    """
    artifacts = []
    if not os.path.isdir(chief_output_dir):
        return artifacts

    os.makedirs(target_dir, exist_ok=True)
    friendly_map = {".md": "report.md", ".pdf": "report.pdf", ".docx": "report.docx"}

    # Group by extension, keep largest file per extension
    by_ext = {}
    for fname in os.listdir(chief_output_dir):
        src = os.path.join(chief_output_dir, fname)
        if not os.path.isfile(src):
            continue
        ext = os.path.splitext(fname)[1].lower()
        if ext not in friendly_map:
            continue
        if ext not in by_ext or os.path.getsize(src) > os.path.getsize(by_ext[ext]):
            by_ext[ext] = src

    for ext, src in by_ext.items():
        friendly = friendly_map[ext]
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
    raw_profile_name = detect_profile_name(config_path)
    profile = MULTI_PROFILES.get(raw_profile_name)
    if profile is None:
        profile_name = "standard"
        profile = MULTI_PROFILES["standard"]
        print(f"INFO: Profile '{raw_profile_name}' not in multi-agent profiles, using 'standard'", file=sys.stderr)
    else:
        profile_name = raw_profile_name
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
        if sys.stdin.isatty():
            print("REVIEW MODE: Pipeline will pause after outline for your feedback.", file=sys.stderr)
            print("Type your feedback to revise, or 'no' to accept and continue.", file=sys.stderr)
        else:
            print("WARNING: --review requires an interactive terminal. "
                  "Use --review-approved with piped feedback for headless mode.", file=sys.stderr)
    elif review_mode == "--review-approved":
        feedback = ""
        if not sys.stdin.isatty():
            raw = sys.stdin.read().strip()
            if raw:
                try:
                    data = json.loads(raw)
                    feedback = data.get("feedback", raw)
                except json.JSONDecodeError:
                    feedback = raw
        if feedback:
            task_config["include_human_feedback"] = True
            # Replace stdin so HumanAgent's input() call reads the pre-loaded feedback
            sys.stdin = io.StringIO(feedback)
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

    # Capture both stdout and stderr to the SAME temp file at fd level.
    # Pipeline sends INFO/URLs/costs to fd 2 (logging), phase labels to fd 1 (print).
    # Using one file ensures OS-level interleaving preserves temporal order.
    real_stdout = sys.stdout
    real_stderr = sys.stderr
    saved_out_fd = os.dup(1)
    saved_err_fd = os.dup(2)
    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.log', prefix='pipeline_')
    os.dup2(tmp_fd, 1)
    os.dup2(tmp_fd, 2)
    os.close(tmp_fd)
    sys.stdout = open(1, 'w', closefd=False)
    sys.stderr = open(2, 'w', closefd=False)

    try:
        chief = ChiefEditorAgent(task_config)
        result_state = await chief.run_research_task()
        # Resolve to absolute path while still in vendor dir (chief.output_dir is relative)
        chief_output_abs = os.path.abspath(chief.output_dir)
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(saved_out_fd, 1)
        os.dup2(saved_err_fd, 2)
        os.close(saved_out_fd)
        os.close(saved_err_fd)
        sys.stdout = real_stdout
        sys.stderr = real_stderr
        os.chdir(original_cwd)

    with open(tmp_path) as f:
        raw_log = f.read()
    os.unlink(tmp_path)
    parsed = parse_pipeline_log(raw_log)

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

    # Save pipeline log (ANSI-stripped) and initial report
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, "pipeline.log")
    with open(log_path, "w") as f:
        f.write(strip_ansi(raw_log))
    artifacts.append("pipeline.log")

    if parsed["initial_report"]:
        drafts_dir = os.path.join(output_dir, "drafts")
        os.makedirs(drafts_dir, exist_ok=True)
        ir_path = os.path.join(drafts_dir, "initial_report.md")
        with open(ir_path, "w") as f:
            f.write(parsed["initial_report"])
        artifacts.append("drafts/initial_report.md")

    # Extract results from state
    report = result_state.get("report", "")
    sources = result_state.get("sources", [])

    result = {
        "report": report,
        "sources": sources,
        "source_count": len(sources),
        "costs_usd": parsed["costs"],
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
        "research_urls": parsed["research_urls"],
        "research_url_count": len(parsed["research_urls"]),
        "elapsed_breakdown": parsed["elapsed_breakdown"],
        "scrape_failures": parsed["scrape_failures"],
    }

    # Write metadata.json (append to artifacts BEFORE writing so file and return value match)
    if "metadata.json" not in artifacts:
        artifacts.append("metadata.json")
    meta_path = os.path.join(output_dir, "metadata.json")
    os.makedirs(output_dir, exist_ok=True)
    with open(meta_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Emit clean summary to stderr
    summary = format_summary(parsed, profile_name, profile["max_sections"], len(sources))
    print(summary, file=sys.stderr)

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
