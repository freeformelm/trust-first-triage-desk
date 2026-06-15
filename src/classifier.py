"""Rules-first claim classifier — baseline that produces silver_claim.

Owner: Data Scientist (Chialing) refines; this is the v0 baseline so the app can
render real data today.

Strategy (matches `agent_briefs/data_scientist.md` three-tier approach):
1. PARSE — silver_facility already has capabilities/equipment/procedures/specialties as ARRAY<STRING>
2. RULES — regex + specialty-code lookup to classify each array element into the Trust-Desk taxonomy
3. LLM (Chialing wires) — for elements rules can't classify, fall back to Foundation Model API

This module covers steps 1 and 2. Output: `silver_claim` Delta table.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from src.config import CFG


# ---------------------------------------------------------------------------
# Capability rule pack — Devpost called out ICU, maternity, emergency, oncology, trauma, NICU
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CapabilityRule:
    capability: str
    text_patterns: tuple[str, ...]
    specialty_codes: tuple[str, ...]


CAPABILITY_RULES: tuple[CapabilityRule, ...] = (
    CapabilityRule(
        capability="icu",
        text_patterns=(
            r"\bICU\b",
            r"\bintensive care\b",
            r"\bcritical care\b",
            r"\bcardiac care unit\b|\bCCU\b",
        ),
        specialty_codes=("criticalCareMedicine",),
    ),
    CapabilityRule(
        capability="nicu",
        text_patterns=(
            r"\bNICU\b",
            r"\bneonatal ICU\b",
            r"\bneonatal intensive care\b",
            r"\bneonatology\b",
        ),
        specialty_codes=("neonatologyPerinatalMedicine",),
    ),
    CapabilityRule(
        capability="maternity",
        text_patterns=(
            r"\bmaternity\b",
            r"\bobstetric",
            r"\blabour ward\b|\blabor ward\b",
            r"\bdelivery suite\b",
            r"\bbirthing\b",
            r"\binstitutional birth",
        ),
        specialty_codes=("gynecologyAndObstetrics", "obstetricsAndGynecology"),
    ),
    CapabilityRule(
        capability="emergency",
        text_patterns=(
            r"\bemergency department\b",
            r"\b24/?7 emergency\b",
            r"\b24[- ]hour emergency\b",
            r"\bcasualty\b",
            r"\bemergency care\b",
            r"\bER\b",
            r"\btrauma & emergency\b",
        ),
        specialty_codes=("emergencyMedicine",),
    ),
    CapabilityRule(
        capability="oncology",
        text_patterns=(
            r"\boncology\b",
            r"\bchemotherap",
            r"\bradiation therap",
            r"\bcancer (treatment|care|centre|center)\b",
            r"\bmedical oncology\b",
            r"\bsurgical oncology\b",
        ),
        specialty_codes=(
            "medicalOncology",
            "hematologyOncology",
            "radiationOncology",
            "surgicalOncology",
            "pediatricOncology",
            "gynecologicOncology",
        ),
    ),
    CapabilityRule(
        capability="trauma",
        text_patterns=(
            r"\btrauma surgery\b",
            r"\bpolytrauma\b",
            r"\btrauma (centre|center)\b",
            r"\btrauma care\b",
            r"\borthopedic trauma\b",
        ),
        specialty_codes=("traumaSurgery", "orthopedicTrauma"),
    ),
)


CONTRADICTION_PATTERN = re.compile(
    r"\b(?:no|not|without|lack of|absence of|unavailable|do(?:es)? not have|doesn'?t have|"
    r"does not offer|not equipped|referred elsewhere|refer(?:s|red)? out|not provided)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _claim_id(facility_id: str, claim_type: str, capability: str, claim_raw: str) -> str:
    h = hashlib.sha1(f"{facility_id}|{claim_type}|{capability}|{claim_raw}".encode("utf-8"))
    return h.hexdigest()[:16]


def _span(text: str, match_start: int, match_end: int, width: int = 200) -> str:
    half = width // 2
    a = max(0, match_start - half)
    b = min(len(text), match_end + half)
    return text[a:b].strip()


def _rule_for_text(elem: str) -> list[tuple[CapabilityRule, re.Match]]:
    """Return all (rule, match) pairs that fire against a text element."""
    hits: list[tuple[CapabilityRule, re.Match]] = []
    for rule in CAPABILITY_RULES:
        for pat in rule.text_patterns:
            m = re.search(pat, elem, re.IGNORECASE)
            if m:
                hits.append((rule, m))
                break  # one fire per rule is enough
    return hits


def _rule_for_specialty_code(code: str) -> CapabilityRule | None:
    for rule in CAPABILITY_RULES:
        if code in rule.specialty_codes:
            return rule
    return None


# ---------------------------------------------------------------------------
# Per-facility classification
# ---------------------------------------------------------------------------


@dataclass
class ClassifiedClaim:
    facility_id: str
    claim_id: str
    claim_type: str  # capability | procedure | equipment | specialty
    claim_value: str  # taxonomy term
    claim_raw: str  # exact array element
    source_field: str  # capabilities | procedures | equipment | specialties
    source_text_span: str
    extraction_confidence: float


def classify_facility(
    facility_id: str,
    capabilities: list[str] | None,
    procedures: list[str] | None,
    equipment: list[str] | None,
    specialties: list[str] | None,
) -> list[ClassifiedClaim]:
    """Return one ClassifiedClaim per (taxonomy capability, source element) match.

    Confidence tiers:
      - 0.85 — explicit text match in `capabilities` (rich, sentence-level)
      - 0.80 — coded specialty match in `specialties`
      - 0.75 — text match in `procedures` or `equipment`
    """
    out: list[ClassifiedClaim] = []

    # 1) capability text matches (richest)
    for elem in (capabilities or []):
        if not elem:
            continue
        for rule, m in _rule_for_text(elem):
            out.append(
                ClassifiedClaim(
                    facility_id=facility_id,
                    claim_id=_claim_id(facility_id, "capability", rule.capability, elem),
                    claim_type="capability",
                    claim_value=rule.capability,
                    claim_raw=elem[:200],
                    source_field="capabilities",
                    source_text_span=_span(elem, m.start(), m.end()),
                    extraction_confidence=0.85,
                )
            )

    # 2) specialty code matches
    for code in (specialties or []):
        if not code:
            continue
        rule = _rule_for_specialty_code(code.strip())
        if rule:
            out.append(
                ClassifiedClaim(
                    facility_id=facility_id,
                    claim_id=_claim_id(facility_id, "specialty", rule.capability, code),
                    claim_type="specialty",
                    claim_value=rule.capability,
                    claim_raw=code,
                    source_field="specialties",
                    source_text_span=code,
                    extraction_confidence=0.80,
                )
            )

    # 3) procedure / equipment text matches (weaker — these are tools/actions, not capabilities per se)
    for source_field, arr in (("procedures", procedures), ("equipment", equipment)):
        for elem in (arr or []):
            if not elem:
                continue
            for rule, m in _rule_for_text(elem):
                out.append(
                    ClassifiedClaim(
                        facility_id=facility_id,
                        claim_id=_claim_id(facility_id, source_field[:-1], rule.capability, elem),
                        claim_type=source_field[:-1],  # "procedures"->"procedure", "equipment"->"equipmen"... fix below
                        claim_value=rule.capability,
                        claim_raw=elem[:200],
                        source_field=source_field,
                        source_text_span=_span(elem, m.start(), m.end()),
                        extraction_confidence=0.75,
                    )
                )

    # Normalize claim_type for the equipment/procedure case
    for c in out:
        if c.claim_type == "procedure":
            pass
        elif c.claim_type == "equipmen":
            c.claim_type = "equipment"
        elif c.claim_type == "equipment":
            pass

    # Dedupe by claim_id (a facility can legitimately have multiple supporting elements
    # for the same capability — keep the first which is highest-confidence per ordering)
    seen: set[str] = set()
    uniq: list[ClassifiedClaim] = []
    for c in out:
        if c.claim_id in seen:
            continue
        seen.add(c.claim_id)
        uniq.append(c)
    return uniq


# ---------------------------------------------------------------------------
# Evidence: re-scan facility text for support / contradiction snippets
# ---------------------------------------------------------------------------


@dataclass
class EvidenceRow:
    evidence_id: str
    claim_id: str
    snippet: str
    source_field: str
    polarity: str  # supports | contradicts | neutral
    retrieval_score: float


def find_evidence_for_capability(
    claim_id: str,
    capability: str,
    text_by_field: dict[str, str | list[str] | None],
) -> list[EvidenceRow]:
    """Scan all text fields for capability mentions; tag polarity."""
    rule = next((r for r in CAPABILITY_RULES if r.capability == capability), None)
    if rule is None:
        return []

    out: list[EvidenceRow] = []
    for field, content in text_by_field.items():
        if content is None:
            continue
        if isinstance(content, list):
            haystacks = [(field, h) for h in content if h]
        else:
            haystacks = [(field, content)]
        for hay_field, haystack in haystacks:
            for pat in rule.text_patterns:
                for m in re.finditer(pat, haystack, re.IGNORECASE):
                    snippet = _span(haystack, m.start(), m.end())
                    before = haystack[max(0, m.start() - 40) : m.start()]
                    polarity = (
                        "contradicts"
                        if CONTRADICTION_PATTERN.search(before)
                        else "supports"
                    )
                    eid = hashlib.sha1(f"{claim_id}|{snippet[:64]}".encode("utf-8")).hexdigest()[:16]
                    out.append(
                        EvidenceRow(
                            evidence_id=eid,
                            claim_id=claim_id,
                            snippet=snippet,
                            source_field=hay_field,
                            polarity=polarity,
                            retrieval_score=1.0,
                        )
                    )
    # dedupe by evidence_id
    seen: set[str] = set()
    uniq: list[EvidenceRow] = []
    for e in out:
        if e.evidence_id in seen:
            continue
        seen.add(e.evidence_id)
        uniq.append(e)
    return uniq
