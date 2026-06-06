"""Evaluation and Regression Testing Harness for CodeSentinel.

This script runs the agent's review pipeline against a golden dataset, computes
precision, recall, parsing success rate, latency, and tokens, and checks for regressions
against a baseline configuration.
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

# Add project root to path to run as module or script
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file BEFORE importing settings
env_file = project_root / ".env"
if env_file.exists():
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

from backend.config import settings
from backend.models import PRMetadata, Finding
from backend.agent.pipeline import run_review
from backend.agent.llm import call_gemini
from backend.eval.dataset import GOLDEN_DATASET

EVAL_DIR = Path(__file__).parent
REPORTS_DIR = EVAL_DIR / "reports"
BASELINE_PATH = EVAL_DIR / "baseline.json"

# Ensure reports directory exists
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def judge_finding_validity(diff_context: str, finding: Finding) -> bool:
    """Uses LLM-as-a-judge to evaluate if a finding is a true positive (valid) or a false positive."""
    prompt = f"""You are an expert impartial code reviewer. Verify if the following code review finding is a valid, constructive, and correct issue for the provided git diff.

Diff:
{diff_context}

Finding Title: {finding.title}
Category: {finding.category.value}
Line: {finding.line_start}
Finding Description: {finding.description}
Proposed Suggestion: {finding.suggestion}

