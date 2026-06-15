# Contracts — Single Source of Truth

If a column name or type changes, update this file in the SAME commit. Drift here breaks the team.

All Delta tables live in `hackathon.trust_desk.*`. Override with `UC_CATALOG` / `UC_SCHEMA` env vars.

## Delta — `bronze_facility`
Raw FDR India rows, 51 columns, untouched. Owner: DE.

## Delta — `silver_facility`
Cleaned facility table. Owner: DE.

| Column | Type | Notes |
|--------|------|-------|
| facility_id | STRING | Stable PK from FDR; if absent, hash(name + lat + lng) |
| name | STRING | Trimmed |
| description | STRING | Free-text, 100% coverage |
| capability_raw | STRING | Original capability field, 99.7% coverage |
| procedure_raw | STRING | Original procedure field, 92.5% coverage |
| equipment_raw | STRING | Original equipment field, 77% coverage |
| year_established | INT | NULLable, 48% coverage |
| capacity | INT | NULLable, 25% coverage |
| state | STRING | Normalized title case |
| district | STRING | Normalized; fallback to PIN lookup if empty |
| pincode | STRING | 6-digit, NULLable |
| latitude | DOUBLE | NULLable |
| longitude | DOUBLE | NULLable |
| has_coords | BOOLEAN | Convenience flag |
| source_url | STRING | If FDR provides |

## Delta — `silver_claim`
Exploded claims, one row per (facility × extracted claim). Owner: DS.

| Column | Type | Notes |
|--------|------|-------|
| facility_id | STRING | FK to silver_facility |
| claim_id | STRING | Hash of facility_id + claim_type + claim_value |
| claim_type | STRING | enum: capability \| procedure \| equipment |
| claim_value | STRING | Normalized; capability claims normalized to CFG.capability_taxonomy or "other" |
| claim_raw | STRING | Exact phrase quoted from input text |
| source_field | STRING | enum: description \| capability \| procedure \| equipment |
| source_text_span | STRING | ≤200 char window containing claim_raw |
| extraction_confidence | DOUBLE | 0-1 |
| llm_model | STRING | Endpoint name |
| extracted_at | TIMESTAMP | UTC |

## Delta — `silver_evidence`
One row per supporting/contradicting snippet for a claim. Owner: DS.

| Column | Type | Notes |
|--------|------|-------|
| evidence_id | STRING | Hash of claim_id + snippet[:64] |
| claim_id | STRING | FK to silver_claim |
| snippet | STRING | Exact quote from facility text |
| source_field | STRING | description \| capability \| procedure \| equipment |
| polarity | STRING | enum: supports \| contradicts \| neutral |
| retrieval_score | DOUBLE | 0-1 |

## Delta — `silver_pincode`
India Post directory, deduped to one row per pincode. Owner: DE.

| Column | Type | Notes |
|--------|------|-------|
| pincode | STRING | PK |
| officename | STRING | Best-priority post office for this pincode |
| officetype | STRING | BO \| PO \| HO |
| district | STRING | Title case |
| statename | STRING | Title case |
| latitude | DOUBLE | NULLable |
| longitude | DOUBLE | NULLable |

Dedupe rule: prefer Head Office > Post Office > Branch Office; tiebreaker = first with non-NA coords.

## Delta — `silver_district_health`
NFHS-5 district indicators, snake_case, NULL-cleaned. Owner: DE.

| Column | Type | Notes |
|--------|------|-------|
| state | STRING | Title case, normalized to match silver_facility.state |
| district | STRING | Title case, normalized |
| <indicator>_value | DOUBLE | Cleaned: `*` → NULL, `(29.5)` → 29.5 |
| <indicator>_low_sample | BOOLEAN | TRUE if value was parenthesized |

(109 indicators total; keep names readable but snake_case.)

## Delta — `gold_facility_trust`
Facility × capability rollup driving the Triage view. Owner: DS.

| Column | Type | Notes |
|--------|------|-------|
| facility_id | STRING | FK |
| capability | STRING | Normalized taxonomy |
| claim_count | INT | how many `silver_claim` rows match |
| supporting_evidence_count | INT | polarity=supports |
| contradicting_evidence_count | INT | polarity=contradicts |
| trust_score | DOUBLE | 0-1 from `src/evidence.py::trust_score` |
| status | STRING | enum: verified \| contradicted \| unclear |
| last_computed_at | TIMESTAMP | UTC |

## Lakebase Postgres — `verifications`
Planner sign-off. Schema in `src/lakebase.py::SCHEMA_SQL`. Owner: DE.

| Column | Type | Notes |
|--------|------|-------|
| id | BIGSERIAL | PK |
| facility_id | TEXT | |
| claim_id | TEXT | |
| planner_id | TEXT | |
| status | TEXT | enum: verified \| rejected \| needs_info |
| reason | TEXT | NULLable |
| notes | TEXT | NULLable |
| created_at | TIMESTAMPTZ | NOW() |

Unique constraint: (facility_id, claim_id, planner_id). UPSERT on conflict.

## Lakebase — `annotations`, `shortlists`, `saved_searches`, `claim_embeddings`
See `src/lakebase.py::SCHEMA_SQL` for exact DDL.

## API: `src/evidence.py::trust_score`
Pure function. Don't change signature without updating gold table rebuild + app caller.
```python
trust_score(claim_count: int, supports: int, contradicts: int, extraction_conf: float) -> float
```

## API: `src/evidence.py::status_label`
```python
status_label(trust: float, supports: int, contradicts: int) -> Literal["verified", "contradicted", "unclear"]
```
