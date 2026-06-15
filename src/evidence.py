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

    - Need multiple supports for high confidence (single mention isn't proof)
    - Any contradicting evidence drops sharply
    - Low extraction confidence caps the score
    """
    if claim_count == 0:
        return 0.0
    # Start below extraction_conf — a single rules hit isn't proof on its own
    base = max(0.0, extraction_conf - 0.20)
    # Reward corroboration up to ~+0.30 (need ~4 supports to fully boost)
    boost = min(0.30, 0.08 * supports)
    # Penalty for contradictions (steep)
    penalty = min(0.80, 0.30 * contradicts)
    return max(0.0, min(1.0, base + boost - penalty))


def status_label(trust: float, supports: int, contradicts: int) -> str:
    # Any contradiction with no countervailing support → contradicted
    if contradicts >= 1 and supports <= contradicts:
        return "contradicted"
    # Mixed signal → unclear
    if contradicts >= 1:
        return "unclear"
    # Need both a healthy trust score AND multiple corroborating supports
    if trust >= 0.75 and supports >= 2:
        return "verified"
    return "unclear"