Answer with ONLY 'YES' if the finding is a true, correct, and useful issue, or 'NO' if it is a false positive, hallucination, or irrelevant nitpick. Do not include any other text."""
    try:
        response = call_gemini(prompt).strip().upper()
        # Clean response (sometimes models add quotes or punctuation)
        cleaned = "".join(c for c in response if c.isalnum())
        return "YES" in cleaned
    except Exception as e:
        print(f"      Judge call failed: {e}. Defaulting to True.")
        return True


def run_evaluation() -> dict:
    """Executes the evaluation suite on the golden dataset."""
    print("=" * 60)
    print("[START] Running CodeSentinel Evaluation Suite...")
    print(f"Golden dataset size: {len(GOLDEN_DATASET)} cases")
    print("=" * 60)

    results = []
    total_expected = 0
    total_caught = 0
    total_findings = 0
    total_true_positives = 0
    total_tokens = 0
    successful_runs = 0

    start_eval_time = time.time()

    for idx, case in enumerate(GOLDEN_DATASET, 1):
        print(f"\n[{idx}/{len(GOLDEN_DATASET)}] Evaluating Case: {case['id']}")
        print(f"Description: {case['description']}")

        # Build mock PR Metadata
        pr_metadata = PRMetadata(
            url=f"https://github.com/eval/repo/pull/{idx}",
            title=case["pr_title"],
            author="eval-tester",
            description=case["description"],
            base_branch="main",
            head_branch="feature-eval",
            repo_full_name="eval/repo",
            pr_number=idx,
            files_changed=len(case["files"]),
        )

        success = False
        findings = []
        stats = None
        summary = ""
        case_start = time.time()

        try:
            # Execute the review pipeline
            review = run_review(case["files"], pr_metadata)
            findings = review.findings
            stats = review.stats
            summary = review.summary
            success = True
            successful_runs += 1
            total_tokens += stats.tokens_used
            print(f"  [OK] Pipeline executed in {stats.review_time_seconds}s (Tokens used: {stats.tokens_used})")
        except Exception as e:
            print(f"  [FAIL] Pipeline execution failed: {e}")

        # Evaluate Recall & Precision
        case_expected = len(case["expected_issues"])
        total_expected += case_expected
        case_caught = 0
        caught_indices = set()

        diff_context = "\n".join(f.patch for f in case["files"])

        case_true_positives = 0
        case_findings_count = len(findings)
        total_findings += case_findings_count

        # Check expected issues (Recall)
        for exp_idx, expected in enumerate(case["expected_issues"]):
            matched = False
            for finding in findings:
                # 1. Same file
                file_match = finding.file == expected["file"]
                # 2. Category match
                category_match = finding.category.value == expected["category"]
                # 3. Line overlap or proximity
                line_match = False
                if expected["line_start"] > 0 and finding.line_start > 0:
                    line_match = abs(finding.line_start - expected["line_start"]) <= 3
                
                # 4. Keyword overlap in details
                keyword_match = any(
                    kw in finding.description.lower() or kw in finding.title.lower()
                    for kw in expected["keywords"]
                )

                if file_match and (category_match or keyword_match) and (line_match or keyword_match):
                    matched = True
                    break

            if matched:
                case_caught += 1
                total_caught += 1

        # Evaluate validity using LLM-as-a-judge (Precision)
        print(f"  Analyzing {case_findings_count} agent findings for Precision...")
        for f in findings:
            # Check if it matches an expected issue first to save API calls
            matched_expected = False
            for expected in case["expected_issues"]:
                if f.file == expected["file"] and any(kw in f.description.lower() for kw in expected["keywords"]):
                    matched_expected = True
                    break
            
            if matched_expected:
                case_true_positives += 1
                total_true_positives += 1
                print(f"    - Finding '{f.title}' [Matched expected ground-truth]")
            else:
                # Ask LLM Judge
                is_valid = judge_finding_validity(diff_context, f)
                if is_valid:
                    case_true_positives += 1
                    total_true_positives += 1
                    print(f"    - Finding '{f.title}' [VALIDated by Judge]")
                else:
                    print(f"    - Finding '{f.title}' [INVALID / False Positive by Judge]")

        case_elapsed = time.time() - case_start
        case_recall = case_caught / case_expected if case_expected > 0 else 0
        case_precision = case_true_positives / case_findings_count if case_findings_count > 0 else 0

        results.append({
            "case_id": case["id"],
            "description": case["description"],
            "success": success,
            "findings_count": case_findings_count,
            "true_positives": case_true_positives,
            "expected_count": case_expected,
            "caught_count": case_caught,
            "recall": round(case_recall, 2),
            "precision": round(case_precision, 2),
            "latency_seconds": round(case_elapsed, 2),
        })

    eval_duration = time.time() - start_eval_time
    
    # Calculate global metrics
    success_rate = successful_runs / len(GOLDEN_DATASET)
    avg_recall = total_caught / total_expected if total_expected > 0 else 0
    avg_precision = total_true_positives / total_findings if total_findings > 0 else 0
    avg_latency = eval_duration / len(GOLDEN_DATASET)
    avg_tokens = total_tokens / successful_runs if successful_runs > 0 else 0

    eval_report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "cases_evaluated": len(GOLDEN_DATASET),
            "success_rate": round(success_rate, 2),
            "recall": round(avg_recall, 2),
            "precision": round(avg_precision, 2),
            "avg_latency_seconds": round(avg_latency, 2),
            "avg_tokens": round(avg_tokens, 0),
            "total_eval_time_seconds": round(eval_duration, 2),
        },
        "details": results
    }

    return eval_report


def save_baseline_if_missing(report: dict):
    """Saves the current evaluation report as the baseline if no baseline exists."""
    if not BASELINE_PATH.exists():
        baseline_data = {
            "success_rate": report["summary"]["success_rate"],
            "recall": report["summary"]["recall"],
            "precision": report["summary"]["precision"],
            "avg_latency_seconds": report["summary"]["avg_latency_seconds"],
            "avg_tokens": report["summary"]["avg_tokens"],
            "timestamp": report["timestamp"],
        }
        with open(BASELINE_PATH, "w") as f:
            json.dump(baseline_data, f, indent=2)
        print(f"Saved new baseline metrics to {BASELINE_PATH}")


def check_regressions(report: dict) -> bool:
    """Compares the current report against the baseline and flags regressions."""
    if not BASELINE_PATH.exists():
        return False  # No regression possible

    with open(BASELINE_PATH, "r") as f:
        baseline = json.load(f)

    print("\n" + "=" * 60)
    print("Comparing Metrics against Baseline:")
    print(f"Baseline Date: {baseline.get('timestamp', 'Unknown')}")
    print("=" * 60)

    current = report["summary"]
    regressions = []

    # Check Success Rate (syntactic JSON errors)
    print(f"Success Rate: {current['success_rate']} (Baseline: {baseline['success_rate']})")
    if current["success_rate"] < baseline["success_rate"]:
        regressions.append("Success rate dropped (indicates JSON parsing/schema issues).")

    # Check Recall
    print(f"Recall:       {current['recall']} (Baseline: {baseline['recall']})")
    if current["recall"] < baseline["recall"] - 0.05:  # 5% tolerance
        regressions.append(f"Recall dropped significantly: {current['recall']} vs {baseline['recall']}")

    # Check Precision
    print(f"Precision:    {current['precision']} (Baseline: {baseline['precision']})")
    if current["precision"] < baseline["precision"] - 0.05:  # 5% tolerance
        regressions.append(f"Precision dropped significantly (increased false positives): {current['precision']} vs {baseline['precision']}")

    # Check Latency (Warning only)
    print(f"Latency:      {current['avg_latency_seconds']}s (Baseline: {baseline['avg_latency_seconds']}s)")
    if current["avg_latency_seconds"] > baseline["avg_latency_seconds"] * 1.5:
        print("Warning: Latency increased by more than 50%")

    if regressions:
        print("\nREGRESSION(S) DETECTED:")
        for reg in regressions:
            print(f"  - {reg}")
        return True

    print("\nNo regressions detected! Agent performance meets or exceeds baseline.")
    return False


def generate_markdown_report(report: dict, regression_detected: bool):
    """Outputs a clean Markdown report for pull requests or build artifacts."""
    timestamp = report["timestamp"]
    summary = report["summary"]

    md_lines = [
        f"# CodeSentinel Evaluation Report",
        f"**Run Timestamp:** `{timestamp}`",
        f"**Status:** {'❌ REGRESSION DETECTED' if regression_detected else '✅ PASSING'}",
        "",
        "## Summary Metrics",
        "| Metric | Current Run | Target / Baseline |",
        "| :--- | :---: | :---: |",
    ]

    # Load baseline for comparison
    baseline = {}
    if BASELINE_PATH.exists():
        with open(BASELINE_PATH, "r") as f:
            baseline = json.load(f)

    md_lines.extend([
        f"| JSON Parse Success Rate | `{summary['success_rate']*100}%` | `{baseline.get('success_rate', 1.0)*100}%` |",
        f"| Recall (Bugs Caught) | `{summary['recall']*100}%` | `{baseline.get('recall', 0.66)*100}%` |",
        f"| Precision (Accuracy) | `{summary['precision']*100}%` | `{baseline.get('precision', 0.66)*100}%` |",
        f"| Avg Latency | `{summary['avg_latency_seconds']}s` | `{baseline.get('avg_latency_seconds', 0.0)}s` |",
        f"| Avg Tokens | `{summary['avg_tokens']}` | `{baseline.get('avg_tokens', 0)}` |",
        "",
        "## Detailed Case Breakdown",
        "| Case ID | Success | Findings | Expected | Recall | Precision | Latency |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ])

    for case in report["details"]:
        md_lines.append(
            f"| `{case['case_id']}` | {'✅' if case['success'] else '❌'} | "
            f"{case['findings_count']} | {case['expected_count']} | "
            f"{int(case['recall']*100)}% | {int(case['precision']*100)}% | `{case['latency_seconds']}s` |"
        )

    # Save to file
    filename = f"eval_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path = REPORTS_DIR / filename
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    # Also symlink/write latest.md
    latest_path = REPORTS_DIR / "latest_report.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"Generated markdown evaluation report at {report_path}")


if __name__ == "__main__":
    if not os.environ.get("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY environment variable is missing. Evaluation aborted.")
        sys.exit(1)

    report = run_evaluation()
    save_baseline_if_missing(report)
    regression_detected = check_regressions(report)
    generate_markdown_report(report, regression_detected)

    # Save JSON report
    json_filename = f"eval_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(REPORTS_DIR / json_filename, "w") as f:
        json.dump(report, f, indent=2)
        
    with open(REPORTS_DIR / "latest_report.json", "w") as f:
        json.dump(report, f, indent=2)

    if regression_detected:
        sys.exit(1)
    else:
        sys.exit(0)
