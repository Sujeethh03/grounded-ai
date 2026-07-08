"""M3: split normalized sections into retrieval-sized chunks.

Strategy: pack whole paragraphs up to a max size with a small overlap between
consecutive chunks. Paragraph-boundary packing (rather than fixed character
windows) keeps sentences and disclosure items intact — the filing equivalent
of the dossier's "chunk by structure, not fixed windows" rule. Sizes are in
characters: ~3000 chars ≈ 700-800 tokens, a comfortable fit for
text-embedding-3-small and small enough that a top-8 context stays cheap.
"""

from dataclasses import dataclass

MAX_CHUNK_CHARS = 3000
OVERLAP_CHARS = 300
MIN_CHUNK_CHARS = 200  # merge-forward threshold: don't emit confetti chunks


@dataclass(frozen=True)
class Chunk:
    section_name: str
    chunk_index: int
    text: str


def chunk_section(section_name: str, text: str, start_index: int = 0) -> list[Chunk]:
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = f"{current}\n{para}".strip() if current else para
        if len(candidate) <= MAX_CHUNK_CHARS:
            current = candidate
            continue
        if current:
            chunks.append(current)
            # Seed the next chunk with the tail of this one for continuity
            # across the boundary (cheap, dependency-free overlap).
            current = current[-OVERLAP_CHARS:] + "\n" + para
        else:
            # Single paragraph longer than the max — hard-split it.
            for i in range(0, len(para), MAX_CHUNK_CHARS - OVERLAP_CHARS):
                chunks.append(para[i : i + MAX_CHUNK_CHARS])
            current = ""
    if current:
        if chunks and len(current) < MIN_CHUNK_CHARS:
            chunks[-1] = f"{chunks[-1]}\n{current}"
        else:
            chunks.append(current)

    return [
        Chunk(section_name=section_name, chunk_index=start_index + i, text=chunk_text)
        for i, chunk_text in enumerate(chunks)
    ]
