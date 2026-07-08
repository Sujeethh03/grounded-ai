"""M2: detect filings whose parsed structure doesn't match what we expect.

The dossier frames this as "the SEC changes form structure under you" — the
M1 normalizer assumes Item-header structure, so the concrete, testable version
of drift detection here is structural expectation checking per form type:

- 10-K / 10-Q filings are Item-structured by regulation. If normalization
  produced no Item sections (just the "Full Text" fallback) or suspiciously
  few, the parser likely failed to recognize the document's structure —
  flag it rather than silently indexing a bad parse.
- 8-K filings are short and sometimes legitimately unstructured, so only an
  effectively-empty parse is drift for those.

Flagged filings get ingestion_status='schema_drift_flagged' and keep their
raw sections so a human (or a later, smarter parser) can triage — the status
lifecycle is the point: never silently mis-parse.
"""

from dataclasses import dataclass

from ingestion.normalize import NormalizedDocument

# 10-Ks have ~15 mandated Items, 10-Qs ~10. Seeing fewer than this many parsed
# sections means the header regex almost certainly missed the document's real
# structure (threshold deliberately loose — false *negatives* here are worse
# than false positives, since a flag just routes to review, not deletion).
MIN_SECTIONS = {"10-K": 5, "10-Q": 4, "8-K": 1}
MIN_TOTAL_CHARS = 500  # anything below this parsed from a real filing is a failed parse


@dataclass(frozen=True)
class DriftCheck:
    ok: bool
    reason: str | None = None


def check_structure(doc: NormalizedDocument) -> DriftCheck:
    total_chars = sum(len(s.text) for s in doc.sections)
    if total_chars < MIN_TOTAL_CHARS:
        return DriftCheck(ok=False, reason=f"near-empty parse: {total_chars} chars total")

    expected_min = MIN_SECTIONS.get(doc.form_type)
    if expected_min is None:
        # Unknown form type is itself a kind of drift — we're parsing something
        # the pipeline was never designed for.
        return DriftCheck(ok=False, reason=f"unknown form type: {doc.form_type}")

    item_sections = [s for s in doc.sections if s.name != "Full Text"]
    if len(item_sections) < expected_min:
        return DriftCheck(
            ok=False,
            reason=(
                f"{doc.form_type} parsed into {len(item_sections)} Item sections, "
                f"expected >= {expected_min} — header structure not recognized"
            ),
        )
    return DriftCheck(ok=True)
