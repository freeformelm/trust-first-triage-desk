# Data Quirks Log

Track gotchas as you encounter them. Future you (and the data scientist) will thank present you.

## FDR India Facility Dataset (10k rows, 51 cols)

### Field coverage (from Devpost kickoff)
| Field            | Coverage | Treat as            |
|------------------|----------|---------------------|
| description      | 100%     | source text         |
| capability       | 99.7%    | claim (verify)      |
| procedure        | 92.5%    | claim (verify)      |
| equipment        | 77.0%    | claim (verify)      |
| year_established | 48.0%    | sparse fact         |
| capacity         | 25.0%    | very sparse claim   |

### Known issues
- `capability`, `procedure`, `equipment` are FREE TEXT lists, often comma- or pipe-separated, sometimes prose
- District / state names vary across facility rows, NFHS-5, and PIN directory — normalize before joining
- Lat/lng presence not guaranteed; some rows geocoded, others not
- Entity resolution already done upstream by FDR → assume one row per facility, but spot-check duplicates

## India Post PIN Code Directory (165,627 rows, 11 cols)
- **Grain = post office, NOT pincode.** Joining on `pincode` fans out rows. Dedupe or aggregate before joining facilities.
- ~12,600 rows have `NA` lat/lng — not every post office is geocoded.
- Office types: Branch (~140k), Post (~25k), Head (~800)

## NFHS-5 District Health Indicators (706 rows, 109 cols)
- Long human-readable column names — rename to snake_case on load.
- `*` = suppressed/unavailable → treat as NULL, not 0.
- `(29.5)` parenthesized values = estimate from 25–49 unweighted cases → flag as low-confidence.
- District/state name spelling drifts vs other sources → prefer spatial join over string match.
- Field period 2019–2021 (NFHS-5). Do NOT mix with NFHS-6 without verifying indicator definitions.

## Claim Extraction Notes
(fill in as we build)

## Evidence Linking Notes
(fill in as we build)

## App / Lakebase Notes
(fill in as we build)
