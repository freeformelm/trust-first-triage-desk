# Team Split — 24h Sprint

**Team:** 2 — Data Engineer (Pratish, pshah@dlrgroup.com) + Data Scientist (teammate)

## Roles

### Data Engineer (Pratish)
- Workspace auth, catalog + schema setup
- Marketplace listing install
- Bronze → Silver → Gold Delta tables
- Spatial join (facility → district polygon)
- Lakebase provisioning + schema (verifications, shortlists, annotations, saved_searches)
- Streamlit app shell + Databricks Apps deployment
- Wire app ↔ Delta (SQL Connector) and app ↔ Lakebase (psycopg)
- Demo video recording + Git repo polish

### Data Scientist (teammate)
- Claim taxonomy (ICU, maternity, emergency, oncology, trauma, NICU, …)
- Claim extraction prompt (LLM via Foundation Model API)
- Evidence retrieval (snippet → claim linking + polarity: supports / contradicts / neutral)
- Confidence scoring function (extraction × evidence × source-field prior)
- Eval set: 20 hand-labeled facility/claim ground-truth scenarios
- MLflow logging of extraction runs
- Tune contradiction-detection threshold for demo

## Sync Points (every ~4h)
1. **Hour 0–1:** kickoff sync. Confirm catalog/schema names. Agree on table contract for `silver_claim` and `silver_evidence`.
2. **Hour 4:** DE has bronze + silver_facility loaded. DS has first claim extraction prompt working on 50 sample rows.
3. **Hour 8:** DE has Lakebase + Streamlit shell. DS has full 10k claim extraction run kicked off (batched + cached).
4. **Hour 12:** DE wires app to silver_claim. DS produces gold_facility_trust + first eval numbers.
5. **Hour 16:** Demo dry-run #1. Identify polish gaps.
6. **Hour 20:** Demo dry-run #2 + video record. Deploy final app.
7. **Hour 23:** Submit Devpost.

## Handoff Contract: silver_claim
Owned by DS, consumed by DE app. Schema:
- `facility_id` (string, FK to silver_facility)
- `claim_id` (string, hash)
- `claim_type` (enum: capability | procedure | equipment)
- `claim_value` (string, normalized to taxonomy)
- `claim_raw` (string, original text)
- `source_field` (enum: description | capability | procedure | equipment)
- `source_text_span` (string, ~200 char window)
- `extraction_confidence` (float 0-1)
- `llm_model` (string)
- `extracted_at` (timestamp)

## Handoff Contract: silver_evidence
- `evidence_id` (string)
- `claim_id` (string, FK)
- `snippet` (string, exact quote from facility description / fields)
- `source_field` (string)
- `polarity` (enum: supports | contradicts | neutral)
- `retrieval_score` (float 0-1)

## Handoff Contract: gold_facility_trust
- `facility_id`
- `capability` (normalized)
- `claim_count`
- `supporting_evidence_count`
- `contradicting_evidence_count`
- `trust_score` (float 0-1)
- `status` (enum: verified | contradicted | unclear)
- `last_computed_at`
