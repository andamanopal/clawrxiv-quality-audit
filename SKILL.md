---
name: clawrxiv-two-dimensional-quality-audit
description: >
  Two-dimensional quality audit of clawRxiv measuring both Form (programmatic
  bibliometric scoring) and Substance (agent-evaluated scientific content).
  Fetches all papers, computes Form scores via 5 Claw4S criteria, evaluates
  Substance via 5 content dimensions, verifies references against Semantic
  Scholar, performs Form-Substance gap analysis with quadrant classification,
  and generates a professional HTML report with all figures. Self-contained — all inline.
version: 1.0.0
allowed-tools: Bash(python *), Bash(pip *), Bash(mkdir *), Bash(curl *), Read, Write
estimated-time: 2-3 hours (depends on corpus size)
---

# clawRxiv Two-Dimensional Quality Audit

## Overview

Complete two-dimensional quality audit of clawRxiv — an AI agent research
archive. Unlike v1, which measured only Form (packaging quality via
bibliometric heuristics), this audit introduces a second axis: Substance
(scientific content quality evaluated by the executing agent). The
intersection of these two dimensions reveals four quadrants that expose
the true state of AI agent science.

**Pipeline:**

1. **Fetch** — Paginate through the clawRxiv API, download full paper content
2. **Form Score** — Programmatic scoring on 5 Claw4S criteria (8 sub-indicators)
3. **Substance Score** — Agent reads each paper and evaluates 5 content dimensions
4. **Reference Verification** — Validate citations against Semantic Scholar API
5. **Cross-Check & Gap Analysis** — Merge scores, classify quadrants, generate report

## Methodology

### Two-Dimensional Quality Framework

A single quality score conflates packaging with content. A paper can score
high on Form (proper structure, metadata, citations) while containing no
genuine scientific contribution — or score low on Form (poor formatting,
missing sections) while containing a genuinely novel insight. This audit
separates the two dimensions to expose that distinction.

    Quality = f(Form, Substance)

    Form measures HOW a paper is packaged: structure, metadata, citations,
    executability, and technical formatting. It is fully programmatic.

    Substance measures WHAT a paper contributes: methodology, evidence,
    novelty, coherence, and rigor. It requires reading comprehension.

### Form Score (Programmatic)

The Form score uses the same 5 Claw4S criteria and weights as v1, grounded
in established bibliometric standards:

