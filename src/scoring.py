"""Composite Quality Index (CQI) scoring engine for clawRxiv papers."""

import re
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


SECTION_PATTERNS = {
    "introduction": r"(?i)^#{1,3}\s*(introduction|background|overview|motivation)",
    "methods": r"(?i)^#{1,3}\s*(method|approach|methodology|design|implementation|framework|pipeline|architecture)",
    "results": r"(?i)^#{1,3}\s*(result|finding|experiment|evaluation|performance|benchmark|output)",
    "discussion": r"(?i)^#{1,3}\s*(discussion|analysis|implication|insight|interpretation)",
    "conclusion": r"(?i)^#{1,3}\s*(conclusion|summary|future.work|limitation|takeaway)",
}

SPAM_TITLE_PATTERNS = [
    r"^test$",
    r"^untitled$",
    r"^asdf",
    r"^hello",
    r"^paper\s*\d*$",
]


@dataclass(frozen=True)
class DimensionScore:
    name: str
    weight: int
    raw: float
    normalized: float
    weighted: float


@dataclass(frozen=True)
class PaperScore:
    paper_id: str
    title: str
    cqi: float
    dimensions: tuple
    is_spam: bool
    is_near_duplicate: bool
    max_title_similarity: float
    raw_sub_indicators: tuple = ()


def score_structural_quality(content):
    """D1: Check for presence of canonical scientific sections."""
    if not content:
        return 0.0
    lines = content.split("\n")
    found = set()
    for line in lines:
        for section_name, pattern in SECTION_PATTERNS.items():
            if re.match(pattern, line.strip()):
                found.add(section_name)
    return len(found) / len(SECTION_PATTERNS)


def score_content_depth(content):
    """D2: Word count and section count as depth proxies."""
    if not content:
        return 0.0
    words = content.split()
    word_count = len(words)
    section_count = len(re.findall(r"^#{1,3}\s+", content, re.MULTILINE))

    word_score = min(word_count, 5000) / 5000
    section_score = min(section_count, 10) / 10
    return 0.7 * word_score + 0.3 * section_score


def score_executable_component(skill_md):
    """D3: Binary — does the paper include an executable skill?"""
    if not skill_md:
        return 0.0
    return 1.0 if len(str(skill_md).strip()) > 10 else 0.0


def score_collaboration(human_names):
    """D4: Binary — does the paper have human co-authors?"""
    if not human_names:
        return 0.0
    if isinstance(human_names, list) and len(human_names) > 0:
        return 1.0
    return 0.0


def score_citation_quality(content):
    """D5: Count unique references in the paper."""
    if not content:
        return 0.0

    ref_patterns = [
        r"\[([^\]]+)\]\(https?://[^\)]+\)",
        r"^\s*\[?\d{1,3}\][\.\)\s]",
        r"(?:doi|DOI|arXiv|arxiv)[:\s]+[\w\.\-/]+",
        r"et\s+al\.?,?\s*[\(\[]?\d{4}",
        r"^\s*[-•]\s+\w+.*[\(\[]\d{4}[\)\]]",
        r"https?://(?:doi\.org|arxiv\.org|pubmed|scholar\.google)[^\s\)]+",
        r"\(\d{4}[a-z]?\)",
    ]

    refs = set()
    for pattern in ref_patterns:
        matches = re.findall(pattern, content, re.MULTILINE)
        for m in matches:
            refs.add(str(m).strip()[:80])

    ref_count = len(refs)
    return min(ref_count, 20) / 20


def score_technical_depth(content):
    """D6: Presence of math, code blocks, and tables."""
    if not content:
        return 0.0

    has_math = bool(re.search(
        r"\$[^$]+\$|\\frac|\\sum|\\int|\\alpha|\\beta|\\theta|\\mathcal|\\nabla",
        content,
    ))
    has_code = bool(re.search(r"```[\s\S]*?```", content))
    has_tables = bool(re.search(r"\|[^|]+\|[^|]+\|", content))

    return (int(has_math) + int(has_code) + int(has_tables)) / 3


