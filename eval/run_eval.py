"""Evaluation harness for the Trust-First Triage Desk classifier + trust pipeline.

Owner: Data Scientist.

Runs the LIVE rules pipeline (src.classifier + src.evidence) over the 20
hand-labeled scenarios in scenarios.json, using the real source rows captured in
fixtures.json, and reports:
  - per-scenario PASS/FAIL (predicted status vs human ground truth)
  - overall accuracy
  - 3x3 confusion matrix (rows = expected, cols = predicted)
  - contradiction precision / recall (the safety-critical metric for a planner)

Deterministic & offline: no DB or LLM needed (fixtures are committed). Re-run
after any change to classifier.py / evidence.py to catch regressions.

Usage:  python -m eval.run_eval        (from repo root)
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.classifier import classify_facility, find_evidence_for_capability
from src.evidence import status_label, trust_score

HERE = os.path.dirname(__file__)
STATUSES = ("verified", "unclear", "contradicted")


def predict(fac: dict, capability: str) -> dict:
    """Run the full pipeline for one (facility, capability) and return its prediction."""
    claims = classify_facility(
        facility_id="eval",
        capabilities=fac.get("capabilities") or [],
        procedures=fac.get("procedures") or [],
        equipment=fac.get("equipment") or [],
        specialties=fac.get("specialties") or [],
    )
    cap_claims = [c for c in claims if c.claim_value == capability]
    if not cap_claims:
        return {"status": "absent", "trust": 0.0, "supports": 0, "contradicts": 0, "claim_count": 0}

    text_by_field = {
        "description": fac.get("description"),
        "capabilities": fac.get("capabilities") or [],
        "procedures": fac.get("procedures") or [],
        "equipment": fac.get("equipment") or [],
        "specialties": fac.get("specialties") or [],
    }
    primary = max(cap_claims, key=lambda c: c.extraction_confidence)
    ev = find_evidence_for_capability(primary.claim_id, capability, text_by_field)
    supports = sum(1 for e in ev if e.polarity == "supports")
    contradicts = sum(1 for e in ev if e.polarity == "contradicts")
    ts = trust_score(len(cap_claims), supports, contradicts, primary.extraction_confidence)
    st = status_label(ts, supports, contradicts)
    return {"status": st, "trust": round(ts, 2), "supports": supports,
            "contradicts": contradicts, "claim_count": len(cap_claims)}


def main() -> int:
    fixtures = json.load(open(os.path.join(HERE, "fixtures.json"), encoding="utf-8"))
    scenarios = json.load(open(os.path.join(HERE, "scenarios.json"), encoding="utf-8"))["scenarios"]

    confusion = {e: {p: 0 for p in (*STATUSES, "absent")} for e in STATUSES}
    n_pass = 0
    rows = []
    for s in scenarios:
        fac = fixtures.get(s["facility_id"])
        if fac is None:
            print(f"  MISSING fixture for scenario {s['id']} ({s['facility_id']})")
            continue
        pred = predict(fac, s["claim_value"])
        expected = s["expected_status"]
        ok = pred["status"] == expected
        n_pass += ok
        confusion[expected][pred["status"]] += 1
        rows.append((s, pred, ok))

    # --- per-scenario table ---
    print("=" * 92)
    print("PER-SCENARIO RESULTS  (live rules pipeline vs hand label)")
    print("=" * 92)
    print(f"{'#':>2}  {'res':4} {'stratum':24} {'capability':12} {'expect':12} {'predict':11} trust  s/c")
    print("-" * 92)
    for s, pred, ok in rows:
        print(f"{s['id']:>2}  {'PASS' if ok else 'FAIL':4} {s['stratum']:24} "
              f"{s['claim_value']:12} {s['expected_status']:12} {pred['status']:11} "
              f"{pred['trust']:.2f}  {pred['supports']}/{pred['contradicts']}   {s['name']}")

    total = len(rows)
    print("-" * 92)
    print(f"ACCURACY: {n_pass}/{total} = {n_pass / total:.0%}")

    # --- confusion matrix ---
    print("\nCONFUSION MATRIX (rows = expected/truth, cols = predicted)")
    header = "expected \\ pred  " + "".join(f"{p:>13}" for p in (*STATUSES, "absent"))
    print(header)
    for e in STATUSES:
        print(f"{e:>15}  " + "".join(f"{confusion[e][p]:>13}" for p in (*STATUSES, "absent")))

    # --- contradiction precision / recall (safety metric) ---
    tp = confusion["contradicted"]["contradicted"]
    fp = sum(confusion[e]["contradicted"] for e in STATUSES if e != "contradicted")
    fn = sum(confusion["contradicted"][p] for p in (*STATUSES, "absent") if p != "contradicted")
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    print("\nCONTRADICTION DETECTION (the planner-safety metric)")
    print(f"  precision = {prec:.0%}  (when we flag 'contradicted', how often we're right)")
    print(f"  recall    = {rec:.0%}  (of truly contradicted claims, how many we catch)")

    # --- misclassifications, called out honestly ---
    misses = [(s, pred) for s, pred, ok in rows if not ok]
    if misses:
        print("\nKNOWN MISSES (documented gaps, not silent failures):")
        for s, pred in misses:
            print(f"  #{s['id']} {s['name']} / {s['claim_value']}: "
                  f"expected {s['expected_status']}, got {pred['status']} — {s['rationale']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
