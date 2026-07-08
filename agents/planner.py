"""M5/M4 Planner: decompose a question into retrieval sub-queries, and decide
whether the knowledge graph should also be consulted.

Multi-hop questions ("how did Apple's supply-chain risk language change
between 2025 and 2026?") retrieve badly as a single query — each hop needs
its own search. Cross-company/topic questions ("which companies discuss
currency risk?") are exactly what the graph answers precisely and vector
search answers vaguely — the planner routes those to graph lookups on top of
(never instead of) text retrieval.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from agents.llm import CHEAP_MODEL, Chat, structured_call
from ingestion.entity_extraction import RISK_TAXONOMY

TOPICS = ", ".join(sorted(RISK_TAXONOMY))

SYSTEM = f"""You decompose questions about SEC filings into retrieval sub-queries,
and decide if the risk knowledge graph should also be consulted.
Return JSON:
{{"sub_queries": ["...", ...],            // 1-3 entries
  "graph_lookups": [                       // 0-2 entries, OMIT unless clearly useful
    {{"kind": "companies_discussing", "arg": "<topic>"}} |
    {{"kind": "topics_for_company", "arg": "<company name>"}} |
    {{"kind": "shared_topics", "arg": ""}}]}}
Valid topics (use EXACTLY these strings): {TOPICS}
Rules:
- Each sub-query must be independently searchable (no pronouns referring to other sub-queries).
- Keep the company name and fiscal year in every sub-query that needs them.
- If the question is already atomic, return it as the single sub-query. Do not decompose needlessly.
- Use graph_lookups ONLY for cross-company comparisons or "which companies..." questions.
- sub_queries may be [] only when graph_lookups fully answer the question; if the question also
  asks WHAT companies say (not just WHICH companies), include text sub-queries too.
- At least one of sub_queries / graph_lookups must be non-empty."""


class GraphLookup(BaseModel):
    kind: Literal["companies_discussing", "topics_for_company", "shared_topics"]
    arg: str = ""


class Plan(BaseModel):
    # sub_queries may be empty ONLY when graph lookups fully cover the question
    # (e.g. "which companies discuss X risk?") — the validator enforces that at
    # least one retrieval arm is always planned.
    sub_queries: list[str] = Field(default_factory=list, max_length=3)
    graph_lookups: list[GraphLookup] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def at_least_one_arm(self) -> "Plan":
        if not self.sub_queries and not self.graph_lookups:
            raise ValueError("plan must include sub_queries or graph_lookups (or both)")
        return self


def plan(question: str, chat: Chat) -> Plan:
    return structured_call(chat, SYSTEM, question, Plan, model=CHEAP_MODEL)
