# Prompts — Trust-First Triage Desk

Living document. DS agent: extend the prompt + few-shots; DE agent: leave alone except to add context fields if the app needs them.

## Master Extraction Prompt (v1)

Source: `src/claims.py::EXTRACTION_PROMPT`. Keep in sync.

```
You extract verifiable healthcare-facility CLAIMS from messy free text.

Capability taxonomy (normalize to one of these or to "other"):
icu, maternity, emergency, oncology, trauma, nicu, surgery, cardiology, dialysis, radiology, pediatrics, ophthalmology

For each claim, output JSON:
{
  "claim_type": "capability" | "procedure" | "equipment",
  "claim_value": "<normalized to taxonomy if capability, else lowercased phrase>",
  "claim_raw": "<exact phrase from input>",
  "source_field": "description" | "capability" | "procedure" | "equipment",
  "source_text_span": "<<=200 char window containing claim_raw>",
  "extraction_confidence": <0-1 float based on how explicit the claim is>
}

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
```

## Few-Shot Examples

### Example 1 — Clear capability + equipment
**Input:**
- name: Apollo Hospitals Chennai
- description: "200-bed multi-specialty hospital with 24/7 emergency, 30-bed ICU with ventilators, neonatal ICU, and full oncology services including chemotherapy and radiation."
- capability: "Emergency, ICU, NICU, Oncology"
- procedure: "Chemotherapy, Radiation therapy"
- equipment: "Ventilators, CT, MRI"

**Expected output:**
```json
[
  {"claim_type":"capability","claim_value":"emergency","claim_raw":"24/7 emergency","source_field":"description","source_text_span":"multi-specialty hospital with 24/7 emergency, 30-bed ICU","extraction_confidence":0.95},
  {"claim_type":"capability","claim_value":"icu","claim_raw":"30-bed ICU with ventilators","source_field":"description","source_text_span":"24/7 emergency, 30-bed ICU with ventilators, neonatal ICU","extraction_confidence":0.98},
  {"claim_type":"capability","claim_value":"nicu","claim_raw":"neonatal ICU","source_field":"description","source_text_span":"ICU with ventilators, neonatal ICU, and full oncology","extraction_confidence":0.95},
  {"claim_type":"capability","claim_value":"oncology","claim_raw":"full oncology services","source_field":"description","source_text_span":"neonatal ICU, and full oncology services including chemotherapy","extraction_confidence":0.95},
  {"claim_type":"procedure","claim_value":"chemotherapy","claim_raw":"chemotherapy","source_field":"description","source_text_span":"full oncology services including chemotherapy and radiation","extraction_confidence":0.9},
  {"claim_type":"equipment","claim_value":"ventilators","claim_raw":"ventilators","source_field":"description","source_text_span":"30-bed ICU with ventilators, neonatal ICU","extraction_confidence":0.9}
]
```

### Example 2 — Contradiction / referral-out
**Input:**
- description: "Primary health centre offering OPD and basic deliveries. ICU cases are referred to district hospital. No NICU."

**Expected output:** Extract the ICU and NICU claims but with LOW confidence and EXPLICIT contradiction wording in source_text_span. The `find_evidence` step will then flag polarity=contradicts.

```json
[
  {"claim_type":"capability","claim_value":"icu","claim_raw":"ICU cases are referred to district hospital","source_field":"description","source_text_span":"basic deliveries. ICU cases are referred to district hospital. No NICU.","extraction_confidence":0.85},
  {"claim_type":"capability","claim_value":"nicu","claim_raw":"No NICU","source_field":"description","source_text_span":"referred to district hospital. No NICU.","extraction_confidence":0.9}
]
```

Note: extraction_confidence stays HIGH because the text is explicit — it's `evidence.py::find_evidence` that classifies polarity as `contradicts` via the cue word "No".

### Example 3 — Capability field with no description support
**Input:**
- description: ""
- capability: "Trauma, Emergency"

**Expected output:**
```json
[
  {"claim_type":"capability","claim_value":"trauma","claim_raw":"Trauma","source_field":"capability","source_text_span":"Trauma, Emergency","extraction_confidence":0.5},
  {"claim_type":"capability","claim_value":"emergency","claim_raw":"Emergency","source_field":"capability","source_text_span":"Trauma, Emergency","extraction_confidence":0.5}
]
```

Confidence is 0.5: the capability field is a structured list but unverified. The downstream `find_evidence` step will look in the description for support — if none found, status becomes `unclear`.

### Example 4 — Empty / vague
**Input:**
- description: "Healthcare facility in Mumbai."
- capability: ""

**Expected output:** `[]`

## Evidence Retrieval Strategy
`src/evidence.py::find_evidence` is pure Python. It:
1. Builds case-insensitive needles from `claim_value` and `claim_raw`
2. Slides a ±80 char window over every facility field
3. Checks for `CONTRADICTION_CUES` in the 40 chars BEFORE the match → polarity = contradicts
4. Otherwise polarity = supports
5. Returns all hits with retrieval_score

No LLM call needed at this stage. Free Edition-friendly.

## Cache + Batch Pattern
- Hash inputs by `facility_id + prompt_version`
- Write each LLM response to a `claim_extraction_cache` Delta table BEFORE parsing
- On re-run, skip facilities already in cache for the current prompt_version
- Bump prompt_version when changing the master prompt

## Prompt Versioning
Increment when:
- Adding/removing fields from the JSON schema
- Changing capability taxonomy
- Adjusting confidence calibration rules

Current version: **v1**.
