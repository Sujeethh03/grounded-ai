"""Graph-arm integration with the agent pipeline — Neo4j mocked; what's under
test is the wiring: planner lookups reach the graph agent, graph facts enter
the citation system, and a dead Neo4j never breaks text-RAG answers."""

import json
import uuid
from unittest.mock import patch

import agents.graph as graph_module
from agents.graph import ask
from agents.retriever_agent import gather_context
from retrieval.hybrid_search import SearchHit


class FakeEmbedder:
    def embed(self, texts):
        return [[0.0] * 1536 for _ in texts]


def _graph_fact(text: str) -> SearchHit:
    return SearchHit(
        chunk_id=uuid.uuid4(),
        filing_accession="knowledge-graph",
        company_name="(graph fact)",
        form_type="KG",
        fiscal_year=None,
        section="Knowledge Graph",
        text=text,
        ocr_confidence=None,
        rrf_score=1.0,
    )


def test_graph_facts_sort_first_and_get_labels(monkeypatch):
    monkeypatch.setattr(
        "agents.retriever_agent.hybrid_search",
        lambda q, e, top_k: [
            SearchHit(
                chunk_id=uuid.uuid4(), filing_accession="a", company_name="Apple", form_type="10-Q",
                fiscal_year=2026, section="Item 1A", text="text chunk", ocr_confidence=None, rrf_score=0.02,
            )
        ],
    )
    fact = _graph_fact("Knowledge graph: companies discussing supply_chain — Apple; Tesla")
    labeled = gather_context(["q"], FakeEmbedder(), extra_hits=[fact])
    assert labeled[0].label == "C1"
    assert labeled[0].hit.section == "Knowledge Graph"  # rrf 1.0 outranks text chunks
    assert labeled[1].hit.text == "text chunk"


def test_planner_lookups_reach_graph_agent():
    chat_responses = iter(
        [
            json.dumps(
                {
                    "sub_queries": ["companies with currency risk"],
                    "graph_lookups": [{"kind": "companies_discussing", "arg": "currency"}],
                }
            ),
            json.dumps({"answer": "Apple and JPMorgan discuss currency risk [C1]."}),
        ]
    )
    fact = _graph_fact("Knowledge graph: companies whose filings discuss currency risk — Apple; JPMorgan")

    with (
        patch.object(graph_module, "gather_context", lambda q, e, extra_hits=None: [
            __import__("agents.retriever_agent", fromlist=["LabeledChunk"]).LabeledChunk(label="C1", hit=fact)
        ]),
        patch("agents.graph_agent.companies_discussing", return_value=[fact]) as mock_lookup,
    ):
        result = ask("Which companies discuss currency risk?", lambda system, user, model: next(chat_responses), FakeEmbedder())

    mock_lookup.assert_called_once_with("currency")
    assert not result.refused
    assert "[C1]" in result.answer


def test_dead_neo4j_degrades_gracefully(monkeypatch):
    def boom(topic):
        raise ConnectionError("neo4j down")

    monkeypatch.setattr("agents.graph_agent.companies_discussing", boom)
    hits = graph_module._run_graph_lookups([{"kind": "companies_discussing", "arg": "currency"}])
    assert hits == []  # swallowed + logged, never raised


def test_invalid_topic_returns_no_facts():
    from agents.graph_agent import companies_discussing

    assert companies_discussing("not_a_real_topic") == []  # no Neo4j call even attempted
