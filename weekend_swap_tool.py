import streamlit as st
import pandas as pd
from datetime import datetime

# --- PASSWORD PROTECTION ---
def check_password():
    """Returns True if the user had the correct password."""
    def password_entered():
        if st.session_state["password"] == st.secrets["PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Enter residency password to access the tool:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Enter residency password to access the tool:", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    else:
        return True

if not check_password():
    st.stop()

# --- STREAMLIT UI SETUP & ROLE SELECTION ---
st.set_page_config(page_title="Weekend Swap Finder", page_icon="🏥")
st.title("🏥 Weekend Swap Finder")

role = st.radio("Select Your PGY Level:", ["Intern (PGY-1)", "Senior (PGY-2 / PGY-3)"], horizontal=True)

# Assign files based on selected role
if role == "Intern (PGY-1)":
    matrix_file = "clean_schedule_matrix.csv"
    weekend_file = "weekend_coverage_schedule.csv"
else:
    matrix_file = "senior_schedule_matrix.csv"
    weekend_file = "senior_weekend_coverage_schedule.csv"

# --- DATA LOADING ---
@st.cache_data
def load_data(m_file, w_file):
    rotation_matrix = pd.read_csv(m_file)
    weekend_coverage = pd.read_csv(w_file)
    
    rotation_matrix["Resident"] = rotation_matrix["Resident"].astype(str).str.strip()
    weekend_coverage["Date"] = weekend_coverage["Date"].astype(str).str.strip()
    weekend_coverage["Scheduled_Coverage"] = weekend_coverage["Scheduled_Coverage"].astype(str).str.strip()
    
    return rotation_matrix, weekend_coverage

rotation_data, weekend_coverage = load_data(matrix_file, weekend_file)

# --- DATE PARSING ---
block_intervals = []
for col in rotation_data.columns:
    if col == "Resident": continue
    try:
        start_str, end_str = col.split("-")
        s_m, s_d = map(int, start_str.strip().split("/"))
        e_m, e_d = map(int, end_str.strip().split("/"))
        s_yr = 2026 if s_m >= 7 else 2027
        e_yr = 2026 if e_m >= 7 else 2027
        block_intervals.append({"column": col, "start": datetime(s_yr, s_m, s_d), "end": datetime(e_yr, e_m, e_d)})
    except Exception: continue

def get_block_column_for_date(target_date_str):
    try:
        target_dt = pd.to_datetime(target_date_str)
        for interval in block_intervals:
            if interval["start"] <= target_dt <= interval["end"]:
                return interval["column"]
    except: return None
    return None

def is_resident_scheduled(coverage_str, target_name):
    names_list = [name.strip().lower() for name in str(coverage_str).split(",")]
    return target_name.lower() in names_list

def is_working(resident_name, check_date_str):
    shift_df = weekend_coverage[weekend_coverage["Date"] == check_date_str]
    if shift_df.empty: return False
    return is_resident_scheduled(shift_df.iloc[0]["Scheduled_Coverage"], resident_name)

# --- MAIN APP LOGIC ---
resident_list = sorted(rotation_data["Resident"].tolist())
resident_input = st.selectbox(f"Select your last name ({role}):", resident_list)

user_scheduled_shifts = weekend_coverage[
    weekend_coverage["Scheduled_Coverage"].apply(lambda x: is_resident_scheduled(x, resident_input))
]
user_dates = sorted(user_scheduled_shifts["Date"].tolist())

if user_dates:
    with st.form(key="swap_search_form"):
        date_input = st.selectbox("Select the weekend date you need to swap out of:", user_dates)
        submit_button = st.form_submit_button(label="🔄 Search Eligible Swappers")
        
    if submit_button:
        target_date_dt = pd.to_datetime(date_input)
        my_block_col = get_block_column_for_date(date_input)
        
        st.write(f"Searching for **mutually eligible** partners to swap {date_input} (Your Block: {my_block_col}).")
        
        eligible_matches = []
        my_row = rotation_data[rotation_data["Resident"] == resident_input].iloc[0]
        
        for _, row in rotation_data.iterrows():
            co_resident = row["Resident"]
            if co_resident == resident_input: continue
            
            # 1. Partner must be on Elective during YOUR shift date
            if row[my_block_col] != "Elective": continue
            
            # 2. Partner MUST NOT be working your shift date already
            if is_working(co_resident, date_input): continue

            # Check all their shifts
            co_resident_shifts = weekend_coverage[
                weekend_coverage["Scheduled_Coverage"].apply(lambda x: is_resident_scheduled(x, co_resident))
            ]
            
            for _, shift in co_resident_shifts.iterrows():
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
                        "Partner": co_resident,
                        "Date_to_Swap": partner_date,
                        "Your_Status": "Elective",
                        "Their_Status": "Elective"
                    })
        
        if eligible_matches:
            st.success(f"✅ Found {len(eligible_matches)} clean reciprocal swap opportunities:")
            st.table(pd.DataFrame(eligible_matches))
        else:
            st.warning("No reciprocal swaps found where both parties are free to cover the other.")
else:
    st.info(f"🎉 **{resident_input}** is not scheduled for any floor coverage weekends!")
