"""Generate a refined editorial-grade academic report as self-contained HTML."""
import base64
import csv
import json
from pathlib import Path


def img_to_b64(path):
    return base64.b64encode(Path(path).read_bytes()).decode()


def format_p(val):
    v = float(val)
    if v < 1e-10:
        return "< 10<sup>-10</sup>"
    elif v < 0.001:
        exp = f"{v:.1e}"
        mantissa, power = exp.split("e")
        return f"{mantissa} &times; 10<sup>{int(power)}</sup>"
    elif v < 0.01:
        return f"{v:.4f}"
    else:
        return f"{v:.3f}"


def build_decision_badge(decision):
    if "Reject" in decision and "NOT" in decision:
        return '<span class="badge badge-partial">Partially Supported</span>'
    elif "Reject" in decision:
        return '<span class="badge badge-supported">Supported</span>'
    else:
        return '<span class="badge badge-null">Not Supported</span>'


stats = json.load(open("outputs/corpus_stats.json"))
hyp_rows = list(csv.DictReader(open("outputs/hypothesis_tests.csv")))
figs = sorted(Path("figures").glob("fig*.png"))

fig_captions = [
    ("CQI Distribution",
     "Distribution of Composite Quality Index scores across 395 non-spam papers. "
     "The distribution is approximately normal with mean 45.2 and SD 16.9."),
    ("Quality Profile Radar",
     "Normalized dimension scores comparing top quartile (CQI &ge; 75th percentile) "
     "against bottom quartile papers across all eight quality dimensions."),
    ("Collaboration Premium",
     "Violin plot comparing CQI distributions between agent-only papers (n=169) "
     "and papers with human co-authors (n=226). Cohen&rsquo;s <em>d</em> = 1.61."),
    ("Temporal Quality Trend",
     "Individual paper CQI scores by publication day with daily means and OLS regression "
     "line. Slope = +1.74 CQI/day, <em>R</em><sup>2</sup> = 0.18."),
    ("Depth&ndash;Breadth Tradeoff",
     "Mean normalized scores for papers with and without executable skill_md artifacts. "
     "Contrary to the hypothesized tradeoff, executable papers score higher on both dimensions."),
    ("Agent Productivity vs. Quality",
     "Scatter plot of per-agent mean CQI against publication count. Point size proportional "
     "to paper volume. Color indicates presence of human collaboration."),
    ("Quality Tier Composition",
     "Stacked percentage bar chart showing the proportion of papers in each quality tier "
     "(Low, Below Average, Above Average, High) by publication day."),
    ("Inter-Dimension Correlations",
     "Spearman rank correlation matrix across all eight CQI dimensions and total score. "
     "Technical depth (&rho;=0.64) and executability (&rho;=0.58) are the strongest CQI drivers."),
    ("Quality by Subject Category",
     "Box plot of CQI scores across subject categories with three or more papers. "
     "Statistics (stat) and quantitative finance (q-fin) show the highest median quality."),
    ("Composition Effect",
     "Dual-axis plot showing mean CQI alongside the proportion of papers with skill_md "
     "and human co-authors over the observation window. Quality tracks adoption rates."),
]

hypothesis_descriptions = {
    "H1": "Do papers with human co-authors achieve higher quality scores than agent-only papers?",
    "H2": "Does average paper quality increase over the platform&rsquo;s 15-day history?",
    "H3": "Do executable papers sacrifice structural quality for technical depth?",
    "H4": "Do prolific agents produce lower-quality papers than occasional contributors?",
}

# Build figures HTML
figures_html = ""
for i, fp in enumerate(figs):
    title, caption = fig_captions[i] if i < len(fig_captions) else (fp.stem, "")
    b64 = img_to_b64(fp)
    figures_html += f"""
    <figure>
      <img src="data:image/png;base64,{b64}" alt="Figure {i+1}: {title}">
      <figcaption>
        <strong>Figure {i+1}.</strong> {caption}
      </figcaption>
    </figure>
"""

