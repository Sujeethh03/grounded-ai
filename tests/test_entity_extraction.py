from ingestion.entity_extraction import extract_topics


def test_matches_supply_chain_topic():
    text = "The Company faces supply chain disruption and relies on outsourcing partners."
    topics = {m.topic for m in extract_topics(text)}
    assert "supply_chain" in topics


def test_evidence_count_orders_topics():
    text = (
        "Supply chain issues. Supply chain constraints. Component shortage persists. "
        "Some litigation exists."
    )
    matches = extract_topics(text)
    assert matches[0].topic == "supply_chain"
    assert matches[0].evidence_count >= 3


def test_min_evidence_filters_passing_mentions():
    text = "One passing mention of inflation."
    assert extract_topics(text, min_evidence=2) == []


def test_no_topics_in_unrelated_text():
    assert extract_topics("The quick brown fox jumps over the lazy dog.") == []
