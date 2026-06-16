"""Trust-First Triage Desk — Databricks App entrypoint (Streamlit).

Run locally:  streamlit run app/app.py
Deploy:       databricks apps deploy
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import streamlit as st

from src import db
from src.db import CAPABILITIES_FOR_TRIAGE
from src.indicators import (
    CAVEAT_KEYS,
    FILTERABLE_INDICATORS,
    extract_facility_indicators,
    indicator_status_map,
)

# ---------------------------------------------------------------------------
# Page config + brand styling
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Trust-First Triage Desk",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATABRICKS_RED = "#FF3621"
DATABRICKS_INK = "#0B2026"
DATABRICKS_CREAM = "#F9F7F4"
DATABRICKS_STONE = "#EEEDE9"

SUPPORTS_GREEN = "#1F8F4E"
CONTRADICTS_RED = "#C0392B"
UNCLEAR_AMBER = "#C07A1B"

st.markdown(
    f"""
    <style>
        /* Hide Streamlit chrome */
        #MainMenu, footer {{ visibility: hidden; }}
        header {{ background: transparent !important; }}

        /* Brand background */
        .stApp {{ background-color: {DATABRICKS_CREAM}; }}
        section[data-testid="stSidebar"] {{ background-color: {DATABRICKS_STONE}; }}

        /* Hero band */
        .hero {{
            background: linear-gradient(95deg, {DATABRICKS_INK} 0%, #133239 100%);
            color: #ffffff !important;
            padding: 1.6rem 1.8rem;
            border-radius: 10px;
            margin-bottom: 1.2rem;
        }}
        .hero h1, .hero h1 * {{
            font-size: 1.85rem;
            margin: 0 0 0.3rem 0;
            font-weight: 700;
            color: #ffffff !important;
        }}
        .hero p {{ margin: 0; color: #d9e4e7 !important; font-size: 1rem; }}
        .hero .accent {{ color: {DATABRICKS_RED} !important; font-weight: 700; }}

        /* Section headers */
        h2, h3 {{ color: {DATABRICKS_INK}; }}

        /* Status badge chips */
        .chip {{
            display: inline-block;
            padding: 0.18rem 0.7rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.02em;
        }}
        .chip-verified    {{ background: #DFF3E5; color: {SUPPORTS_GREEN}; border: 1px solid {SUPPORTS_GREEN}; }}
        .chip-unclear     {{ background: #FBEFD9; color: {UNCLEAR_AMBER};  border: 1px solid {UNCLEAR_AMBER}; }}
        .chip-contradicted{{ background: #F7DDD8; color: {CONTRADICTS_RED}; border: 1px solid {CONTRADICTS_RED}; }}
        .chip-available   {{ background: #DFF3E5; color: {SUPPORTS_GREEN}; border: 1px solid {SUPPORTS_GREEN}; }}
        .chip-unavailable {{ background: #F7DDD8; color: {CONTRADICTS_RED}; border: 1px solid {CONTRADICTS_RED}; }}

        /* Evidence cards */
        .evcard {{
            padding: 0.6rem 0.85rem;
            border-radius: 8px;
            margin-bottom: 0.45rem;
            font-size: 0.9rem;
            border-left: 4px solid #ccc;
            background: white;
        }}
        .ev-supports   {{ border-left-color: {SUPPORTS_GREEN};   background: #F2FAF4; }}
        .ev-contradicts{{ border-left-color: {CONTRADICTS_RED};  background: #FDF2F0; }}
        .ev-neutral    {{ border-left-color: #999;               background: #FAFAFA; }}
        .evcard .src   {{ font-size: 0.7rem; color: #666; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.2rem; }}

        /* Trust bar */
        .trust-wrap {{ background: {DATABRICKS_STONE}; height: 10px; border-radius: 999px; overflow: hidden; margin: 0.3rem 0 0.4rem 0; }}
        .trust-bar  {{ height: 100%; background: linear-gradient(90deg, {DATABRICKS_RED}, {SUPPORTS_GREEN}); }}

        /* Facility row cards */
        .facrow {{
            background: white;
            border-radius: 8px;
            padding: 0.75rem 1rem;
            margin-bottom: 0.5rem;
            border: 1px solid {DATABRICKS_STONE};
        }}
        .facrow:hover {{ border-color: {DATABRICKS_RED}; }}

        /* Buttons */
        .stButton > button {{ border-radius: 6px; font-weight: 500; }}
        div[data-testid="stPrimaryButton"] > button {{ background: {DATABRICKS_RED} !important; color: white !important; border: none; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# Hero
st.markdown(
    """
    <div class="hero">
        <h1>Trust-First Triage Desk <span class="accent">·</span> Healthcare Facility Intelligence</h1>
        <p>Verify what 10,088 Indian healthcare facilities actually claim. Every score cites the source text. Uncertainty is shown honestly.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state for cross-tab facility selection
# ---------------------------------------------------------------------------

if "selected_facility" not in st.session_state:
    st.session_state.selected_facility = ""
if "open_dialog_for" not in st.session_state:
    st.session_state.open_dialog_for = ""


# ---------------------------------------------------------------------------
# Sidebar — planner identity, filters, demo shortcuts
# ---------------------------------------------------------------------------

DEMO_FACILITIES = [
    ("India Hospital — contradicted ICU", "5c39dc80-0f8e-4fa1-9f53-fc27fbd2634e"),
    ("Kamala Nehru Hospital — contradicted ICU", "60adac06-d48e-4010-a6d6-03ae8b23b46e"),
    ("Wadia Children Hospital — verified NICU", "f73e1e8e-f5b0-4d55-9e93-9854283da691"),
    ("Cloudnine Gurgaon — verified NICU", "c710d0a6-a688-4613-a8a5-3bc155f9ceb8"),
]

with st.sidebar:
    st.markdown("### 👤 Planner")
    planner_id = st.text_input("Your handle", value="planner", label_visibility="collapsed")

    st.markdown("---")
    st.markdown("### 🔍 Filters")
    capability = st.selectbox("Capability", CAPABILITIES_FOR_TRIAGE, index=0)
    state = st.text_input("State or city (prefix OK)", value="", placeholder="e.g. Kerala, Mumbai")
    min_trust = st.slider("Min trust score", 0.0, 1.0, 0.0, 0.05)

    st.markdown("**Operations & access**")
    _ind_label_to_key = {label: key for key, label in FILTERABLE_INDICATORS}
    require_labels = st.multiselect(
        "Must offer",
        options=list(_ind_label_to_key.keys()),
        help="Keep only facilities whose own text says they offer these (each is cited in Facility Detail).",
    )
    require_indicator_keys = [_ind_label_to_key[lbl] for lbl in require_labels]
    hide_caveats = st.checkbox("Hide temporarily closed / under construction")

    st.markdown("---")
    st.markdown("### ⭐ Demo shortcuts")
    st.caption("Click to open facility detail in a modal")
    for label, fid in DEMO_FACILITIES:
        if st.button(label, key=f"demo-{fid}", use_container_width=True):
            st.session_state.open_dialog_for = fid
            st.rerun()

    st.markdown("---")
    with st.expander("🔑 Lakebase token (1h TTL)", expanded=False):
        st.caption(
            "Paste a fresh OAuth token here to use Lakebase persistence without "
            "redeploying. Token TTL is ~1 hour."
        )
        token_input = st.text_input(
            "OAuth token",
            value="",
            type="password",
            key="lakebase_token_input",
            label_visibility="collapsed",
            placeholder="eyJraWQ...",
        )
        if token_input.strip():
            os.environ["LAKEBASE_PASSWORD"] = token_input.strip()
            st.success("Token applied for this session.")
        st.caption("Generate fresh in a workspace notebook:")
        st.code(
            'from databricks.sdk import WorkspaceClient\n'
            'w = WorkspaceClient()\n'
            'cred = w.database.generate_database_credential(\n'
            '    request_id="trust-desk-app",\n'
            '    instance_names=["ep-solitary-shape-d8czihec"],\n'
            ')\n'
            'print(cred.token)',
            language="python",
        )

    st.markdown("---")
    st.caption(
        "**Why this matters.** The dataset's `capability`, `equipment`, "
        "and `procedure` fields are CLAIMS, not verified facts. "
        "Trust Desk grounds every score in the facility's own text."
    )


# ---------------------------------------------------------------------------
# Helpers for UI
# ---------------------------------------------------------------------------


def status_chip(status: str) -> str:
    label = {"verified": "Verified", "unclear": "Unclear", "contradicted": "Contradicted"}.get(status, status)
    return f'<span class="chip chip-{status}">{label}</span>'


def trust_bar_html(score: float) -> str:
    pct = max(0.0, min(1.0, float(score))) * 100
    return f'<div class="trust-wrap"><div class="trust-bar" style="width:{pct:.0f}%"></div></div>'


def evidence_card_html(snippet: str, source_field: str, polarity: str) -> str:
    icon = {"supports": "🟢", "contradicts": "🔴", "neutral": "⚪"}.get(polarity, "·")
    return (
        f'<div class="evcard ev-{polarity}">'
        f'<div class="src">{icon} {source_field}</div>'
        f'<div>{snippet}</div>'
        f'</div>'
    )


def safe_list(val) -> list:
    if val is None:
        return []
    try:
        return list(val)
    except TypeError:
        return []


# ---------------------------------------------------------------------------
# Facility detail — shared between modal (dialog) and tab
# ---------------------------------------------------------------------------


def render_facility_detail(fid: str, planner_id: str) -> None:
    try:
        fac = db.facility_detail(fid)
    except Exception as e:
        st.error(f"Lookup failed: {e}")
        return

    if fac.empty:
        st.warning("Facility not found.")
        return

    f = fac.iloc[0]
    st.markdown(f"## {f['name']}")
    meta_cols = st.columns(4)
    meta_cols[0].metric("City", f.get("city") or "—")
    meta_cols[1].metric("State", f.get("state") or "—")
    meta_cols[2].metric("Pincode", f.get("pincode") or "—")
    meta_cols[3].metric("Year est.", str(f.get("year_established") or "—"))

    with st.expander("📝 Description (source text)", expanded=True):
        st.write(f.get("description") or "_(no description in source)_")

    # Operations & access indicators — practical signals a planner needs that
    # aren't clinical capabilities (open 24/7, wheelchair access, ambulance,
    # blood bank, pharmacy, cashless; plus closure/under-construction caveats).
    # Computed live from the facility's own text; every chip cites its source.
    indicators = extract_facility_indicators(
        capabilities=safe_list(f.get("capabilities")),
        procedures=safe_list(f.get("procedures")),
        equipment=safe_list(f.get("equipment")),
        description=f.get("description"),
    )
    if indicators:
        st.markdown("### Operations & access")
        for ind in [i for i in indicators if i.status == "attention"]:
            st.warning(f"{ind.icon} **{ind.label}** — “{ind.source_quote}”  ·  source: `{ind.source_field}`")
        features = [i for i in indicators if i.status != "attention"]
        if features:
            cols = st.columns(3)
            for idx, ind in enumerate(features):
                with cols[idx % 3]:
                    suffix = "" if ind.status == "available" else " — not available"
                    st.markdown(
                        f'<span class="chip chip-{ind.status}">{ind.icon} {ind.label}{suffix}</span>',
                        unsafe_allow_html=True,
                    )
                    st.caption(f"“{ind.source_quote[:90]}” · {ind.source_field}")

    st.markdown("### Capability claims & evidence")
    claims = db.facility_claims_with_evidence(fid)
    if claims.empty:
        st.info("No claims classified for this facility.")
    else:
        all_evidence = db.facility_evidence(fid)
        for capability_val, group in claims.groupby("claim_value"):
            status_v = group.iloc[0]["status"] or "unclear"
            trust = float(group.iloc[0]["trust_score"] or 0)
            sup = int(group.iloc[0]["supporting_evidence_count"] or 0)
            con = int(group.iloc[0]["contradicting_evidence_count"] or 0)
            expand = status_v == "contradicted"
            with st.expander(
                f"**{capability_val.upper()}**  ·  trust {trust:.2f}  ·  {sup} supporting · {con} contradicting",
                expanded=expand,
            ):
                st.markdown(
                    f"{status_chip(status_v)}{trust_bar_html(trust)}",
                    unsafe_allow_html=True,
                )
                st.markdown("**Claimed in:**")
                for _, c in group.iterrows():
                    st.markdown(f"- `{c['source_field']}` &nbsp;→&nbsp; *“{c['claim_raw'][:160]}”*")

                ev_for_cap = all_evidence[all_evidence["claim_id"].isin(group["claim_id"])]
                if not ev_for_cap.empty:
                    st.markdown("**Evidence**")
                    for _, e in ev_for_cap.iterrows():
                        st.markdown(
                            evidence_card_html(e["snippet"], e["source_field"], e["polarity"]),
                            unsafe_allow_html=True,
                        )

                b1, b2, b3 = st.columns(3)
                cid = group.iloc[0]["claim_id"]
                with b1:
                    if st.button("✅ Verify", key=f"v-{fid}-{cid}", use_container_width=True):
                        try:
                            db.record_verification(fid, cid, planner_id, "verified")
                            st.success(f"Saved — {capability_val.upper()} verified.")
                        except Exception as e:
                            st.error(f"Lakebase write failed: {e}")
                with b2:
                    if st.button("❌ Reject", key=f"r-{fid}-{cid}", use_container_width=True):
                        try:
                            db.record_verification(fid, cid, planner_id, "rejected")
                            st.success(f"Saved — {capability_val.upper()} rejected.")
                        except Exception as e:
                            st.error(f"Lakebase write failed: {e}")
                with b3:
                    if st.button("⚠️ Needs info", key=f"n-{fid}-{cid}", use_container_width=True):
                        try:
                            db.record_verification(fid, cid, planner_id, "needs_info")
                            st.success(f"Saved — {capability_val.upper()} needs info.")
                        except Exception as e:
                            st.error(f"Lakebase write failed: {e}")

    st.markdown("### 📝 Planner note")
    note = st.text_area(
        "Add context",
        placeholder="e.g. Confirmed by phone — refers all ICU cases to NMC Hospital.",
        label_visibility="collapsed",
        key=f"note-{fid}",
    )
    if st.button("Save note", key=f"savenote-{fid}") and note.strip():
        try:
            db.add_annotation(fid, planner_id, note.strip())
            st.success("Note saved.")
        except Exception as e:
            st.error(f"Lakebase write failed: {e}")

    urls = safe_list(f.get("source_urls"))
    if urls:
        st.markdown("### 🔗 Sources")
        seen: set[str] = set()
        for u in urls:
            if u and u not in seen:
                seen.add(u)
                st.markdown(f"- {u}")
                if len(seen) >= 10:
                    break


@st.dialog("Facility Detail", width="large")
def _facility_dialog(fid: str, planner_id: str) -> None:
    render_facility_detail(fid, planner_id)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

# Open dialog if a facility was selected (Inspect button or demo shortcut)
if st.session_state.open_dialog_for:
    fid_dialog = st.session_state.open_dialog_for
    st.session_state.open_dialog_for = ""  # consume so it doesn't reopen on next rerun
    _facility_dialog(fid_dialog, planner_id)

tabs = st.tabs(["🔍 Triage", "🏥 Facility Detail", "🗺️ District Context", "📝 My Work"])
tab_triage, tab_facility, tab_district, tab_work = tabs


# ---------------------------------------------------------------------------
# Tab 1 — Triage
# ---------------------------------------------------------------------------

with tab_triage:
    where_clause = f"in **{state}**" if state else "across India"
    st.markdown(f"#### Facilities claiming **{capability.upper()}** {where_clause}")

    try:
        df = db.triage_facilities(
            capability=capability,
            state=state or None,
            min_trust=min_trust,
            limit=200,
        )
    except Exception as e:
        st.error(f"Delta query failed: {e}")
        df = pd.DataFrame()

    # Operations & access filter — computed live per row from the facility's text.
    if not df.empty and (require_indicator_keys or hide_caveats):
        def _passes_indicator_filter(r) -> bool:
            status = indicator_status_map(
                safe_list(r.get("capabilities")),
                safe_list(r.get("procedures")),
                safe_list(r.get("equipment")),
                r.get("description"),
            )
            if hide_caveats and any(status.get(k) == "attention" for k in CAVEAT_KEYS):
                return False
            return all(status.get(k) == "available" for k in require_indicator_keys)

        n_before = len(df)
        df = df[df.apply(_passes_indicator_filter, axis=1)].reset_index(drop=True)
        active = ", ".join(require_labels) + (" · excl. closed/under-construction" if hide_caveats else "")
        st.caption(f"Operations & access filter ({active}): {len(df)} of {n_before} match.")

    if df.empty:
        st.info("No facilities match. Loosen filters or try a different capability.")
    else:
        verified = int((df["status"] == "verified").sum())
        unclear = int((df["status"] == "unclear").sum())
        contradicted = int((df["status"] == "contradicted").sum())
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Claiming the capability", len(df))
        c2.metric("✅ Verified", verified)
        c3.metric("⚠️ Unclear", unclear)
        c4.metric("❌ Contradicted", contradicted)

        with st.expander("📍 Map of these facilities", expanded=False):
            with_coords = df.dropna(subset=["latitude", "longitude"])
            if not with_coords.empty:
                st.map(with_coords.rename(columns={"latitude": "lat", "longitude": "lon"}))
            else:
                st.caption("No geocoded coordinates for these results.")

        st.markdown("##### Results")
        st.caption(
            "Sorted by status (verified · unclear · contradicted) then trust score. "
            "Click 'Inspect' to load full evidence."
        )

        # Render top 50 as polished rows
        for _, r in df.head(50).iterrows():
            with st.container():
                c_left, c_mid, c_right = st.columns([5, 2, 1])
                with c_left:
                    st.markdown(
                        f"**{r['name']}** &nbsp; {status_chip(r['status'])}<br>"
                        f"<span style='color:#666;font-size:0.85rem;'>📍 {r['city'] or '—'}, {r['state'] or '—'} &nbsp;·&nbsp; "
                        f"{int(r['supporting_evidence_count'] or 0)} supporting · "
                        f"{int(r['contradicting_evidence_count'] or 0)} contradicting</span>"
                        f"{trust_bar_html(r['trust_score'] or 0)}",
                        unsafe_allow_html=True,
                    )
                with c_mid:
                    st.markdown(
                        f"<div style='text-align:right;font-size:0.85rem;color:#666;'>Trust score</div>"
                        f"<div style='text-align:right;font-size:1.3rem;font-weight:700;color:{DATABRICKS_INK};'>"
                        f"{(r['trust_score'] or 0):.2f}</div>",
                        unsafe_allow_html=True,
                    )
                with c_right:
                    if st.button("Inspect →", key=f"inspect-{r['facility_id']}"):
                        st.session_state.open_dialog_for = r["facility_id"]
                        st.rerun()


# ---------------------------------------------------------------------------
# Tab 2 — Facility Detail
# ---------------------------------------------------------------------------

with tab_facility:
    st.caption("Or paste a facility ID directly here:")
    fid_input = st.text_input(
        "Facility ID",
        value=st.session_state.selected_facility,
        key="facility_id_input",
        label_visibility="collapsed",
    )
    if not fid_input:
        st.info("Use **Inspect →** in the Triage tab (or sidebar Demo shortcuts) to open a facility.")
    else:
        try:
            fac = db.facility_detail(fid_input)
        except Exception as e:
            st.error(f"Lookup failed: {e}")
            fac = pd.DataFrame()

        if fac.empty:
            st.warning("Facility not found.")
        else:
            render_facility_detail(fid_input, planner_id)


# ---------------------------------------------------------------------------
# Tab 3 — District context
# ---------------------------------------------------------------------------

with tab_district:
    st.markdown("#### District health context — NFHS-5 (2019–21)")
    state_for_district = st.text_input(
        "State", value=state or "Madhya Pradesh", help="e.g. Madhya Pradesh — has Jhabua at the bottom of literacy"
    )
    if state_for_district:
        try:
            d = db.district_health_for(state_for_district)
        except Exception as e:
            st.error(f"Query failed: {e}")
            d = pd.DataFrame()
        if d.empty:
            st.info("No NFHS-5 rows for that state. Try INITCAP spelling, e.g. 'Madhya Pradesh'.")
        else:
            st.caption(
                "Lower women's literacy and lower institutional birth rates flag districts where "
                "verified facility coverage matters most. Use Trust Desk to find real facilities, not claimed ones."
            )
            st.dataframe(
                d.sort_values("women_age_15_49_who_are_literate_pct"),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "district": "District",
                    "state": "State",
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
# Tab 4 — My Work
# ---------------------------------------------------------------------------

with tab_work:
    st.markdown(f"#### Work history for `{planner_id}`")
    try:
        work = db.planner_work(planner_id)
    except Exception as e:
        st.error(f"Lakebase read failed: {e}")
        work = {"verifications": pd.DataFrame(), "annotations": pd.DataFrame()}

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### ✅ Verifications")
        if work["verifications"].empty:
            st.info("No verifications yet. Inspect a facility and click Verify / Reject / Needs info.")
        else:
            st.dataframe(work["verifications"], hide_index=True, use_container_width=True)
    with col2:
        st.markdown("##### 📝 Annotations")
        if work["annotations"].empty:
            st.info("No notes yet.")
        else:
            st.dataframe(work["annotations"], hide_index=True, use_container_width=True)
