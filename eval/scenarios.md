# Eval Scenarios — Hand-Labeled Ground Truth

20 `(facility × capability)` scenarios drawn from **real Marketplace source rows** (captured in
`fixtures.json`), each given a human ground-truth `expected_status` after reading the facility's
own text. `run_eval.py` runs the **live rules pipeline** (`src/classifier.py` + `src/evidence.py`)
over them and scores predictions against these labels.

Reproduce: `python -m eval.run_eval` (from repo root — deterministic, offline, no DB/LLM needed).

## What "prediction" vs "hand-label" means
- **Hand-label (ground truth):** what a human says the status *should* be — the answer key.
- **Prediction:** what the pipeline actually outputs (`classify_facility` → `find_evidence_for_capability` → `trust_score` → `status_label`).
- The eval asks, for each scenario, *did prediction == hand-label?* → confusion matrix + contradiction precision/recall.

## Latest results (2026-06-16, rules-only pipeline)
- **Accuracy: 17/20 = 85%**
- **Contradiction detection: precision 100%, recall 100%** ← the safety-critical metric (never tell a planner a denied/under-construction service exists, never miss one).

| Expected ↓ \ Predicted → | verified | unclear | contradicted |
|---|---|---|---|
| **verified** | 4 | 2 | 0 |
| **unclear** | 1 | 9 | 0 |
| **contradicted** | 0 | 0 | 4 |

Note the error direction: the 2 verified→unclear misses are *conservative* (under-claiming, the safe direction); zero claims leak into `contradicted` wrongly, and zero contradictions are missed.

## The 20 scenarios

| # | Stratum | Facility | Capability | Expected | Source basis |
|---|---------|----------|-----------|----------|--------------|
| 1 | verified | Aravind Eye Hospital | icu | verified | "22-bed Level II ICU with 11 ventilator beds" |
| 2 | verified | Aravind Eye Hospital | dialysis | verified | "Dialysis unit of 20 beds under PM National Dialysis Programme" |
| 3 | verified | SCB Medical College, Cuttack | oncology | verified | Regional Cancer Centre; "surgical oncology and chemotherapy services" |
| 4 | verified | Krishna Inst. of Medical Sciences | nicu | verified | "NICU and PICU with Neonatal ECMO" |
| 5 | contradicted | Ankur Hospital | nicu | contradicted | "NICU facility not available" |
| 6 | contradicted | Ankur Hospital | radiology | contradicted | "Ultrasound (sonography) center not available" |
| 7 | contradicted | SCB Medical College, Cuttack | trauma | contradicted | "multi-specialty trauma center is under construction" |
| 8 | contradicted | Rajindra Hospital, Patiala | trauma | contradicted | "300-bed trauma care hospital under construction" |
| 9 | unclear | Fortis Hospital, Gurugram | icu | unclear | specialty code `criticalCareMedicine` only, no prose |
| 10 | unclear | Fortis Hospital, Gurugram | emergency | unclear | specialty code `emergencyMedicine` only |
| 11 | unclear | Aravind Eye Hospital | maternity | unclear | OB/GYN code on an eye hospital, no maternity described |
| 12 | unclear | Fortis Hospital Anandapur | maternity | unclear | OB/GYN code only |
| 13 | unclear | RAM Hospital, Kanpur | maternity | unclear | OB/GYN code only |
| 14 | unclear | Rajindra Hospital, Patiala | oncology | unclear | "Specialised in cancer" but thin; "Morphine is not available" |
| 15 | low-extraction-conf | RAM Hospital, Kanpur | nicu | unclear | single equipment-field mention (conf 0.75) |
| 16 | low-extraction-conf | Fatima Hospital | dialysis | unclear | single procedure-field mention (conf 0.75) |
| 17 | low-extraction-conf | Krishna Inst. of Medical Sciences | emergency | **verified** | real ("Emergency & Critical Care services") but terse → pipeline under-calls |
| 18 | edge-case | Ankur Hospital | icu | **unclear** | evidence is PEDIATRIC ICU, not general ICU |
| 19 | edge-case | Vedanta Hospital | trauma | **verified** | "unit of Kanpur Trauma and Ortho Centre" — but only in description prose |
| 20 | edge-case | Vedanta Hospital | oncology | unclear | precision check: nearby "Morphine not available" must NOT contradict oncology |

## What the eval revealed (3 documented gaps → next DS work)
1. **#17 verified-recall is conservative.** A genuinely-offered capability with only one terse mention scores `unclear` (needs ≥2 supports + trust ≥0.75 for `verified`). Safe but under-credits real services. → candidate for threshold tuning or counting *distinct corroborating fields* rather than raw mention count.
2. **#18 PICU inflates ICU.** "pediatric intensive care unit" matches the `icu` `intensive care` cue. → consider separating PICU, or down-weighting ICU when the only evidence is pediatric.
3. **#19 description-only evidence under-weighted.** A core capability stated in the prose description (not the arrays) yields too few supports to verify. → consider weighting description matches or a small boost when description corroborates.

## Coverage targets (met)
4 verified · 4 contradicted · 6 unclear · 3 low-extraction-confidence · 3 edge cases = 20.
