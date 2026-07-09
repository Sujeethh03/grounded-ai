"""CLI entrypoint: ingest openFDA drug labels for one or more drugs.

Usage:
    python -m scripts.ingest_drug warfarin ibuprofen aspirin
    python -m scripts.ingest_drug lisinopril --limit 2

Names may be generic or brand; unknown names report fetched=0 rather than
failing (openFDA answers "no such drug" and the pipeline respects it).
"""

import argparse
import asyncio

import structlog
from dotenv import load_dotenv

load_dotenv()

from ingestion.pipeline import ingest_drug  # noqa: E402  (must follow load_dotenv)

structlog.configure(processors=[structlog.dev.ConsoleRenderer()])
log = structlog.get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest openFDA drug labels into GroundedAI.")
    parser.add_argument("drugs", nargs="+", help="Drug names (generic or brand)")
    parser.add_argument("--limit", type=int, default=2, help="Max labels per drug this run")
    args = parser.parse_args()

    async def run() -> None:
        for drug in args.drugs:
            summary = await ingest_drug(drug, limit=args.limit)
            log.info("drug_done", drug=drug, **summary)

    asyncio.run(run())


if __name__ == "__main__":
    main()
