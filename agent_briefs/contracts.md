# Contracts — Single Source of Truth

If a column name or type changes, update this file in the SAME commit. Drift here breaks the team.

All Delta tables live in `hackathon.trust_desk.*`. Override with `UC_CATALOG` / `UC_SCHEMA` env vars.

## Source Tables (read-only — Databricks Marketplace listing `19326b3d-db63-4627-abc0-cf4e8131a305`)

### `databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities`
10,088 India healthcare facility rows, 51 cols (all `string` except `latitude`/`longitude` = `double`).
Schema confirmed 2026-06-15.

| Source column | Type | Purpose |
|---------------|------|---------|
| unique_id | string | PK |
| name | string | facility name |
| description | string | free-text overview, 100% coverage |
| organization_type | string | "facility" |
| facilityTypeId | string | "clinic", "hospital", etc. |
| operatorTypeId | string | "private", "public", etc. |
| specialties | string (JSON array) | coded specialty list (e.g. "emergencyMedicine", "neonatologyPerinatalMedicine") |
| procedure | string (JSON array) | free-text procedure claims |
| equipment | string (JSON array) | free-text equipment claims |
| capability | string (JSON array) | **richest claim source** — sentence-level capability claims |
| capacity | string | bed count, ~25% coverage |
| yearEstablished | string | ~48% coverage |
| numberDoctors | string | physician count |
| address_line1/2/3 | string | street |
| address_city | string | city |
| address_stateOrRegion | string | state — needs INITCAP + trim |
| address_zipOrPostcode | string | pincode (6-digit India) |
| address_country | string | "India" |
| latitude / longitude | double | ~98.83% present; **some outside India** — must bbox-filter |
| source_urls | string (JSON array) | **citation source** for any claim |
| recency_of_page_update | string | YYYY-MM-DD — trust-signal prior |
| distinct_social_media_presence_count | string | trust signal |
| affiliated_staff_presence | string ("true"/"false") | trust signal |
| custom_logo_presence | string ("true"/"false") | trust signal |
| number_of_facts_about_the_organization | string | trust signal |
| officialPhone, officialWebsite, email | string | contact |
| source_content_id, cluster_id | string | provenance |

**Bad-geocoding alert:** sample row `Sanjivani Multi Speciality Hospital` lists Kerala address but coordinates `(59.94, -38.26)` are in the North Atlantic. Apply India bounding box `lat 6-37, lng 68-98` in silver.

### `...india_post_pincode_directory`
165,627 post offices.

| Source column | Type | Notes |
|---------------|------|-------|
| circlename, regionname, divisionname | string | postal hierarchy |
| officename | string | post-office name |
| pincode | long | 6-digit; cast to string before joining facility.pincode |
| officetype | string | HO / PO / BO |
| delivery | string | yes/no |
| district | string | needs INITCAP |
| statename | string | needs INITCAP |
| latitude, longitude | **string** | "NA" or numeric — parse with TRY_CAST and NULLIF('NA') |

### `...nfhs_5_district_health_indicators`
706 districts × 109 indicators. Already snake_case ✓.

| Key columns | Type | Notes |
|-------------|------|-------|
| district_name | string | needs INITCAP normalization |
| state_ut | string | needs INITCAP normalization |
| households_surveyed, women_15_49_interviewed, men_15_54_interviewed | double | sample sizes |
| women_age_15_49_who_are_literate_pct | double | demo indicator (range 38.6%-99.7%) |
| hh_member_covered_health_insurance_pct | double | demo indicator (avg 40%) |
| institutional_birth_5y_pct | double | maternal-care indicator |
| births_delivered_by_csection_5y_pct | double | C-section rate |
| ...106 more | double or string | string-typed cols may contain `*` (suppressed) or `(29.5)` (low-sample) |

## Our Delta Tables (write side — `hackathon.trust_desk.*`)

### `bronze_facility`
Raw copy of source `facilities`. No transforms. Owner: DE.

### `silver_facility`
| Column | Type | Notes |
|--------|------|-------|
| facility_id | STRING | from unique_id |
| name | STRING | trimmed |
| organization_type | STRING | lowered |
| facility_type | STRING | lowered, from facilityTypeId |
| operator_type | STRING | lowered, from operatorTypeId |
| description | STRING | unchanged from source |
| specialties | ARRAY<STRING> | parsed JSON |
| procedures | ARRAY<STRING> | parsed JSON (renamed from `procedure`) |
| equipment | ARRAY<STRING> | parsed JSON |
| capabilities | ARRAY<STRING> | parsed JSON (renamed from `capability`) |
| source_urls | ARRAY<STRING> | parsed JSON — use for citations |
| capacity | INT | NULLable |
| year_established | INT | NULLable |
| number_doctors | INT | NULLable |
| **state** | STRING | **Canonical (resolved). Pincode lookup > known-state list > NULL.** Use this for joins/filters. |
| **state_raw** | STRING | **Original `address_stateOrRegion`** (sometimes a district name in source). Kept for audit. |
| **district** | STRING | **From pincode lookup** (canonical) |
| **district_raw** | STRING | Same as `district` for now (placeholder for future spatial-join result) |
| **state_source** | STRING | **enum: `pincode` \| `source` \| `unresolved`** — provenance of `state` resolution |
| city | STRING | INITCAP normalized |
| pincode | STRING | 6-digit |
| address_line1/2/3, address_country, address_country_code | STRING | – |
| latitude, longitude | DOUBLE | – |
| has_valid_coords | BOOLEAN | TRUE iff within India bounding box (lat 6-37, lng 68-98) |
| recency_of_page_update | STRING | yyyy-mm-dd |
| social_media_presence_count | INT | – |
| has_affiliated_staff | BOOLEAN | – |
| has_custom_logo | BOOLEAN | – |
| facts_count | INT | – |
| official_phone, email, official_website | STRING | – |
| source_content_id, cluster_id | STRING | provenance |

