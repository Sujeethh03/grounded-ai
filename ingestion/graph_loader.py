"""M4: sync Postgres filings into the Neo4j knowledge graph.

Graph schema (scoped per CLAUDE.md — do not grow without a justifying query):
    (:Company {cik, name})
    (:Filing {accession, form_type, fiscal_year})
    (:RiskFactor {topic})
    (Company)-[:FILED]->(Filing)
    (Filing)-[:DISCUSSES {evidence_count}]->(RiskFactor)

Person/BOARD_MEMBER_OF nodes are deferred until DEF 14A proxy statements are
ingested (see entity_extraction.py docstring).

Idempotent by construction: everything is MERGE, so re-running syncs rather
than duplicates — same property the ingestion pipeline has.
"""

import os

import structlog
from neo4j import GraphDatabase
from sqlalchemy import select

from db.models import Filing, FilingSection
from db.session import get_session
from ingestion.entity_extraction import extract_topics

log = structlog.get_logger(__name__)

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "ledgerlens")

# Topics extracted only from sections likely to discuss risk — matching the
# whole filing would tag every company with every topic mentioned in passing.
RISK_SECTION_HINTS = ("risk factor", "management's discussion", "management’s discussion")
MIN_EVIDENCE = 2  # a single phrase hit in MD&A is noise; two+ is a discussion


def load_graph() -> dict[str, int]:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    summary = {"companies": 0, "filings": 0, "discusses_edges": 0}

    with get_session() as session, driver.session() as neo:
        filings = session.scalars(select(Filing).where(Filing.ingestion_status == "indexed")).all()

        for filing in filings:
            neo.run(
                """
                MERGE (c:Company {cik: $cik})
                  ON CREATE SET c.name = $name
                MERGE (f:Filing {accession: $accession})
                  ON CREATE SET f.form_type = $form_type, f.fiscal_year = $fiscal_year
                MERGE (c)-[:FILED]->(f)
                """,
                cik=filing.company_cik,
                name=filing.company_name,
                accession=filing.accession_number,
                form_type=filing.form_type,
                fiscal_year=filing.fiscal_year,
            )
            summary["filings"] += 1

            sections = session.scalars(
                select(FilingSection).where(FilingSection.filing_id == filing.id)
            ).all()
            risk_text = "\n".join(
                s.text for s in sections if any(hint in s.section_name.lower() for hint in RISK_SECTION_HINTS)
            )
            if not risk_text:
                continue

            for match in extract_topics(risk_text, min_evidence=MIN_EVIDENCE):
                neo.run(
                    """
                    MATCH (f:Filing {accession: $accession})
                    MERGE (r:RiskFactor {topic: $topic})
                    MERGE (f)-[d:DISCUSSES]->(r)
                      SET d.evidence_count = $evidence
                    """,
                    accession=filing.accession_number,
                    topic=match.topic,
                    evidence=match.evidence_count,
                )
                summary["discusses_edges"] += 1

        result = neo.run("MATCH (c:Company) RETURN count(c) AS n").single()
        summary["companies"] = result["n"]

    driver.close()
    log.info("graph_loaded", **summary)
    return summary
