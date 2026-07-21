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

# 1. Select Resident Name
resident_list = sorted(rotation_data["Resident"].tolist())
resident_input = st.selectbox("Select your last name:", resident_list)

# 2. DYNAMICALLY FILTER THE DATES FOR THE SELECTED RESIDENT
# Filter rows where the selected last name appears in the Scheduled_Coverage column
user_scheduled_shifts = weekend_coverage[
    weekend_coverage["Scheduled_Coverage"].astype(str).str.lower().str.contains(resident_input.lower(), na=False)
]
user_dates = user_scheduled_shifts["Date"].tolist()

# 3. Date Dropdown - dynamically switches options based on name selection
if user_dates:
    date_input = st.selectbox("Select the weekend date you need to swap out of:", user_dates)
    
    if submit_button:
        target_date_dt = pd.to_datetime(date_input)
        my_block_col = get_block_column_for_date(date_input)
        
        st.write(f"Searching for **mutually eligible** partners to swap {date_input} (Your Block: {my_block_col}).")
        
        eligible_matches = []
        my_row = rotation_data[rotation_data["Resident"] == resident_input].iloc[0]
        
        # Helper to check if a specific resident is working on a specific date
        def is_working(resident_name, check_date_str):
            shift_df = weekend_coverage[weekend_coverage["Date"] == check_date_str]
            if shift_df.empty: return False
            coverage_list = [n.strip().lower() for n in str(shift_df.iloc[0]["Scheduled_Coverage"]).split(",")]
            return resident_name.lower() in coverage_list

        for _, row in rotation_data.iterrows():
            co_intern = row["Resident"]
            if co_intern == resident_input: continue
            
            # 1. Partner must be on Elective during YOUR shift date
            if row[my_block_col] != "Elective": continue
            
            # 2. Partner MUST NOT be working your shift date already
            if is_working(co_intern, date_input): continue

            # Check all their shifts
            co_intern_shifts = weekend_coverage[
                weekend_coverage["Scheduled_Coverage"].apply(lambda x: is_resident_scheduled(x, co_intern))
            ]
            
            for _, shift in co_intern_shifts.iterrows():
                partner_date = shift["Date"]
                partner_date_dt = pd.to_datetime(partner_date)
                
                if partner_date_dt <= target_date_dt: continue
                
                partner_block_col = get_block_column_for_date(partner_date)
                if not partner_block_col: continue
                
                # 3. YOU must be on Elective during THEIR shift date
                i_am_elective_for_partner = my_row[partner_block_col] == "Elective"
                
                # 4. YOU must not already be working their shift date
                i_am_already_working = is_working(resident_input, partner_date)
                
                if i_am_elective_for_partner and not i_am_already_working:
                    eligible_matches.append({
                        "Partner": co_intern,
                        "Date_to_Swap": partner_date,
                        "Your_Status": "Elective",
                        "Their_Status": "Elective"
                    })
        
        if eligible_matches:
            st.success(f"✅ Found {len(eligible_matches)} clean reciprocal swap opportunities:")
            df_results = pd.DataFrame(eligible_matches)
            st.table(df_results)
        else:
            st.warning("No reciprocal swaps found where both parties are free to cover the other.")