def score_metadata_quality(title, abstract, tags):
    """D7: Quality of paper metadata."""
    title_words = len(title.split()) if title else 0
    title_score = 1.0 if 5 <= title_words <= 20 else 0.5 if title_words > 0 else 0.0

    abstract_words = len(abstract.split()) if abstract else 0
    if 50 <= abstract_words <= 300:
        abstract_score = 1.0
    elif abstract_words < 50:
        abstract_score = abstract_words / 50 if abstract_words > 0 else 0.0
    else:
        abstract_score = 300 / abstract_words

    tag_count = len(tags) if tags else 0
    tag_score = min(tag_count, 5) / 5

    return (title_score + abstract_score + tag_score) / 3


def detect_spam(title, content):
    """Flag papers that appear to be spam or test submissions."""
    if not content:
        return True
    if not title:
        return True

    word_count = len(content.split())
    if word_count < 50:
        return True

    title_lower = title.strip().lower()
    for pattern in SPAM_TITLE_PATTERNS:
        if re.match(pattern, title_lower):
            return True

    return False


def compute_title_similarities(papers):
    """Compute pairwise title cosine similarity using TF-IDF."""
    titles = [p.get("title", "") or "" for p in papers]
    if len(titles) < 2:
        return np.zeros((len(titles), len(titles)))

    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=5000,
        min_df=1,
    )
    tfidf_matrix = vectorizer.fit_transform(titles)
    sim_matrix = cosine_similarity(tfidf_matrix)
    np.fill_diagonal(sim_matrix, 0.0)
    return sim_matrix


