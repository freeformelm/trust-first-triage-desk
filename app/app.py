"""Trust-First Triage Desk — Databricks App entrypoint (Streamlit).

Run locally:  streamlit run app/app.py
Deploy:       databricks apps deploy

Required env vars (set via app.yaml or local .env):
  - DATABRICKS_HOST
  - DATABRICKS_HTTP_PATH        (Serverless SQL warehouse HTTP path)
  - DATABRICKS_TOKEN            (auto-provided on Databricks Apps)
  - LAKEBASE_HOST
  - LAKEBASE_DB
  - LAKEBASE_USER
  - LAKEBASE_PASSWORD
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import streamlit as st

from src import db
from src.db import CAPABILITIES_FOR_TRIAGE

st.set_page_config(
    page_title="Trust-First Triage Desk",
    page_icon="🩺",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Sidebar — planner identity + global filters
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### Trust-First Triage Desk")
    st.caption("Verify what 10,000 Indian healthcare facilities actually claim.")
    planner_id = st.text_input("Planner handle", value="planner")
    st.divider()
    capability = st.selectbox("Capability", CAPABILITIES_FOR_TRIAGE, index=0)
    state = st.text_input("State (optional, exact match)", value="")
    min_trust = st.slider("Minimum trust score", 0.0, 1.0, 0.0, 0.05)
    st.caption("Every score is backed by a quoted source snippet. We never present weak evidence as fact.")


tab_triage, tab_facility, tab_district, tab_work = st.tabs(
    ["🔍 Triage", "🏥 Facility Detail", "🗺️ District Context", "📝 My Work"]
)


# ---------------------------------------------------------------------------
# Tab 1 — Triage list
# ---------------------------------------------------------------------------


with tab_triage:
    st.subheader(f"Facilities claiming `{capability}`" + (f" in {state}" if state else ""))
    try:
        df = db.triage_facilities(
            capability=capability,
            state=state or None,
            min_trust=min_trust,
            limit=200,
        )
    except Exception as e:
        st.error(f"Query failed: {e}")
        df = pd.DataFrame()

    if df.empty:
        st.info("No facilities match. Loosen filters.")
    else:
        verified = (df["status"] == "verified").sum()
        unclear = (df["status"] == "unclear").sum()
        contradicted = (df["status"] == "contradicted").sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total claiming", len(df))
        c2.metric("✅ Verified", verified)
        c3.metric("⚠️ Unclear", unclear)
        c4.metric("❌ Contradicted", contradicted)

        # Map for facilities with coords
        with_coords = df.dropna(subset=["latitude", "longitude"])
        if not with_coords.empty:
            with st.expander("📍 Map", expanded=False):
                st.map(with_coords.rename(columns={"latitude": "lat", "longitude": "lon"}))

        # Table view
        display_df = df[
            ["facility_id", "name", "city", "state", "status", "trust_score",
             "supporting_evidence_count", "contradicting_evidence_count", "claim_count"]
        ].copy()
        display_df["status"] = display_df["status"].map(
            {"verified": "✅ Verified", "unclear": "⚠️ Unclear", "contradicted": "❌ Contradicted"}
        )
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "trust_score": st.column_config.ProgressColumn(
                    "Trust", min_value=0.0, max_value=1.0, format="%.2f"
                ),
            },
        )

        st.caption("Click into a facility on the Facility Detail tab using its ID.")


# ---------------------------------------------------------------------------
# Tab 2 — Facility detail with evidence + verify/reject
# ---------------------------------------------------------------------------


with tab_facility:
    st.subheader("Facility Detail")
    fid = st.text_input("Facility ID", help="Copy from the Triage table")
    if not fid:
        st.info("Paste a facility ID from the Triage tab.")
    else:
        try:
            fac = db.facility_detail(fid)
        except Exception as e:
            st.error(f"Lookup failed: {e}")
            fac = pd.DataFrame()

        if fac.empty:
            st.warning("Facility not found.")
        else:
            f = fac.iloc[0]
            st.markdown(f"## {f['name']}")
            meta_cols = st.columns(4)
            meta_cols[0].metric("City", f.get("city") or "—")
            meta_cols[1].metric("State", f.get("state") or "—")
            meta_cols[2].metric("Pincode", f.get("pincode") or "—")
            meta_cols[3].metric("Year est.", str(f.get("year_established") or "—"))

            with st.expander("Description", expanded=True):
                st.write(f.get("description") or "_(no description in source)_")

            # Claims table
            st.markdown("### Claims")
            claims = db.facility_claims_with_evidence(fid)
            if claims.empty:
                st.info("No claims classified for this facility yet.")
            else:
                # Group by capability for the verify UI
                for capability_val, group in claims.groupby("claim_value"):
                    status = group.iloc[0]["status"] or "unclear"
                    trust = group.iloc[0]["trust_score"] or 0.0
                    sup = int(group.iloc[0]["supporting_evidence_count"] or 0)
                    con = int(group.iloc[0]["contradicting_evidence_count"] or 0)
                    badge = {"verified": "✅", "unclear": "⚠️", "contradicted": "❌"}.get(status, "·")

                    with st.expander(
                        f"{badge} **{capability_val.upper()}** · trust {trust:.2f} · "
                        f"{sup} supporting · {con} contradicting",
                        expanded=(status == "contradicted"),
                    ):
                        st.dataframe(
                            group[["claim_raw", "source_field", "extraction_confidence"]],
                            hide_index=True,
                            use_container_width=True,
                        )

                        # Evidence snippets for this capability
                        all_evidence = db.facility_evidence(fid)
                        ev_for_cap = all_evidence[
                            all_evidence["claim_id"].isin(group["claim_id"])
                        ]
                        if not ev_for_cap.empty:
                            st.markdown("**Evidence**")
                            for _, e in ev_for_cap.iterrows():
                                pol_icon = {"supports": "🟢", "contradicts": "🔴", "neutral": "⚪"}.get(
                                    e["polarity"], "·"
                                )
                                st.markdown(f"{pol_icon} `{e['source_field']}` — {e['snippet']}")

                        # Verify / reject buttons → Lakebase
                        b1, b2, b3 = st.columns(3)
                        cid = group.iloc[0]["claim_id"]
                        with b1:
                            if st.button(f"✅ Verify {capability_val}", key=f"v-{cid}"):
                                try:
                                    db.record_verification(fid, cid, planner_id, "verified")
                                    st.success("Saved.")
                                except Exception as e:
                                    st.error(f"Lakebase write failed: {e}")
                        with b2:
                            if st.button(f"❌ Reject {capability_val}", key=f"r-{cid}"):
                                try:
                                    db.record_verification(fid, cid, planner_id, "rejected")
                                    st.success("Saved.")
                                except Exception as e:
                                    st.error(f"Lakebase write failed: {e}")
                        with b3:
                            if st.button(f"⚠️ Needs info {capability_val}", key=f"n-{cid}"):
                                try:
                                    db.record_verification(fid, cid, planner_id, "needs_info")
                                    st.success("Saved.")
                                except Exception as e:
                                    st.error(f"Lakebase write failed: {e}")

            # Planner notes
            st.markdown("### Planner Note")
            note = st.text_area("Add a note (saved to Lakebase, attached to this facility)")
            if st.button("Save note") and note:
                try:
                    db.add_annotation(fid, planner_id, note)
                    st.success("Note saved.")
                except Exception as e:
                    st.error(f"Lakebase write failed: {e}")

            # Source URLs (citations) — handle numpy array safely
            urls_raw = f.get("source_urls")
            urls: list = []
            if urls_raw is not None:
                try:
                    urls = list(urls_raw)
                except TypeError:
                    urls = []
            if urls:
                st.markdown("### Sources")
                for u in urls[:10]:
                    if u:
                        st.markdown(f"- {u}")


# ---------------------------------------------------------------------------
# Tab 3 — District context (NFHS-5)
# ---------------------------------------------------------------------------


with tab_district:
    st.subheader("District Health Context — NFHS-5")
    state_for_district = st.text_input("State", value=state or "Madhya Pradesh")
    if state_for_district:
        try:
            d = db.district_health_for(state_for_district)
        except Exception as e:
            st.error(f"Query failed: {e}")
            d = pd.DataFrame()
        if d.empty:
            st.info("No district health data for that state.")
        else:
            st.caption(
                "Lower women's literacy correlates with maternal-health burden. "
                "Use this view to spot districts where verified facility coverage matters most."
            )
            st.dataframe(
                d.sort_values("women_age_15_49_who_are_literate_pct"),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "women_age_15_49_who_are_literate_pct": st.column_config.ProgressColumn(
                        "Women literate (%)", min_value=0, max_value=100, format="%.1f"
                    ),
                    "hh_member_covered_health_insurance_pct": st.column_config.ProgressColumn(
                        "Health insurance (%)", min_value=0, max_value=100, format="%.1f"
                    ),
                    "institutional_birth_5y_pct": st.column_config.ProgressColumn(
                        "Institutional birth (%)", min_value=0, max_value=100, format="%.1f"
                    ),
                    "births_delivered_by_csection_5y_pct": st.column_config.ProgressColumn(
                        "C-section (%)", min_value=0, max_value=100, format="%.1f"
                    ),
                },
            )


# ---------------------------------------------------------------------------
# Tab 4 — Planner work persistence (Lakebase-backed)
# ---------------------------------------------------------------------------


with tab_work:
    st.subheader(f"Work history — `{planner_id}`")
    try:
        work = db.planner_work(planner_id)
    except Exception as e:
        st.error(f"Lakebase read failed: {e}")
        work = {"verifications": pd.DataFrame(), "annotations": pd.DataFrame()}

    st.markdown("#### Verifications")
    if work["verifications"].empty:
        st.info("No verifications yet.")
    else:
        st.dataframe(work["verifications"], hide_index=True, use_container_width=True)

    st.markdown("#### Annotations")
    if work["annotations"].empty:
        st.info("No notes yet.")
    else:
        st.dataframe(work["annotations"], hide_index=True, use_container_width=True)
