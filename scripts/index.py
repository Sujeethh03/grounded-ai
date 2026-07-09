"""M3 CLI: chunk + embed everything ingested but not yet indexed.

Usage:
    python -m scripts.index
"""

import structlog
from dotenv import load_dotenv

load_dotenv()

from retrieval.embeddings import OpenAIEmbedder  # noqa: E402
from retrieval.indexer import index_pending_documents  # noqa: E402

structlog.configure(processors=[structlog.dev.ConsoleRenderer()])


def main() -> None:
    summary = index_pending_documents(OpenAIEmbedder())
    structlog.get_logger().info("done", **summary)


if __name__ == "__main__":
    main()
