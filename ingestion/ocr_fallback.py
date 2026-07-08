"""M2: OCR fallback for filings/exhibits whose content isn't extractable text.

Path: content sniffed as PDF -> render each page to an image (pypdfium2, no
poppler needed) -> Tesseract OCR (pytesseract) -> per-page confidence from
Tesseract's word-level scores. The mean page confidence is persisted onto the
chunks later (doc_chunks.ocr_confidence) so retrieval can discount low-quality
text instead of trusting it blindly.

Scope note: EDGAR *primary* documents are almost always HTML — scanned PDFs
show up as exhibits and older filings. The pipeline routes here only when the
fetched bytes are a PDF or the HTML path yields near-zero text; pulling every
exhibit of every filing is deliberately out of scope for now (recorded in
PROGRESS.md).
"""

import io
from dataclasses import dataclass

import structlog

log = structlog.get_logger(__name__)

OCR_RENDER_SCALE = 2.0  # ~144 dpi; Tesseract accuracy drops hard below ~120 dpi
MAX_OCR_PAGES = 50  # cost guard: a 400-page scanned 10-K is a job queue problem, not an M2 one


@dataclass(frozen=True)
class OCRResult:
    text: str
    confidence: float  # 0.0-1.0 mean word confidence across pages
    pages_processed: int
    pages_total: int


def looks_like_pdf(content: bytes) -> bool:
    return content.lstrip()[:5] == b"%PDF-"


def extract_text_via_ocr(pdf_bytes: bytes) -> OCRResult:
    import pypdfium2 as pdfium
    import pytesseract

    pdf = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    try:
        pages_total = len(pdf)
        page_texts: list[str] = []
        confidences: list[float] = []

        for i in range(min(pages_total, MAX_OCR_PAGES)):
            page = pdf[i]
            bitmap = page.render(scale=OCR_RENDER_SCALE)
            image = bitmap.to_pil()

            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            words = [w for w, conf in zip(data["text"], data["conf"]) if w.strip() and conf != -1]
            page_conf = [int(c) for w, c in zip(data["text"], data["conf"]) if w.strip() and c != -1]

            page_texts.append(" ".join(words))
            confidences.extend(page_conf)
            log.debug("ocr_page_done", page=i, words=len(words))

        mean_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0
        result = OCRResult(
            text="\n\n".join(page_texts).strip(),
            confidence=round(mean_conf, 2),
            pages_processed=min(pages_total, MAX_OCR_PAGES),
            pages_total=pages_total,
        )
        log.info(
            "ocr_extraction_done",
            pages=result.pages_processed,
            of=result.pages_total,
            confidence=result.confidence,
            chars=len(result.text),
        )
        return result
    finally:
        pdf.close()
