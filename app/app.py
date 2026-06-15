"""Trust-First Triage Desk — Databricks App entrypoint (Streamlit).

Run locally:  streamlit run app/app.py
Deploy:       databricks apps deploy
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Trust-First Triage Desk",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Trust-First Triage Desk")
st.caption(
    "Verify what 10,000 Indian healthcare facilities actually claim — with evidence and honest uncertainty."
)

# Sidebar — planner identity + filters
with st.sidebar:
    st.header("Planner")
    planner_id = st.text_input("Your handle", value="planner")
    st.divider()
    st.header("Filters")
    capability = st.selectbox(
        "Capability",
        ["icu", "maternity", "emergency", "oncology", "trauma", "nicu"],
    )
    state = st.text_input("State (optional)")
    min_trust = st.slider("Minimum trust score", 0.0, 1.0, 0.0, 0.05)

tab_triage, tab_facility, tab_district, tab_work = st.tabs(
    ["Triage", "Facility Detail", "District Context", "My Work"]
)

with tab_triage:
    st.subheader(f"Facilities claiming `{capability}`")
    st.info(
        "TODO: query gold_facility_trust where capability = :capability "
        "AND trust_score >= :min_trust. Render table with status badge "
        "(verified / contradicted / unclear) and claim count."
    )

with tab_facility:
    st.subheader("Facility Detail")
    facility_id = st.text_input("Facility ID")
    if facility_id:
        st.info(
            "TODO: load facility header (name, district, lat/lng), claims table, "
            "and per-claim evidence snippets with polarity color-coding."
        )
        col_verify, col_reject, col_info = st.columns(3)
        with col_verify:
            st.button("Mark Verified", type="primary")
        with col_reject:
            st.button("Mark Rejected")
        with col_info:
            st.button("Needs Info")
        st.text_area("Planner notes")

with tab_district:
    st.subheader("District Context (NFHS-5)")
    st.info(
        "TODO: bar chart of district burden indicators + verified facility "
        "coverage for selected capability. Stretch goal."
    )

with tab_work:
    st.subheader("My Work")
    st.info(
        "TODO: pull verifications + annotations + shortlists from Lakebase, "
        "filtered to current planner_id."
    )
