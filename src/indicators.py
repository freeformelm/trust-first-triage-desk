"""Facility-level operational & access indicators.

Owner: Data Scientist.

Beyond the 12-capability *clinical* taxonomy, planners and patients need to know
practical, facility-level signals that don't fit a "capability":
  - Operational status: open 24/7, temporarily closed, service under construction
  - Access & amenities: wheelchair/disabled access, ambulance, blood bank,
    pharmacy, cashless / government-insurance acceptance

These are extracted on demand from the same semi-structured text the classifier
uses (capabilities / procedures / equipment / description). Each detected
indicator carries a quoted source snippet (cite-or-die) and a status:
  - "available"   — mentioned without a negation
  - "unavailable" — mentioned with a negation/closure cue near it
  - "attention"   — operational caveats (temporarily closed / under construction)

Pure Python, no LLM, deterministic — safe to call live in the app per facility.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Reuse the same negation/closure cues the evidence layer uses, so polarity here
# stays consistent with capability contradiction detection.
from src.classifier import CONTRADICTION_AFTER, CONTRADICTION_BEFORE


@dataclass(frozen=True)
class IndicatorRule:
    key: str
    label: str
    icon: str
    kind: str                      # "operational" | "access"
    patterns: tuple[str, ...]
    # If True, ANY mention is itself the warning (closure/construction) — these are
    # surfaced as "attention" regardless of surrounding negation.
    is_caveat: bool = False


INDICATOR_RULES: tuple[IndicatorRule, ...] = (
    # --- Operational status ---
    IndicatorRule(
        "temporarily_closed", "Temporarily closed", "⛔", "operational",
        (r"\btemporarily closed\b", r"\bcurrently closed\b",
         r"\bclosed (?:temporarily|for|due to|until)\b", r"\bshut down\b"),
        is_caveat=True,
    ),
    IndicatorRule(
        "under_construction", "Service under construction / not yet operational", "🚧", "operational",
        (r"\bunder construction\b", r"\bunder renovation\b", r"\bnot yet operational\b",
         r"\byet to be (?:commissioned|operational|functional)\b", r"\bnon[- ]?functional\b",
         r"\bbeing (?:built|constructed|set up)\b"),
        is_caveat=True,
    ),
    IndicatorRule(
        "open_24_7", "Open 24/7", "🕒", "operational",
        (r"\b24\s*[x/]\s*7\b", r"\b24[- ]?hours?\b", r"\bround[- ]the[- ]clock\b",
         r"\bopen 24\b", r"\b24/7\b"),
    ),
    # --- Access & amenities ---
    IndicatorRule(
        "wheelchair_access", "Wheelchair / disabled access", "♿", "access",
        (r"\bwheel\s?chair\b", r"\bdifferently[- ]abled\b", r"\bdisabled[- ]friendly\b",
         r"\bdivyang\b", r"\bramp access\b", r"\bbarrier[- ]free\b", r"\bwheelchair[- ]accessible\b"),
    ),
    IndicatorRule(
        "ambulance", "Ambulance service", "🚑", "access",
        (r"\bambulance\b", r"\bair ambulance\b", r"\b108 service\b"),
    ),
    IndicatorRule(
        "blood_bank", "Blood bank", "🩸", "access",
        (r"\bblood bank\b", r"\bblood storage unit\b"),
    ),
    IndicatorRule(
        "pharmacy", "Pharmacy / medicines on site", "💊", "access",
        (r"\bpharmacy\b", r"\bjan aushadhi\b", r"\bin-?house pharmacy\b",
         r"\bmedicines? available\b", r"\bdispensary\b"),
    ),
    IndicatorRule(
        "cashless_insurance", "Cashless / insurance accepted", "💳", "access",
        (r"\bcashless\b", r"\bayushman\b", r"\bempanel", r"\bnetwork hospital\b",
         r"\binsurance (?:network|accepted|facility|scheme)\b", r"\bPMJAY\b"),
    ),
)


@dataclass
class Indicator:
    key: str
    label: str
    icon: str
    kind: str           # operational | access
    status: str         # available | unavailable | attention
    source_field: str
    source_quote: str   # exact text, for citation


def _negated_near(text: str, start: int, end: int) -> bool:
    before = text[max(0, start - 50): start]
    after = text[end: min(len(text), end + 60)]
    return bool(CONTRADICTION_BEFORE.search(before) or CONTRADICTION_AFTER.search(after))


def extract_facility_indicators(
    capabilities: list[str] | None,
    procedures: list[str] | None,
    equipment: list[str] | None,
    description: str | None,
) -> list[Indicator]:
    """Scan a facility's text for operational + access indicators.

    Returns one Indicator per detected key (deduped). For a normal access feature,
    a positive mention anywhere wins; if only negated mentions exist it's reported
    "unavailable". Caveat indicators (closed / under construction) are always
    surfaced as "attention" since their mere presence is the warning.
    """
    fields: list[tuple[str, str]] = []
    for fname, arr in (("capabilities", capabilities), ("procedures", procedures), ("equipment", equipment)):
        for el in arr or []:
            if el and str(el).strip():
                fields.append((fname, str(el)))
    if description and str(description).strip():
        fields.append(("description", str(description)))

    # key -> best Indicator found so far
    found: dict[str, Indicator] = {}

    for rule in INDICATOR_RULES:
        for fname, text in fields:
            for pat in rule.patterns:
                m = re.search(pat, text, re.IGNORECASE)
                if not m:
                    continue
                snippet = text.strip()[:200]
                if rule.is_caveat:
                    status = "attention"
                else:
                    status = "unavailable" if _negated_near(text, m.start(), m.end()) else "available"

                existing = found.get(rule.key)
                # Prefer: attention > available > unavailable (most actionable first),
                # but a genuine "available" should override an earlier "unavailable".
                rank = {"attention": 2, "available": 1, "unavailable": 0}
                if existing is None or rank[status] > rank[existing.status]:
                    found[rule.key] = Indicator(
                        key=rule.key, label=rule.label, icon=rule.icon, kind=rule.kind,
                        status=status, source_field=fname, source_quote=snippet,
                    )
                break  # one pattern hit per (rule, field) is enough

    # Order: operational caveats first (most urgent), then access features.
    order = {r.key: i for i, r in enumerate(INDICATOR_RULES)}
    return sorted(found.values(), key=lambda ind: order[ind.key])


# Filterable access/operations indicators for the sidebar (non-caveat), and the
# caveat keys used by the "hide closed / under construction" toggle.
FILTERABLE_INDICATORS: tuple[tuple[str, str], ...] = tuple(
    (r.key, f"{r.icon} {r.label}") for r in INDICATOR_RULES if not r.is_caveat
)
CAVEAT_KEYS: tuple[str, ...] = tuple(r.key for r in INDICATOR_RULES if r.is_caveat)


def indicator_status_map(
    capabilities: list[str] | None,
    procedures: list[str] | None,
    equipment: list[str] | None,
    description: str | None,
) -> dict[str, str]:
    """key -> status ('available' | 'unavailable' | 'attention') for fast filtering."""
    return {
        ind.key: ind.status
        for ind in extract_facility_indicators(capabilities, procedures, equipment, description)
    }


if __name__ == "__main__":
    demo = extract_facility_indicators(
        capabilities=[
            "24/7 emergency care", "Ambulance service available",
            "On-site Blood Bank", "Trauma centre under construction",
            "Help desk for senior citizens and the differently abled",
            "Cashless insurance facility available", "Ultrasound center not available",
        ],
        procedures=[], equipment=[],
        description="Jan Aushadhi medicines available. The MCH building is temporarily closed for renovation.",
    )
    for ind in demo:
        print(f"  {ind.icon} [{ind.status:11}] {ind.kind:11} {ind.label:42} <- {ind.source_field}: {ind.source_quote[:60]!r}")
