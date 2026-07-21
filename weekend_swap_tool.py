import streamlit as st
import pandas as pd
from datetime import datetime
import re

# --- SECURITY ---
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False
            
    if "password_correct" not in st.session_state:
        st.text_input("Enter residency password to access the tool:", type="password", on_change=password_entered, key="password")
        return False
    return st.session_state["password_correct"]

if not check_password():
    st.stop()

# --- APP HEADER & ROLE SELECTION ---
st.set_page_config(page_title="Weekend Shift Swap Tool", page_icon="📅")
st.title("📅 Weekend Shift Swap Tool")

role = st.radio("Select Your PGY Level:", ["Intern (PGY-1)", "Senior (PGY-2 / PGY-3)"], horizontal=True)

# Assign files based on selected role
if role == "Intern (PGY-1)":
    matrix_file = "clean_schedule_matrix.csv"
    weekend_file = "weekend_coverage_schedule.csv"
else:
    matrix_file = "senior_schedule_matrix.csv"
    weekend_file = "senior_weekend_coverage_schedule.csv"

# --- DATA LOADING & HARDENING ---
@st.cache_data
def load_data(m_file, w_file):
    try:
        matrix_df = pd.read_csv(m_file)
        matrix_df.columns = [str(c).strip() for c in matrix_df.columns]
        
        # Robust loader for weekend coverage schedule
        weekend_rows = []
        with open(w_file, 'r', encoding='utf-8-sig') as f:
            header = f.readline()
            for line in f:
                line = line.strip()
                if not line: 
                    continue
                parts = line.split(',', 1)
                if len(parts) == 2:
                    d_val = parts[0].strip()
                    cov_val = parts[1].strip()
                    names = [n.strip() for n in cov_val.split(',')]
                    for name in names:
                        if name:
                            weekend_rows.append({"Date": d_val, "Scheduled_Coverage": name})
                            
        weekend_df = pd.DataFrame(weekend_rows)
        return matrix_df, weekend_df
    except Exception as e:
        st.error(f"⚠️ Error loading CSV files for {role}. Please ensure all required CSVs are uploaded to GitHub.")
        st.stop()

matrix_df, weekend_df = load_data(matrix_file, weekend_file)

# --- HELPER FUNCTIONS ---
def parse_academic_date(date_str):
    """Safely converts date strings (with or without years) into accurate academic year dates."""
    try:
        clean_s = str(date_str).strip()
        parts = clean_s.split("/")
        month = int(parts[0])
        day = int(parts[1])
        
        if len(parts) == 3:
            year = int(parts[2])
            if year < 100:
                year += 2000
        else:
            year = 2026 if month >= 7 else 2027
            
        return datetime(year, month, day).date()
    except Exception:
        return None

def extract_date_range_from_col(col_name):
    """Extracts start and end dates from any column header string using regex."""
    dates = re.findall(r'\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b', str(col_name))
    if len(dates) >= 2:
        start_dt = parse_academic_date(dates[0])
        end_dt = parse_academic_date(dates[1])
        return start_dt, end_dt
    return None, None

def find_resident_col(df):
    """Automatically finds the resident name column in the matrix dataframe."""
    for col in df.columns:
        if any(keyword in col.lower() for keyword in ["resident", "name", "senior", "pgy"]):
            return col
    return df.columns[0]

def clean_tokens(name_str):
    """Extracts lowercase tokens ignoring punctuation."""
    return re.findall(r'[a-zA-Z]+', str(name_str).lower())

def is_same_resident(target, candidate):
    """Flexible matching between resident names and CSV entries."""
    t_tokens = clean_tokens(target)
    c_tokens = clean_tokens(candidate)
    
    if not t_tokens or not c_tokens:
        return False
        
    if t_tokens == c_tokens:
        return True
        
    if len(t_tokens) == 1 and t_tokens[0] in c_tokens:
        return True
    if len(c_tokens) == 1 and c_tokens[0] in t_tokens:
        return True
        
    if set(t_tokens) == set(c_tokens):
        return True
        
    if all(tok in c_tokens for tok in t_tokens) or all(tok in t_tokens for tok in c_tokens):
        return True
        
    return False

def get_rotation_for_date(resident_name, shift_date_str):
    """Determines what rotation block a resident is on during a given weekend shift date."""
    target_dt = parse_academic_date(shift_date_str)
    if not target_dt:
        return "Unknown"
        
    matching_col = None
    for col in matrix_df.columns:
        start_dt, end_dt = extract_date_range_from_col(col)
        if start_dt and end_dt and (start_dt <= target_dt <= end_dt):
            matching_col = col
            break

    if not matching_col:
        return "Unknown"

    res_col = find_resident_col(matrix_df)
    res_row = matrix_df[matrix_df[res_col].apply(lambda x: is_same_resident(resident_name, x))]
    if res_row.empty:
        return "Unknown"

    return str(res_row.iloc[0][matching_col]).strip()

