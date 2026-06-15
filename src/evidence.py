"""Evidence retrieval + confidence + contradiction detection.

Owner: Data Scientist.
For each extracted claim, find supporting / contradicting snippets in the
facility's own text. Pure-Python sliding-window match is fine for 10k facilities;
no vector index required at this scale.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


CONTRADICTION_CUES = (
    "no ", "not ", "without", "lack of", "absence of", "unavailable",
    "do not have", "doesn't have", "does not offer", "not equipped",
    "referred elsewhere", "refer out", "not provided",
)


@dataclass
class EvidenceSnippet:
    claim_id: str
    snippet: str
    source_field: str
    polarity: str  # supports | contradicts | neutral
    retrieval_score: float


def find_evidence(
    claim_value: str,
    claim_raw: str,
    facility_text_by_field: dict[str, str],
) -> list[EvidenceSnippet]:
    """Slide a window over facility text; flag matches by polarity."""
    results: list[EvidenceSnippet] = []
    needles = {claim_value.lower(), claim_raw.lower()}
    for field, text in facility_text_by_field.items():
        if not text:
            continue
        haystack = text.lower()
        for needle in needles:
            for m in re.finditer(re.escape(needle), haystack):
                start = max(0, m.start() - 80)
                end = min(len(text), m.end() + 80)
                snippet = text[start:end]
                polarity = _polarity(snippet.lower(), needle)
                results.append(
                    EvidenceSnippet(
                        claim_id="",  # filled in by caller
                        snippet=snippet.strip(),
                        source_field=field,
                        polarity=polarity,
                        retrieval_score=1.0 if needle == claim_raw.lower() else 0.7,
                    )
                )
    return results


def _polarity(snippet_lower: str, needle: str) -> str:
    idx = snippet_lower.find(needle)
    if idx == -1:
        return "neutral"
    before = snippet_lower[max(0, idx - 40) : idx]
    return "contradicts" if any(cue in before for cue in CONTRADICTION_CUES) else "supports"


def trust_score(
    claim_count: int,
    supports: int,
    contradicts: int,
    extraction_conf: float,
) -> float:
    """Weighted aggregate.

    - More supporting evidence raises score
    - Any contradicting evidence drops sharply
    - Low extraction confidence caps the score
    """
    if claim_count == 0:
        return 0.0
    base = extraction_conf
    boost = min(0.3, 0.08 * supports)
    penalty = min(0.6, 0.25 * contradicts)
    return max(0.0, min(1.0, base + boost - penalty))


def status_label(trust: float, supports: int, contradicts: int) -> str:
    if contradicts > 0 and supports == 0:
        return "contradicted"
    if trust >= 0.7 and supports >= 1:
        return "verified"
    return "unclear"
