"""Statistical analysis for the clawRxiv quality audit."""

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import statsmodels.api as sm


RANDOM_STATE = 42


@dataclass(frozen=True)
class HypothesisResult:
    name: str
    test_name: str
    statistic: float
    p_value: float
    effect_size: float
    effect_ci_low: float
    effect_ci_high: float
    decision: str
    details: str


def build_dataframe(papers, scores):
    """Build a pandas DataFrame from papers and their scores."""
    rows = []
    for paper, score in zip(papers, scores):
        created = paper.get("createdAt") or paper.get("created_at", "")
        try:
            dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            day_num = (dt - datetime(2026, 3, 17, tzinfo=dt.tzinfo)).days + 1
            date_str = dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            day_num = None
            date_str = None

        dim_dict = {d.name: d.normalized for d in score.dimensions}
        raw_dict = dict(score.raw_sub_indicators) if score.raw_sub_indicators else {}

        rows.append({
            "paper_id": score.paper_id,
            "title": score.title,
            "cqi": score.cqi,
            "cqi_no_collab": raw_dict.get("cqi_no_collab", score.cqi),
            "is_spam": score.is_spam,
            "is_near_duplicate": score.is_near_duplicate,
            "max_title_sim": score.max_title_similarity,
            "claw_name": paper.get("clawName", ""),
            "category": paper.get("category", ""),
            "subcategory": paper.get("subcategory", ""),
            "tags": paper.get("tags", []),
            "has_skill_md": raw_dict.get("executable", 0) > 0,
            "has_collab": raw_dict.get("collaboration", 0) > 0,
            "upvotes": paper.get("upvotes", 0),
            "downvotes": paper.get("downvotes", 0),
            "net_votes": paper.get("upvotes", 0) - paper.get("downvotes", 0),
            "created_at": date_str,
            "day_num": day_num,
            "c1_executability": dim_dict.get("Executability", 0),
            "c2_reproducibility": dim_dict.get("Reproducibility", 0),
            "c3_rigor": dim_dict.get("Scientific Rigor", 0),
            "c4_generalizability": dim_dict.get("Generalizability", 0),
            "c5_clarity": dim_dict.get("Clarity for Agents", 0),
            "raw_structural": raw_dict.get("structural", 0),
            "raw_technical": raw_dict.get("technical", 0),
            "raw_citations": raw_dict.get("citations", 0),
            "raw_depth": raw_dict.get("depth", 0),
            "raw_metadata": raw_dict.get("metadata", 0),
            "word_count": len((paper.get("content", "") or "").split()),
            "has_claw4s_tag": "claw4s-2026" in (paper.get("tags") or []),
        })

    return pd.DataFrame(rows)


def filter_valid(df):
    """Filter to non-spam papers for hypothesis testing."""
    return df[~df["is_spam"]].copy()


def cohens_d(group1, group2):
    """Compute Cohen's d effect size."""
    n1, n2 = len(group1), len(group2)
    var1, var2 = group1.var(ddof=1), group2.var(ddof=1)
    pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    if pooled_std == 0:
        return 0.0
    return (group1.mean() - group2.mean()) / pooled_std


def bootstrap_ci(group1, group2, n_boot=10000, alpha=0.05):
    """Bootstrap 95% CI for Cohen's d."""
    rng = np.random.RandomState(RANDOM_STATE)
    d_boot = []
    for _ in range(n_boot):
        s1 = rng.choice(group1, size=len(group1), replace=True)
        s2 = rng.choice(group2, size=len(group2), replace=True)
        d_boot.append(cohens_d(pd.Series(s1), pd.Series(s2)))
    lower = np.percentile(d_boot, 100 * alpha / 2)
    upper = np.percentile(d_boot, 100 * (1 - alpha / 2))
    return lower, upper


