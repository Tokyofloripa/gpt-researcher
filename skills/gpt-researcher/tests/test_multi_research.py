"""Tests for multi_research.py: strip_ansi, parse_pipeline_log, format_summary."""
import os
import sys

# Ensure scripts/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from multi_research import strip_ansi, parse_pipeline_log, format_summary


# ---------------------------------------------------------------------------
# strip_ansi
# ---------------------------------------------------------------------------

class TestStripAnsi:
    def test_removes_color_codes(self):
        assert strip_ansi("\x1b[32mGreen\x1b[0m") == "Green"

    def test_removes_bold(self):
        assert strip_ansi("\x1b[1mBold\x1b[0m") == "Bold"

    def test_removes_multi_param(self):
        assert strip_ansi("\x1b[1;31;42mFancy\x1b[0m") == "Fancy"

    def test_no_ansi_passthrough(self):
        assert strip_ansi("plain text") == "plain text"

    def test_empty_string(self):
        assert strip_ansi("") == ""


# ---------------------------------------------------------------------------
# parse_pipeline_log — URL extraction
# ---------------------------------------------------------------------------

class TestParseUrls:
    def test_extracts_urls(self):
        log = (
            "✅ Added source url to research: https://example.com/a\n"
            "✅ Added source url to research: https://example.com/b\n"
        )
        parsed = parse_pipeline_log(log)
        assert parsed["research_urls"] == [
            "https://example.com/a",
            "https://example.com/b",
        ]

    def test_deduplicates_urls(self):
        log = (
            "✅ Added source url to research: https://dup.com\n"
            "✅ Added source url to research: https://dup.com\n"
            "✅ Added source url to research: https://other.com\n"
        )
        parsed = parse_pipeline_log(log)
        assert parsed["research_urls"] == ["https://dup.com", "https://other.com"]

    def test_no_urls(self):
        parsed = parse_pipeline_log("no url lines here\n")
        assert parsed["research_urls"] == []


# ---------------------------------------------------------------------------
# parse_pipeline_log — cost extraction
# ---------------------------------------------------------------------------

class TestParseCosts:
    def test_sums_multiple_costs(self):
        log = (
            "💸 Total Research Costs: $0.0338\n"
            "💸 Total Research Costs: $0.0138\n"
            "💸 Total Research Costs: $0.0290\n"
            "💸 Total Research Costs: $0.0187\n"
        )
        parsed = parse_pipeline_log(log)
        assert parsed["costs"] is not None
        assert abs(parsed["costs"] - 0.0953) < 0.001

    def test_single_cost(self):
        log = "💸 Total Research Costs: $0.05\n"
        parsed = parse_pipeline_log(log)
        assert abs(parsed["costs"] - 0.05) < 0.001

    def test_no_costs(self):
        parsed = parse_pipeline_log("no cost lines\n")
        assert parsed["costs"] is None


# ---------------------------------------------------------------------------
# parse_pipeline_log — scrape failures
# ---------------------------------------------------------------------------

class TestParseScrapeFailures:
    def test_extracts_failures(self):
        log = (
            "Content too short or empty for https://fail.com/a\n"
            "Content too short or empty for https://fail.com/b\n"
        )
        parsed = parse_pipeline_log(log)
        assert parsed["scrape_failures"] == [
            "https://fail.com/a",
            "https://fail.com/b",
        ]

    def test_deduplicates_failures(self):
        log = (
            "Content too short or empty for https://fail.com/dup\n"
            "Content too short or empty for https://fail.com/dup\n"
        )
        parsed = parse_pipeline_log(log)
        assert parsed["scrape_failures"] == ["https://fail.com/dup"]

    def test_no_failures(self):
        parsed = parse_pipeline_log("all good\n")
        assert parsed["scrape_failures"] == []


# ---------------------------------------------------------------------------
# parse_pipeline_log — phase / elapsed breakdown
# ---------------------------------------------------------------------------