**Build order:** `silver_pincode` MUST be built before `silver_facility` (the latter joins on pincode). `run_all_silver` enforces this.

### `silver_claim`
Owner: DS. (Schema unchanged from initial contract — see prior version.)

| Column | Type | Notes |
|--------|------|-------|
| facility_id | STRING | FK |
| claim_id | STRING | hash(facility_id + claim_type + claim_value) |
| claim_type | STRING | enum: capability \| procedure \| equipment \| specialty |
| claim_value | STRING | normalized to CFG.capability_taxonomy or "other" |
| claim_raw | STRING | exact quote from source array element |
| source_field | STRING | enum: description \| capabilities \| procedures \| equipment \| specialties |
| source_text_span | STRING | ≤200 char window |
| extraction_confidence | DOUBLE | 0-1 |
| llm_model | STRING | endpoint name |
| extracted_at | TIMESTAMP | UTC |

### `silver_evidence`
Owner: DS.

| Column | Type | Notes |
|--------|------|-------|
| evidence_id | STRING | hash(claim_id + snippet[:64]) |
| claim_id | STRING | FK |
| snippet | STRING | exact quote |
| source_field | STRING | enum: description \| capabilities \| procedures \| equipment \| specialties |
| polarity | STRING | enum: supports \| contradicts \| neutral |
| retrieval_score | DOUBLE | 0-1 |

### `silver_pincode`
Owner: DE. Deduped to one row per pincode (HO > PO > BO priority, non-NA coords tiebreaker).

| Column | Type | Notes |
|--------|------|-------|
| pincode | STRING | PK |
| officename | STRING | – |
| officetype | STRING | HO/PO/BO |
| district | STRING | INITCAP |
| statename | STRING | INITCAP |
| latitude, longitude | DOUBLE | NULLable |

### `silver_district_health`
Owner: DE.

| Column | Type | Notes |
|--------|------|-------|
| district | STRING | INITCAP-normalized from district_name |
| state | STRING | INITCAP-normalized from state_ut |
| ...all source NFHS-5 columns | as-is | string-typed indicator cols still contain `*`/`(x)` — caller uses TRY_CAST |

### `gold_facility_trust`
Owner: DS.

| Column | Type | Notes |
|--------|------|-------|
| facility_id | STRING | FK |
| capability | STRING | normalized taxonomy |
| claim_count | INT | – |
| supporting_evidence_count | INT | polarity=supports |
| contradicting_evidence_count | INT | polarity=contradicts |
| trust_score | DOUBLE | 0-1, from src/evidence.py::trust_score |
| status | STRING | enum: verified \| contradicted \| unclear |
| last_computed_at | TIMESTAMP | UTC |

## Lakebase Postgres — see `src/lakebase.py::SCHEMA_SQL` for DDL
- `verifications` — planner sign-off (UPSERT on facility_id + claim_id + planner_id)
- `annotations` — planner notes per facility
- `shortlists` — saved facility groups
- `saved_searches` — query JSON
- `claim_embeddings` — pgvector

## Capability Taxonomy → Source Specialty Code (mapping helper)
Built from the row-2 sample. DS should refine.

| Trust-Desk capability | Specialty codes that imply it | Capability/description cues |
|----------------------|-------------------------------|------------------------------|
| icu | criticalCareMedicine | "ICU", "intensive care", "central oxygen" |
| nicu | neonatologyPerinatalMedicine | "NICU", "neonatal ICU", "Level III" |
| maternity | gynecologyAndObstetrics | "obstetrics", "delivery", "labor room", "birthing" |
| emergency | emergencyMedicine | "Emergency Department", "24/7 emergency", "casualty" |
| oncology | medicalOncology, hematologyOncology, radiationOncology, surgicalOncology | "chemotherapy", "radiation therapy", "cancer" |
| trauma | traumaSurgery, orthopedicTrauma | "trauma surgery", "polytrauma", "trauma center" |
| surgery | generalSurgery | "OT", "operating room", "modular operation theater" |

## API: `src/evidence.py::trust_score`
Pure function. Don't change signature without updating gold table rebuild + app caller.
```python
trust_score(claim_count: int, supports: int, contradicts: int, extraction_conf: float) -> float
```

## API: `src/evidence.py::status_label`
```python
status_label(trust: float, supports: int, contradicts: int) -> Literal["verified", "contradicted", "unclear"]
```
