"""M3 CLI: hybrid search over the index.

Usage:
    python -m scripts.search "supply chain risks"
"""

import argparse

from dotenv import load_dotenv

load_dotenv()

from retrieval.embeddings import OpenAIEmbedder  # noqa: E402
from retrieval.hybrid_search import hybrid_search  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Hybrid search over indexed documents.")
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    hits = hybrid_search(args.query, OpenAIEmbedder(), top_k=args.top_k)
    if not hits:
        print("No results — is anything indexed? Run: python -m scripts.index")
        return
    for i, hit in enumerate(hits, 1):
        year = hit.year if hit.year is not None else "-"
        print(f"\n[{i}] {hit.entity_name} {hit.doc_type} {year} — {hit.section}")
        print(f"    source_key={hit.source_key}  rrf={hit.rrf_score}")
        preview = " ".join(hit.text.split())[:300]
        print(f"    {preview}...")


if __name__ == "__main__":
    main()
