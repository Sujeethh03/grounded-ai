"""M4: extract RiskFactor topics from filing sections — deterministically.

Scoped deviation from the dossier (recorded): the dossier sketched LLM-based
entity extraction including Person/executive nodes. Person nodes need DEF 14A
proxy statements (not ingested yet), and LLM extraction adds cost + a
hallucination surface to a component whose whole value is being *reliable*
graph ground truth. So v1 is a keyword-taxonomy matcher: cheap, testable,
zero-hallucination. LLM-assisted extraction (and Person nodes) layer on later
when proxy statements are in the corpus.

The taxonomy is small on purpose — topics broad enough to recur across
companies, which is what makes cross-company graph queries meaningful.
"""

import re
from dataclasses import dataclass

RISK_TAXONOMY: dict[str, list[str]] = {
    "supply_chain": ["supply chain", "supply constraint", "component shortage", "outsourcing partner", "single source supplier"],
    "semiconductor": ["semiconductor", "chip shortage", "nand", "dram", "foundry"],
    "currency": ["foreign exchange", "currency", "exchange rate", "hedging"],
    "litigation": ["litigation", "legal proceeding", "lawsuit", "class action", "antitrust"],
    "cybersecurity": ["cybersecurity", "cyber attack", "data breach", "ransomware", "information security"],
    "regulation": ["regulatory", "regulation", "compliance", "government investigation", "digital markets act"],
    "competition": ["competition", "competitive pressure", "price competition", "market share"],
    "interest_rate": ["interest rate", "monetary policy", "federal reserve"],
    "macroeconomic": ["inflation", "recession", "macroeconomic", "economic downturn", "consumer demand"],
    "talent": ["key personnel", "attract and retain", "talent", "workforce"],
}


@dataclass(frozen=True)
class TopicMatch:
    topic: str
    evidence_count: int  # how many taxonomy phrases matched — crude signal strength


def extract_topics(text: str, min_evidence: int = 1) -> list[TopicMatch]:
    lowered = text.lower()
    matches = []
    for topic, phrases in RISK_TAXONOMY.items():
        count = sum(len(re.findall(re.escape(phrase), lowered)) for phrase in phrases)
        if count >= min_evidence:
            matches.append(TopicMatch(topic=topic, evidence_count=count))
    return sorted(matches, key=lambda m: m.evidence_count, reverse=True)
