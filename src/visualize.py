"""Publication-quality figures for the clawRxiv quality audit."""

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.patches import FancyBboxPatch

FIGURES_DIR = Path(__file__).resolve().parent.parent / "figures"
RANDOM_STATE = 42

PALETTE = {
    "primary": "#1B2A4A",
    "accent": "#D55E00",
    "secondary": "#0072B2",
    "success": "#009E73",
    "warning": "#E69F00",
    "danger": "#CC3333",
    "light": "#F5F5F5",
    "text": "#333333",
    "grid": "#E0E0E0",
}

TIER_COLORS = ["#CC3333", "#E69F00", "#0072B2", "#009E73"]
TIER_LABELS = ["Low (0-25)", "Below Avg (25-50)", "Above Avg (50-75)", "High (75-100)"]


def setup_style():
    """Configure matplotlib for publication-quality output."""
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "grid.linestyle": "--",
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.2,
    })


def save_fig(fig, name):
    """Save figure to the figures directory."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    filepath = FIGURES_DIR / f"{name}.png"
    fig.savefig(filepath)
    plt.close(fig)
    print(f"  Saved {filepath}")


def fig1_cqi_distribution(df):
    """Figure 1: CQI distribution histogram with KDE."""
    valid = df[~df["is_spam"]]
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.hist(
        valid["cqi"], bins=30, color=PALETTE["secondary"], alpha=0.7,
        edgecolor="white", linewidth=0.5, label="Papers", zorder=2,
    )

    ax2 = ax.twinx()
    valid["cqi"].plot.kde(ax=ax2, color=PALETTE["primary"], linewidth=2.5, label="Density")
    ax2.set_ylabel("")
    ax2.set_yticks([])
    ax2.spines["right"].set_visible(False)

    mean_cqi = valid["cqi"].mean()
    median_cqi = valid["cqi"].median()
    ax.axvline(mean_cqi, color=PALETTE["accent"], linestyle="--", linewidth=2, label=f"Mean ({mean_cqi:.1f})")
    ax.axvline(median_cqi, color=PALETTE["success"], linestyle="-.", linewidth=2, label=f"Median ({median_cqi:.1f})")

    for threshold in [25, 50, 75]:
        ax.axvline(threshold, color=PALETTE["grid"], linestyle=":", linewidth=1, alpha=0.8)

    ax.set_xlabel("Composite Quality Index (CQI)")
    ax.set_ylabel("Number of Papers")
    ax.set_title("Distribution of Paper Quality Across clawRxiv")
    ax.legend(loc="upper right", framealpha=0.9)
    ax.set_xlim(0, 100)

    n = len(valid)
    textstr = f"n = {n}\nMean = {mean_cqi:.1f}\nMedian = {median_cqi:.1f}\nSD = {valid['cqi'].std():.1f}"
    props = dict(boxstyle="round,pad=0.5", facecolor=PALETTE["light"], alpha=0.8)
    ax.text(0.02, 0.95, textstr, transform=ax.transAxes, fontsize=10,
            verticalalignment="top", bbox=props)

    save_fig(fig, "fig1_cqi_distribution")


def fig2_radar_chart(df):
    """Figure 2: Radar chart comparing quality profiles."""
    valid = df[~df["is_spam"]]
    dim_cols = ["c1_executability", "c2_reproducibility", "c3_rigor",
                "c4_generalizability", "c5_clarity"]
    dim_labels = ["Executability", "Reproducibility", "Scientific\nRigor",
                  "Generalizability", "Clarity"]

    q75 = valid["cqi"].quantile(0.75)
    q25 = valid["cqi"].quantile(0.25)
    top = valid[valid["cqi"] >= q75]
    bottom = valid[valid["cqi"] <= q25]

    means_all = valid[dim_cols].mean().values
    means_top = top[dim_cols].mean().values
    means_bottom = bottom[dim_cols].mean().values

    angles = np.linspace(0, 2 * np.pi, len(dim_labels), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

    for means, color, label, alpha in [
        (means_all, PALETTE["secondary"], "All Papers", 0.15),
        (means_top, PALETTE["success"], "Top Quartile", 0.1),
        (means_bottom, PALETTE["danger"], "Bottom Quartile", 0.1),
    ]:
        values = means.tolist() + [means[0]]
        ax.plot(angles, values, "o-", linewidth=2, color=color, label=label)
        ax.fill(angles, values, alpha=alpha, color=color)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(dim_labels, fontsize=10)
    ax.set_ylim(0, 1)
    ax.set_title("Quality Profile: Top vs Bottom Quartile", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), framealpha=0.9)

    save_fig(fig, "fig2_radar_chart")


def fig3_collaboration_effect(df):
    """Figure 3: Violin plot comparing CQI by collaboration status."""
    valid = df[~df["is_spam"]].copy()
    valid["group"] = valid["has_collab"].map({True: "Human Co-author", False: "Agent Only"})

    fig, ax = plt.subplots(figsize=(8, 6))

    parts = ax.violinplot(
        [valid[valid["group"] == g]["cqi"].values for g in ["Agent Only", "Human Co-author"]],
        positions=[0, 1], showmeans=True, showmedians=True,
    )

    colors = [PALETTE["secondary"], PALETTE["accent"]]
    for i, pc in enumerate(parts["bodies"]):
        pc.set_facecolor(colors[i])
        pc.set_alpha(0.6)

    for key in ["cmeans", "cmedians", "cmins", "cmaxes", "cbars"]:
        if key in parts:
            parts[key].set_color(PALETTE["primary"])

    for i, group in enumerate(["Agent Only", "Human Co-author"]):
        data = valid[valid["group"] == group]["cqi"]
        rng = np.random.RandomState(RANDOM_STATE)
        jitter = rng.normal(0, 0.04, size=len(data))
        ax.scatter(
            np.full(len(data), i) + jitter, data,
            alpha=0.3, s=15, color=colors[i], zorder=3,
        )

    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Agent Only", "Human Co-author"])
    ax.set_ylabel("Composite Quality Index (CQI)")
    ax.set_title("H1: Collaboration Premium — CQI by Author Type")

    solo_mean = valid[valid["group"] == "Agent Only"]["cqi"].mean()
    collab_mean = valid[valid["group"] == "Human Co-author"]["cqi"].mean()
    diff = collab_mean - solo_mean
    ax.text(0.5, 0.95, f"Difference: {diff:+.1f} CQI points",
            transform=ax.transAxes, ha="center", fontsize=11,
            bbox=dict(boxstyle="round", facecolor=PALETTE["light"], alpha=0.8))

    save_fig(fig, "fig3_collaboration_effect")


def fig4_temporal_trend(df):
    """Figure 4: Scatter plot with regression line for temporal quality trend."""
    valid = df[~df["is_spam"]].dropna(subset=["day_num"])

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.scatter(
        valid["day_num"], valid["cqi"],
        alpha=0.3, s=20, color=PALETTE["secondary"], zorder=2,
    )

    daily = valid.groupby("day_num")["cqi"].agg(["mean", "std", "count"]).reset_index()
    ax.plot(
        daily["day_num"], daily["mean"],
        "o-", color=PALETTE["accent"], linewidth=2, markersize=8,
        label="Daily Mean", zorder=3,
    )
    ax.fill_between(
        daily["day_num"],
        daily["mean"] - daily["std"],
        daily["mean"] + daily["std"],
        alpha=0.15, color=PALETTE["accent"],
    )

    z = np.polyfit(valid["day_num"], valid["cqi"], 1)
    p = np.poly1d(z)
    x_line = np.linspace(valid["day_num"].min(), valid["day_num"].max(), 100)
    ax.plot(x_line, p(x_line), "--", color=PALETTE["danger"], linewidth=2,
            label=f"Trend: {z[0]:+.2f} CQI/day")

    ax.set_xlabel("Day (since platform launch)")
    ax.set_ylabel("Composite Quality Index (CQI)")
    ax.set_title("H2: Learning Curve — Quality Over Time")
    ax.legend(loc="upper left", framealpha=0.9)
    ax.set_xlim(0.5, daily["day_num"].max() + 0.5)

    save_fig(fig, "fig4_temporal_trend")


def fig5_depth_breadth(df):
    """Figure 5: Grouped bar chart for depth-breadth tradeoff."""
    valid = df[~df["is_spam"]]

    skill = valid[valid["has_skill_md"]]
    no_skill = valid[~valid["has_skill_md"]]

    metrics = {
        "Technical\nDepth": ("raw_technical", PALETTE["secondary"]),
        "Structural\nQuality": ("raw_structural", PALETTE["accent"]),
        "Citation\nQuality": ("raw_citations", PALETTE["success"]),
        "Content\nDepth": ("raw_depth", PALETTE["warning"]),
    }

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(metrics))
    width = 0.35

    means_skill = [skill[col].mean() for _, (col, _) in metrics.items()]
    means_no = [no_skill[col].mean() for _, (col, _) in metrics.items()]
    sems_skill = [skill[col].sem() for _, (col, _) in metrics.items()]
    sems_no = [no_skill[col].sem() for _, (col, _) in metrics.items()]

    bars1 = ax.bar(x - width / 2, means_skill, width, yerr=sems_skill,
                   label="Has skill_md", color=PALETTE["accent"], alpha=0.85,
                   capsize=4, edgecolor="white")
    bars2 = ax.bar(x + width / 2, means_no, width, yerr=sems_no,
                   label="No skill_md", color=PALETTE["secondary"], alpha=0.85,
                   capsize=4, edgecolor="white")

    ax.set_xticks(x)
    ax.set_xticklabels(list(metrics.keys()))
    ax.set_ylabel("Mean Normalized Score (0-1)")
    ax.set_title("H3: Do Executable Papers Trade Structure for Depth?")
    ax.legend(framealpha=0.9)
    ax.set_ylim(0, 1)

    save_fig(fig, "fig5_depth_breadth")


def fig6_agent_productivity(df):
    """Figure 6: Agent productivity vs quality scatter."""
    valid = df[~df["is_spam"]]
    agent = valid.groupby("claw_name").agg(
        count=("cqi", "size"),
        mean_cqi=("cqi", "mean"),
        has_collab=("has_collab", "any"),
    ).reset_index()

    fig, ax = plt.subplots(figsize=(10, 7))

    for has_c, color, label in [(True, PALETTE["accent"], "Has human collab"),
                                 (False, PALETTE["secondary"], "Agent only")]:
        subset = agent[agent["has_collab"] == has_c]
        ax.scatter(
            subset["count"], subset["mean_cqi"],
            s=subset["count"] * 30, alpha=0.6, color=color,
            edgecolors="white", linewidth=0.5, label=label, zorder=3,
        )

    top5 = agent.nlargest(5, "count")
    for _, row in top5.iterrows():
        name = row["claw_name"][:20]
        ax.annotate(
            name, (row["count"], row["mean_cqi"]),
            textcoords="offset points", xytext=(8, 8),
            fontsize=8, alpha=0.8,
            arrowprops=dict(arrowstyle="-", alpha=0.4),
        )

    ax.set_xlabel("Papers Published (per agent)")
    ax.set_ylabel("Mean CQI")
    ax.set_title("Agent Productivity vs. Quality")
    ax.legend(framealpha=0.9)

    if agent["count"].max() > 20:
        ax.set_xscale("symlog", linthresh=5)
        ax.xaxis.set_major_formatter(mticker.ScalarFormatter())

    save_fig(fig, "fig6_agent_productivity")


def fig7_quality_tiers(df):
    """Figure 7: Stacked bar chart of quality tiers over time."""
    valid = df[~df["is_spam"]].dropna(subset=["day_num"])

    valid = valid.copy()
    valid["tier"] = pd.cut(
        valid["cqi"], bins=[0, 25, 50, 75, 100],
        labels=TIER_LABELS, include_lowest=True,
    )

    pivot = valid.groupby(["day_num", "tier"], observed=False).size().unstack(fill_value=0)
    pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100

    fig, ax = plt.subplots(figsize=(12, 6))

    for col in TIER_LABELS:
        if col not in pivot_pct.columns:
            pivot_pct[col] = 0
    pivot_pct = pivot_pct[TIER_LABELS]

    pivot_pct.plot.bar(stacked=True, ax=ax, color=TIER_COLORS, alpha=0.85,
                       edgecolor="white", linewidth=0.5)

    ax.set_xlabel("Day (since platform launch)")
    ax.set_ylabel("Percentage of Papers")
    ax.set_title("Quality Tier Composition Over Time")
    ax.legend(title="Quality Tier", bbox_to_anchor=(1.02, 1), loc="upper left", framealpha=0.9)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())

    save_fig(fig, "fig7_quality_tiers")


def fig8_correlation_heatmap(df):
    """Figure 8: Correlation heatmap of quality dimensions."""
    valid = df[~df["is_spam"]]
    dim_cols = ["c1_executability", "c2_reproducibility", "c3_rigor",
                "c4_generalizability", "c5_clarity", "cqi"]
    labels = ["Executability", "Reproducibility", "Rigor",
              "Generalizability", "Clarity", "CQI"]

    corr = valid[dim_cols].corr(method="spearman")

    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)

    fig, ax = plt.subplots(figsize=(9, 8))
    sns.heatmap(
        corr, mask=mask, annot=True, fmt=".2f",
        cmap="RdBu_r", center=0, vmin=-1, vmax=1,
        square=True, linewidths=1, linecolor="white",
        xticklabels=labels, yticklabels=labels,
        ax=ax, cbar_kws={"label": "Spearman ρ", "shrink": 0.8},
    )
    ax.set_title("Inter-Dimension Correlations (Spearman)")

    save_fig(fig, "fig8_correlation_heatmap")


def fig9_category_quality(df):
    """Figure 9: Box plot of CQI by category."""
    valid = df[~df["is_spam"]]
    cat_counts = valid["category"].value_counts()
    valid_cats = cat_counts[cat_counts >= 3].index.tolist()
    plot_data = valid[valid["category"].isin(valid_cats)]

    cat_order = plot_data.groupby("category")["cqi"].median().sort_values(ascending=False).index.tolist()

    fig, ax = plt.subplots(figsize=(10, 6))

    bp = ax.boxplot(
        [plot_data[plot_data["category"] == c]["cqi"].values for c in cat_order],
        labels=cat_order, patch_artist=True, widths=0.6,
        medianprops=dict(color=PALETTE["accent"], linewidth=2),
        whiskerprops=dict(color=PALETTE["primary"]),
        capprops=dict(color=PALETTE["primary"]),
        flierprops=dict(marker="o", markerfacecolor=PALETTE["secondary"], markersize=4, alpha=0.5),
    )
    for patch in bp["boxes"]:
        patch.set_facecolor(PALETTE["secondary"])
        patch.set_alpha(0.6)

    for i, cat in enumerate(cat_order):
        n = len(plot_data[plot_data["category"] == cat])
        ax.text(i + 1, ax.get_ylim()[0] - 2, f"n={n}", ha="center", fontsize=9, color=PALETTE["text"])

    ax.set_xlabel("Category")
    ax.set_ylabel("Composite Quality Index (CQI)")
    ax.set_title("Paper Quality by Subject Category")

    save_fig(fig, "fig9_category_quality")


def fig10_confound_analysis(df):
    """Figure 10: Temporal confound — skill/collab rates co-evolve with quality."""
    valid = df[~df["is_spam"]].dropna(subset=["day_num"])

    daily = valid.groupby("day_num").agg(
        mean_cqi=("cqi", "mean"),
        pct_skill=("has_skill_md", "mean"),
        pct_collab=("has_collab", "mean"),
        count=("cqi", "size"),
    ).reset_index()

    fig, ax1 = plt.subplots(figsize=(10, 6))

    color_cqi = PALETTE["primary"]
    ax1.plot(daily["day_num"], daily["mean_cqi"], "o-", color=color_cqi,
             linewidth=2.5, markersize=8, label="Mean CQI", zorder=3)
    ax1.set_xlabel("Day (since platform launch)")
    ax1.set_ylabel("Mean CQI", color=color_cqi)
    ax1.tick_params(axis="y", labelcolor=color_cqi)
    ax1.set_ylim(0, 100)

    ax2 = ax1.twinx()
    ax2.plot(daily["day_num"], daily["pct_skill"] * 100, "s--", color=PALETTE["accent"],
             linewidth=2, markersize=6, alpha=0.8, label="% with skill_md")
    ax2.plot(daily["day_num"], daily["pct_collab"] * 100, "^--", color=PALETTE["success"],
             linewidth=2, markersize=6, alpha=0.8, label="% with human co-author")
    ax2.set_ylabel("Percentage (%)")
    ax2.set_ylim(0, 110)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="center left",
               framealpha=0.9, fontsize=10)

    ax1.set_title("The Composition Effect: Quality Tracks Skill & Collaboration Adoption")

    for i, row in daily.iterrows():
        ax1.annotate(f"n={int(row['count'])}", (row["day_num"], row["mean_cqi"]),
                     textcoords="offset points", xytext=(0, 12),
                     fontsize=7, ha="center", alpha=0.6)

    save_fig(fig, "fig10_confound_analysis")


def generate_all_figures(df):
    """Generate all 10 figures."""
    setup_style()
    print("\n" + "=" * 60)
    print("Generating Figures")
    print("=" * 60)

    fig_funcs = [
        ("Figure 1: CQI Distribution", fig1_cqi_distribution),
        ("Figure 2: Radar Chart", fig2_radar_chart),
        ("Figure 3: Collaboration Effect", fig3_collaboration_effect),
        ("Figure 4: Temporal Trend", fig4_temporal_trend),
        ("Figure 5: Depth-Breadth Tradeoff", fig5_depth_breadth),
        ("Figure 6: Agent Productivity", fig6_agent_productivity),
        ("Figure 7: Quality Tiers", fig7_quality_tiers),
        ("Figure 8: Correlation Heatmap", fig8_correlation_heatmap),
        ("Figure 9: Category Quality", fig9_category_quality),
        ("Figure 10: Confound Analysis", fig10_confound_analysis),
    ]

    for name, func in fig_funcs:
        print(f"\n  Generating {name}...")
        try:
            func(df)
        except Exception as e:
            print(f"    ERROR generating {name}: {e}")

    print(f"\nAll figures saved to {FIGURES_DIR}/")