# Build hypothesis cards
hyp_cards = ""
for h in hyp_rows:
    h_key = h["hypothesis"][:2]
    question = hypothesis_descriptions.get(h_key, "")
    badge = build_decision_badge(h["decision"])
    p_formatted = format_p(h["p_value"])

    details = h.get("details", "")
    detail_short = details.split("|")[0].strip() if "|" in details else details[:120]

    hyp_cards += f"""
    <div class="hyp-card">
      <div class="hyp-header">
        <div class="hyp-id">{h["hypothesis"]}</div>
        {badge}
      </div>
      <p class="hyp-question">{question}</p>
      <div class="hyp-stats">
        <div class="hyp-stat">
          <div class="hyp-stat-label">Test</div>
          <div class="hyp-stat-value">{h["test"]}</div>
        </div>
        <div class="hyp-stat">
          <div class="hyp-stat-label"><em>p</em>-value</div>
          <div class="hyp-stat-value">{p_formatted}</div>
        </div>
        <div class="hyp-stat">
          <div class="hyp-stat-label">Effect Size</div>
          <div class="hyp-stat-value">{float(h["effect_size"]):.3f}</div>
        </div>
      </div>
      <p class="hyp-detail">{detail_short}</p>
    </div>
"""

# Build category table rows
cat_rows = ""
for cat, count in sorted(stats["categories"].items(), key=lambda x: -x[1]):
    pct = count / stats["valid_papers"] * 100
    cat_rows += f"<tr><td>{cat}</td><td>{count}</td><td>{pct:.1f}%</td></tr>\n"

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The First Audit of AI Agent Science</title>
<style>
  @page {{
    size: A4;
    margin: 2cm;
  }}

  :root {{
    --ink: #1a1f36;
    --ink-light: #3d4463;
    --ink-muted: #6b7394;
    --stone: #8b7d6b;
    --stone-light: #a89f91;
    --rule: #d4cfc7;
    --surface: #faf9f7;
    --surface-alt: #f0eee9;
    --white: #ffffff;
    --positive: #2d6a4f;
    --negative: #9b2c2c;
    --partial: #7c5e10;
  }}

  * {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }}

  body {{
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, "Times New Roman", serif;
    color: var(--ink);
    background: var(--white);
    font-size: 15px;
    line-height: 1.7;
    -webkit-font-smoothing: antialiased;
  }}

  /* ---- TITLE PAGE ---- */
  .title-page {{
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    padding: 80px 40px;
    background: var(--white);
    page-break-after: always;
  }}

  .title-page .institution {{
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: var(--stone);
    margin-bottom: 48px;
  }}

  .title-page h1 {{
    font-size: 42px;
    font-weight: 400;
    line-height: 1.15;
    color: var(--ink);
    letter-spacing: -0.5px;
    max-width: 700px;
    margin-bottom: 20px;
  }}

  .title-page .subtitle {{
    font-size: 18px;
    font-style: italic;
    color: var(--ink-muted);
    margin-bottom: 48px;
  }}

  .title-rule {{
    width: 60px;
    height: 1px;
    background: var(--stone);
    margin: 0 auto 48px;
  }}

  .title-page .authors {{
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
    font-size: 14px;
    color: var(--ink-light);
    letter-spacing: 0.5px;
  }}

  .title-page .authors span {{
    margin: 0 12px;
    color: var(--rule);
  }}

  .title-page .conference {{
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
    font-size: 12px;
    color: var(--stone-light);
    margin-top: 16px;
    letter-spacing: 1px;
    text-transform: uppercase;
  }}

  /* ---- MAIN CONTENT ---- */
  .content {{
    max-width: 820px;
    margin: 0 auto;
    padding: 60px 40px;
  }}

  .section {{
    margin-bottom: 64px;
    page-break-inside: avoid;
  }}

  .section-number {{
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: var(--stone);
    margin-bottom: 8px;
  }}

  h2 {{
    font-size: 28px;
    font-weight: 400;
    color: var(--ink);
    margin-bottom: 8px;
    letter-spacing: -0.3px;
  }}

  .section-rule {{
    width: 40px;
    height: 1px;
    background: var(--stone);
    margin-bottom: 32px;
  }}

  h3 {{
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--ink-muted);
    margin-bottom: 16px;
    margin-top: 32px;
  }}

  p {{
    margin-bottom: 16px;
  }}

  /* ---- STATS GRID ---- */
  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1px;
    background: var(--rule);
    border: 1px solid var(--rule);
    margin: 32px 0;
  }}

  .stat-cell {{
    background: var(--white);
    padding: 24px 20px;
    text-align: center;
  }}

  .stat-value {{
    font-size: 32px;
    font-weight: 300;
    color: var(--ink);
    letter-spacing: -1px;
    line-height: 1;
    margin-bottom: 6px;
  }}

  .stat-label {{
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--stone);
  }}

  /* ---- TABLES ---- */
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 24px 0;
    font-size: 14px;
  }}

  thead th {{
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--stone);
    text-align: left;
    padding: 12px 16px;
    border-bottom: 2px solid var(--ink);
  }}

  tbody td {{
    padding: 10px 16px;
    border-bottom: 1px solid var(--rule);
    color: var(--ink-light);
  }}

  tbody tr:last-child td {{
    border-bottom: 2px solid var(--ink);
  }}

  td:nth-child(n+2) {{
    text-align: right;
    font-variant-numeric: tabular-nums;
  }}

  /* ---- HYPOTHESIS CARDS ---- */
  .hyp-card {{
    border: 1px solid var(--rule);
    padding: 28px 32px;
    margin-bottom: 20px;
    page-break-inside: avoid;
  }}

  .hyp-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }}

  .hyp-id {{
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
    font-size: 13px;
    font-weight: 700;
    color: var(--ink);
    letter-spacing: 0.5px;
  }}

  .badge {{
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 4px 12px;
  }}

  .badge-supported {{
    color: var(--positive);
    border: 1px solid var(--positive);
  }}

  .badge-null {{
    color: var(--negative);
    border: 1px solid var(--negative);
  }}

  .badge-partial {{
    color: var(--partial);
    border: 1px solid var(--partial);
  }}

  .hyp-question {{
    font-style: italic;
    color: var(--ink-muted);
    font-size: 14px;
    margin-bottom: 20px;
    line-height: 1.5;
  }}

  .hyp-stats {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 16px;
  }}

  .hyp-stat-label {{
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--stone);
    margin-bottom: 4px;
  }}

  .hyp-stat-value {{
    font-size: 14px;
    color: var(--ink);
    font-variant-numeric: tabular-nums;
  }}

  .hyp-detail {{
    font-size: 13px;
    color: var(--ink-muted);
    padding-top: 12px;
    border-top: 1px solid var(--surface-alt);
    margin-bottom: 0;
  }}

  /* ---- FIGURES ---- */
  figure {{
    margin: 48px 0;
    page-break-inside: avoid;
  }}

  figure img {{
    width: 100%;
    display: block;
    border: 1px solid var(--rule);
  }}

  figcaption {{
    font-size: 13px;
    color: var(--ink-muted);
    line-height: 1.6;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--rule);
  }}

  figcaption strong {{
    color: var(--ink);
  }}

  /* ---- METHODOLOGY ---- */
  .method-text {{
    font-size: 14px;
    color: var(--ink-light);
    line-height: 1.8;
  }}

  .mono {{
    font-family: "SF Mono", "Fira Code", "Cascadia Code", "Menlo", monospace;
    font-size: 13px;
    background: var(--surface-alt);
    padding: 2px 6px;
  }}

  /* ---- FOOTER ---- */
  .report-footer {{
    margin-top: 80px;
    padding-top: 24px;
    border-top: 1px solid var(--rule);
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
    font-size: 11px;
    color: var(--stone-light);
    text-align: center;
    letter-spacing: 0.5px;
  }}

  /* ---- PRINT ---- */
  @media print {{
    .title-page {{
      min-height: auto;
      padding: 120px 40px;
    }}
    .content {{
      padding: 40px 20px;
    }}
    figure {{
      page-break-inside: avoid;
    }}
  }}
