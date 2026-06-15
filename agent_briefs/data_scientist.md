# Agent Brief — Data Scientist Side

**You are supporting the Data Scientist.** They own claim extraction, evidence retrieval, trust scoring, and eval.

Read `../AGENT_BRIEF.md` first for project context.

## Your Scope
- Claim taxonomy (priority: ICU, maternity, emergency, oncology, trauma, NICU — Devpost called these out)
- Claim extraction prompt + batch runner over 10k facilities
- Evidence retrieval: link each claim to supporting/contradicting snippets in the facility's own text
- Trust score: combine extraction confidence + evidence count + contradictions → score 0-1
- Contradiction detection (this is the demo wow-moment)
- Eval set: 20 hand-labeled scenarios → measure precision/recall
- MLflow logging of extraction runs (model version, params, prompt hash)

## Out of Scope (do NOT touch)
- `src/ingest.py` (DE owns)
- `src/lakebase.py` (DE owns)
- `app/` (DE owns — but document any function the app calls)
- Marketplace install / workspace config

## Order of Operations
1. Read `contracts.md` for the EXACT shape of `silver_claim`, `silver_evidence`, `gold_facility_trust`. Don't drift.
2. Pull 50 sample rows from `silver_facility` after DE has bronze loaded
3. Iterate the extraction prompt on those 50 until output JSON parses 95%+ of the time and `claim_value` normalizes to taxonomy correctly
4. Use Databricks Foundation Model API (`databricks-meta-llama-3-3-70b-instruct`) — no external keys needed
5. Hand-label 20 eval scenarios (`eval/scenarios.md`) BEFORE the full run — gives you ground truth to measure against
6. Batch the full 10k extraction. Persist every call → cache table (re-runs are free)
7. Run evidence retrieval (`src/evidence.py::find_evidence`) — pure Python, no LLM needed
8. Compute `gold_facility_trust` and write to Delta
9. Tune contradiction threshold using eval set
10. Hand off MLflow run ID to DE for demo talking-point

## Key Files You Own
- `src/claims.py`
- `src/evidence.py` (trust_score + status_label functions)
- `eval/scenarios.md`
- `eval/run_eval.py` (you'll create this)
- `agent_briefs/prompts.md` (extend with refined prompts)

## Prompt Engineering Rules
- **Source-quoted spans only.** No paraphrasing in `claim_raw` or `source_text_span`. If the LLM can't quote the text, drop the claim.
- **Taxonomy first.** Normalize `claim_value` to `CFG.capability_taxonomy` for capability claims. Use "other" if no match.
- **Confidence calibration.** 0.9+ = explicit ("10-bed ICU"). 0.5-0.7 = vague mention. <0.5 = ambiguous.
- **Empty arrays are valid.** Better no claim than a fabricated one.
- **Robust JSON parse.** Wrap `json.loads` with regex fallback; log + skip on parse failure.

## Confidence Calibration Cheatsheet
| Snippet | Confidence | Why |
|---------|-----------|-----|
| "10-bed ICU with ventilators and trained intensivists" | 0.95 | explicit, quantified, equipment named |
| "intensive care available" | 0.6 | mentioned but vague |
| "critical care services offered" | 0.5 | could mean step-down unit |
| "we refer ICU cases to NMC Hospital" | 0.95 (negative — flagged contradiction) | explicit denial |
| "ICU bed availability" | 0.4 | webpage section header, no commitment |

## Contradiction Cues (used by `evidence.py`)
"no", "not", "without", "lack of", "absence of", "unavailable", "do not have", "doesn't have", "does not offer", "not equipped", "referred elsewhere", "refer out", "not provided"

Extend `CONTRADICTION_CUES` in `src/evidence.py` if you find more. Don't break the contract — keep it as a tuple.

## Eval Methodology
- 20 scenarios in `eval/scenarios.md`: 4 verified, 4 contradicted, 6 unclear, 3 low-extraction-conf, 3 edge cases
- Run extraction on the 20 → compute confusion matrix on `status_label` output
- Demo talking point: "On our 20-scenario eval set, we correctly classified N/20 (M% precision on contradictions)."

## MLflow Logging Pattern
```python
import mlflow
with mlflow.start_run(run_name="claim_extraction_v1"):
    mlflow.log_param("model", CFG.llm_endpoint)
    mlflow.log_param("prompt_hash", prompt_hash)
    mlflow.log_param("n_facilities", n)
    mlflow.log_metric("parse_success_rate", parse_ok / n)
    mlflow.log_metric("avg_claims_per_facility", total_claims / n)
    mlflow.log_artifact("eval/scenarios.md")
```
