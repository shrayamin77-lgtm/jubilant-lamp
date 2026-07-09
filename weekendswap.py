import streamlit as st
import pandas as pd
from datetime import datetime

@st.cache_data
def load_data():
    rotation_matrix = pd.read_csv("clean_schedule_matrix.csv")
    weekend_coverage = pd.read_csv("weekend_coverage_schedule.csv")
    return rotation_matrix, weekend_coverage

rotation_data, weekend_coverage = load_data()

# --- PARSE DATE WINDOWS FROM THE MATRIX HEADERS ---
block_intervals = []
for col in rotation_data.columns:
    if col == "Resident":
        continue
    try:
        start_str, end_str = col.split("-")
        start_month, start_day = map(int, start_str.strip().split("/"))
        end_month, end_day = map(int, end_str.strip().split("/"))
        
        start_yr = 2026 if start_month >= 7 else 2027
        end_yr = 2026 if end_month >= 7 else 2027
        
        start_date = datetime(start_yr, start_month, start_day)
        end_date = datetime(end_yr, end_month, end_day)
        
        block_intervals.append({"column": col, "start": start_date, "end": end_date})
    except Exception:
        continue

def get_block_column_for_date(target_date_str):
    try:
        target_dt = datetime.strptime(target_date_str, "%m/%d/%Y")
    except ValueError:
        st.error(f"Date format error for {target_date_str}. Expected MM/DD/YYYY.")
        return None
        
    for interval in block_intervals:
        if interval["start"] <= target_dt <= interval["end"]:
            return interval["column"]
    return None

# --- STREAMLIT UI ---
st.set_page_config(page_title="Weekend Swap Finder", page_icon="🏥", layout="centered")
st.title("🏥 Weekend Swap Finder")

# Dropdown list displays clean last names
resident_list = sorted(rotation_data["Resident"].tolist())
resident_input = st.selectbox("Select your last name:", resident_list)

date_list = weekend_coverage["Date"].tolist()
date_input = st.selectbox("Select the weekend date you need to swap out of:", date_list)

if st.button("🔄 Search Eligible Swappers"):
    target_block_col = get_block_column_for_date(date_input)
    
    if not target_block_col:
        st.error("Could not map the selected weekend date to an academic block.")
    else:
        eligible_matches = []
        
        for _, row in rotation_data.iterrows():
            co_intern = row["Resident"]
            
            # Skip yourself
            if co_intern == resident_input:
                continue
                
            # Check if they are on an Elective block
            if row[target_block_col] == "Elective":
                
                # Check when this co-intern is scheduled to work floor shifts
                co_intern_shifts = weekend_coverage[
                    weekend_coverage["Scheduled_Coverage"].astype(str).str.lower().str.contains(co_intern.lower(), na=False)
                ]
                
                if not co_intern_shifts.empty:
                    shift_dates = co_intern_shifts["Date"].tolist()
                    formatted_dates = ", ".join(shift_dates)
                    eligible_matches.append(f"**{co_intern}** (Scheduled: {formatted_dates})")
                else:
                    eligible_matches.append(f"**{co_intern}** (Not working any floor weekends)")
        
        st.markdown("---")
        if eligible_matches:
            st.success(f"✅ **{len(eligible_matches)} potential swap options found** for {date_input} (Block: {target_block_col}):")
            for match in eligible_matches:
                st.markdown(f"- {match}")
        else:
            st.warning(f"No co-interns are currently on an Elective block during the {target_block_col} window.")