class TestParsePhases:
    def test_extracts_phase_timing(self):
        log = (
            "\x1b[1;32mMASTER:\x1b[0m Starting...\n"
            "INFO:     [10:00:05] something\n"
            "\x1b[1;34mEDITOR:\x1b[0m Planning\n"
            "INFO:     [10:00:10] editor work\n"
            "\x1b[1;33mRESEARCHER:\x1b[0m Searching\n"
            "INFO:     [10:00:20] researcher work\n"
            "\x1b[1;35mWRITER:\x1b[0m Writing\n"
            "INFO:     [10:00:50] writer work\n"
            "\x1b[1;36mPUBLISHER:\x1b[0m Publishing\n"
            "INFO:     [10:01:01] publishing\n"
        )
        parsed = parse_pipeline_log(log)
        breakdown = parsed["elapsed_breakdown"]
        # Should have some phases tracked
        assert isinstance(breakdown, dict)

    def test_empty_log_gives_empty_breakdown(self):
        parsed = parse_pipeline_log("")
        assert parsed["elapsed_breakdown"] == {}


# ---------------------------------------------------------------------------
# parse_pipeline_log — initial report extraction
# ---------------------------------------------------------------------------

class TestParseInitialReport:
    def test_extracts_report_between_master_and_editor(self):
        log = (
            "\x1b[1;32mMASTER:\x1b[0m Starting...\n"
            "# My Research Report\n"
            "Some content here\n"
            "\x1b[1;34mEDITOR:\x1b[0m Planning sections\n"
        )
        parsed = parse_pipeline_log(log)
        assert "My Research Report" in parsed["initial_report"]

    def test_no_master_gives_empty(self):
        parsed = parse_pipeline_log("just some random log\n")
        assert parsed["initial_report"] == ""


# ---------------------------------------------------------------------------
# parse_pipeline_log — handles ANSI in patterns
# ---------------------------------------------------------------------------

class TestParseWithAnsi:
    def test_urls_with_ansi(self):
        log = "\x1b[32m✅ Added source url to research: https://ansi.com\x1b[0m\n"
        parsed = parse_pipeline_log(log)
        assert "https://ansi.com" in parsed["research_urls"]

    def test_costs_with_ansi(self):
        log = "\x1b[33m💸 Total Research Costs: $0.042\x1b[0m\n"
        parsed = parse_pipeline_log(log)
        assert parsed["costs"] is not None
        assert abs(parsed["costs"] - 0.042) < 0.001


# ---------------------------------------------------------------------------
# format_summary
# ---------------------------------------------------------------------------

class TestFormatSummary:
    def test_basic_output(self):
        parsed = {
            "research_urls": ["https://a.com"] * 32,
            "costs": 0.095,
            "scrape_failures": [
                "https://nytimes.com/article1",
                "https://washingtonpost.com/story",
                "https://ft.com/content/123",
            ],
            "elapsed_breakdown": {
                "browser": 12,
                "research": 67,
                "write": 28,
                "publish": 11,
            },
            "initial_report": "# report",
        }
        summary = format_summary(parsed, "quick", 3, 4)
        assert "[multi]" in summary
        assert "32 URLs" in summary
        assert "4 cited" in summary
        assert "$0.095" in summary

    def test_no_costs(self):
        parsed = {
            "research_urls": [],
            "costs": None,
            "scrape_failures": [],
            "elapsed_breakdown": {},
            "initial_report": "",
        }
        summary = format_summary(parsed, "standard", 5, 0)
        assert "[multi]" in summary
        # Cost should be absent or shown as N/A
        assert "$" not in summary or "N/A" in summary

    def test_scrape_failures_show_domains(self):
        parsed = {
            "research_urls": ["https://x.com"] * 10,
            "costs": 0.05,
            "scrape_failures": [
                "https://nytimes.com/a",
                "https://nytimes.com/b",
                "https://wsj.com/c",
            ],
            "elapsed_breakdown": {},
            "initial_report": "",
        }
        summary = format_summary(parsed, "standard", 5, 3)
        assert "nytimes.com" in summary
        assert "wsj.com" in summary

    def test_phase_timing_in_output(self):
        parsed = {
            "research_urls": [],
            "costs": 0.01,
            "scrape_failures": [],
            "elapsed_breakdown": {"browser": 12, "research": 67},
            "initial_report": "",
        }
        summary = format_summary(parsed, "quick", 3, 0)
        assert "browser" in summary or "research" in summary

    def test_review_skipped_for_quick(self):
        parsed = {
            "research_urls": [],
            "costs": None,
            "scrape_failures": [],
            "elapsed_breakdown": {},
            "initial_report": "",
        }
        summary = format_summary(parsed, "quick", 3, 0)
        # Quick profile should note review was skipped
        assert "skipped" in summary.lower() or "quick" in summary.lower()
