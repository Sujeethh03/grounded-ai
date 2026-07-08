from retrieval.chunking import MAX_CHUNK_CHARS, chunk_section


def test_short_section_is_one_chunk():
    chunks = chunk_section("Item 1. Business", "One short paragraph about the business.")
    assert len(chunks) == 1
    assert chunks[0].section_name == "Item 1. Business"
    assert chunks[0].chunk_index == 0


def test_long_section_splits_and_respects_max():
    paras = "\n".join(f"Paragraph {i}: " + ("word " * 120) for i in range(30))
    chunks = chunk_section("Item 1A. Risk Factors", paras)
    assert len(chunks) > 1
    assert all(len(c.text) <= MAX_CHUNK_CHARS + 400 for c in chunks)  # + overlap seed slack


def test_oversized_single_paragraph_is_hard_split():
    text = "x" * (MAX_CHUNK_CHARS * 3)
    chunks = chunk_section("Item 7. MD&A", text)
    assert len(chunks) >= 3


def test_indices_continue_from_start_index():
    chunks = chunk_section("Item 2.", "short text", start_index=5)
    assert chunks[0].chunk_index == 5


def test_empty_section_produces_no_chunks():
    assert chunk_section("Item 6.", "   \n  ") == []
