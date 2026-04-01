"""Fetch all papers from the clawRxiv API and save to disk."""

import json
import time
from pathlib import Path

import requests

BASE_URL = "https://clawrxiv.io"
API_URL = f"{BASE_URL}/api/posts"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_FILE = DATA_DIR / "papers_raw.json"
PAGE_SIZE = 100
RATE_LIMIT_DELAY = 0.5


def fetch_all_papers():
    """Paginate through the clawRxiv API and collect every paper."""
    all_papers = []
    page = 1
    total = None

    while True:
        params = {"limit": PAGE_SIZE, "page": page}
        response = requests.get(API_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        posts = data.get("posts", [])
        if total is None:
            total = data.get("total", 0)
            print(f"Total papers reported by API: {total}")

        if not posts:
            break

        all_papers.extend(posts)
        print(f"  Page {page}: fetched {len(posts)} papers (cumulative: {len(all_papers)})")

        if len(all_papers) >= total:
            break

        page += 1
        time.sleep(RATE_LIMIT_DELAY)

    return all_papers


def fetch_full_paper(paper_id):
    """Fetch a single paper with full content."""
    response = requests.get(f"{API_URL}/{paper_id}", timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_all_with_content():
    """Fetch listing, then fetch full content for each paper."""
    papers = fetch_all_papers()
    full_papers = []

    for i, paper in enumerate(papers):
        pid = paper.get("id")
        print(f"  Fetching full content for paper {pid} ({i + 1}/{len(papers)})...")
        try:
            full = fetch_full_paper(pid)
            full_papers.append(full)
        except requests.RequestException as e:
            print(f"    WARNING: Failed to fetch paper {pid}: {e}")
            full_papers.append(paper)
        time.sleep(RATE_LIMIT_DELAY)

    return full_papers


def save_papers(papers, filepath=None):
    """Save papers to JSON file."""
    filepath = filepath or OUTPUT_FILE
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(papers, f, indent=2, default=str)
    print(f"Saved {len(papers)} papers to {filepath}")


def load_papers(filepath=None):
    """Load papers from JSON file."""
    filepath = filepath or OUTPUT_FILE
    with open(filepath) as f:
        return json.load(f)


def main():
    print("=" * 60)
    print("clawRxiv Paper Fetcher")
    print("=" * 60)

    print("\nFetching all papers with full content...")
    full_papers = fetch_all_with_content()

    print("\nSaving to disk...")
    save_papers(full_papers)

    print(f"\nDone! {len(full_papers)} papers saved.")
    return full_papers


if __name__ == "__main__":
    main()
