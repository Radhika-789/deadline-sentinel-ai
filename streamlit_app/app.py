from datetime import datetime

import pandas as pd
import streamlit as st

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
                
                st.session_state.upload_success = f"Successfully parsed and saved: {result.get('company_name', 'Unknown Company')} - {result.get('role', 'Unknown Role') or 'Opportunity'}"
                
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

        deadlines = get_deadlines(
            company_name=company_name or None,
            category=category or None,
            status=status or None,
            deadline_from=deadline_from,
            deadline_to=deadline_to,
            skip=0,
            limit=limit,
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


def days_remaining(deadline):

    deadline = pd.to_datetime(
        deadline,
        format="mixed",
        errors="coerce",
    )

    if pd.isna(deadline):
        return "-"

    return (deadline.date() - datetime.now().date()).days


df["Days Remaining"] = df["deadline"].apply(days_remaining)

today = datetime.now().date()

deadline_dates = pd.to_datetime(
    df["deadline"],
    format="mixed",
    errors="coerce",
)

upcoming = (deadline_dates.dt.date >= today).sum()

expired = (deadline_dates.dt.date < today).sum()

completed = (
    df["status"]
    .astype(str)
    .str.lower()
    .eq("completed")
).sum()

total = len(df)


# Metrics


st.divider()
st.subheader("Dashboard Overview")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Total Deadlines", total)
col2.metric("Upcoming", upcoming)
col3.metric("Completed", completed)
col4.metric("Expired", expired)


# Table


st.divider()
st.subheader("All Deadlines")

df["deadline"] = (
    pd.to_datetime(
        df["deadline"],
        format="mixed",
        errors="coerce",
    )
    .dt.strftime("%d %b %Y")
)

display_df = df[
    [
        "company_name",
        "role",
        "category",
        "deadline",
        "status",
        "Days Remaining",
    ]
].rename(
    columns={
        "company_name": "Company",
        "role": "Role",
        "category": "Category",
        "deadline": "Deadline",
        "status": "Status",
    }
)

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
)