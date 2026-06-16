---
marp: true
title: Trust-First Triage Desk
paginate: true
theme: default
class: lead
style: |
  section { font-size: 1.5rem; }
  h1 { color: #0B2026; }
  strong { color: #FF3621; }
  .small { font-size: 1.05rem; color: #555; }
  table { font-size: 1.15rem; }
---

<!--
Marp deck. Render to PDF/PPTX:
  npx @marp-team/marp-cli slides.md -o slides.pdf
  npx @marp-team/marp-cli slides.md -o slides.pptx
Or use the "Marp for VS Code" extension. Speaker notes are in HTML comments.
-->

# 🩺 Trust-First Triage Desk

### Verify what **10,088** Indian healthcare facilities actually claim — with evidence and **honest uncertainty**

Databricks × Virtue Foundation Hackathon 2026 · Track 1: Facility Trust Desk

**Live app:** trust-first-triage-desk-108684035875991.aws.databricksapps.com

<span class="small">Perin Shah (Data Engineer) · Chialing Wei (Data Scientist)</span>

<!-- 30s opener: the data is messy; claims aren't facts; planners need to know what's real. -->

---

# The problem

- The dataset gives **10,088 facility records** scraped from the open web (Bright Data → GenAI extraction → entity resolution).
- The `capability`, `equipment`, and `procedure` fields are **claims, not verified facts** — coverage ranges 100% → 25%.
- A hospital can list "ICU" in free text while its own description says *"ICU cases referred elsewhere."*

> **143M** people await surgery in LMICs each year · **2.88B** DALYs lost to inadequate care.

**VF Match already shows *where* the deserts are. The unanswered question: *can this facility actually do what it claims?***

<!-- Geography is half the problem. Capability verification is the other half — and it's unsolved. -->

---

# What it does

A **Databricks App for a non-technical planner**:

- **Triage view** — pick one of **12 capabilities** (ICU, NICU, maternity, emergency, oncology, trauma + 6 more), filter by state/city. Facilities ranked by trust and color-coded **✅ Verified · ⚠️ Unclear · ❌ Contradicted**.
- **Facility Detail** — exact claim text + every supporting/contradicting snippet from the facility's *own* fields, with a trust gauge.
- **Operations & access** — 24/7, wheelchair, ambulance, blood bank… and flags **closed / under-construction** before a planner commits.
- **Persistent work** — verify / reject / notes saved to **Lakebase Postgres**.

**Every badge cites a quoted snippet. We never present weak evidence as fact.**

---

# How it works — claim → evidence → trust

```
Source arrays        Three-tier classifier      Evidence scan         Trust score
(capability,    →    1. parse JSON arrays   →   match capability  →   conf, supports,
 specialties,        2. rules + codes           terms in the          contradicts
 equipment,          3. LLM fallback            facility's OWN   →    → Verified /
 description)         (Llama 3.3 70B)           text, ± window         Unclear /
                                                 polarity              Contradicted
```

$$\text{trust}=\max\!\big(0,\min(1,\ (\text{conf}-0.20)+\min(0.30,0.08s)-\min(0.80,0.30c))\big)$$

<span class="small">Base starts *below* extraction confidence — one mention isn't proof. Verified needs trust ≥ 0.75 **and** ≥ 2 corroborations. Any contradiction with s ≤ c → Contradicted.</span>

---

# Honest uncertainty is the point

| Status | What it means | Example |
|---|---|---|
| ✅ **Verified** | quantified + corroborated | *"22-bed Level II ICU with 11 ventilators"* |
| ⚠️ **Unclear** | claimed via code only, no prose backing | specialty code `criticalCareMedicine`, nothing else |
| ❌ **Contradicted** | denied or not operational | *"NICU facility not available"* · *"trauma centre under construction"* |

- Tightening thresholds moved **3,000+ facilities from "verified" to "unclear"** — and that's the **right answer**.
- The contradiction detector scans **both before and after** the mention → catches *"ICU cases referred to NMC Hospital."*

<!-- This slide IS the Evidence & Uncertainty judging criterion. -->

---

# Operations & access — what a planner needs next

Beyond clinical capability, surfaced live from the facility's own text (each **cited**):

- 🕒 Open 24/7 · ♿ Wheelchair / disabled access · 🚑 Ambulance
- 🩸 Blood bank · 💊 Pharmacy / Jan Aushadhi · 💳 Cashless / Ayushman
- 🚧 **Under construction** · ⛔ **Temporarily closed** (shown as warnings)

**Sidebar filter** — "Must offer" + "Hide closed / under-construction".
Filters on *stated evidence* — absence is never treated as denial.

<!-- Real planner value: route donations / referrals to facilities that are open and accessible. -->

---

# Evidence it works

**20 hand-labeled scenarios** from real Marketplace rows — reproducible, offline, deterministic (`python -m eval.run_eval`):

| Metric | Result |
|---|---|
| Overall accuracy | **17 / 20 = 85%** |
| Contradiction **precision** | **100%** |
| Contradiction **recall** | **100%** |

- A planner is **never told a denied/under-construction service exists**, and **never misses one** the text states.
- The 3 remaining errors are all in the **safe direction** (under-claiming, never over-claiming).

<!-- We optimized for contradiction P/R on purpose — the planner-safety metric. -->

---

# Built on Databricks Free Edition — end to end

- **Medallion Delta** (Bronze → Silver → Gold) on Unity Catalog
- **Foundation Model API** (Llama 3.3 70B) for the LLM classification tier — no external keys
- **Lakebase Postgres** (+ pgvector) for persistent planner verifications, notes, shortlists
- **Databricks Apps + Streamlit** — live URL within 2 hours; push → sync → deploy
- **Provenance baked into the schema:** `state_source`, `extraction_method`, `has_valid_coords` — *how* each value was derived

<span class="small">India bounding-box geo-validation caught a "Kerala" hospital geocoded to the North Atlantic. Pincode lookup fixes district-in-state-column errors (165,627 post offices → 19,586 pincodes).</span>

---

# Impact & what's next

- **Complements VF Match:** discovery (*where*) + verification (*whether*) in one workflow.
- **District context** (NFHS-5): Jhabua, MP at **38.6%** women's literacy — find *verified* coverage where burden is highest.
- **Unlocks the other tracks:** verified `gold_facility_trust` makes a Medical Desert Planner and Referral Copilot trustworthy by side effect.

**Roadmap:** PICU/ICU disambiguation · description-supported boolean · Mosaic AI agent for NL queries · daily Lakeflow refresh with flip-to-contradicted alerts.

### Verify what facilities actually claim. Trust, with the receipts.

<!-- Close on the one-liner. Then live demo: contradicted ICU → verified NICU → district panel. -->