def score_paper(paper, max_title_sim=0.0):
    """Compute the full CQI for a single paper.

    Scoring is organized under the Claw4S conference's official review criteria
    (https://claw4s.github.io/), using the venue's published weights. Each
    criterion is operationalized via one or more programmatically measurable
    sub-indicators grounded in established standards:

      - FAIR Principles (Wilkinson et al., Scientific Data, 2016)
      - SciScore / Rigor & Transparency Index (Menke et al., iScience, 2020)
      - NeurIPS Review Form (Quality, Clarity, Significance, Originality)
      - APRES Rubric (Zhao et al., arXiv:2603.03142)
    """
    title = paper.get("title", "") or ""
    abstract = paper.get("abstract", "") or ""
    content = paper.get("content", "") or ""
    skill_md = paper.get("skillMd") or paper.get("skill_md")
    human_names = paper.get("humanNames") or paper.get("human_names")
    tags = paper.get("tags") or []
    paper_id = paper.get("paperId") or paper.get("paper_id") or str(paper.get("id", ""))

    # Compute raw sub-indicator scores (each in [0, 1])
    raw_structural = score_structural_quality(content)
    raw_depth = score_content_depth(content)
    raw_executable = score_executable_component(skill_md)
    raw_collab = score_collaboration(human_names)
    raw_citations = score_citation_quality(content)
    raw_technical = score_technical_depth(content)
    raw_metadata = score_metadata_quality(title, abstract, tags)
    raw_originality = 1.0 - max_title_sim

    # Map sub-indicators to the 5 official Claw4S criteria.
    # Each criterion score is the mean of its constituent sub-indicators.
    # Weights match the venue's published review rubric exactly.
    #
    # C1 Executability  (25%) — FAIR "Accessible"; can an agent run it?
    #    → executable component (skill_md present)
    # C2 Reproducibility (25%) — FAIR "Reusable"; can another agent reproduce?
    #    → technical depth (code, math, tables) + collaboration (human verification)
    # C3 Scientific Rigor (20%) — NeurIPS "Quality"; sound methodology?
    #    → structural quality (IMRaD) + citation quality + content depth
    # C4 Generalizability (15%) — NeurIPS "Significance"; adaptable?
    #    → metadata quality (discoverability) + originality
    # C5 Clarity for Agents (15%) — NeurIPS "Clarity"; parseable by AI?
    #    → metadata quality + structural quality
    #    (Note: clarity re-uses structural and metadata signals because
    #     well-structured, well-labeled papers are inherently clearer to agents.)

    c1_exec = raw_executable
    c2_repro = (raw_technical + raw_collab) / 2
    c3_rigor = (raw_structural + raw_citations + raw_depth) / 3
    c4_general = (raw_metadata + raw_originality) / 2
    c5_clarity = (raw_metadata + raw_structural) / 2

    # Claw4S official weights (sum to 100)
    dimensions_config = [
        ("Executability", 25, c1_exec),
        ("Reproducibility", 25, c2_repro),
        ("Scientific Rigor", 20, c3_rigor),
        ("Generalizability", 15, c4_general),
        ("Clarity for Agents", 15, c5_clarity),
    ]

    total_weight = sum(w for _, w, _ in dimensions_config)
    assert total_weight == 100, f"CQI weights must sum to 100, got {total_weight}"

    dimensions = []
    total_cqi = 0.0
    for name, weight, raw in dimensions_config:
        normalized = max(0.0, min(1.0, raw))
        weighted = normalized * weight
        total_cqi += weighted
        dimensions.append(DimensionScore(
            name=name,
            weight=weight,
            raw=raw,
            normalized=normalized,
            weighted=weighted,
        ))

    is_spam = detect_spam(title, content)
    is_near_dup = max_title_sim > 0.85

    # Also compute collaboration-blind CQI for H1 circularity check
    c2_repro_blind = raw_technical  # exclude collab from reproducibility
    cqi_no_collab = (
        25 * max(0, min(1, c1_exec))
        + 25 * max(0, min(1, c2_repro_blind))
        + 20 * max(0, min(1, c3_rigor))
        + 15 * max(0, min(1, c4_general))
        + 15 * max(0, min(1, c5_clarity))
    )

    raw_subs = (
        ("structural", raw_structural),
        ("depth", raw_depth),
        ("executable", raw_executable),
        ("collaboration", raw_collab),
        ("citations", raw_citations),
        ("technical", raw_technical),
        ("metadata", raw_metadata),
        ("originality", raw_originality),
        ("cqi_no_collab", cqi_no_collab),
    )

    return PaperScore(
        paper_id=paper_id,
        title=title,
        cqi=total_cqi,
        dimensions=tuple(dimensions),
        is_spam=is_spam,
        is_near_duplicate=is_near_dup,
        max_title_similarity=max_title_sim,
        raw_sub_indicators=raw_subs,
    )


def score_all_papers(papers):
    """Score all papers, including pairwise similarity computation."""
    print(f"Computing title similarities for {len(papers)} papers...")
    sim_matrix = compute_title_similarities(papers)

    print("Scoring papers...")
    scores = []
    for i, paper in enumerate(papers):
        max_sim = float(sim_matrix[i].max()) if len(sim_matrix) > 0 else 0.0
        paper_score = score_paper(paper, max_title_sim=max_sim)
        scores.append(paper_score)

    non_spam = [s for s in scores if not s.is_spam]
    spam = [s for s in scores if s.is_spam]
    dups = [s for s in scores if s.is_near_duplicate]

    print(f"  Total papers scored: {len(scores)}")
    print(f"  Non-spam papers: {len(non_spam)}")
    print(f"  Spam/low-quality flagged: {len(spam)}")
    print(f"  Near-duplicates flagged: {len(dups)}")
    if non_spam:
        cqis = [s.cqi for s in non_spam]
        print(f"  CQI range: {min(cqis):.1f} - {max(cqis):.1f}")
        print(f"  Mean CQI: {np.mean(cqis):.1f}")
        print(f"  Median CQI: {np.median(cqis):.1f}")

    return scores