1. **Venue criteria.** The 5 review dimensions and weights are taken directly
   from the Claw4S conference (https://claw4s.github.io/).
2. **Established standards.** Each criterion is operationalized via sub-indicators
   from published frameworks:
   - FAIR Principles (Wilkinson et al., Scientific Data, 2016; ~14,000 citations)
   - SciScore / RTI (Menke et al., iScience, 2020; NIH-funded, 1.58M papers)
   - NeurIPS Review Form (Quality, Clarity, Significance, Originality)
   - APRES Rubric (Zhao et al., arXiv:2603.03142; 60+ items, 8 categories)
3. **Guardrails.** Per the Leiden Manifesto (Nature, 2015) and DORA (22,300
   signatories), Form scores supplement expert review, not replace it.

    Form = sum(w_k * C_k) for k = 1..5, each C_k in [0,1], Form in [0,100]

| Criterion (C_k) | Weight | Sub-indicators | Standard |
|---|---|---|---|
| C1: Executability | 25% | skill_md present (binary) | FAIR "Accessible" |
| C2: Reproducibility | 25% | (technical_depth + collaboration) / 2 | FAIR "Reusable", SciScore |
| C3: Scientific Rigor | 20% | (structural_quality + citations + depth) / 3 | NeurIPS "Quality", EQUATOR |
| C4: Generalizability | 15% | (metadata_quality + originality) / 2 | NeurIPS "Significance" |
| C5: Clarity | 15% | (metadata_quality + structural_quality) / 2 | NeurIPS "Clarity" |

Sub-indicators: structural quality (IMRaD regex), content depth (word+heading
count), executable component (skill_md binary), collaboration (human_names
binary), citation quality (7 regex patterns, cap 20), technical depth (math +
code + tables), metadata quality (title + abstract + tags), originality
(1 - max TF-IDF cosine similarity).

### Substance Score (Agent-Evaluated)

The executing agent reads each paper's full content and evaluates it on
5 dimensions, each scored 1-5:

| Dimension | What It Measures | Anchors |
|---|---|---|
| Methodology | Is the approach well-defined and appropriate? | 1=no method, 5=rigorous design |
| Claim Support | Are claims backed by evidence? | 1=unsupported, 5=strong evidence |
| Novelty | Does this contribute something new? | 1=derivative, 5=genuinely original |
| Coherence | Does the argument flow logically? | 1=incoherent, 5=tight narrative |
| Rigor | Are limitations acknowledged, edge cases considered? | 1=no rigor, 5=thorough |

    Substance = (sum of 5 dimension scores / 25) * 100

This is NOT an LLM API call. The executing agent IS the evaluator. It reads
the paper content inline and applies its own judgment.

### Quadrant Classification

Papers are classified into four quadrants based on a threshold of 50 on
each axis:

```
                        Substance >= 50
                    YES                 NO
               +-----------+----------+
Form >= 50 YES | Genuine   | Well-    |
               | Quality   | Packaged |
               |           | Slop     |
               +-----------+----------+
           NO  | Hidden    | Low      |
               | Gem       | Effort   |
               +-----------+----------+
```

- **Genuine Quality** (Form >= 50, Substance >= 50): Well-packaged AND scientifically sound
- **Well-Packaged Slop** (Form >= 50, Substance < 50): Looks good but lacks substance
- **Hidden Gem** (Form < 50, Substance >= 50): Good science, poor packaging
- **Low Effort** (Form < 50, Substance < 50): Neither well-packaged nor substantive

### Reference Verification

Each paper's citations are extracted via regex and verified against the
Semantic Scholar Academic Graph API. This provides an independent signal
about whether papers cite real, findable scholarly work.

### Key Research Questions

- **RQ1:** What is the correlation between Form and Substance across clawRxiv?
- **RQ2:** What fraction of papers are "Well-Packaged Slop" vs "Genuine Quality"?
- **RQ3:** Do papers with verified references score higher on Substance?
- **RQ4:** Which Form sub-indicators best predict Substance?

---

## Step 0: Setup (~30s)

```bash
pip install pandas==2.2.3 numpy==1.26.4 scipy==1.14.1 statsmodels==0.14.4 \
  scikit-learn==1.5.2 matplotlib==3.9.3 seaborn==0.13.2 requests==2.32.3
mkdir -p data outputs figures
```

Ask the user for their Semantic Scholar API key:

> **USER INPUT REQUIRED:** Please provide your Semantic Scholar API key.
> Store it as an environment variable: `export S2_API_KEY="your-key-here"`
> Get a free key at: https://www.semanticscholar.org/product/api#api-key

**Validation:**
```bash
python -c "import pandas,numpy,scipy,statsmodels,sklearn,matplotlib,seaborn,requests;print('All dependencies OK')"
echo "S2_API_KEY is set: ${S2_API_KEY:+yes}"
```

---

## Step 1: Fetch Papers (~5 min)

Paginate through the clawRxiv API and fetch full content for each paper.

```bash
cat <<'PYEOF' > fetch_papers.py
"""Fetch all clawRxiv papers via paginated API."""
import json, time
from pathlib import Path
import requests

API_URL = "https://clawrxiv.io/api/posts"
DATA_DIR = Path("data")
OUTPUT = DATA_DIR / "papers_raw.json"

def fetch_all():
    """Paginate through listing endpoint."""
    papers, page, total = [], 1, None
    while True:
        r = requests.get(API_URL, params={"limit": 100, "page": page}, timeout=30)
        r.raise_for_status()
        data = r.json()
        posts = data.get("posts", [])
        if total is None:
            total = data.get("total", 0)
            print(f"Total papers on platform: {total}")
        if not posts:
            break
        papers.extend(posts)
        print(f"  Page {page}: {len(posts)} fetched (cumulative: {len(papers)})")
        if len(papers) >= total:
            break
        page += 1
        time.sleep(0.3)
    return papers

def fetch_full(pid):
    """Fetch full content for a single paper."""
    r = requests.get(f"{API_URL}/{pid}", timeout=30)
    r.raise_for_status()
    return r.json()

def main():
    print("=" * 60)
    print("clawRxiv Paper Fetcher")
    print("=" * 60)
    papers = fetch_all()
    full = []
    for i, p in enumerate(papers):
        pid = p.get("id")
        if (i + 1) % 50 == 0 or i == 0:
            print(f"  Fetching full content: {i+1}/{len(papers)}...")
        try:
            full.append(fetch_full(pid))
        except requests.RequestException as e:
            print(f"    WARN: paper {pid}: {e}")
            full.append(p)
        time.sleep(0.3)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(full, f, indent=2, default=str)
    print(f"\nSaved {len(full)} papers to {OUTPUT}")

if __name__ == "__main__":
    main()
PYEOF
python fetch_papers.py
```

**Validation:**
```bash
python -c "
import json
d = json.load(open('data/papers_raw.json'))
print(f'{len(d)} papers loaded')
assert len(d) >= 100, f'Expected >= 100 papers, got {len(d)}'
sample = d[0]
assert 'content' in sample or 'title' in sample, 'Missing expected fields'
print('Validation passed')
"
```

---

## Step 2: Form Score (~1 min)

Compute programmatic Form scores for all papers using 5 Claw4S criteria
weighted [25, 25, 20, 15, 15] and 8 sub-indicators.

```bash
cat <<'PYEOF' > compute_form.py
"""Compute programmatic Form scores for all papers on 5 Claw4S criteria."""
import json, re
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

RANDOM_STATE = 42; np.random.seed(RANDOM_STATE)
DATA_DIR, OUTPUTS_DIR = Path("data"), Path("outputs")

SECTION_PATTERNS = {
    "introduction": r"(?i)^#{1,3}\s*(introduction|background|overview|motivation)",
    "methods": r"(?i)^#{1,3}\s*(method|approach|methodology|design|implementation|framework|pipeline|architecture)",
    "results": r"(?i)^#{1,3}\s*(result|finding|experiment|evaluation|performance|benchmark|output)",
    "discussion": r"(?i)^#{1,3}\s*(discussion|analysis|implication|insight|interpretation)",
    "conclusion": r"(?i)^#{1,3}\s*(conclusion|summary|future.work|limitation|takeaway)",
}
SPAM_PATTERNS = [r"^test$", r"^untitled$", r"^asdf", r"^hello", r"^paper\s*\d*$"]
CITE_PATTERNS = [r"\[([^\]]+)\]\(https?://[^\)]+\)", r"^\s*\[?\d{1,3}\][\.\)\s]",
    r"(?:doi|DOI|arXiv|arxiv)[:\s]+[\w\.\-/]+", r"et\s+al\.?,?\s*[\(\[]?\d{4}",
    r"^\s*[-\u2022]\s+\w+.*[\(\[]\d{4}[\)\]]",
    r"https?://(?:doi\.org|arxiv\.org|pubmed|scholar\.google)[^\s\)]+", r"\(\d{4}[a-z]?\)"]
WEIGHTS = [25, 25, 20, 15, 15]  # C1-C5

def score_structural(c):
    if not c: return 0.0
    found = set()
    for line in c.split("\n"):
        for name, pat in SECTION_PATTERNS.items():
            if re.match(pat, line.strip()): found.add(name)
    return len(found) / len(SECTION_PATTERNS)

def score_depth(c):
    if not c: return 0.0
    return 0.7*min(len(c.split()),5000)/5000 + 0.3*min(len(re.findall(r"^#{1,3}\s+",c,re.M)),10)/10

def score_executable(s): return 1.0 if s and len(str(s).strip()) > 10 else 0.0
def score_collab(h): return 1.0 if isinstance(h, list) and len(h) > 0 else 0.0

def score_citations(c):
    if not c: return 0.0
    refs = set()
    for pat in CITE_PATTERNS:
        for m in re.findall(pat, c, re.M): refs.add(str(m).strip()[:80])
    return min(len(refs), 20) / 20

def score_technical(c):
    if not c: return 0.0
    has_math = bool(re.search(r"\$[^$]+\$|\\frac|\\sum|\\int|\\alpha|\\beta|\\theta|\\mathcal|\\nabla", c))
    has_code = bool(re.search(r"```[\s\S]*?```", c))
    has_tables = bool(re.search(r"\|[^|]+\|[^|]+\|", c))
    return (int(has_math) + int(has_code) + int(has_tables)) / 3

def score_metadata(title, abstract, tags):
    tw = len(title.split()) if title else 0
    ts = 1.0 if 5 <= tw <= 20 else 0.5 if tw > 0 else 0.0
    aw = len(abstract.split()) if abstract else 0
    asc = 1.0 if 50<=aw<=300 else (aw/50 if aw>0 else 0.0) if aw<50 else 300/aw
    tg = min(len(tags) if tags else 0, 5) / 5
    return (ts + asc + tg) / 3

def detect_spam(title, content):
    if not content or not title: return True
    if len(content.split()) < 50: return True
    return any(re.match(p, title.strip().lower()) for p in SPAM_PATTERNS)

def title_similarities(papers):
    titles = [p.get("title","") or "" for p in papers]
    if len(titles) < 2: return np.zeros((len(titles), len(titles)))
    sim = cosine_similarity(TfidfVectorizer(stop_words="english",max_features=5000,min_df=1).fit_transform(titles))
    np.fill_diagonal(sim, 0.0); return sim

def score_paper(paper, max_sim=0.0):
    """Map 8 sub-indicators to 5 Claw4S criteria -> Form score."""
    title = paper.get("title","") or ""; abstract = paper.get("abstract","") or ""
    content = paper.get("content","") or ""
    skill = paper.get("skillMd") or paper.get("skill_md")
    humans = paper.get("humanNames") or paper.get("human_names")
    tags = paper.get("tags") or []
    pid = paper.get("paperId") or paper.get("paper_id") or str(paper.get("id",""))

    rs = score_structural(content); rd = score_depth(content)
    re_ = score_executable(skill); rc = score_collab(humans)
    rci = score_citations(content); rt = score_technical(content)
    rm = score_metadata(title, abstract, tags); ro = 1.0 - max_sim

    criteria = [re_, (rt+rc)/2, (rs+rci+rd)/3, (rm+ro)/2, (rm+rs)/2]
    form = sum(max(0,min(1,c))*w for c,w in zip(criteria, WEIGHTS))
    R = lambda x: round(x, 4)

    return {"paper_id":pid,"title":title,"form_score":round(form,2),
        "is_spam":detect_spam(title,content),"max_title_sim":R(max_sim),
        "word_count":len(content.split()),"has_skill_md":re_>0,"has_collab":rc>0,
        "c1_executability":R(criteria[0]),"c2_reproducibility":R(criteria[1]),
        "c3_rigor":R(criteria[2]),"c4_generalizability":R(criteria[3]),
        "c5_clarity":R(criteria[4]),
        "raw_structural":R(rs),"raw_depth":R(rd),"raw_executable":R(re_),
        "raw_collab":R(rc),"raw_citations":R(rci),"raw_technical":R(rt),
        "raw_metadata":R(rm),"raw_originality":R(ro)}

def main():
    print("="*60+"\nForm Score Computation (5 Claw4S Criteria)\n"+"="*60)
    with open(DATA_DIR/"papers_raw.json") as f: papers = json.load(f)
    print(f"Loaded {len(papers)} papers")
    print("Computing title similarities..."); sim = title_similarities(papers)
    print("Scoring...")
    rows = [score_paper(p, float(sim[i].max()) if len(sim)>0 else 0.0) for i,p in enumerate(papers)]
    df = pd.DataFrame(rows); valid = df[~df["is_spam"]]
    print(f"\n  Total: {len(df)}, Valid: {len(valid)}, Spam: {df['is_spam'].sum()}")
    if len(valid) > 0:
        print(f"  Form: {valid['form_score'].min():.1f}-{valid['form_score'].max():.1f}, "
              f"Mean: {valid['form_score'].mean():.1f}, SD: {valid['form_score'].std():.1f}")
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUTS_DIR/"form_scores.csv", index=False)
    print(f"\nSaved to {OUTPUTS_DIR/'form_scores.csv'}")
    print("\n  Top 5:")
    for _,r in valid.nlargest(5,"form_score").iterrows(): print(f"    {r['form_score']:.1f}  {r['title'][:65]}")
    print("  Bottom 5:")
    for _,r in valid.nsmallest(5,"form_score").iterrows(): print(f"    {r['form_score']:.1f}  {r['title'][:65]}")

if __name__ == "__main__":
    main()
PYEOF
python compute_form.py
```

**Validation:**
```bash
python -c "
import pandas as pd
df = pd.read_csv('outputs/form_scores.csv')
assert len(df) >= 100, f'Expected >= 100 papers, got {len(df)}'
assert df['form_score'].between(0, 100).all(), 'Form scores out of range'
assert 'c1_executability' in df.columns
assert 'raw_structural' in df.columns
valid = df[~df['is_spam']]
print(f'OK: {len(df)} papers ({len(valid)} valid), Form {valid[\"form_score\"].min():.1f}-{valid[\"form_score\"].max():.1f}')
"
```

---

## Step 3: Substance Score (~20-30 min)

This step is NOT a Python script. The executing agent reads each paper and
evaluates its scientific content directly. The agent IS the evaluator.

### Instructions for the Executing Agent

For each paper in `data/papers_raw.json`, do the following:

1. **Read the paper's content.** Use the `content` field (markdown body text).
   Also consider `title`, `abstract`, and `skillMd` if present.

2. **Skip spam papers.** If the paper was flagged as spam in `outputs/form_scores.csv`
   (is_spam == True), assign all dimension scores as 1 and substance_score as 20.0.
   Write "Spam/test submission" as the summary.

3. **Evaluate on 5 dimensions** (each scored 1-5 as integers):

   **Methodology (1-5):**
   - 1: No discernible method. The paper is a stream-of-consciousness dump.
   - 2: Vague method mentioned but not explained. "We used AI to do X."
   - 3: Method described at a high level. Steps are listed but lack detail.
   - 4: Method is clear and reproducible. Inputs, process, and outputs defined.
   - 5: Rigorous methodology with justification for choices, alternatives considered.

   **Claim Support (1-5):**
   - 1: Claims are entirely unsupported. No evidence, data, or examples.
   - 2: Anecdotal support only. "In our experience, X works."
   - 3: Some evidence provided but gaps remain. Partial results shown.
   - 4: Claims well-supported with data, examples, or logical argument.
   - 5: Every major claim backed by strong evidence. Counter-arguments addressed.

   **Novelty (1-5):**
   - 1: Entirely derivative. Restates known facts with no new angle.
   - 2: Minor variation on existing work. Incremental at best.
   - 3: Interesting combination or application of known ideas.
   - 4: Clear novel contribution. New framework, finding, or approach.
   - 5: Genuinely original. Introduces a new concept or paradigm.

   **Coherence (1-5):**
   - 1: Incoherent. Sections contradict each other or are unrelated.
   - 2: Loosely connected ideas. Reader must infer the thread.
   - 3: Adequate flow but with logical gaps or abrupt transitions.
   - 4: Well-organized with clear narrative arc. Sections build on each other.
   - 5: Exceptionally tight. Every paragraph serves the central argument.

   **Rigor (1-5):**
   - 1: No acknowledgment of limitations. No edge cases considered.
   - 2: Limitations mentioned in passing but not explored.
   - 3: Some limitations discussed. Partial awareness of scope boundaries.
   - 4: Thorough treatment of limitations and scope. Caveats stated.
   - 5: Comprehensive rigor. Threats to validity addressed, reproducibility considered.

4. **Compute substance_score:**

       substance_score = (methodology + claim_support + novelty + coherence + rigor) / 25 * 100

5. **Write a one-sentence summary** capturing the paper's core contribution
   (or lack thereof). Maximum 120 characters.

6. **Output format.** Save results to `outputs/substance_scores.csv` with columns:
   ```
   paper_id, title, methodology, claim_support, novelty, coherence, rigor, substance_score, summary
   ```

### Calibration Guidelines

- **Be consistent.** Apply the same standard to every paper. A "3" for Paper A
  should mean the same thing as a "3" for Paper B.
- **Read charitably but honestly.** Assume the author had good intentions, but
  do not inflate scores for effort alone.
- **Score the content, not the topic.** A paper on a mundane topic with rigorous
  methodology scores higher than an exciting topic with no methodology.
- **Consider the intended scope.** A workshop-style position paper is not expected
  to have the rigor of a full research paper, but it should still have some.
- **Use the full range.** If everything gets a 3, the scoring is useless.
  Differentiate. Some papers deserve 1s; some deserve 5s.

### Process

Read `data/papers_raw.json`. For each paper:
- Extract `paperId` (as paper_id, falling back to `id`), `title`, `content`, `abstract`, `skillMd`
- Check if `is_spam` in `outputs/form_scores.csv` — if True, use default scores
- Read the content carefully
- Assign 5 dimension scores
- Compute substance_score
- Write one-sentence summary

Build the full CSV in memory and write it once to `outputs/substance_scores.csv`.

### Batching Strategy

Process papers in batches of ~20 to manage context. After evaluating all papers, write the complete CSV.
Print progress: `Evaluated {n}/{total}: "{title}" -> {substance_score}`

**Validation:**
```bash
python -c "
import pandas as pd
df = pd.read_csv('outputs/substance_scores.csv')
assert len(df) >= 100, f'Expected >= 100, got {len(df)}'
for col in ['methodology', 'claim_support', 'novelty', 'coherence', 'rigor']:
    assert df[col].between(1, 5).all(), f'{col} out of range'
assert df['substance_score'].between(20, 100).all(), 'substance_score out of range'
print(f'OK: {len(df)} papers evaluated')
print(f'  Substance: {df[\"substance_score\"].min():.1f}-{df[\"substance_score\"].max():.1f}')
print(f'  Mean: {df[\"substance_score\"].mean():.1f}, Median: {df[\"substance_score\"].median():.1f}')
print(f'  Score distribution:')
for col in ['methodology', 'claim_support', 'novelty', 'coherence', 'rigor']:
    print(f'    {col}: mean={df[col].mean():.2f}, std={df[col].std():.2f}')
"
```

---

## Step 4: Reference Verification (~5 min)

Extract citation patterns from each paper and verify them against the
Semantic Scholar Academic Graph API.

```bash
cat <<'PYEOF' > verify_references.py
"""Extract and verify references against Semantic Scholar API."""
import json, os, re, time
from pathlib import Path
import requests, pandas as pd

DATA_DIR, OUTPUTS_DIR = Path("data"), Path("outputs")
S2_API_KEY = os.environ.get("S2_API_KEY", "")
S2_BASE = "https://api.semanticscholar.org/graph/v1/paper"
S2_HEADERS = {"x-api-key": S2_API_KEY} if S2_API_KEY else {}
S2_FIELDS = "title,year,authors"

ARXIV_RE = re.compile(r"(?:arXiv|arxiv)[:\s]*([\d]{4}\.[\d]{4,5}(?:v\d+)?)")
DOI_RE = re.compile(r"(?:doi|DOI)[:\s]*(10\.\d{4,}/[^\s\)]+)")
AY_RE = re.compile(r"([A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z][a-z]+)?(?:\s+et\s+al\.?)?),?\s*[\(\[]?(\d{4})[a-z]?[\)\]]?")
REF_SEC_RE = re.compile(r"(?:^|\n)#{1,3}\s*(?:References?|Bibliography|Works Cited|Citations?)\s*\n", re.I)
REF_ENTRY_RE = re.compile(r"^\s*(?:\[?\d{1,3}\]\.?\s*|[-\u2022]\s+)(.+?)(?:\.\s*$|\n)", re.M)

def extract_citations(content):
    if not content: return []
    cites = []
    for m in ARXIV_RE.finditer(content):
        cites.append({"type":"arxiv","raw":m.group(0),"query":f"arxiv:{m.group(1)}","arxiv_id":m.group(1)})
    for m in DOI_RE.finditer(content):
        cites.append({"type":"doi","raw":m.group(0),"query":m.group(1),"doi":m.group(1)})

    ref_m = REF_SEC_RE.search(content)
    if ref_m:
        sec = content[ref_m.end():]
        ns = re.search(r"\n#{1,3}\s+", sec)
        if ns: sec = sec[:ns.start()]
        for m in REF_ENTRY_RE.finditer(sec):
            entry = m.group(1).strip()
            if 15 < len(entry) < 300:
                tm = re.search(r'"([^"]{10,})"', entry)
                q = tm.group(1) if tm else re.sub(r"^[A-Z][a-z]+(?:,?\s+[A-Z]\.?)+(?:\s+et\s+al\.?)?\s*[\(\[]?\d{4}[\)\]]?\.?\s*","",entry)[:80]
                if len(q) > 10:
                    cites.append({"type":"ref_entry","raw":entry[:120],"query":q})

    seen_ay = set()
    for m in AY_RE.finditer(content):
        key = f"{m.group(1)} {m.group(2)}"
        if key not in seen_ay and len(seen_ay) < 15:
            seen_ay.add(key)
            cites.append({"type":"author_year","raw":m.group(0),"query":key})

    seen = set(); unique = []
    for c in cites:
        q = c["query"].lower().strip()
        if q not in seen: seen.add(q); unique.append(c)
    return unique[:30]

def s2_lookup(url, params=None):
    r = requests.get(url, params={**(params or {}), "fields": S2_FIELDS}, headers=S2_HEADERS, timeout=15)
    if r.status_code != 200: return None
    return r.json()

def verify_citation(cite):
    res = {"type":cite["type"],"raw":cite["raw"][:120],"query":cite["query"][:120],
           "verified":False,"s2_title":"","s2_year":"","s2_authors":"","match_confidence":0.0}
    try:
        # Direct lookup for arXiv/DOI
        for id_type, key in [("arxiv_id","ARXIV"),("doi","DOI")]:
            if cite.get(id_type):
                data = s2_lookup(f"{S2_BASE}/{key}:{cite[id_type]}")
                if data:
                    res.update(verified=True, s2_title=(data.get("title") or "")[:120],
                        s2_year=str(data.get("year","")), match_confidence=1.0,
                        s2_authors=", ".join(a.get("name","") for a in (data.get("authors") or [])[:3]))
                    return res
        # Search fallback
        data = s2_lookup(f"{S2_BASE}/search", {"query":cite["query"],"limit":3})
        if data and data.get("data"):
            best = data["data"][0]
            res["s2_title"] = (best.get("title") or "")[:120]
            res["s2_year"] = str(best.get("year",""))
            res["s2_authors"] = ", ".join(a.get("name","") for a in (best.get("authors") or [])[:3])
            qw = set(cite["query"].lower().split())
            tw = set((best.get("title") or "").lower().split())
            overlap = len(qw & tw) / max(len(qw), 1)
            res["match_confidence"] = round(overlap, 2)
            res["verified"] = overlap > 0.3
    except requests.RequestException as e:
        res["error"] = str(e)[:80]
    return res

def main():
    print("="*60+"\nReference Verification via Semantic Scholar\n"+"="*60)
    if not S2_API_KEY:
        print("WARNING: S2_API_KEY not set. Rate limits will be strict.")
    with open(DATA_DIR/"papers_raw.json") as f: papers = json.load(f)
    form_df = pd.read_csv(OUTPUTS_DIR/"form_scores.csv")
    spam_ids = set(form_df[form_df["is_spam"]]["paper_id"].astype(str))

    rows, total_cites, total_verified = [], 0, 0
    for i, paper in enumerate(papers):
        pid = str(paper.get("paperId") or paper.get("paper_id") or paper.get("id",""))
        title = paper.get("title","") or ""
        if pid in spam_ids: continue
        cites = extract_citations(paper.get("content","") or "")
        if not cites:
            rows.append({"paper_id":pid,"title":title[:80],"total_citations_found":0,
                "citations_verified":0,"verification_rate":0.0,"citation_details":"[]"})
            continue
        verified = 0; details = []
        for c in cites:
            r = verify_citation(c)
            if r["verified"]: verified += 1
            details.append(r); time.sleep(1.0)
        total_cites += len(cites); total_verified += verified
        rows.append({"paper_id":pid,"title":title[:80],"total_citations_found":len(cites),
            "citations_verified":verified,"verification_rate":round(verified/len(cites),4),
            "citation_details":json.dumps(details,default=str)})
        if (i+1) % 10 == 0 or i == 0:
            print(f"  {i+1}/{len(papers)}: {title[:50]}... ({len(cites)} cites, {verified} verified)")

    df = pd.DataFrame(rows)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUTS_DIR/"reference_verification.csv", index=False)
    print(f"\n  Processed: {len(rows)}, Citations: {total_cites}, Verified: {total_verified}")
    if total_cites > 0: print(f"  Rate: {total_verified/total_cites:.1%}")

if __name__ == "__main__":
    main()
PYEOF
python verify_references.py
```

**Validation:**
```bash
python -c "
import pandas as pd
df = pd.read_csv('outputs/reference_verification.csv')
print(f'OK: {len(df)} papers processed')
print(f'  Papers with citations: {(df[\"total_citations_found\"] > 0).sum()}')
print(f'  Mean verification rate: {df[\"verification_rate\"].mean():.1%}')
assert len(df) > 0, 'No reference verification results'
assert 'verification_rate' in df.columns
print('Validation passed')
"
```

---

## Step 5: Cross-Check & Gap Analysis (~1 min)

Merge Form scores, Substance scores, and Reference verification.
Compute Form-Substance Gap, assign quadrants, run correlation analysis,
and generate all figures plus a professional HTML report.

```bash
cat <<'PYEOF' > cross_check.py
"""Cross-check Form and Substance scores, perform gap analysis, generate report."""
import json, base64
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np, pandas as pd, seaborn as sns
from scipy import stats

RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)
DATA_DIR, OUTPUTS_DIR, FDIR = Path("data"), Path("outputs"), Path("figures")

P = {"primary":"#1B2A4A","accent":"#D55E00","secondary":"#0072B2","success":"#009E73",
     "warning":"#E69F00","danger":"#CC3333","light":"#F5F5F5","text":"#333333","grid":"#E0E0E0",
     "genuine":"#009E73","slop":"#CC3333","gem":"#0072B2","low":"#999999"}
QC = {"Genuine Quality":P["genuine"],"Well-Packaged Slop":P["slop"],
      "Hidden Gem":P["gem"],"Low Effort":P["low"]}
QUADS = list(QC.keys())

def setup_mpl():
    plt.rcParams.update({"font.family":"sans-serif","font.size":11,
        "axes.titlesize":13,"axes.titleweight":"bold","axes.spines.top":False,
        "axes.spines.right":False,"axes.grid":True,"grid.alpha":0.3,
        "grid.linestyle":"--","figure.dpi":150,"savefig.dpi":300,
        "savefig.bbox":"tight","savefig.pad_inches":0.2})

def sf(fig, name):
    FDIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FDIR / f"{name}.png"); plt.close(fig)
    print(f"  Saved figures/{name}.png")

def fv(df): return df[~df["is_spam"]]

# ---- Data loading and merging ----

def load_and_merge():
    form = pd.read_csv(OUTPUTS_DIR / "form_scores.csv")
    substance = pd.read_csv(OUTPUTS_DIR / "substance_scores.csv")
    refs = pd.read_csv(OUTPUTS_DIR / "reference_verification.csv")
    for d in [form, substance, refs]: d["paper_id"] = d["paper_id"].astype(str)

    merged = form.merge(
        substance[["paper_id","methodology","claim_support","novelty",
                    "coherence","rigor","substance_score","summary"]],
        on="paper_id", how="left")
    merged = merged.merge(
        refs[["paper_id","total_citations_found","citations_verified","verification_rate"]],
        on="paper_id", how="left")

    for col in ["methodology","claim_support","novelty","coherence","rigor"]:
        merged[col] = merged[col].fillna(1)
    merged["substance_score"] = merged["substance_score"].fillna(20.0)
    merged["summary"] = merged["summary"].fillna("Spam/test submission")
    for col in ["total_citations_found","citations_verified"]:
        merged[col] = merged[col].fillna(0).astype(int)
    merged["verification_rate"] = merged["verification_rate"].fillna(0.0)
    merged["fs_gap"] = merged["form_score"] - merged["substance_score"]

    def quadrant(row):
        f, s = row["form_score"], row["substance_score"]
        if f >= 50 and s >= 50: return "Genuine Quality"
        if f >= 50: return "Well-Packaged Slop"
        if s >= 50: return "Hidden Gem"
        return "Low Effort"
    merged["quadrant"] = merged.apply(quadrant, axis=1)
    return merged

# ---- Statistics & correlations ----

def compute_statistics(df):
    v = fv(df)
    return {
        "total_papers": len(df), "valid_papers": len(v),
        "spam_flagged": int(df["is_spam"].sum()),
        "form_mean": round(v["form_score"].mean(),1),
        "form_median": round(v["form_score"].median(),1),
        "form_std": round(v["form_score"].std(),1),
        "form_min": round(v["form_score"].min(),1),
        "form_max": round(v["form_score"].max(),1),
        "substance_mean": round(v["substance_score"].mean(),1),
        "substance_median": round(v["substance_score"].median(),1),
        "substance_std": round(v["substance_score"].std(),1),
        "substance_min": round(v["substance_score"].min(),1),
        "substance_max": round(v["substance_score"].max(),1),
        "gap_mean": round(v["fs_gap"].mean(),1),
        "gap_median": round(v["fs_gap"].median(),1),
        "gap_std": round(v["fs_gap"].std(),1),
        "quadrant_counts": v["quadrant"].value_counts().to_dict(),
        "quadrant_pcts": (v["quadrant"].value_counts(normalize=True)*100).round(1).to_dict(),
        "papers_with_refs": int((v["total_citations_found"]>0).sum()),
        "mean_verification_rate": round(
            v[v["total_citations_found"]>0]["verification_rate"].mean(),3
        ) if (v["total_citations_found"]>0).any() else 0,
    }

def compute_correlations(df):
    v = fv(df)
    results = {}
    rho, p = stats.spearmanr(v["form_score"], v["substance_score"])
    results["form_substance_spearman"] = {"rho":round(rho,4),"p":round(p,6),"n":len(v)}
    r_p, p_p = stats.pearsonr(v["form_score"], v["substance_score"])
    results["form_substance_pearson"] = {"r":round(r_p,4),"p":round(p_p,6)}

    has_refs, no_refs = v[v["total_citations_found"]>0], v[v["total_citations_found"]==0]
    if len(has_refs) > 5 and len(no_refs) > 5:
        t, pv = stats.ttest_ind(has_refs["substance_score"], no_refs["substance_score"], equal_var=False)
        results["refs_vs_substance"] = {"t":round(t,4),"p":round(pv,6),
            "mean_with_refs":round(has_refs["substance_score"].mean(),1),
            "mean_without_refs":round(no_refs["substance_score"].mean(),1),
            "n_with":len(has_refs),"n_without":len(no_refs)}
    if len(has_refs) > 10:
        rv, pv = stats.spearmanr(has_refs["verification_rate"], has_refs["substance_score"])
        results["verification_rate_vs_substance"] = {"rho":round(rv,4),"p":round(pv,6),"n":len(has_refs)}

    sub_ind = ["raw_structural","raw_depth","raw_executable","raw_collab",
               "raw_citations","raw_technical","raw_metadata","raw_originality"]
    pc = {}
    for col in sub_ind:
        if col in v.columns:
            r, pv = stats.spearmanr(v[col], v["substance_score"])
            pc[col] = {"rho":round(r,4),"p":round(pv,6)}
    results["sub_indicator_vs_substance"] = pc
    return results

# ---- 10 Figures ----

def fig1_2d_scatter(df):
    v = fv(df); fig, ax = plt.subplots(figsize=(11,9))
    ax.axvline(50,color=P["grid"],ls="--",lw=1.5,alpha=0.7,zorder=1)
    ax.axhline(50,color=P["grid"],ls="--",lw=1.5,alpha=0.7,zorder=1)
    for q,c in QC.items():
        s = v[v["quadrant"]==q]
        ax.scatter(s["form_score"],s["substance_score"],c=c,alpha=0.65,s=50,
                   edgecolors="white",lw=0.5,label=f"{q} (n={len(s)})",zorder=3)
    for x,y,t,c in [(75,75,"GENUINE\nQUALITY",P["genuine"]),(25,75,"HIDDEN\nGEM",P["gem"]),
                     (75,25,"WELL-PACKAGED\nSLOP",P["slop"]),(25,25,"LOW\nEFFORT",P["low"])]:
        ax.text(x,y,t,color=c,fontsize=11,fontweight="bold",alpha=0.4,ha="center",va="center")
    ax.plot([0,100],[0,100],":",color=P["text"],alpha=0.3,lw=1)
    rho,p = stats.spearmanr(v["form_score"],v["substance_score"])
    ax.text(0.02,0.02,f"Spearman rho = {rho:.3f} (p = {p:.2e})\nn = {len(v)}",
        transform=ax.transAxes,fontsize=10,va="bottom",
        bbox=dict(boxstyle="round,pad=0.5",facecolor=P["light"],alpha=0.9))
    ax.set(xlabel="Form Score (Packaging Quality)",ylabel="Substance Score (Scientific Content)",
           title="Form vs. Substance: The Two Dimensions of Paper Quality",xlim=(-2,102),ylim=(-2,102))
    ax.legend(loc="upper left",framealpha=0.9,fontsize=10); ax.set_aspect("equal")
    sf(fig,"fig1_form_vs_substance")

def fig2_gap_distribution(df):
    v = fv(df); fig, ax = plt.subplots(figsize=(10,6)); gaps = v["fs_gap"]
    bins = np.linspace(gaps.min()-2,gaps.max()+2,35)
    _,be,patches = ax.hist(gaps,bins=bins,edgecolor="white",lw=0.5,alpha=0.85,zorder=2)
    bw = be[1]-be[0]
    for pt,le in zip(patches,be):
        pt.set_facecolor(P["slop"] if le+bw/2>0 else P["gem"] if le+bw/2<0 else P["secondary"])
    ax.axvline(0,color=P["primary"],ls="-",lw=2,alpha=0.8,zorder=3)
    ax.axvline(gaps.mean(),color=P["accent"],ls="--",lw=2,label=f"Mean ({gaps.mean():+.1f})",zorder=3)
    ax.axvline(gaps.median(),color=P["success"],ls="-.",lw=2,label=f"Median ({gaps.median():+.1f})",zorder=3)
    over,under = (gaps>0).sum(),(gaps<0).sum()
    ax.text(0.98,0.95,f"Form > Substance: {over} ({over/len(v)*100:.0f}%)\n"
        f"Substance > Form: {under} ({under/len(v)*100:.0f}%)",
        transform=ax.transAxes,ha="right",va="top",fontsize=10,
        bbox=dict(boxstyle="round,pad=0.5",facecolor=P["light"],alpha=0.9))
    ax.set(xlabel="Form - Substance Gap",ylabel="Number of Papers",title="Form-Substance Gap Distribution")
    ax.legend(loc="upper left",framealpha=0.9); sf(fig,"fig2_gap_distribution")

def fig3_quadrant_pie(df):
    v = fv(df); counts = v["quadrant"].value_counts()
    sizes = [counts.get(q,0) for q in QUADS]
    fig, ax = plt.subplots(figsize=(9,9))
    wedges,_,at = ax.pie(sizes,labels=None,colors=[QC[q] for q in QUADS],
        autopct="%1.0f%%",startangle=90,pctdistance=0.78,
        wedgeprops=dict(width=0.45,edgecolor="white",linewidth=2))
    for t in at: t.set_fontsize(12); t.set_fontweight("bold"); t.set_color("white")
    ax.legend(wedges,[f"{q}\n{s} ({s/sum(sizes)*100:.0f}%)" for q,s in zip(QUADS,sizes)],
        loc="center left",bbox_to_anchor=(0.85,0,0.5,1),fontsize=11,framealpha=0.9)
    ax.set_title("Quadrant Distribution of clawRxiv Papers",fontsize=14,pad=20)
    ax.text(0,0,f"n={sum(sizes)}",ha="center",va="center",fontsize=18,fontweight="bold",color=P["primary"])
    sf(fig,"fig3_quadrant_distribution")

def fig4_scores_by_quadrant(df):
    v = fv(df).copy()
    fig,(ax1,ax2) = plt.subplots(1,2,figsize=(14,6),sharey=True)
    for ax,col,lab in [(ax1,"form_score","Form Score"),(ax2,"substance_score","Substance Score")]:
        data = [v[v["quadrant"]==q][col].values for q in QUADS]
        bp = ax.boxplot(data,labels=[q.replace(" ","\n") for q in QUADS],patch_artist=True,widths=0.6,
            medianprops=dict(color=P["accent"],lw=2))
        for patch,q in zip(bp["boxes"],QUADS): patch.set_facecolor(QC[q]); patch.set_alpha(0.6)
        ax.set_ylabel(lab if ax==ax1 else ""); ax.set_title(f"{lab} by Quadrant"); ax.set_ylim(-5,105)
        for i,q in enumerate(QUADS):
            ax.text(i+1,-3,f"n={len(v[v['quadrant']==q])}",ha="center",fontsize=9,color=P["text"])
    plt.tight_layout(); sf(fig,"fig4_scores_by_quadrant")

def fig5_substance_radar(df):
    v = fv(df); dims = ["methodology","claim_support","novelty","coherence","rigor"]
    dlabels = ["Methodology","Claim\nSupport","Novelty","Coherence","Rigor"]
    angles = np.linspace(0,2*np.pi,len(dims),endpoint=False).tolist()+[0]
    fig, ax = plt.subplots(figsize=(9,9),subplot_kw=dict(polar=True))
    for q in QUADS:
        s = v[v["quadrant"]==q]
        if len(s)==0: continue
        vals = s[dims].mean().values.tolist()+[s[dims[0]].mean()]
        ax.plot(angles,vals,"o-",lw=2,color=QC[q],label=f"{q} (n={len(s)})")
        ax.fill(angles,vals,alpha=0.08,color=QC[q])
    ax.set_xticks(angles[:-1]); ax.set_xticklabels(dlabels,fontsize=10)
    ax.set_ylim(0,5); ax.set_yticks([1,2,3,4,5])
    ax.set_title("Substance Dimensions by Quadrant",pad=20)
    ax.legend(loc="upper right",bbox_to_anchor=(1.35,1.1),framealpha=0.9)
    sf(fig,"fig5_substance_radar")

def fig6_predictors(df):
    v = fv(df)
    inds = [("raw_structural","Structural"),("raw_depth","Depth"),("raw_executable","Executable"),
            ("raw_collab","Collaboration"),("raw_citations","Citations"),("raw_technical","Technical"),
            ("raw_metadata","Metadata"),("raw_originality","Originality")]
    corrs,labs = zip(*[(stats.spearmanr(v[c],v["substance_score"])[0],l) for c,l in inds if c in v.columns])
    corrs,labs = list(corrs),list(labs)
    idx = np.argsort(np.abs(corrs))[::-1]; corrs=[corrs[i] for i in idx]; labs=[labs[i] for i in idx]
    fig, ax = plt.subplots(figsize=(10,6))
    ax.barh(range(len(labs)),corrs,color=[P["success"] if c>0 else P["danger"] for c in corrs],alpha=0.85)
    ax.set_yticks(range(len(labs))); ax.set_yticklabels(labs); ax.axvline(0,color=P["primary"],lw=1)
    for i,c in enumerate(corrs): ax.text(c+0.01*np.sign(c),i,f"{c:.3f}",va="center",fontsize=10)
    ax.invert_yaxis(); ax.set(xlabel="Spearman rho with Substance",title="RQ4: Which Form Sub-Indicators Predict Substance?")
    sf(fig,"fig6_predictor_correlations")

def fig7_refs(df):
    v = fv(df); hr = v[v["total_citations_found"]>0].copy()
    fig, ax = plt.subplots(figsize=(10,7))
    sc = ax.scatter(hr["verification_rate"]*100,hr["substance_score"],c=hr["form_score"],
        cmap="viridis",alpha=0.6,s=hr["total_citations_found"]*8+20,edgecolors="white",lw=0.5,zorder=3)
    plt.colorbar(sc,ax=ax,label="Form Score",shrink=0.8)
    if len(hr)>5:
        rho,p = stats.spearmanr(hr["verification_rate"],hr["substance_score"])
        ax.text(0.02,0.98,f"Spearman rho = {rho:.3f} (p = {p:.2e})\nn = {len(hr)}",
            transform=ax.transAxes,va="top",fontsize=10,
            bbox=dict(boxstyle="round,pad=0.5",facecolor=P["light"],alpha=0.9))
    ax.set(xlabel="Citation Verification Rate (%)",ylabel="Substance Score",
        title="RQ3: Do Verified References Predict Scientific Quality?",xlim=(-5,105),ylim=(-2,102))
    sf(fig,"fig7_refs_vs_substance")

def fig8_tables(df):
    v = fv(df); cols = ["title","form_score","substance_score","fs_gap","quadrant"]
    top = v.nlargest(10,"substance_score")[cols].copy(); top["title"]=top["title"].str[:50]
    bot = v.nsmallest(10,"substance_score")[cols].copy(); bot["title"]=bot["title"].str[:50]
    fig,(a1,a2) = plt.subplots(2,1,figsize=(14,10))
    for ax,data,lab,c in [(a1,top,"Top 10 by Substance",P["genuine"]),(a2,bot,"Bottom 10 by Substance",P["danger"])]:
        ax.axis("off")
        tb = ax.table(cellText=data.values,colLabels=["Title","Form","Substance","Gap","Quadrant"],loc="center",cellLoc="left")
        tb.auto_set_font_size(False); tb.set_fontsize(8); tb.scale(1,1.4)
        for (r,c_),cell in tb.get_celld().items():
            if r==0: cell.set_facecolor(c); cell.set_text_props(color="white",fontweight="bold")
            else: cell.set_facecolor(P["light"] if r%2==0 else "white")
        ax.set_title(lab,fontsize=13,fontweight="bold",pad=10)
    plt.tight_layout(); sf(fig,"fig8_top_bottom_tables")

def fig9_form_comp(df):
    v = fv(df); top = v.nlargest(15,"substance_score").copy(); bot = v.nsmallest(15,"substance_score").copy()
    crit = [("c1_executability","Exec",25),("c2_reproducibility","Repro",25),
            ("c3_rigor","Rigor",20),("c4_generalizability","Gen",15),("c5_clarity","Clarity",15)]
    cc = [P["secondary"],P["accent"],P["success"],P["warning"],P["danger"]]
    fig,(a1,a2) = plt.subplots(1,2,figsize=(16,8),sharey=True)
    for ax,data,lab in [(a1,top,"Top 15 by Substance"),(a2,bot,"Bottom 15 by Substance")]:
        titles = data["title"].str[:35].values; yp = np.arange(len(titles)); left = np.zeros(len(titles))
        for (col,nm,w),color in zip(crit,cc):
            widths = data[col].values * w
            ax.barh(yp,widths,left=left,color=color,alpha=0.85,edgecolor="white",lw=0.5,label=nm); left += widths
        ax.set_yticks(yp); ax.set_yticklabels(titles,fontsize=8)
        ax.set_xlabel("Form Score (weighted)"); ax.set_title(lab); ax.set_xlim(0,100); ax.invert_yaxis()
    h,l = a1.get_legend_handles_labels()
    fig.legend(h,l,loc="lower center",ncol=5,bbox_to_anchor=(0.5,-0.02),framealpha=0.9)
    plt.tight_layout(rect=[0,0.04,1,1]); sf(fig,"fig9_form_composition")

def fig10_cross_corr(df):
    v = fv(df)
    cols = ["c1_executability","c2_reproducibility","c3_rigor","c4_generalizability","c5_clarity",
            "methodology","claim_support","novelty","coherence","rigor","form_score","substance_score"]
    labs = ["F:Exec","F:Repro","F:Rigor","F:Gen","F:Clarity",
            "S:Method","S:Claims","S:Novel","S:Cohere","S:Rigor","Form","Substance"]
    corr = v[cols].corr(method="spearman")
    mask = np.triu(np.ones_like(corr,dtype=bool),k=1)
    fig, ax = plt.subplots(figsize=(12,10))
    sns.heatmap(corr,mask=mask,annot=True,fmt=".2f",cmap="RdBu_r",center=0,vmin=-1,vmax=1,
        square=True,linewidths=1,linecolor="white",xticklabels=labs,yticklabels=labs,ax=ax,
        cbar_kws={"label":"Spearman rho","shrink":0.8})
    ax.set_title("Cross-Domain Correlations: Form vs. Substance"); plt.xticks(rotation=45,ha="right")
    sf(fig,"fig10_cross_correlation")

# ---- HTML report ----

def generate_report(df, sd, corrs):
    v = fv(df)
    fig_files = sorted(FDIR.glob("fig*.png"))
    fig_titles = ["Form vs. Substance","Gap Distribution","Quadrant Distribution",
        "Scores by Quadrant","Substance Radar","Sub-Indicator Predictors",
        "References vs. Substance","Top & Bottom Papers","Form Composition","Cross Correlations"]
    fig_html = ""
    for i,fp in enumerate(fig_files):
        t = fig_titles[i] if i<len(fig_titles) else fp.stem
        b64 = base64.b64encode(fp.read_bytes()).decode()
        fig_html += f'<h3>Figure {i+1}: {t}</h3>\n<img src="data:image/png;base64,{b64}" style="max-width:100%;border:1px solid #ddd;border-radius:8px;margin-bottom:24px;">\n'

    fs = corrs.get("form_substance_spearman",{}); refs = corrs.get("refs_vs_substance",{})
    rho_abs = abs(fs.get("rho",0))
    strength = "strongly" if rho_abs>0.5 else "moderately" if rho_abs>0.3 else "weakly"

    quad_rows = "".join(f'<tr><td style="color:{QC[q]};font-weight:bold">{q}</td>'
        f'<td>{sd["quadrant_counts"].get(q,0)}</td><td>{sd["quadrant_pcts"].get(q,0)}%</td></tr>'
        for q in QUADS)

    pred_rows = "".join(f'<tr><td>{c.replace("raw_","").title()}</td><td>{v["rho"]}</td><td>{v["p"]:.2e}</td></tr>'
        for c,v in sorted(corrs.get("sub_indicator_vs_substance",{}).items(),
                          key=lambda x:abs(x[1]["rho"]),reverse=True))

    def paper_rows(papers):
        return "".join(f'<tr><td>{r["title"][:60]}</td><td>{r["form_score"]:.1f}</td>'
            f'<td>{r["substance_score"]:.1f}</td><td>{r["fs_gap"]:+.1f}</td>'
            f'<td style="color:{QC.get(r["quadrant"],"#999")};font-weight:bold">{r["quadrant"]}</td></tr>'
            for _,r in papers.iterrows())

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>clawRxiv Two-Dimensional Quality Audit</title>
<style>
body{{font-family:'Helvetica Neue',Arial,sans-serif;max-width:1100px;margin:40px auto;padding:0 20px;color:#2c3e50;line-height:1.6}}
h1{{color:#2E4057;border-bottom:3px solid #FF6B35;padding-bottom:12px}}
h2{{color:#2E4057;margin-top:40px}} h3{{color:#4A90D9}}
table{{border-collapse:collapse;width:100%;margin:16px 0}}
th,td{{border:1px solid #ddd;padding:10px 14px;text-align:left}}
th{{background:#2E4057;color:white}} tr:nth-child(even){{background:#f8f9fa}}
.sg{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:20px 0}}
.sc{{background:#f8f9fa;border-left:4px solid #FF6B35;padding:16px;border-radius:4px}}
.sc .v{{font-size:28px;font-weight:bold;color:#2E4057}} .sc .l{{font-size:13px;color:#7f8c8d}}
.tc{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}
.footer{{margin-top:60px;padding-top:20px;border-top:1px solid #ddd;color:#95a5a6;font-size:13px}}
</style></head><body>
<h1>The Two-Dimensional Audit of AI Agent Science</h1>
<p><em>Measuring Both Form and Substance on clawRxiv</em></p>
<h2>Key Finding</h2>
<p style="font-size:18px;background:#f8f9fa;padding:20px;border-left:4px solid {P['accent']};border-radius:4px;">
Form and Substance are <strong>{strength}</strong> correlated (Spearman rho = {fs.get('rho','N/A')}).
{'Packaging reliably predicts content.' if rho_abs>0.5
 else 'Packaging is a partial signal, not reliable alone.' if rho_abs>0.3
 else 'Packaging tells you almost nothing about scientific content.'}</p>
<h2>Corpus Overview</h2>
<div class="sg">
<div class="sc"><div class="v">{sd['valid_papers']}</div><div class="l">Valid Papers</div></div>
<div class="sc"><div class="v">{sd['form_mean']}</div><div class="l">Mean Form</div></div>
<div class="sc"><div class="v">{sd['substance_mean']}</div><div class="l">Mean Substance</div></div>
<div class="sc"><div class="v">{sd['gap_mean']:+.1f}</div><div class="l">Mean Gap</div></div>
<div class="sc"><div class="v">{sd['quadrant_pcts'].get('Genuine Quality',0):.0f}%</div><div class="l">Genuine Quality</div></div>
<div class="sc"><div class="v">{sd['quadrant_pcts'].get('Well-Packaged Slop',0):.0f}%</div><div class="l">Well-Packaged Slop</div></div>
</div>
<div class="tc"><div><h3>Form</h3><table>
<tr><td>Mean</td><td>{sd['form_mean']}</td></tr><tr><td>Median</td><td>{sd['form_median']}</td></tr>
<tr><td>SD</td><td>{sd['form_std']}</td></tr><tr><td>Range</td><td>{sd['form_min']}-{sd['form_max']}</td></tr>
</table></div><div><h3>Substance</h3><table>
<tr><td>Mean</td><td>{sd['substance_mean']}</td></tr><tr><td>Median</td><td>{sd['substance_median']}</td></tr>
<tr><td>SD</td><td>{sd['substance_std']}</td></tr><tr><td>Range</td><td>{sd['substance_min']}-{sd['substance_max']}</td></tr>
</table></div></div>
<h2>Research Questions</h2>
<h3>RQ1: Form-Substance Correlation</h3>
<p>Spearman rho = {fs.get('rho','N/A')}, p = {fs.get('p','N/A')}, n = {fs.get('n','N/A')}</p>
<h3>RQ2: Quadrant Distribution</h3>
<table><tr><th>Quadrant</th><th>Count</th><th>%</th></tr>{quad_rows}</table>
<h3>RQ3: References and Substance</h3>
<p>With refs: mean={refs.get('mean_with_refs','N/A')}, without={refs.get('mean_without_refs','N/A')}
(t={refs.get('t','N/A')}, p={refs.get('p','N/A')})</p>
<h3>RQ4: Best Predictors</h3>
<table><tr><th>Sub-Indicator</th><th>rho</th><th>p</th></tr>{pred_rows}</table>
<h2>Top 10 (by Substance)</h2>
<table><tr><th>Title</th><th>Form</th><th>Substance</th><th>Gap</th><th>Quadrant</th></tr>
{paper_rows(v.nlargest(10,"substance_score"))}</table>
<h2>Bottom 10 (by Substance)</h2>
<table><tr><th>Title</th><th>Form</th><th>Substance</th><th>Gap</th><th>Quadrant</th></tr>
{paper_rows(v.nsmallest(10,"substance_score"))}</table>
<h2>Figures</h2>{fig_html}
<div class="footer"><p>Generated by clawRxiv Two-Dimensional Quality Audit &mdash; random_state=42</p>
<p>Claw4S Conference 2026</p></div></body></html>"""

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    Path(OUTPUTS_DIR/"audit_report.html").write_text(html)
    print(f"\nReport saved: outputs/audit_report.html ({len(html)/1024:.0f} KB)")
    print(f"  {len(fig_files)} figures inlined")

# ---- Main ----

def main():
    setup_mpl()
    print("="*60+"\nCross-Check & Gap Analysis\n"+"="*60)
    print("\nMerging Form + Substance + References...")
    df = load_and_merge(); v = fv(df)
    print(f"  {len(df)} total, {len(v)} valid")

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUTS_DIR/"merged_scores.csv", index=False); print("  Saved merged_scores.csv")

    print("\nComputing statistics...")
    sd = compute_statistics(df)
    with open(OUTPUTS_DIR/"two_dim_stats.json","w") as f: json.dump(sd,f,indent=2,default=str)
    print(f"  Form: {sd['form_mean']} +/- {sd['form_std']}")
    print(f"  Substance: {sd['substance_mean']} +/- {sd['substance_std']}")
    print(f"  Gap: {sd['gap_mean']:+.1f} +/- {sd['gap_std']}")
    for q in QUADS:
        print(f"    {q:25s}: {sd['quadrant_counts'].get(q,0):4d} ({sd['quadrant_pcts'].get(q,0):.1f}%)")

    print("\nComputing correlations...")
    corrs = compute_correlations(df)
    with open(OUTPUTS_DIR/"correlations.json","w") as f: json.dump(corrs,f,indent=2,default=str)
    fs = corrs.get("form_substance_spearman",{})
    print(f"  RQ1: rho={fs.get('rho')}, p={fs.get('p')}")

    print("\nGenerating figures...")
    for name,fn in [("1: Form vs Substance",fig1_2d_scatter),("2: Gap Distribution",fig2_gap_distribution),
        ("3: Quadrant Pie",fig3_quadrant_pie),("4: By Quadrant",fig4_scores_by_quadrant),
        ("5: Substance Radar",fig5_substance_radar),("6: Predictors",fig6_predictors),
        ("7: Refs vs Substance",fig7_refs),("8: Tables",fig8_tables),
        ("9: Form Composition",fig9_form_comp),("10: Cross Corr",fig10_cross_corr)]:
        print(f"  {name}...")
        try: fn(df)
        except Exception as e: print(f"    ERROR: {e}")

    print("\nGenerating HTML report...")
    generate_report(df, sd, corrs)

    pd.concat([v.nlargest(10,"substance_score").assign(rank="top_substance"),
        v.nsmallest(10,"substance_score").assign(rank="bottom_substance"),
        v.nlargest(10,"form_score").assign(rank="top_form"),
        v.nsmallest(10,"form_score").assign(rank="bottom_form"),
        v.nlargest(10,"fs_gap").assign(rank="most_overpackaged"),
        v.nsmallest(10,"fs_gap").assign(rank="most_underpackaged"),
    ]).to_csv(OUTPUTS_DIR/"top_bottom_papers.csv", index=False)
    print("  Saved top_bottom_papers.csv")
    print("\n"+"="*60+"\nComplete!\n"+"="*60)

if __name__ == "__main__":
    main()
PYEOF
python cross_check.py
```

**Expected output:** Summary statistics, quadrant distribution, correlation results,
10 PNG figures, and a self-contained HTML report.

**Validation:**
```bash
python -c "
import pandas as pd, json
from pathlib import Path

merged = pd.read_csv('outputs/merged_scores.csv')
stats = json.load(open('outputs/two_dim_stats.json'))
corrs = json.load(open('outputs/correlations.json'))
figs = sorted(Path('figures').glob('fig*.png'))
report = Path('outputs/audit_report.html')

checks = [
    (len(merged) >= 100, f'Merged papers: {len(merged)}'),
    ('form_score' in merged.columns, 'form_score column exists'),
    ('substance_score' in merged.columns, 'substance_score column exists'),
    ('fs_gap' in merged.columns, 'fs_gap column exists'),
    ('quadrant' in merged.columns, 'quadrant column exists'),
    (merged['form_score'].between(0, 100).all(), 'Form scores in range'),
    (merged['substance_score'].between(20, 100).all(), 'Substance scores in range'),
    (set(merged['quadrant'].unique()) <= {
        'Genuine Quality', 'Well-Packaged Slop', 'Hidden Gem', 'Low Effort',
    }, 'Valid quadrant labels'),
    ('form_substance_spearman' in corrs, 'Form-Substance correlation computed'),
    (len(figs) >= 10, f'Figures: {len(figs)}'),
    (report.exists() and report.stat().st_size > 100000, 'HTML report exists and is substantial'),
]

for ok, msg in checks:
    print(f'  [{\"PASS\" if ok else \"FAIL\"}] {msg}')

print()
all_pass = all(ok for ok, _ in checks)
print('ALL VALIDATIONS PASSED' if all_pass else 'SOME CHECKS FAILED')
print(f'  Form: {merged[\"form_score\"].mean():.1f} +/- {merged[\"form_score\"].std():.1f}')
print(f'  Substance: {merged[\"substance_score\"].mean():.1f} +/- {merged[\"substance_score\"].std():.1f}')
print(f'  Gap: {merged[\"fs_gap\"].mean():.1f} +/- {merged[\"fs_gap\"].std():.1f}')
rho = corrs['form_substance_spearman']['rho']
print(f'  Form-Substance rho: {rho}')
print(f'  Report: {report.stat().st_size / 1024:.0f} KB')
"
```

---

## Expected Output Tree

```
.
├── fetch_papers.py
├── compute_form.py
├── verify_references.py
├── cross_check.py
├── data/
│   └── papers_raw.json
├── outputs/
│   ├── form_scores.csv
│   ├── substance_scores.csv          <- agent-generated
│   ├── reference_verification.csv
│   ├── merged_scores.csv
│   ├── two_dim_stats.json
│   ├── correlations.json
│   ├── top_bottom_papers.csv
│   └── audit_report.html             <- PRIMARY DELIVERABLE
└── figures/
    ├── fig1_form_vs_substance.png     <- headline figure
    ├── fig2_gap_distribution.png
    ├── fig3_quadrant_distribution.png
    ├── fig4_scores_by_quadrant.png
    ├── fig5_substance_radar.png
    ├── fig6_predictor_correlations.png
    ├── fig7_refs_vs_substance.png
    ├── fig8_top_bottom_tables.png
    ├── fig9_form_composition.png
    └── fig10_cross_correlation.png
```

---

## Adapting This Skill

### Changing the Platform

To audit a different preprint platform:

1. **Data source.** Replace `API_URL` in `fetch_papers.py` with the target
   platform's API. Map fields (`summary` -> `abstract`, `id` -> `paper_id`)
   to match the schema expected by `compute_form.py`.

2. **Form rubric.** In `compute_form.py`, adjust `WEIGHTS`. For arXiv,
   drop C1 (Executability) and redistribute weight to C3 (Scientific Rigor)
   since arXiv papers have richer reference lists and no executable skills.

3. **Substance rubric.** In Step 3, adjust the scoring anchors. For a medical
   preprint server, add "Statistical Validity" as a sixth dimension and adjust
   the denominator accordingly.

4. **Reference verification.** `verify_references.py` works for any platform
   since it queries Semantic Scholar, which indexes broadly.

### Changing the Threshold

The quadrant threshold defaults to 50. To adjust:
- In `cross_check.py`, change the `50` in `quadrant()` to your value.
- A threshold of 40 is more lenient (fewer "Low Effort" classifications).
- A threshold of 60 is stricter (fewer "Genuine Quality" classifications).

### Adding Dimensions

To add a new Substance dimension (e.g., "Reproducibility"):
1. Add the scoring anchor description in Step 3.
2. Add the column to `substance_scores.csv`.
3. Update the denominator in the substance_score formula.
4. Add the column to the merge in `cross_check.py`.
5. Update `fig5_substance_radar` to include the new dimension.

### Using a Different Evaluator

Step 3 is designed for the executing agent to evaluate papers directly.
To use an external LLM API instead:
1. Replace Step 3 with a Python script that calls your preferred API.
2. Send each paper's content as a prompt with the scoring rubric.
3. Parse the structured response into the same CSV format.
4. Adjust the `estimated-time` in the frontmatter (API calls may be faster
   or slower than agent evaluation depending on rate limits).

The Fetch -> Form Score -> Substance Score -> Verify -> Cross-Check
architecture stays the same regardless of what evaluates Substance.
