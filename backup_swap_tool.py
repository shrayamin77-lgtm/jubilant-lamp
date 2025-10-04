import streamlit as st
import pandas as pd

# Load backup and rotation schedules
@st.cache_data
def load_data():
    backup_df = pd.read_csv("backup_schedule_final.csv")
    rotation_df = pd.read_csv("rotation_schedule.csv", index_col=0)
    return backup_df, rotation_df

backup_df, rotation_df = load_data()

# Build list of all backup assignments
assignments = []
for _, row in backup_df.iterrows():
    block = row['block']
    date = row['date']
    if pd.notna(row['1st Backup']):
        assignments.append({'Resident': row['1st Backup'], 'Block': block, 'Date': date})
    if pd.notna(row['2nd Backup']) and row['2nd Backup'] != '—':
        assignments.append({'Resident': row['2nd Backup'], 'Block': block, 'Date': date})

assignments_df = pd.DataFrame(assignments)

# Sidebar – select resident and block
st.sidebar.header("Backup Swap Finder")
resident = st.sidebar.selectbox("Select your name", sorted(assignments_df['Resident'].unique()))
resident_blocks = assignments_df[assignments_df['Resident'] == resident]['Block'].tolist()
selected_block = st.sidebar.selectbox("Select the block you want to swap out of", resident_blocks)

# Determine elective residents by block
elective_by_block = {
    int(block): set(rotation_df.columns[rotation_df.loc[:, str(block)] == "Elective"])
    for block in range(1, 27)
}

# Determine eligible swaps
def find_eligible_swaps(current_resident, current_block):
    eligible = []
    for _, row in assignments_df.iterrows():
        other_resident = row['Resident']
        other_block = row['Block']
        other_date = row['Date']

        if other_block == current_block:
            continue
        if current_resident not in elective_by_block.get(other_block, set()):
            continue
        if other_resident not in elective_by_block.get(current_block, set()):
            continue

        eligible.append({
            "Swap With": other_resident,
            "Their Block": other_block,
            "Their Block Dates": other_date
        })
    return pd.DataFrame(eligible)

# Display eligible swaps
st.title("🔄 Backup Block Swap Tool")
st.write(f"You're assigned as backup in **Block {selected_block}**.")
swaps_df = find_eligible_swaps(resident, selected_block)

if not swaps_df.empty:
    st.success("Here are your eligible swap options:")
    st.dataframe(swaps_df)
else:
    st.warning("No eligible swaps found for your selected block.")
