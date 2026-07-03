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


# SIDEBAR

with st.sidebar:

    st.title("Deadline Sentinel AI")

    st.divider()

    if get_health():
        st.success("🟢 Backend Online")
    else:
        st.error("🔴 Backend Offline")

    st.divider()

    if st.button("🔄 Refresh Dashboard"):
        st.rerun()

# FETCH

with st.spinner("Loading deadlines..."):

    try:
        deadlines = get_deadlines()

    except Exception as e:
        st.error(f"Could not connect to backend.\n\n{e}")
        st.stop()

# EMPTY STATE

if not deadlines:

    st.info("No deadlines found.")

    st.stop()




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


col1, col2, col3, col4 = st.columns(4)

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

col1.metric("Total Deadlines", total)
col2.metric("Upcoming", upcoming)
col3.metric("Completed", completed)
col4.metric("Expired", expired)