def test_h1_collaboration(df):
    """H1: Papers with human co-authors score higher on CQI.

    To address circularity (collaboration is a CQI sub-indicator), we report
    the effect on both full CQI and collaboration-blind CQI (which excludes
    the collaboration signal from the Reproducibility criterion).
    """
    valid = filter_valid(df)
    collab = valid[valid["has_collab"]]["cqi"].values
    solo = valid[~valid["has_collab"]]["cqi"].values

    t_stat, p_welch = stats.ttest_ind(collab, solo, equal_var=False)
    u_stat, p_mann = stats.mannwhitneyu(collab, solo, alternative="two-sided")
    d = cohens_d(pd.Series(collab), pd.Series(solo))
    ci_low, ci_high = bootstrap_ci(collab, solo)

    # Collaboration-blind CQI (removes circularity)
    collab_blind = valid[valid["has_collab"]]["cqi_no_collab"].values
    solo_blind = valid[~valid["has_collab"]]["cqi_no_collab"].values
    d_blind = cohens_d(pd.Series(collab_blind), pd.Series(solo_blind))
    t_blind, p_blind = stats.ttest_ind(collab_blind, solo_blind, equal_var=False)

    decision = "Reject H0" if p_welch < 0.05 else "Fail to reject H0"

    return HypothesisResult(
        name="H1: Collaboration Premium",
        test_name="Welch's t-test",
        statistic=t_stat,
        p_value=p_welch,
        effect_size=d,
        effect_ci_low=ci_low,
        effect_ci_high=ci_high,
        decision=decision,
        details=(
            f"Collab: n={len(collab)}, mean={np.mean(collab):.1f}, sd={np.std(collab, ddof=1):.1f} | "
            f"Solo: n={len(solo)}, mean={np.mean(solo):.1f}, sd={np.std(solo, ddof=1):.1f} | "
            f"Mann-Whitney U={u_stat:.0f}, p={p_mann:.4f} | "
            f"Collab-blind CQI: d={d_blind:.3f}, t={t_blind:.2f}, p={p_blind:.2e}"
        ),
    )


def test_h2_learning_curve(df):
    """H2: Paper quality increases over the observation window.

    We run two models: (1) naive OLS with day_num only, and (2) controlled
    OLS adding has_skill_md and has_collab as covariates to disentangle the
    composition effect from a genuine temporal trend.
    """
    valid = filter_valid(df).dropna(subset=["day_num"])
    y = valid["cqi"].values.astype(float)

    # Naive model (day_num only)
    x = valid["day_num"].values.astype(float)
    X_naive = sm.add_constant(x)
    model_naive = sm.OLS(y, X_naive).fit(cov_type="HC3")
    beta_naive = model_naive.params[1]
    p_naive = model_naive.pvalues[1]
    r_sq_naive = model_naive.rsquared

    # Controlled model (day_num + has_skill_md + has_collab)
    X_ctrl = np.column_stack([
        x,
        valid["has_skill_md"].astype(float).values,
        valid["has_collab"].astype(float).values,
    ])
    X_ctrl = sm.add_constant(X_ctrl)
    model_ctrl = sm.OLS(y, X_ctrl).fit(cov_type="HC3")
    beta_ctrl = model_ctrl.params[1]
    p_ctrl = model_ctrl.pvalues[1]
    r_sq_ctrl = model_ctrl.rsquared

    rho, p_spearman = stats.spearmanr(x, y)

    decision = "Reject H0" if p_naive < 0.05 else "Fail to reject H0"

    return HypothesisResult(
        name="H2: Learning Curve",
        test_name="OLS Regression (HC3)",
        statistic=beta_naive,
        p_value=p_naive,
        effect_size=r_sq_naive,
        effect_ci_low=model_naive.conf_int()[1][0],
        effect_ci_high=model_naive.conf_int()[1][1],
        decision=decision,
        details=(
            f"Naive: beta={beta_naive:.3f}, R²={r_sq_naive:.4f}, n={len(x)} | "
            f"Controlled (+ skill_md, collab): beta={beta_ctrl:.3f}, p={p_ctrl:.4f}, R²={r_sq_ctrl:.4f} | "
            f"Spearman rho={rho:.3f}, p={p_spearman:.4f}"
        ),
    )


def test_h3_depth_breadth(df):
    """H3: Skill papers have higher technical depth but lower structural quality."""
    valid = filter_valid(df)
    skill = valid[valid["has_skill_md"]]
    no_skill = valid[~valid["has_skill_md"]]

    tech_skill = skill["raw_technical"].values
    tech_noskill = no_skill["raw_technical"].values
    struct_skill = skill["raw_structural"].values
    struct_noskill = no_skill["raw_structural"].values

    u_tech, p_tech = stats.mannwhitneyu(tech_skill, tech_noskill, alternative="two-sided")
    u_struct, p_struct = stats.mannwhitneyu(struct_skill, struct_noskill, alternative="two-sided")

    d_tech = cohens_d(pd.Series(tech_skill), pd.Series(tech_noskill))
    d_struct = cohens_d(pd.Series(struct_skill), pd.Series(struct_noskill))

    p_bonf_tech = min(p_tech * 2, 1.0)
    p_bonf_struct = min(p_struct * 2, 1.0)

    tech_higher = np.mean(tech_skill) > np.mean(tech_noskill)
    struct_lower = np.mean(struct_skill) < np.mean(struct_noskill)

    if tech_higher and struct_lower and p_bonf_tech < 0.05 and p_bonf_struct < 0.05:
        decision = "Reject H0 (tradeoff confirmed)"
    elif p_bonf_tech < 0.05 or p_bonf_struct < 0.05:
        decision = "Reject H0 (difference found, but NOT the predicted tradeoff)"
    else:
        decision = "Fail to reject H0"

    return HypothesisResult(
        name="H3: Depth-Breadth Tradeoff",
        test_name="Mann-Whitney U (Bonferroni)",
        statistic=u_tech,
        p_value=p_bonf_tech,
        effect_size=d_tech,
        effect_ci_low=d_struct,
        effect_ci_high=p_bonf_struct,
        decision=decision,
        details=(
            f"Tech Depth — skill: mean={np.mean(tech_skill):.3f}, no_skill: mean={np.mean(tech_noskill):.3f}, "
            f"U={u_tech:.0f}, p(adj)={p_bonf_tech:.4f}, d={d_tech:.3f} | "
            f"Structural — skill: mean={np.mean(struct_skill):.3f}, no_skill: mean={np.mean(struct_noskill):.3f}, "
            f"U={u_struct:.0f}, p(adj)={p_bonf_struct:.4f}, d={d_struct:.3f}"
        ),
    )


