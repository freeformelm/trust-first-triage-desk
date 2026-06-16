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
import json
import re
from dataclasses import dataclass

from src.config import CFG

# Ceiling for LLM-assigned confidence — Tier 2 is a fallback, never as trusted as
# an explicit rules match on quoted text.
LLM_CONF_CAP = 0.75


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
    # --- Extended taxonomy (DS, beyond the 6 Devpost priorities) -----------
    CapabilityRule(
        capability="surgery",
        text_patterns=(
            r"\boperation theat",         # operation theatre/theater
            r"\boperating room\b",
            r"\bmodular ot\b",
            r"\bsurgical suite\b",
            r"\blaparoscop",
            r"\bgeneral surgery\b",
        ),
        specialty_codes=("generalSurgery",),
    ),
    CapabilityRule(
        capability="cardiology",
        text_patterns=(
            r"\bcardiology\b",
            r"\bcardiac\b",
            r"\bcath(?:eterization|eterisation)? lab\b",
            r"\becho ?cardiograph",
            r"\bangiograph",
            r"\bangioplast",
        ),
        specialty_codes=("cardiology", "interventionalCardiology"),
    ),
    CapabilityRule(
        capability="dialysis",
        text_patterns=(
            r"\bdialysis\b",
            r"\bh[ae]modialysis\b",
            r"\brenal replacement\b",
        ),
        specialty_codes=(),  # nephrology code does not, by itself, imply dialysis service
    ),
    CapabilityRule(
        capability="radiology",
        text_patterns=(
            r"\bradiology\b",
            r"\bMRI\b",
            r"\bCT scan\b",
            r"\bx-?ray\b",
            r"\bultrasound\b",
            r"\bsonograph",
            r"\bPET scan\b",
            r"\bdiagnostic imaging\b",
        ),
        specialty_codes=("radiology", "diagnosticRadiology"),
    ),
    CapabilityRule(
        capability="pediatrics",
        text_patterns=(
            r"\bp[ae]diatric",
            r"\bchild health\b",
        ),
        specialty_codes=("pediatrics", "paediatrics"),
    ),
    CapabilityRule(
        capability="ophthalmology",
        text_patterns=(
            r"\bophthalmolog",
            r"\beye care\b",
            r"\bcataract\b",
            r"\bophthalmic\b",
        ),
        specialty_codes=("ophthalmology",),
    ),
)


# Negations / pre-modifiers that appear BEFORE the capability term.
CONTRADICTION_BEFORE = re.compile(
    r"\b(?:no|not|without|lack of|absence of|unavailable|do(?:es)? not have|doesn'?t have|"
    r"does not offer|not equipped|not provided|in-?house\s+(?:no|none)|"
    r"proposed|upcoming|non[- ]?functional)\b",  # claimed-but-not-yet-operational
    re.IGNORECASE,
)

