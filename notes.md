# Data Quirks Log

Track gotchas as you encounter them. Future you (and the data scientist) will thank present you.

## FDR India Facility Dataset (`facilities`)

**Actual row count (EDA):** 10,088 (Devpost said ~10k)
**Coordinate quality:** 99% valid → spatial join is the strong path
**Missing data:** <1% across key fields
**Top states by facility count:** Maharashtra 1,575 · Gujarat 981 · UP 919

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

## India Post PIN Code Directory (`india_post_pincode_dire...`)
- **EDA confirmed:** 165,627 post offices · 19,586 unique pincodes
- **Coordinate coverage:** 93% (EDA — better than initial 92% estimate)
- **Grain = post office, NOT pincode.** Joining on `pincode` fans out rows. Dedupe or aggregate before joining facilities.
- Office types: Branch (~140k), Post (~25k), Head (~800)

## NFHS-5 District Health Indicators (`nfhs_5_district_health_...`)
- **EDA confirmed:** 706 districts × 109 indicators, across 36 Indian states/UTs
- Long human-readable column names — rename to snake_case on load.
- `*` = suppressed/unavailable → treat as NULL, not 0.
- `(29.5)` parenthesized values = estimate from 25–49 unweighted cases → flag as low-confidence.
- District/state name spelling drifts vs other sources → prefer spatial join over string match.
- Field period 2019–2021 (NFHS-5). Do NOT mix with NFHS-6 without verifying indicator definitions.

### EDA — interesting district health stats (demo talking points)
- **Women's literacy:** mean 74.33%, range 38.6% (Jhabua, MP) → 99.7% (Kerala). Leaders: Kerala, Mizoram, Puducherry.
- **Health insurance coverage:** average only 40%
- **Water access:** 94%; **improved sanitation:** 72%

→ Stretch panel: low-literacy districts (e.g. Jhabua) × verified facility coverage gap is a strong "underserved" story.

## State Name Normalization (CRITICAL)
EDA flagged state names need standardization (case/spacing variations) across `facilities`, NFHS-5, and pincode tables.
- Strategy: build `dim_state` lookup with canonical title-case names + alias list
- Pre-join cleanup: `INITCAP(TRIM(REGEXP_REPLACE(state, '\\s+', ' ')))`
- For districts: spatial join preferred, but string-match fallback uses same normalization

## Bad Geocoding (real example)
- `Sanjivani Multi Speciality Hospital` — Kerala address (Alappuzha district, pin 690509) but lat/lng `(59.94, -38.26)` → North Atlantic. Bad geocoding.
- Solution: India bounding box `lat 6-37, lng 68-98` → `has_valid_coords` flag in silver.
- Implication: 98.83% raw geocoding ≠ 98.83% usable geocoding. Real usable % computed in `notebooks/02_build_silver.py` sanity checks.

## Source Field Strategy
Confirmed from schema: facility table has FIVE rich claim surfaces.
1. **`capability`** (JSON array) — sentence-level statements. Richest. e.g. "NICU Level III", "Centre of Excellence in Fertility Medicine", "24/7 Emergency Department".
2. **`equipment`** (JSON array) — equipment items. e.g. "CT scanner", "Modular operation theater with laminar air flow".
3. **`procedure`** (JSON array) — procedures performed. e.g. "Performs joint replacement surgery".
4. **`specialties`** (JSON array) — coded specialty taxonomy. e.g. "criticalCareMedicine", "neonatologyPerinatalMedicine". Second-signal for cross-verification.
5. **`description`** (string) — short prose blurb. Background context.

**Implication:** much of the "extraction" is actually parsing + normalization, not free-text NER. The free-text fields here already arrive semi-structured. Big efficiency win for Free Edition LLM budget.

**Citation source:** `source_urls` (JSON array per facility) — every trust-desk score can cite a URL.

## Claim Extraction Notes
- **State column unreliable** — confirmed real example: row `fac0cc70-...` (Kerala Sanjivani) has `address_stateOrRegion = "Alappuzha"` (a district, not a state). Source-data quality issue. Use pincode lookup for canonical state/district when possible.
- **Baseline classifier** (`src/classifier.py`) is rules-only with regex + specialty-code mapping. Six target capabilities: icu, nicu, maternity, emergency, oncology, trauma.
- **Confidence tiers (rules baseline):** 0.85 capabilities text · 0.80 specialty code · 0.75 procedures/equipment text. LLM fallback (Chialing) will refine.
- **6 / 10,088 facilities** dropped by India bounding-box filter — 99.94% have usable coordinates after cleaning.

## Evidence Linking Notes
(fill in as we build)

## App / Lakebase Notes
- Lakebase database `trust_desk` provisioned ✓ (2026-06-15)