def is_on_elective(resident_name, shift_date_str):
    """Verifies if resident is on Elective status on the target date."""
    rot = get_rotation_for_date(resident_name, shift_date_str)
    return rot.lower() == "elective"

# --- USER INTERFACE & SWAP LOGIC ---
st.write("Find residents to swap **weekend floor coverage shifts** with. Both residents must be on **Elective** during the shift dates.")

res_col_name = find_resident_col(matrix_df)
all_scheduled_residents = sorted(list(set(
    matrix_df[res_col_name].unique().tolist() + weekend_df["Scheduled_Coverage"].unique().tolist()
)))

selected_resident = st.selectbox(f"Select Your Last Name ({role}):", all_scheduled_residents)

# Find weekend dates assigned to selected resident
user_shifts = weekend_df[weekend_df["Scheduled_Coverage"].apply(lambda x: is_same_resident(selected_resident, x))]
user_dates = sorted(user_shifts["Date"].unique(), key=lambda x: parse_academic_date(x) or datetime.min.date())

if user_dates:
    selected_date = st.selectbox("Select the Weekend Shift Date You Need to Swap Out Of:", user_dates)
    
    # Verify user's rotation status on that date
    user_rot = get_rotation_for_date(selected_resident, selected_date)
    if user_rot.lower() != "elective":
        st.warning(f"⚠️ You are listed on **{user_rot}** during {selected_date}. Shift swaps typically require being on an Elective block.")

    if st.button("🔎 Search Weekend Shift Swaps"):
        eligible_swaps = []
        
        for _, row in weekend_df.iterrows():
            other_resident = str(row["Scheduled_Coverage"]).strip()
            other_date = str(row["Date"]).strip()
            
            # Skip self or same shift date
            if is_same_resident(other_resident, selected_resident) or other_date == selected_date:
                continue
                
            # Check reciprocal Elective status
            other_on_elective_for_my_date = is_on_elective(other_resident, selected_date)
            i_am_on_elective_for_their_date = is_on_elective(selected_resident, other_date)
            
            # Check if either resident is already working on the prospective swap date
            other_already_working_my_date = not weekend_df[
                (weekend_df["Date"] == selected_date) & 
                (weekend_df["Scheduled_Coverage"].apply(lambda x: is_same_resident(other_resident, x)))
            ].empty
            
            i_am_already_working_their_date = not weekend_df[
                (weekend_df["Date"] == other_date) & 
                (weekend_df["Scheduled_Coverage"].apply(lambda x: is_same_resident(selected_resident, x)))
            ].empty
            
            if other_on_elective_for_my_date and i_am_on_elective_for_their_date:
                if other_already_working_my_date or i_am_already_working_their_date:
                    status = "🔴 Shift Overlap / Conflict"
                    notes = "One resident is already working a floor shift on that date"
                else:
                    status = "🟢 Eligible Swap Partner"
                    notes = "Both on Elective & free of floor shifts"

                eligible_swaps.append({
                    "Status": status,
                    "Swap With": other_resident,
                    "Their Shift Date": other_date,
                    "Their Rotation": get_rotation_for_date(other_resident, other_date),
                    "Notes": notes
                })

        if eligible_swaps:
            df_swaps = pd.DataFrame(eligible_swaps).drop_duplicates()
            st.success(f"✅ Found {len(df_swaps)} possible weekend swap options for {selected_date}:")
            st.caption("🟢 **Green Dot:** Clear of floor shifts & verified on Elective. | 🔴 **Red Dot:** Elective verified, but has a shift overlap.")
            st.table(df_swaps)
        else:
            st.warning("No eligible reciprocal weekend swaps found for this shift date.")
else:
    st.info(f"No scheduled weekend floor shifts found for **{selected_resident}**.")
matrix_df, weekend_df = load_data(matrix_file, weekend_file)

# --- HELPER FUNCTIONS ---
def parse_academic_date(date_str):
    """Safely converts date strings (with or without years) into accurate academic year dates."""
    try:
        clean_s = str(date_str).strip()
        parts = clean_s.split("/")
        month = int(parts[0])
        day = int(parts[1])
        
        if len(parts) == 3:
            year = int(parts[2])
            if year < 100:
                year += 2000
        else:
            year = 2026 if month >= 7 else 2027
            
        return datetime(year, month, day).date()
    except Exception:
        return None

def is_same_resident(target, candidate):
    """Normalizes names to check equality regardless of spacing or periods."""
    t = re.sub(r'\s+', ' ', str(target).lower().replace(".", " ")).strip()
    c = re.sub(r'\s+', ' ', str(candidate).lower().replace(".", " ")).strip()
    return t == c

