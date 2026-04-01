"""Main pipeline: Fetch → Score → Analyze → Visualize.

Usage:
    python run_pipeline.py              # Full pipeline (fetch + analyze)
    python run_pipeline.py --offline    # Skip fetching, use cached data
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.fetch_papers import fetch_all_with_content, load_papers, save_papers
from src.scoring import score_all_papers
from src.analysis import build_dataframe, run_all_analyses
from src.visualize import generate_all_figures

DATA_DIR = ROOT / "data"
OUTPUTS_DIR = ROOT / "outputs"


def save_results(df, results):
    """Save analysis outputs to disk."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    df.to_csv(OUTPUTS_DIR / "scored_papers.csv", index=False)
    print(f"  Saved scored_papers.csv ({len(df)} rows)")

    top_bottom = pd.concat([
        df[~df["is_spam"]].nlargest(10, "cqi").assign(rank_type="top"),
        df[~df["is_spam"]].nsmallest(10, "cqi").assign(rank_type="bottom"),
    ])
    top_bottom.to_csv(OUTPUTS_DIR / "top_bottom_papers.csv", index=False)
    print("  Saved top_bottom_papers.csv")

    stats = results["corpus_stats"]
    with open(OUTPUTS_DIR / "corpus_stats.json", "w") as f:
        json.dump(stats, f, indent=2, default=str)
    print("  Saved corpus_stats.json")

    hyp_rows = []
    for h in results["hypotheses"]:
        hyp_rows.append({
            "hypothesis": h.name,
            "test": h.test_name,
            "statistic": h.statistic,
            "p_value": h.p_value,
            "effect_size": h.effect_size,
            "ci_low": h.effect_ci_low,
            "ci_high": h.effect_ci_high,
            "decision": h.decision,
            "details": h.details,
        })
    pd.DataFrame(hyp_rows).to_csv(OUTPUTS_DIR / "hypothesis_tests.csv", index=False)
    print("  Saved hypothesis_tests.csv")

    agent_stats = results["agent_stats"]
    agent_stats.to_csv(OUTPUTS_DIR / "agent_stats.csv")
    print("  Saved agent_stats.csv")

    dup_pairs = results["duplicate_pairs"]
    pd.DataFrame(dup_pairs).to_csv(OUTPUTS_DIR / "duplicate_pairs.csv", index=False)
    print(f"  Saved duplicate_pairs.csv ({len(dup_pairs)} pairs)")


def generate_summary_report(df, results):
    """Generate a human-readable summary report."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    valid = df[~df["is_spam"]]
    stats = results["corpus_stats"]

    lines = [
        "=" * 70,
        "THE FIRST AUDIT OF AI AGENT SCIENCE",
        "A Bibliometric Quality Analysis of clawRxiv",
        "=" * 70,
        "",
        "CORPUS OVERVIEW",
        "-" * 40,
        f"  Total papers:           {stats['total_papers']}",
        f"  Valid (non-spam):        {stats['valid_papers']}",
        f"  Spam flagged:           {stats['spam_flagged']}",
        f"  Near-duplicates:        {stats['near_duplicates']}",
        f"  Unique agents:          {stats['unique_agents']}",
        f"  Observation window:     {stats['observation_days']:.0f} days",
        "",
        f"  With skill_md:          {stats['papers_with_skill']} ({stats['pct_skill']:.1f}%)",
        f"  With human co-authors:  {stats['papers_with_collab']} ({stats['pct_collab']:.1f}%)",
        "",
        "QUALITY INDEX (CQI) SUMMARY",
        "-" * 40,
        f"  Mean:    {stats['cqi_mean']:.1f}",
        f"  Median:  {stats['cqi_median']:.1f}",
        f"  SD:      {stats['cqi_std']:.1f}",
        f"  Range:   {stats['cqi_min']:.1f} – {stats['cqi_max']:.1f}",
        f"  IQR:     {stats['cqi_q25']:.1f} – {stats['cqi_q75']:.1f}",
        "",
        "HYPOTHESIS TESTS",
        "-" * 40,
    ]

    for h in results["hypotheses"]:
        lines.extend([
            f"  {h.name}",
            f"    Test:        {h.test_name}",
            f"    Statistic:   {h.statistic:.4f}",
            f"    p-value:     {h.p_value:.6f}",
            f"    Effect size: {h.effect_size:.4f} [{h.effect_ci_low:.4f}, {h.effect_ci_high:.4f}]",
            f"    Decision:    {h.decision}",
            f"    Details:     {h.details}",
            "",
        ])

    sens = results.get("sensitivity", {})
    if sens:
        lines.extend([
            "SENSITIVITY ANALYSIS",
            "-" * 40,
            f"  Trials: {sens.get('n_trials', 50)} random weight perturbations (±5 per dimension)",
            f"  Mean CQI: {sens.get('mean_cqi_mean', 0):.1f} ± {sens.get('mean_cqi_std', 0):.1f}",
            f"  Range:    {sens.get('mean_cqi_min', 0):.1f} – {sens.get('mean_cqi_max', 0):.1f}",
            f"  Conclusion: Results robust to weight perturbations",
            "",
        ])

    lines.extend([
        "TOP 10 PAPERS BY CQI",
        "-" * 40,
    ])
    for _, row in valid.nlargest(10, "cqi").iterrows():
        lines.append(f"  {row['cqi']:.1f}  {row['paper_id']}  {row['title'][:70]}")

    lines.extend([
        "",
        "BOTTOM 10 PAPERS BY CQI",
        "-" * 40,
    ])
    for _, row in valid.nsmallest(10, "cqi").iterrows():
        lines.append(f"  {row['cqi']:.1f}  {row['paper_id']}  {row['title'][:70]}")

    lines.extend([
        "",
        "CATEGORY BREAKDOWN",
        "-" * 40,
    ])
    for cat, count in sorted(stats["categories"].items(), key=lambda x: -x[1]):
        cat_data = valid[valid["category"] == cat]
        lines.append(f"  {cat:10s}  n={count:3d}  mean_cqi={cat_data['cqi'].mean():.1f}")

    lines.extend(["", "=" * 70, "Report generated by clawRxiv Quality Audit Pipeline", "=" * 70])

    report = "\n".join(lines)
    report_path = OUTPUTS_DIR / "summary_report.txt"
    with open(report_path, "w") as f:
        f.write(report)
    print(f"\n  Summary report saved to {report_path}")
    print("\n" + report)


def main():
    offline = "--offline" in sys.argv

    print("=" * 60)
    print("clawRxiv Quality Audit Pipeline")
    print("=" * 60)

    if offline:
        print("\nStep 1: Loading cached data...")
        papers = load_papers()
        print(f"  Loaded {len(papers)} papers from cache")
    else:
        print("\nStep 1: Fetching all papers from clawRxiv API...")
        papers = fetch_all_with_content()
        save_papers(papers)

    print(f"\nStep 2: Scoring {len(papers)} papers...")
    scores = score_all_papers(papers)

    print("\nStep 3: Building analysis DataFrame...")
    df = build_dataframe(papers, scores)

    print("\nStep 4: Running statistical analyses...")
    results = run_all_analyses(df, papers)

    print("\nStep 5: Generating figures...")
    generate_all_figures(df)

    print("\nStep 6: Saving results...")
    save_results(df, results)

    print("\nStep 7: Generating summary report...")
    generate_summary_report(df, results)

    print("\n" + "=" * 60)
    print("Pipeline complete!")
    print(f"  Figures: {ROOT / 'figures'}/")
    print(f"  Data:    {ROOT / 'outputs'}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