def test_h4_lotka_law(df):
    """H4: Prolific agents produce lower-quality papers (Lotka's Law analog)."""
    valid = filter_valid(df)
    agent = valid.groupby("claw_name").agg(
        count=("cqi", "size"),
        mean_cqi=("cqi", "mean"),
    ).reset_index()

    agent_multi = agent[agent["count"] >= 2]

    rho, p_spearman = stats.spearmanr(agent_multi["count"], agent_multi["mean_cqi"])

    decision = "Reject H0" if p_spearman < 0.05 else "Fail to reject H0"

    return HypothesisResult(
        name="H4: Lotka's Law (Quantity-Quality Tradeoff)",
        test_name="Spearman rank correlation",
        statistic=rho,
        p_value=p_spearman,
        effect_size=rho,
        effect_ci_low=0.0,
        effect_ci_high=0.0,
        decision=decision,
        details=(
            f"Agents with >=2 papers: n={len(agent_multi)} | "
            f"Spearman rho={rho:.3f}, p={p_spearman:.4f} | "
            f"Most prolific: {agent.nlargest(3, 'count')[['claw_name', 'count', 'mean_cqi']].to_dict('records')}"
        ),
    )


def compute_corpus_statistics(df):
    """Compute summary statistics for the full corpus."""
    valid = filter_valid(df)
    return {
        "total_papers": len(df),
        "valid_papers": len(valid),
        "spam_flagged": int(df["is_spam"].sum()),
        "near_duplicates": int(df["is_near_duplicate"].sum()),
        "unique_agents": df["claw_name"].nunique(),
        "papers_with_skill": int(valid["has_skill_md"].sum()),
        "papers_with_collab": int(valid["has_collab"].sum()),
        "pct_skill": valid["has_skill_md"].mean() * 100,
        "pct_collab": valid["has_collab"].mean() * 100,
        "cqi_mean": valid["cqi"].mean(),
        "cqi_median": valid["cqi"].median(),
        "cqi_std": valid["cqi"].std(),
        "cqi_min": valid["cqi"].min(),
        "cqi_max": valid["cqi"].max(),
        "cqi_q25": valid["cqi"].quantile(0.25),
        "cqi_q75": valid["cqi"].quantile(0.75),
        "word_count_mean": valid["word_count"].mean(),
        "word_count_median": valid["word_count"].median(),
        "papers_per_day_mean": valid.groupby("created_at").size().mean() if valid["created_at"].notna().any() else 0,
        "observation_days": int(valid["day_num"].max()) if valid["day_num"].notna().any() else 0,
        "categories": valid["category"].value_counts().to_dict(),
    }


def compute_agent_stats(df):
    """Compute per-agent quality statistics."""
    valid = filter_valid(df)
    agent_groups = valid.groupby("claw_name")

    agent_stats = agent_groups.agg(
        paper_count=("cqi", "size"),
        mean_cqi=("cqi", "mean"),
        std_cqi=("cqi", "std"),
        has_collab=("has_collab", "any"),
        has_skill=("has_skill_md", "any"),
        skill_rate=("has_skill_md", "mean"),
    ).sort_values("paper_count", ascending=False)

    return agent_stats


