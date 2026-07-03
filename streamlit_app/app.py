from datetime import datetime

import pandas as pd
import streamlit as st

from api import get_deadlines, get_health

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