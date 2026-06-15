# Eval Scenarios — Hand-Labeled Ground Truth

20 scenarios across the 6 priority capabilities. Each scenario = one facility × one claim with a human-decided expected status.

Used to:
- Tune trust-score threshold for `verified` vs `unclear`
- Catch regressions in claim extraction prompt
- Provide demo talking points ("on our eval set, we correctly classified N/20")

## Format

| # | facility_id | claim_type | claim_value | expected_status | rationale |
|---|-------------|------------|-------------|-----------------|-----------|
| 1 | TBD         | capability | icu         | verified        | description: "10-bed ICU with ventilators" |
| 2 | TBD         | capability | nicu        | contradicted    | description: "no neonatal ICU; refers to..." |
| 3 | TBD         | capability | trauma      | unclear         | only mentioned in capability field, no detail |

(fill in 17 more once we see the actual data)

## Coverage targets
- 4 × verified (clear positive evidence)
- 4 × contradicted (explicit denial or referred-out language)
- 6 × unclear (vague single-word mentions, no detail)
- 3 × low-confidence-extraction (typos, mixed-language, ambiguous phrasing)
- 3 × edge cases (claim_value not in taxonomy, capacity claims with no number)