# Referral / not-yet-operational language that appears AFTER the capability term.
# The "under construction / not yet operational" group catches facilities that LIST a
# capability they are still building — a dangerous false-positive for a planner.
CONTRADICTION_AFTER = re.compile(
    r"\b(?:cases? (?:are )?referred to|patients? (?:are )?referred to|refer(?:s|red)? out|"
    r"transferred to|managed elsewhere|treated elsewhere|sent to|not available|"
    r"not (?:offered|provided|in[- ]?house)|elsewhere|"
    r"under construction|under renovation|not (?:yet )?operational|"
    r"yet to be|non[- ]?functional|temporarily closed|being (?:built|constructed|set up))\b",
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
    # "neonatal ICU" fires both nicu (\bneonatal ICU\b) and icu (\bICU\b). NICU is a
    # distinct capability — drop the spurious plain-ICU claim from the same element.
    caps = {rule.capability for rule, _ in hits}
    if "nicu" in caps:
        hits = [(rule, m) for rule, m in hits if rule.capability != "icu"]
    return hits


def _rule_for_specialty_code(code: str) -> CapabilityRule | None:
    for rule in CAPABILITY_RULES:
        if code in rule.specialty_codes:
            return rule
    return None


# ---------------------------------------------------------------------------
# Tier 3 — LLM fallback for free-text elements the rules can't classify
# ---------------------------------------------------------------------------
CLASSIFY_PROMPT = """You classify ONE healthcare-facility claim into a fixed taxonomy.

Taxonomy (pick exactly one, or "other" if none fit):
{taxonomy}

Rules:
- Decide ONLY from the text given. No medical inference, no outside knowledge.
- "other" is correct and expected when the text names a service outside the taxonomy.
- confidence: 0.9+ explicit & quantified, 0.6-0.8 clearly named, <0.6 vague.

Return ONLY a JSON object, no prose:
{{"claim_value": "<taxonomy term or other>", "confidence": <0-1 float>}}

Claim text ({source_field}): {text}
"""

_JSON_OBJ_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def parse_classify_response(raw: str) -> tuple[str, float] | None:
    """Robust parse: json.loads, then regex-extract first object as fallback.

    Returns (taxonomy_term, confidence) or None. "other" is returned as-is so the
    caller can decide to drop it.
    """
    if not raw:
        return None
    for candidate in (raw, *_JSON_OBJ_RE.findall(raw)):
        try:
            obj = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        val = str(obj.get("claim_value", "")).strip().lower()
        if not val:
            continue
        if val not in CFG.capability_taxonomy and val != "other":
            val = "other"
        try:
            conf = float(obj.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        return val, max(0.0, min(LLM_CONF_CAP, conf))
    return None


def classify_element_by_llm(text: str, source_field: str, llm_client) -> tuple[str, float] | None:
    """Classify one leftover free-text element. Returns (taxonomy_term, conf) or None.

    Never raises — the batch runner must not crash on a single bad call.
    """
    prompt = CLASSIFY_PROMPT.format(
        taxonomy=", ".join(CFG.capability_taxonomy),
        source_field=source_field,
        text=(text or "")[:500],
    )
    try:
        resp = llm_client.chat.completions.create(
            model=CFG.llm_endpoint,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=60,
        )
        raw = resp.choices[0].message.content
    except Exception:  # noqa: BLE001 — log+skip at the batch level
        return None
    return parse_classify_response(raw)


def _llm_claim(
    facility_id: str, elem: str, source_field: str, claim_type: str, llm_client
) -> "ClassifiedClaim | None":
    """Run the LLM fallback on one element; build a claim unless it maps to 'other'."""
    result = classify_element_by_llm(elem, source_field, llm_client)
    if not result:
        return None
    claim_value, conf = result
    if claim_value == "other":  # outside the taxonomy → don't pollute silver_claim
        return None
    return ClassifiedClaim(
        facility_id=facility_id,
        claim_id=_claim_id(facility_id, claim_type, claim_value, elem),
        claim_type=claim_type,
        claim_value=claim_value,
        claim_raw=elem[:200],
        source_field=source_field,
        source_text_span=elem[:200],
        extraction_confidence=conf,
        extraction_method="llm",
    )


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
    extraction_method: str = "rules"  # rules | llm — provenance for trust_compute.llm_model


def classify_facility(
    facility_id: str,
    capabilities: list[str] | None,
    procedures: list[str] | None,
    equipment: list[str] | None,
    specialties: list[str] | None,
    llm_client=None,
) -> list[ClassifiedClaim]:
    """Return one ClassifiedClaim per (taxonomy capability, source element) match.

    Confidence tiers:
      - 0.85 — explicit text match in `capabilities` (rich, sentence-level)
      - 0.80 — coded specialty match in `specialties`
      - 0.75 — text match in `procedures` or `equipment`
      - <=0.75 — LLM fallback on free-text elements the rules can't classify (only
                 when `llm_client` is supplied; "other" results are dropped)
    """
    out: list[ClassifiedClaim] = []

    # 1) capability text matches (richest)
    for elem in (capabilities or []):
        if not elem:
            continue
        hits = _rule_for_text(elem)
        for rule, m in hits:
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
        if not hits and llm_client is not None:
            llm = _llm_claim(facility_id, elem, "capabilities", "capability", llm_client)
            if llm:
                out.append(llm)

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
    _claim_type_for = {"procedures": "procedure", "equipment": "equipment"}
    for source_field, arr in (("procedures", procedures), ("equipment", equipment)):
        claim_type = _claim_type_for[source_field]
        for elem in (arr or []):
            if not elem:
                continue
            hits = _rule_for_text(elem)
            for rule, m in hits:
                out.append(
                    ClassifiedClaim(
                        facility_id=facility_id,
                        claim_id=_claim_id(facility_id, claim_type, rule.capability, elem),
                        claim_type=claim_type,
                        claim_value=rule.capability,
                        claim_raw=elem[:200],
                        source_field=source_field,
                        source_text_span=_span(elem, m.start(), m.end()),
                        extraction_confidence=0.75,
                    )
                )
            if not hits and llm_client is not None:
                llm = _llm_claim(facility_id, elem, source_field, claim_type, llm_client)
                if llm:
                    out.append(llm)

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
                    before = haystack[max(0, m.start() - 50) : m.start()]
                    after = haystack[m.end() : min(len(haystack), m.end() + 80)]
                    if CONTRADICTION_BEFORE.search(before) or CONTRADICTION_AFTER.search(after):
                        polarity = "contradicts"
                    else:
                        polarity = "supports"
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
