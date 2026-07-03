from datetime import datetime

import pandas as pd
import streamlit as st
import plotly.express as px

from api import get_deadlines, get_health, upload_file

# Initialize session state for notifications
if "upload_success" not in st.session_state:
    st.session_state.upload_success = None
if "upload_error" not in st.session_state:
    st.session_state.upload_error = None

st.set_page_config(
    page_title="Deadline Sentinel AI",
    page_icon="📅",
    layout="wide",
)

st.title("📅 Deadline Sentinel AI")
st.caption("AI-powered placement & opportunity tracker")


# Sidebar


with st.sidebar:

    st.title("Deadline Sentinel AI")

    st.divider()

    if get_health():
        st.success("🟢 Backend Online")
    else:
        st.error("🔴 Backend Offline")

    st.divider()

    st.subheader("Upload Opportunity")
    uploaded_file = st.file_uploader(
        "Supported: PDF, DOCX, TXT, PNG, JPG",
        type=["pdf", "docx", "txt", "png", "jpg", "jpeg"],
        label_visibility="collapsed"
    )

    if uploaded_file is not None:
        if st.button("🚀 Upload & Process", use_container_width=True):
            st.session_state.upload_success = None
            st.session_state.upload_error = None
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                status_text.text("Reading file...")
                progress_bar.progress(25)
                
                status_text.text("Uploading to backend...")
                progress_bar.progress(50)
                
                status_text.text("Extracting and analyzing deadline data...")
                progress_bar.progress(75)
                
                result = upload_file(uploaded_file)
                
                progress_bar.progress(100)
                status_text.text("Success!")
                
                if result.get("is_updated"):
                    st.session_state.upload_success = f"Existing opportunity updated: {result.get('company_name', 'Unknown Company')} - {result.get('role', 'Unknown Role') or 'Opportunity'}"
                else:
                    st.session_state.upload_success = f"New opportunity added: {result.get('company_name', 'Unknown Company')} - {result.get('role', 'Unknown Role') or 'Opportunity'}"
                
                progress_bar.empty()
                status_text.empty()
                st.rerun()
                
            except Exception as e:
                progress_bar.empty()
                status_text.empty()
                
                error_msg = str(e)
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_detail = e.response.json().get("detail", "")
                        if error_detail:
                            error_msg = error_detail
                    except Exception:
                        pass
                st.session_state.upload_error = f"Upload failed: {error_msg}"
                st.rerun()

    if st.session_state.upload_success:
        st.success(st.session_state.upload_success)
        st.session_state.upload_success = None
        
    if st.session_state.upload_error:
        st.error(st.session_state.upload_error)
        st.session_state.upload_error = None

    st.divider()

    st.subheader("Filters")

    company_name = st.text_input(
        "Company Name",
        placeholder="e.g. Microsoft",
    )

    category = st.selectbox(
        "Category",
        [
            "",
            "placement",
            "internship",
            "hackathon",
            "scholarship",
            "competition",
            "other",
        ],
    )

    status = st.selectbox(
        "Status",
        [
            "",
            "upcoming",
            "completed",
            "expired",
        ],
    )

    deadline_from = st.date_input(
        "Deadline From",
        value=None,
    )

    deadline_to = st.date_input(
        "Deadline To",
        value=None,
    )

    

    st.divider()

    sort_by = st.selectbox(
        "Sort By",
        [
            "deadline",
            "company_name",
            "created_at",
        ],
    )

    order = st.radio(
        "Order",
        [
            "asc",
            "desc",
        ],
        horizontal=True,
    )

    limit = st.selectbox(
        "Results Per Page",
        [
            10,
            20,
            50,
        ],
        index=1,
    )

    st.divider()

    if st.button("🔄 Refresh Dashboard"):
        st.rerun()


# Fetch Data
with st.spinner("Loading deadlines..."):
    try:
        # Fetch up to 100 deadlines to build accurate charts and timelines
        deadlines = get_deadlines(
            company_name=company_name or None,
            category=category or None,
            status=status or None,
            deadline_from=deadline_from,
            deadline_to=deadline_to,
            skip=0,
            limit=100,
            sort_by=sort_by,
            order=order,
        )
    except Exception as e:
        st.error(f"Could not connect to backend.\n\n{e}")
        st.stop()


# Empty State
if not deadlines:
    st.info("📭 No deadlines matched your filters.")
    st.stop()


# DataFrame
df = pd.DataFrame(deadlines)

# Process Dates
df["deadline_dt"] = pd.to_datetime(df["deadline"], format="mixed", errors="coerce")
df["created_dt"] = pd.to_datetime(df["created_at"], format="mixed", errors="coerce")

# Calculate Days Remaining
def days_remaining(deadline_val):
    if pd.isna(deadline_val):
        return "-"
    return (deadline_val.date() - datetime.now().date()).days

df["Days Remaining"] = df["deadline_dt"].apply(days_remaining)

# Metrics calculation
today = datetime.now().date()
total = len(df)
upcoming = (df["status"].astype(str).str.lower() == "upcoming").sum()
completed = df["status"].astype(str).str.lower().isin(["completed", "applied"]).sum()
expired = (df["status"].astype(str).str.lower() == "expired").sum()


# --- SECTION 1: Analytics Cards (Gradients) ---
st.divider()
st.subheader("📊 Analytics Overview")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); padding: 1.2rem; border-radius: 12px; color: white; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-left: 5px solid #00c6ff;">
            <div style="font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #d2dae2;">Total Opportunities</div>
            <div style="font-size: 2.2rem; font-weight: 800; margin-top: 0.4rem; line-height: 1;">{total}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
