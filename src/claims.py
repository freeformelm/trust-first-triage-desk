"""Claim extraction from facility free-text fields.

Owner: Data Scientist.
Strategy: one LLM call per facility, prompted to emit structured claims as JSON,
with source_text_span quoted from the facility's own fields.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.config import CFG

EXTRACTION_PROMPT = """You extract verifiable healthcare-facility CLAIMS from messy free text.

Capability taxonomy (normalize to one of these or to "other"):
{taxonomy}

For each claim, output JSON:
{{
  "claim_type": "capability" | "procedure" | "equipment",
  "claim_value": "<normalized to taxonomy if capability, else lowercased phrase>",
  "claim_raw": "<exact phrase from input>",
  "source_field": "description" | "capability" | "procedure" | "equipment",
  "source_text_span": "<<=200 char window containing claim_raw>",
  "extraction_confidence": <0-1 float based on how explicit the claim is>
}}

Rules:
- ONLY claims supported by the input text. No inference, no medical knowledge.
- If a field is empty or vague, emit no claim for it.
- Confidence 0.9+ for direct statements ("has 10-bed ICU"), 0.5-0.7 for vague mentions ("intensive care available"), <0.5 for ambiguous ("critical care services").
- Return a JSON array. Empty array if no verifiable claims.

Facility input:
- name: {name}
- description: {description}
- capability: {capability}
- procedure: {procedure}
- equipment: {equipment}
"""


@dataclass
class FacilityInput:
    facility_id: str
    name: str
    description: str
    capability: str
    procedure: str
    equipment: str


@dataclass
class ExtractedClaim:
    facility_id: str
    claim_type: str
    claim_value: str
    claim_raw: str
    source_field: str
    source_text_span: str
    extraction_confidence: float


def build_prompt(f: FacilityInput) -> str:
    return EXTRACTION_PROMPT.format(
        taxonomy=", ".join(CFG.capability_taxonomy),
        name=f.name or "",
        description=(f.description or "")[:4000],
        capability=f.capability or "",
        procedure=f.procedure or "",
        equipment=f.equipment or "",
    )


def extract_claims(f: FacilityInput, llm_client) -> list[ExtractedClaim]:
    """Single-facility extraction. Wrap in batch + cache caller for 10k run."""
    # TODO: call llm_client.chat.completions.create(...) with EXTRACTION_PROMPT
    # TODO: parse JSON robustly (json.loads with fallback)
    raise NotImplementedError
