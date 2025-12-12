#!/usr/bin/env python3
"""Quality Dashboard - review quality metrics over time."""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import Settings
from app.core.logging_config import get_logger, setup_logging


def load_metrics(metrics_file: Path) -> list[dict]:
    """
    Load quality metrics from JSONL file.

    Args:
        metrics_file: Path to JSONL file

    Returns:
        List of metric dictionaries
    """
    metrics = []
    if not metrics_file.exists():
        return metrics

    with open(metrics_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                metric = json.loads(line)
                metrics.append(metric)
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping invalid JSON line: {e}")
                continue

    return metrics


def compute_statistics(metrics: list[dict]) -> dict:
    """
    Compute statistics from metrics.

    Args:
        metrics: List of metric dictionaries

    Returns:
        Dictionary with statistics
    """
    if not metrics:
        return {}

    stats = {
        "total_episodes": len(metrics),
        "scores": {},
        "rolling_averages": {},
    }

    # Score types
    score_types = ["overall_score", "visual_score", "content_score", "technical_score"]

    for score_type in score_types:
        scores = [m.get(score_type, 0) for m in metrics if score_type in m]
        if scores:
            stats["scores"][score_type] = {
                "min": min(scores),
                "max": max(scores),
                "avg": sum(scores) / len(scores),
                "count": len(scores),
            }

    # Rolling averages (last 10, last 50)
    if len(metrics) >= 10:
        last_10 = metrics[-10:]
        for score_type in score_types:
            scores = [m.get(score_type, 0) for m in last_10 if score_type in m]
            if scores:
                stats["rolling_averages"][f"{score_type}_last_10"] = sum(scores) / len(scores)

    if len(metrics) >= 50:
        last_50 = metrics[-50:]
        for score_type in score_types:
            scores = [m.get(score_type, 0) for m in last_50 if score_type in m]
            if scores:
                stats["rolling_averages"][f"{score_type}_last_50"] = sum(scores) / len(scores)

    return stats


def print_console_table(metrics: list[dict], stats: dict) -> None:
    """
    Print console table with quality metrics.

    Args:
        metrics: List of metric dictionaries
        stats: Statistics dictionary
    """
    if not metrics:
        print("No quality metrics found.")
        return

    print("=" * 80)
    print("QUALITY DASHBOARD")
    print("=" * 80)
    print(f"Total Episodes: {stats.get('total_episodes', 0)}")
    print()

    # Overall statistics
    if "scores" in stats:
        print("Overall Statistics:")
        print("-" * 80)
        for score_type in ["overall_score", "visual_score", "content_score", "technical_score"]:
            if score_type in stats["scores"]:
                s = stats["scores"][score_type]
                print(
                    f"  {score_type:20s} | "
                    f"Min: {s['min']:6.2f} | "
                    f"Max: {s['max']:6.2f} | "
                    f"Avg: {s['avg']:6.2f} | "
                    f"Count: {s['count']:3d}"
                )
        print()

    # Rolling averages
    if "rolling_averages" in stats and stats["rolling_averages"]:
        print("Rolling Averages:")
        print("-" * 80)
        for key, value in sorted(stats["rolling_averages"].items()):
            print(f"  {key:30s} | {value:6.2f}")
        print()

    # Recent episodes (last 10)
    print("Recent Episodes (Last 10):")
    print("-" * 80)
    print(
        f"{'Episode ID':20s} | "
        f"{'Overall':>8s} | "
        f"{'Visual':>8s} | "
        f"{'Content':>8s} | "
        f"{'Technical':>8s} | "
        f"{'Date':>19s}"
    )
    print("-" * 80)

    for metric in metrics[-10:]:
        episode_id = metric.get("episode_id", "unknown")[:18]
        timestamp = metric.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                date_str = timestamp[:16]
        else:
            date_str = "N/A"

        print(
            f"{episode_id:20s} | "
            f"{metric.get('overall_score', 0):8.2f} | "
            f"{metric.get('visual_score', 0):8.2f} | "
            f"{metric.get('content_score', 0):8.2f} | "
            f"{metric.get('technical_score', 0):8.2f} | "
            f"{date_str:>19s}"
        )

    print("=" * 80)


def generate_html_report(metrics: list[dict], stats: dict, output_path: Path) -> None:
    """
    Generate HTML report with quality metrics.

    Args:
        metrics: List of metric dictionaries
        stats: Statistics dictionary
        output_path: Path to save HTML report
    """
    html = """<!DOCTYPE html>
<html>
<head>
    <title>Quality Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
        h1 { color: #333; }
        h2 { color: #666; border-bottom: 2px solid #ddd; padding-bottom: 10px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f0f0f0; font-weight: bold; }
        tr:hover { background: #f9f9f9; }
        .score-high { color: #28a745; font-weight: bold; }
        .score-medium { color: #ffc107; font-weight: bold; }
        .score-low { color: #dc3545; font-weight: bold; }
        .stats-box { display: inline-block; margin: 10px; padding: 15px; background: #f8f9fa; border-radius: 5px; }
        .stats-box h3 { margin: 0 0 10px 0; color: #495057; }
        .stats-box .value { font-size: 24px; font-weight: bold; color: #007bff; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Quality Dashboard</h1>
        <p>Generated: {timestamp}</p>
"""

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = html.format(timestamp=timestamp)

    # Statistics
    if stats:
        html += "<h2>Overall Statistics</h2>\n"
        html += "<div>\n"
        if "scores" in stats:
            for score_type in ["overall_score", "visual_score", "content_score", "technical_score"]:
                if score_type in stats["scores"]:
                    s = stats["scores"][score_type]
                    html += f"""
                    <div class="stats-box">
                        <h3>{score_type.replace('_', ' ').title()}</h3>
                        <div class="value">{s['avg']:.2f}</div>
                        <div>Min: {s['min']:.2f} | Max: {s['max']:.2f}</div>
                    </div>
                    """
        html += "</div>\n"

        # Rolling averages
        if "rolling_averages" in stats and stats["rolling_averages"]:
            html += "<h2>Rolling Averages</h2>\n"
            html += "<table>\n"
            html += "<tr><th>Metric</th><th>Value</th></tr>\n"
            for key, value in sorted(stats["rolling_averages"].items()):
                html += f"<tr><td>{key.replace('_', ' ').title()}</td><td>{value:.2f}</td></tr>\n"
            html += "</table>\n"

    # Recent episodes table
    html += "<h2>Recent Episodes</h2>\n"
    html += "<table>\n"
    html += "<tr><th>Episode ID</th><th>Overall</th><th>Visual</th><th>Content</th><th>Technical</th><th>Date</th></tr>\n"

    for metric in metrics[-50:]:  # Last 50 episodes
        episode_id = metric.get("episode_id", "unknown")
        timestamp = metric.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                date_str = timestamp[:16]
        else:
            date_str = "N/A"

        overall = metric.get("overall_score", 0)
        visual = metric.get("visual_score", 0)
        content = metric.get("content_score", 0)
        technical = metric.get("technical_score", 0)

        # Score color classes
        def score_class(score):
            if score >= 80:
                return "score-high"
            elif score >= 60:
                return "score-medium"
            else:
                return "score-low"

        html += f"""
        <tr>
            <td>{episode_id[:20]}</td>
            <td class="{score_class(overall)}">{overall:.2f}</td>
            <td class="{score_class(visual)}">{visual:.2f}</td>
            <td class="{score_class(content)}">{content:.2f}</td>
            <td class="{score_class(technical)}">{technical:.2f}</td>
            <td>{date_str}</td>
        </tr>
        """

    html += "</table>\n"
    html += """
    </div>
</body>
</html>
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)

    print(f"HTML report saved to: {output_path}")


def main():
    """Main entry point for quality dashboard."""
    parser = argparse.ArgumentParser(description="Quality Dashboard - review quality metrics")
    parser.add_argument(
        "--metrics-file",
        type=str,
        default=None,
        help="Path to quality_metrics.jsonl file (default: storage/episodes/quality_metrics.jsonl)",
    )
    parser.add_argument(
        "--html",
        type=str,
        default=None,
        help="Generate HTML report (path to output file, default: outputs/quality_report.html)",
    )
    parser.add_argument(
        "--no-console",
        action="store_true",
        help="Skip console output (only generate HTML if --html is set)",
    )
    args = parser.parse_args()

    # Setup logging
    setup_logging()
    logger = get_logger(__name__)

    # Determine metrics file path
    if args.metrics_file:
        metrics_file = Path(args.metrics_file)
    else:
        settings = Settings()
        metrics_file = Path(settings.storage_path) / "quality_metrics.jsonl"

    logger.info(f"Loading metrics from: {metrics_file}")

    # Load metrics
    metrics = load_metrics(metrics_file)

    if not metrics:
        print("No quality metrics found.")
        print(f"Metrics file: {metrics_file}")
        print("Run the pipeline to generate quality metrics.")
        return 1

    # Compute statistics
    stats = compute_statistics(metrics)

    # Print console table
    if not args.no_console:
        print_console_table(metrics, stats)

    # Generate HTML report if requested
    if args.html:
        html_path = Path(args.html)
    elif args.html is None and not args.no_console:
        # Default HTML output
        html_path = Path("outputs/quality_report.html")
    else:
        html_path = None

    if html_path:
        generate_html_report(metrics, stats, html_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())