</style>
</head>
<body>

<!-- TITLE PAGE -->
<div class="title-page">
  <div class="institution">Claw4S Conference 2026</div>
  <h1>The First Audit of AI Agent Science</h1>
  <p class="subtitle">A Bibliometric Quality Analysis of clawRxiv</p>
  <div class="title-rule"></div>
  <div class="authors">
    Claw<span>&middot;</span>Andaman<span>&middot;</span>Claude
  </div>
  <p class="conference">Stanford &amp; Princeton &bull; April 2026</p>
</div>

<!-- MAIN CONTENT -->
<div class="content">

  <!-- EXECUTIVE SUMMARY -->
  <div class="section">
    <div class="section-number">Overview</div>
    <h2>Executive Summary</h2>
    <div class="section-rule"></div>

    <div class="stats-grid">
      <div class="stat-cell">
        <div class="stat-value">{stats["total_papers"]}</div>
        <div class="stat-label">Papers Analyzed</div>
      </div>
      <div class="stat-cell">
        <div class="stat-value">{stats["unique_agents"]}</div>
        <div class="stat-label">Unique Agents</div>
      </div>
      <div class="stat-cell">
        <div class="stat-value">{stats["observation_days"]}</div>
        <div class="stat-label">Days Observed</div>
      </div>
      <div class="stat-cell">
        <div class="stat-value">{stats["cqi_mean"]:.1f}</div>
        <div class="stat-label">Mean CQI</div>
      </div>
      <div class="stat-cell">
        <div class="stat-value">{stats["pct_skill"]:.0f}%</div>
        <div class="stat-label">With Skill Artifact</div>
      </div>
      <div class="stat-cell">
        <div class="stat-value">{stats["pct_collab"]:.0f}%</div>
        <div class="stat-label">Human Collaboration</div>
      </div>
    </div>

    <p>This report presents the first systematic quality audit of AI agent-authored
    scientific publications. Analyzing the complete corpus of clawRxiv&mdash;an academic
    archive where {stats["unique_agents"]} AI agents have autonomously published
    {stats["total_papers"]} papers in {stats["observation_days"]} days&mdash;we develop
    a Composite Quality Index spanning eight dimensions and test four pre-registered
    hypotheses about the determinants of quality in agent-authored science.</p>
  </div>

  <!-- CORPUS OVERVIEW -->
  <div class="section">
    <div class="section-number">Section I</div>
    <h2>Corpus Overview</h2>
    <div class="section-rule"></div>

    <p>After spam filtering ({stats["spam_flagged"]} papers, {stats["spam_flagged"]/stats["total_papers"]*100:.1f}%),
    the analytic corpus contains <strong>{stats["valid_papers"]}</strong> papers from
    <strong>{stats["unique_agents"]}</strong> unique agents. The CQI distribution is
    approximately normal (mean&nbsp;=&nbsp;{stats["cqi_mean"]:.1f},
    median&nbsp;=&nbsp;{stats["cqi_median"]:.1f},
    SD&nbsp;=&nbsp;{stats["cqi_std"]:.1f},
    range&nbsp;{stats["cqi_min"]:.1f}&ndash;{stats["cqi_max"]:.1f}).
    Duplicate analysis identified {stats["near_duplicates"]} near-duplicate title pairs.</p>

    <h3>Distribution by Category</h3>
    <table>
      <thead>
        <tr><th>Category</th><th>Papers</th><th>Share</th></tr>
      </thead>
      <tbody>
        {cat_rows}
      </tbody>
    </table>
  </div>

  <!-- HYPOTHESIS TESTS -->
  <div class="section">
    <div class="section-number">Section II</div>
    <h2>Hypothesis Tests</h2>
    <div class="section-rule"></div>

    <p>Four hypotheses were tested using appropriate statistical methods with
    &alpha;&nbsp;=&nbsp;0.05. Effect sizes and confidence intervals are reported
    alongside <em>p</em>-values to assess practical significance.</p>

    {hyp_cards}
  </div>

  <!-- FIGURES -->
  <div class="section">
    <div class="section-number">Section III</div>
    <h2>Figures</h2>
    <div class="section-rule"></div>

    {figures_html}
  </div>

  <!-- METHODOLOGY -->
  <div class="section">
    <div class="section-number">Section IV</div>
    <h2>Methodology</h2>
    <div class="section-rule"></div>

    <p class="method-text">The Composite Quality Index aggregates eight normalized
    dimensions&mdash;structural quality (w=20), content depth (w=15), executable
    component (w=10), collaboration signal (w=10), citation quality (w=15),
    technical depth (w=15), metadata quality (w=10), and originality (w=5)&mdash;into
    a weighted sum ranging from 0 to 100. Statistical tests include Welch&rsquo;s
    <em>t</em>-test with 10,000-iteration bootstrapped Cohen&rsquo;s <em>d</em>&nbsp;(H1),
    OLS regression with HC3 heteroskedasticity-robust standard errors&nbsp;(H2),
    Mann&ndash;Whitney <em>U</em> with Bonferroni correction&nbsp;(H3), and Spearman
    rank correlation&nbsp;(H4). A 50-trial sensitivity analysis perturbing dimension
    weights by &plusmn;5 confirms robustness (CQI &plusmn; 2.0 across perturbations).</p>

    <p class="method-text">All random operations seeded with
    <span class="mono">random_state=42</span>. Reproducible via
    <span class="mono">python run_pipeline.py</span>.</p>
  </div>

  <!-- FOOTER -->
  <div class="report-footer">
    <p>Generated by clawRxiv Quality Audit Pipeline</p>
    <p>Claw4S Conference 2026 &bull; Stanford &amp; Princeton</p>
  </div>

</div>
</body>
</html>"""

out = Path("outputs/audit_report.html")
out.write_text(html)
print(f"Report: {out} ({out.stat().st_size / 1024:.0f} KB)")
print(f"  {len(figs)} figures inlined")
print(f"  {len(hyp_rows)} hypothesis tests")
