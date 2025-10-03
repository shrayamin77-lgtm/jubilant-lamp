import streamlit as st
import pandas as pd
from datetime import datetime

@st.cache_data
def load_data():
    rotation_data = pd.read_csv("rotation_schedule.csv")
    weekend_coverage = pd.read_csv("weekend_coverage_cleaned.csv")
    return rotation_data, weekend_coverage

rotation_data, weekend_coverage = load_data()

# Extract block dates from header
block_date_ranges = rotation_data.iloc[0, 1:]
block_start_dates = [datetime.strptime(d.split("-")[0], "%m/%d/%y") for d in block_date_ranges]
block_end_dates = [datetime.strptime(d.split("-")[1], "%m/%d/%y") for d in block_date_ranges]
rotation_data = rotation_data.iloc[1:]  # remove date header row
rotation_data = rotation_data.rename(columns={"Unnamed: 0": "Resident"})

def find_block_for_date(date_str):
    date_obj = datetime.strptime(date_str, "%m/%d/%y")
    for i, (start, end) in enumerate(zip(block_start_dates, block_end_dates)):
        if start <= date_obj <= end:
            return i
    return None

def is_on_elective(resident_name, date_str):
    block_num = find_block_for_date(date_str)
    if block_num is None:
        return False
    row = rotation_data[rotation_data["Resident"].str.lower() == resident_name.lower()]
    if row.empty:
        return False
    block_col = f"Block {block_num + 1}"
    return str(row[block_col].values[0]).strip().lower() == "elective"

st.title("🏥 Weekend Swap Finder")

resident_input = st.selectbox("Select your name:", rotation_data["Resident"].tolist())
date_input = st.selectbox("Select the weekend date you're scheduled for:", weekend_coverage["Date"].tolist())

if st.button("🔄 Find Swap Options"):
    eligible = []
    for name in rotation_data["Resident"]:
        if name != resident_input and is_on_elective(name, date_input):
            # Find what date that person is currently scheduled
            for col in ["Day 1", "Night 1", "Night 2"]:
                match = weekend_coverage[weekend_coverage[col].astype(str).str.lower() == name.lower()]
                if not match.empty:
                    scheduled_date = match.iloc[0]["Date"]
                    eligible.append(f"{name} (Scheduled: {scheduled_date})")
                    break
            else:
                eligible.append(f"{name} (Not currently scheduled)")
    
    if eligible:
        st.success(f"✅ You can swap with the following residents for {date_input}:")
        for entry in eligible:
            st.markdown(f"- {entry}")
    else:
        st.warning("No eligible residents available for swap on that date.")
