"""OCR path test: build a real image-only PDF in memory, then OCR it.

This exercises the actual Tesseract + pypdfium2 stack rather than mocking it —
if the system tesseract binary is missing the test fails loudly, which is
correct: the OCR path being silently broken is exactly the failure mode M2
exists to prevent.
"""

import io

from PIL import Image, ImageDraw

from ingestion.ocr_fallback import extract_text_via_ocr, looks_like_pdf

SAMPLE_TEXT = "RISK FACTORS INCLUDE SUPPLY CHAIN DISRUPTION AND CURRENCY FLUCTUATION"


def _make_scanned_style_pdf(text: str) -> bytes:
    # White page with black text, saved as an image-only PDF — no text layer,
    # like a scanned exhibit.
    image = Image.new("RGB", (1400, 400), "white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 150), text, fill="black")
    buf = io.BytesIO()
    image.save(buf, format="PDF")
    return buf.getvalue()


def test_looks_like_pdf():
    assert looks_like_pdf(b"%PDF-1.7 blah")
    assert looks_like_pdf(b"  \n%PDF-1.4")
    assert not looks_like_pdf(b"<html><body>hi</body></html>")


def test_ocr_extracts_text_from_image_only_pdf():
    pdf_bytes = _make_scanned_style_pdf(SAMPLE_TEXT)
    assert looks_like_pdf(pdf_bytes)

    result = extract_text_via_ocr(pdf_bytes)

    assert result.pages_processed == 1
    # OCR of clean synthetic text should recover the key words; exact match
    # is too brittle across tesseract versions.
    assert "RISK" in result.text.upper()
    assert "SUPPLY" in result.text.upper()
    assert result.confidence > 0.5
