"""M4 CLI: sync indexed filings from Postgres into the Neo4j knowledge graph.

Usage:
    python -m scripts.load_graph
"""

import structlog
from dotenv import load_dotenv

load_dotenv()

from ingestion.graph_loader import load_graph  # noqa: E402

structlog.configure(processors=[structlog.dev.ConsoleRenderer()])


def main() -> None:
    summary = load_graph()
    structlog.get_logger().info("done", **summary)


if __name__ == "__main__":
    main()
