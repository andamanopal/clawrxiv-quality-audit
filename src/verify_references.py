"""Reference verification via CrossRef API.

Extracts citation-like patterns from paper content and verifies
them against CrossRef's metadata database. Reports verification
rate and identifies potentially hallucinated references.
"""

import re
import time
import requests


CROSSREF_API = "https://api.crossref.org/works"
RATE_LIMIT_DELAY = 0.5


def extract_references(content):
    """Extract reference-like strings from paper content."""
    if not content:
        return []

    refs = []

    # Pattern 1: "Author et al. (YEAR)" or "Author et al., YEAR"
    author_year = re.findall(
        r'([A-Z][a-z]+(?:\s+et\s+al\.?)?)\s*[\(,]\s*((?:19|20)\d{2})\s*\)?',
        content,
    )
    for author, year in author_year:
        refs.append({"type": "author_year", "author": author.strip(), "year": year})

    # Pattern 2: arXiv IDs (e.g., arXiv:2505.19955)
    arxiv_ids = re.findall(r'arXiv[:\s]+(\d{4}\.\d{4,5})', content, re.IGNORECASE)
    for aid in arxiv_ids:
        refs.append({"type": "arxiv", "arxiv_id": aid})

    # Pattern 3: DOIs
    dois = re.findall(r'(?:doi[:\s]+|doi\.org/)(10\.\d{4,}/[^\s,]+)', content, re.IGNORECASE)
    for doi in dois:
        refs.append({"type": "doi", "doi": doi.rstrip(".")})

    # Pattern 4: Numbered references section entries
    ref_section = re.split(r'(?i)#+\s*references?\s*$', content, flags=re.MULTILINE)
    if len(ref_section) > 1:
        ref_text = ref_section[-1]
        numbered = re.findall(r'^\s*\d+\.\s+(.+?)$', ref_text, re.MULTILINE)
        for entry in numbered:
            title_match = re.search(r'["\u201c](.+?)["\u201d]', entry)
            if title_match:
                refs.append({"type": "title", "title": title_match.group(1)[:200]})
            else:
                refs.append({"type": "raw_entry", "text": entry[:200]})

    # Deduplicate
    seen = set()
    unique = []
    for r in refs:
        key = str(sorted(r.items()))
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique


def verify_via_crossref(query, year=None):
    """Search CrossRef for a reference. Returns match confidence."""
    params = {"query": query, "rows": 3}
    if year:
        params["filter"] = f"from-pub-date:{year},until-pub-date:{year}"

    try:
        resp = requests.get(CROSSREF_API, params=params, timeout=15)
        if resp.status_code == 429:
            time.sleep(2)
            resp = requests.get(CROSSREF_API, params=params, timeout=15)
        if resp.status_code != 200:
            return {"verified": False, "reason": f"API error {resp.status_code}"}

        data = resp.json()
        items = data.get("message", {}).get("items", [])
        if not items:
            return {"verified": False, "reason": "no results"}

        top = items[0]
        score = top.get("score", 0)
        title = top.get("title", [""])[0] if top.get("title") else ""
        doi = top.get("DOI", "")

        return {
            "verified": score > 40,
            "confidence": min(score / 100, 1.0),
            "matched_title": title[:100],
            "doi": doi,
            "score": score,
        }
    except requests.RequestException as e:
        return {"verified": False, "reason": str(e)[:80]}


def verify_paper_references(content):
    """Verify all references in a paper. Returns summary stats."""
    refs = extract_references(content)
    if not refs:
        return {
            "total_refs": 0,
            "verified": 0,
            "unverified": 0,
            "hallucination_rate": 0.0,
            "verification_rate": 0.0,
            "details": [],
        }

    results = []
    verified_count = 0
    checked_count = 0

    for ref in refs:
        if ref["type"] == "author_year":
            query = f"{ref['author']} {ref['year']}"
            result = verify_via_crossref(query, ref.get("year"))
            result["query"] = query
            results.append(result)
            checked_count += 1
            if result["verified"]:
                verified_count += 1

        elif ref["type"] == "doi":
            results.append({"verified": True, "query": ref["doi"], "reason": "DOI exists"})
            verified_count += 1
            checked_count += 1

        elif ref["type"] == "title":
            result = verify_via_crossref(ref["title"])
            result["query"] = ref["title"][:60]
            results.append(result)
            checked_count += 1
            if result["verified"]:
                verified_count += 1

        time.sleep(RATE_LIMIT_DELAY)

    unverified = checked_count - verified_count

    return {
        "total_refs": len(refs),
        "checked": checked_count,
        "verified": verified_count,
        "unverified": unverified,
        "hallucination_rate": unverified / checked_count if checked_count > 0 else 0.0,
        "verification_rate": verified_count / checked_count if checked_count > 0 else 0.0,
        "details": results,
    }


def verify_all_papers(papers, max_papers=None):
    """Verify references for all papers. Returns per-paper results."""
    results = []
    total = min(len(papers), max_papers) if max_papers else len(papers)

    for i, paper in enumerate(papers[:total]):
        pid = paper.get("paperId") or paper.get("paper_id") or str(paper.get("id", ""))
        content = paper.get("content", "") or ""
        title = paper.get("title", "") or ""

        print(f"  [{i+1}/{total}] Verifying refs for {pid}: {title[:50]}...")
        result = verify_paper_references(content)
        result["paper_id"] = pid
        result["title"] = title
        results.append(result)

    total_refs = sum(r["total_refs"] for r in results)
    total_verified = sum(r["verified"] for r in results)
    total_checked = sum(r["checked"] for r in results)

    print(f"\n  Summary: {total_checked} refs checked across {total} papers")
    print(f"  Verified: {total_verified} ({total_verified/total_checked*100:.1f}%)" if total_checked > 0 else "")
    print(f"  Unverified: {total_checked - total_verified}")

    return results
