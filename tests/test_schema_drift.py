from ingestion.normalize import NormalizedDocument, NormalizedSection
from ingestion.schema_drift import check_structure


def _doc(form_type: str, sections: list[tuple[str, int]]) -> NormalizedDocument:
    return NormalizedDocument(
        accession_number="acc",
        form_type=form_type,
        sections=[
            NormalizedSection(name=name, index=i, text="x" * chars)
            for i, (name, chars) in enumerate(sections)
        ],
    )


def test_well_structured_10q_passes():
    doc = _doc("10-Q", [(f"Item {i}. Something", 500) for i in range(1, 7)])
    assert check_structure(doc).ok


def test_10k_with_only_full_text_fallback_is_flagged():
    doc = _doc("10-K", [("Full Text", 50_000)])
    result = check_structure(doc)
    assert not result.ok
    assert "header structure not recognized" in result.reason


def test_near_empty_parse_is_flagged():
    doc = _doc("10-Q", [("Item 1. Business", 100)])
    result = check_structure(doc)
    assert not result.ok
    assert "near-empty" in result.reason


def test_8k_with_single_full_text_section_is_ok():
    # 8-Ks are often legitimately unstructured — a substantive Full Text
    # parse must NOT be treated as drift, or we'd flag half of EDGAR.
    doc = _doc("8-K", [("Item 5.02 Departure of Directors", 2000)])
    assert check_structure(doc).ok


def test_unknown_form_type_is_flagged():
    doc = _doc("S-1", [("Full Text", 10_000)])
    result = check_structure(doc)
    assert not result.ok
    assert "unknown form type" in result.reason