def get_rotation_for_date(resident_name, shift_date_str):
    """Determines what rotation block a resident is on during a given weekend shift date."""
    target_dt = parse_academic_date(shift_date_str)
    if not target_dt:
        return "Unknown"
        
    matching_col = None
    for col in matrix_df.columns:
        if col == "Resident": 
            continue
        try:
            # Handle standard hyphen '-', en-dash '–', or em-dash '—'
            normalized_col = col.replace("–", "-").replace("—", "-")
            col_parts = normalized_col.split("-")
            
            col_start = parse_academic_date(col_parts[0].strip())
            col_end = parse_academic_date(col_parts[1].strip())
            
            if col_start and col_end and (col_start <= target_dt <= col_end):
                matching_col = col
                break
        except Exception:
            continue

    if not matching_col:
        return "Unknown"

    res_row = matrix_df[matrix_df["Resident"].apply(lambda x: is_same_resident(x, resident_name))]
    if res_row.empty:
        return "Unknown"

    return str(res_row.iloc[0][matching_col]).strip()

def is_on_elective(resident_name, shift_date_str):
    """Verifies if resident is on Elective status on the target date."""
    rot = get_rotation_for_date(resident_name, shift_date_str)
    return rot.lower() == "elective"

# --- USER INTERFACE & SWAP LOGIC ---
st.write("Find residents to swap **weekend floor coverage shifts** with. Both residents must be on **Elective** during the shift dates.")

# Get list of residents who have scheduled weekend shifts
all_scheduled_residents = sorted(list(set(
    matrix_df["Resident"].unique().tolist() + weekend_df["Scheduled_Coverage"].unique().tolist()
)))

selected_resident = st.selectbox(f"Select Your Last Name ({role}):", all_scheduled_residents)

# Find weekend dates assigned to selected resident
user_shifts = weekend_df[weekend_df["Scheduled_Coverage"].apply(lambda x: is_same_resident(x, selected_resident))]
user_dates = sorted(user_shifts["Date"].unique(), key=lambda x: parse_academic_date(x) or datetime.min.date())

if user_dates:
    selected_date = st.selectbox("Select the Weekend Shift Date You Need to Swap Out Of:", user_dates)
    
    # Verify user's rotation status on that date
    user_rot = get_rotation_for_date(selected_resident, selected_date)
    if user_rot.lower() != "elective":
        st.warning(f"⚠️ You are listed on **{user_rot}** during {selected_date}. Shift swaps typically require being on an Elective block.")

    if st.button("🔎 Search Weekend Shift Swaps"):
        eligible_swaps = []
        
        for _, row in weekend_df.iterrows():
            other_resident = str(row["Scheduled_Coverage"]).strip()
            other_date = str(row["Date"]).strip()
            
            # Skip self or same shift date
            if is_same_resident(other_resident, selected_resident) or other_date == selected_date:
                continue
                
            # Check reciprocal Elective status
            other_on_elective_for_my_date = is_on_elective(other_resident, selected_date)
            i_am_on_elective_for_their_date = is_on_elective(selected_resident, other_date)
            
            # Check if either resident is already working on the prospective swap date
            other_already_working_my_date = not weekend_df[
                (weekend_df["Date"] == selected_date) & 
                (weekend_df["Scheduled_Coverage"].apply(lambda x: is_same_resident(x, other_resident)))
            ].empty
            
            i_am_already_working_their_date = not weekend_df[
                (weekend_df["Date"] == other_date) & 
                (weekend_df["Scheduled_Coverage"].apply(lambda x: is_same_resident(x, selected_resident)))
            ].empty
            
            if other_on_elective_for_my_date and i_am_on_elective_for_their_date:
                if other_already_working_my_date or i_am_already_working_their_date:
                    status = "🔴 Shift Overlap / Conflict"
                    notes = "One resident is already working a floor shift on that date"
                else:
                    status = "🟢 Eligible Swap Partner"
                    notes = "Both on Elective & free of floor shifts"

                eligible_swaps.append({
                    "Status": status,
                    "Swap With": other_resident,
                    "Their Shift Date": other_date,
                    "Their Rotation": get_rotation_for_date(other_resident, other_date),
                    "Notes": notes
                })

        if eligible_swaps:
            df_swaps = pd.DataFrame(eligible_swaps).drop_duplicates()
            st.success(f"✅ Found {len(df_swaps)} possible weekend swap options for {selected_date}:")
            st.caption("🟢 **Green Dot:** Clear of floor shifts & verified on Elective. | 🔴 **Red Dot:** Elective verified, but has a shift overlap.")
            st.table(df_swaps)
        else:
            st.warning("No eligible reciprocal weekend swaps found for this shift date.")
else:
    st.info(f"No scheduled weekend floor shifts found for **{selected_resident}**.")