with col2:
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, #fbc02d 0%, #f57f17 100%); padding: 1.2rem; border-radius: 12px; color: white; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-left: 5px solid #ffeb3b;">
            <div style="font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #fffde7;">Upcoming Deadlines</div>
            <div style="font-size: 2.2rem; font-weight: 800; margin-top: 0.4rem; line-height: 1;">{upcoming}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
with col3:
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, #2e7d32 0%, #1b5e20 100%); padding: 1.2rem; border-radius: 12px; color: white; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-left: 5px solid #00e676;">
            <div style="font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #e8f5e9;">Completed/Applied</div>
            <div style="font-size: 2.2rem; font-weight: 800; margin-top: 0.4rem; line-height: 1;">{completed}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
with col4:
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, #c62828 0%, #b71c1c 100%); padding: 1.2rem; border-radius: 12px; color: white; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-left: 5px solid #ff1744;">
            <div style="font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #ffebee;">Expired Deadlines</div>
            <div style="font-size: 2.2rem; font-weight: 800; margin-top: 0.4rem; line-height: 1;">{expired}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


# --- SECTION 2 & 3: Category & Status Distribution Charts ---
st.divider()
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    category_counts = df["category"].value_counts().reset_index()
    category_counts.columns = ["Category", "Count"]
    category_counts["Category"] = category_counts["Category"].str.capitalize()
    
    fig_category = px.pie(
        category_counts,
        names="Category",
        values="Count",
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Safe,
        title="Opportunities by Category"
    )
    fig_category.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        height=320,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig_category, use_container_width=True)

with chart_col2:
    status_counts = df["status"].value_counts().reset_index()
    status_counts.columns = ["Status", "Count"]
    status_counts["Status"] = status_counts["Status"].str.capitalize()
    
    status_colors = {
        "Upcoming": "#fbc02d",
        "Completed": "#2e7d32",
        "Applied": "#2e7d32",
        "Expired": "#c62828",
    }
    
    fig_status = px.bar(
        status_counts,
        x="Status",
        y="Count",
        color="Status",
        color_discrete_map=status_colors,
        title="Opportunities by Status"
    )
    fig_status.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        height=320,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False
    )
    st.plotly_chart(fig_status, use_container_width=True)


# --- SECTION 4: Upcoming Deadlines Timeline ---
st.divider()
st.subheader("📅 Upcoming Deadlines Timeline")

upcoming_df = df[df["status"].astype(str).str.lower() == "upcoming"].copy()
if not upcoming_df.empty:
    upcoming_df = upcoming_df.dropna(subset=["deadline_dt"]).sort_values("deadline_dt")
    
    # Generate timeline scatter chart
    fig_timeline = px.scatter(
        upcoming_df,
        x="deadline_dt",
        y="company_name",
        color="category",
        size=[12] * len(upcoming_df),
        hover_data=["role", "cgpa_criteria", "deadline"],
        labels={"deadline_dt": "Deadline Date", "company_name": "Company", "category": "Category"},
        title="Timeline of Pending Deadlines (Sorted chronologically)"
    )
    fig_timeline.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.2)"),
        yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.2)"),
    )
    st.plotly_chart(fig_timeline, use_container_width=True)
else:
    st.info("🎉 No upcoming deadlines to show on the timeline.")


# --- SECTION 5: Recent Uploads ---
st.divider()
with st.expander("📥 Recent Uploads (Last 5 files processed)", expanded=True):
    recent_df = df.sort_values("created_dt", ascending=False).head(5).copy()
    recent_df["deadline"] = recent_df["deadline_dt"].dt.strftime("%d %b %Y")
    recent_df["created_at"] = recent_df["created_dt"].dt.strftime("%d %b %Y %H:%M")
    
    recent_display = recent_df[
        [
            "company_name",
            "role",
            "category",
            "deadline",
            "source_type",
            "created_at",
        ]
    ].rename(
        columns={
            "company_name": "Company",
            "role": "Role",
            "category": "Category",
            "deadline": "Deadline",
            "source_type": "Source Type",
            "created_at": "Extracted At",
        }
    )
    st.dataframe(
        recent_display,
        use_container_width=True,
        hide_index=True,
    )


# --- SECTION 6 & 7: Main Table with Status Color Coding ---
st.divider()
st.subheader("📋 All Filtered Deadlines")

# Format deadline column for display
df_display = df.copy()
df_display["deadline_str"] = df_display["deadline_dt"].dt.strftime("%d %b %Y")

display_df = df_display[
    [
        "company_name",
        "role",
        "category",
        "deadline_str",
        "status",
        "Days Remaining",
    ]
].rename(
    columns={
        "company_name": "Company",
        "role": "Role",
        "category": "Category",
        "deadline_str": "Deadline",
        "status": "Status",
    }
)

# Apply limit configuration
display_df = display_df.head(limit)

# Color coding styling for the status column
def style_status_column(val):
    val_lower = str(val).lower()
    if val_lower in ("completed", "applied"):
        return "color: #00e676; font-weight: bold;"
    elif val_lower == "upcoming":
        return "color: #fbc02d; font-weight: bold;"
    elif val_lower == "expired":
        return "color: #ff1744; font-weight: bold;"
    return ""

styled_display_df = display_df.style.map(style_status_column, subset=["Status"])

st.dataframe(
    styled_display_df,
    use_container_width=True,
    hide_index=True,
)