def compute_duplicate_pairs(papers, threshold=0.85):
    """Find near-duplicate paper pairs based on title similarity."""
    titles = [p.get("title", "") or "" for p in papers]
    ids = [p.get("paperId") or p.get("paper_id") or str(p.get("id", "")) for p in papers]

    vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
    tfidf = vectorizer.fit_transform(titles)
    sim = cosine_similarity(tfidf)
    np.fill_diagonal(sim, 0)

    pairs = []
    seen = set()
    for i in range(len(titles)):
        for j in range(i + 1, len(titles)):
            if sim[i, j] > threshold:
                pair_key = (min(ids[i], ids[j]), max(ids[i], ids[j]))
                if pair_key not in seen:
                    seen.add(pair_key)
                    pairs.append({
                        "paper_a": ids[i],
                        "title_a": titles[i][:80],
                        "paper_b": ids[j],
                        "title_b": titles[j][:80],
                        "similarity": sim[i, j],
                    })

    return sorted(pairs, key=lambda p: p["similarity"], reverse=True)


def run_sensitivity_analysis(df, papers, n_trials=50):
    """Sensitivity analysis: perturb CQI weights and check stability."""
    from src.scoring import score_paper, compute_title_similarities

    sim_matrix = compute_title_similarities(papers)
    default_weights = [25, 25, 20, 15, 15]
    rng = np.random.RandomState(RANDOM_STATE)

    trial_means = []
    for trial in range(n_trials):
        perturbed = [max(1, w + rng.randint(-5, 6)) for w in default_weights]
        total = sum(perturbed)
        perturbed = [w * 100 / total for w in perturbed]

        cqis = []
        for i, paper in enumerate(papers):
            max_sim = float(sim_matrix[i].max()) if len(sim_matrix) > 0 else 0.0
            score = score_paper(paper, max_title_sim=max_sim)
            new_cqi = sum(d.normalized * pw for d, pw in zip(score.dimensions, perturbed))
            cqis.append(new_cqi)

        trial_means.append(np.mean(cqis))

    return {
        "mean_cqi_mean": np.mean(trial_means),
        "mean_cqi_std": np.std(trial_means),
        "mean_cqi_min": np.min(trial_means),
        "mean_cqi_max": np.max(trial_means),
        "n_trials": n_trials,
    }


def run_all_analyses(df, papers):
    """Run the complete analysis pipeline."""
    print("\n" + "=" * 60)
    print("Statistical Analysis")
    print("=" * 60)

    print("\n--- Corpus Statistics ---")
    corpus_stats = compute_corpus_statistics(df)
    for key, val in corpus_stats.items():
        if key != "categories":
            print(f"  {key}: {val}")

    print("\n--- Hypothesis Tests ---")
    h1 = test_h1_collaboration(df)
    h2 = test_h2_learning_curve(df)
    h3 = test_h3_depth_breadth(df)
    h4 = test_h4_lotka_law(df)

    for h in [h1, h2, h3, h4]:
        print(f"\n  {h.name}")
        print(f"    Test: {h.test_name}")
        print(f"    Statistic: {h.statistic:.4f}")
        print(f"    p-value: {h.p_value:.6f}")
        print(f"    Effect size: {h.effect_size:.4f} [{h.effect_ci_low:.4f}, {h.effect_ci_high:.4f}]")
        print(f"    Decision: {h.decision}")
        print(f"    Details: {h.details}")

    print("\n--- Agent Statistics (Top 15) ---")
    agent_stats = compute_agent_stats(df)
    print(agent_stats.head(15).to_string())

    print("\n--- Duplicate Pairs ---")
    dup_pairs = compute_duplicate_pairs(papers)
    print(f"  Found {len(dup_pairs)} near-duplicate pairs (threshold=0.85)")
    for pair in dup_pairs[:10]:
        print(f"    {pair['paper_a']} <-> {pair['paper_b']} (sim={pair['similarity']:.3f})")

    print("\n--- CQI vs Community Votes Validation ---")
    valid = filter_valid(df)
    voted = valid[valid["net_votes"] != 0]
    if len(voted) >= 5:
        rho_v, p_v = stats.spearmanr(voted["cqi"], voted["net_votes"])
        print(f"  Papers with votes: n={len(voted)}")
        print(f"  Spearman rho(CQI, net_votes) = {rho_v:.3f}, p = {p_v:.4f}")
    else:
        rho_v, p_v = float("nan"), float("nan")
        print(f"  Too few voted papers ({len(voted)}) for validation")

    print("\n--- Sensitivity Analysis (50 weight perturbations ±5) ---")
    sens = run_sensitivity_analysis(df, papers)
    print(f"  Mean CQI across trials: {sens['mean_cqi_mean']:.1f} ± {sens['mean_cqi_std']:.1f}")
    print(f"  Range: {sens['mean_cqi_min']:.1f} – {sens['mean_cqi_max']:.1f}")

    return {
        "corpus_stats": corpus_stats,
        "hypotheses": [h1, h2, h3, h4],
        "agent_stats": agent_stats,
        "duplicate_pairs": dup_pairs,
        "sensitivity": sens,
        "vote_validation": {"rho": rho_v, "p": p_v, "n": len(voted)},
    }
