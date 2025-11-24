import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import matplotlib.pyplot as plt

import requests

import streamlit as st
import math
import time
import threading

lock = threading.Lock()
telescope_colors = {
    # Space telescopes (blue–purple tones)
    "JWST": "#3B4CC0",          # deep blue
    "HST": "#5E61D1",           # violet-blue
    "Kepler": "#7B77E5",        # medium purple
    "Spitzer": "#A48CF0",       # light lavender
    "TESS": "#C6A8FF",          # pale purple

    # Ground telescopes (green–orange tones)
    "VLT": "#1B9E77",           # teal green
    "Gemini": "#66A856",  # medium green
    "CFHT": "#A6D854",          # light green
    "ESO 3.6": "#F6C141",       # warm yellow-orange
    "Keck": "#E66101",          # orange
}
def safe_append(sheet, rows):
    with lock:  # ensure only one write at a time
        try:
            sheet.append_rows(rows)
        except Exception as e:
            st.error(f"Error writing to sheet: {e}")
            time.sleep(2)

if "delete_trigger" not in st.session_state:
    st.session_state.delete_trigger = 0  # used to force rerun on delete
st.set_page_config(page_title="Institute Travel CO2", layout="wide")
st.title("🔭 Institute-Wide CO2 Emissions from Observing 🔭")
st.text("On this webpage, we will calculate the CO2 emissions from our telescope use. Here you input all of the new observations you took this year.\
 You will pick a telescope and enter how long your observation was. Once you have added all of your observations be sure to submit them!")

# --- Google Sheets connection ---
SHEET_KEY = "1iKFaS57XbMItrd4IyNfe5uADxeZq2ZTBaf2dT3zFbQU"
def connect_to_gsheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_KEY).sheet1

@st.cache_data(ttl=5)
def load_all_records():
    sheet = connect_to_gsheet()
    return pd.DataFrame(sheet.get_all_records())
sheet = connect_to_gsheet()

if "trips_df" not in st.session_state:
    st.session_state.trips_df = pd.DataFrame(columns=["Telescope", "Hours"])

# --- Add trips form ---
with st.form("add_trip_form"):
    col1, col2, col3, col4 = st.columns([3,3,1,2])
    with col1:
        from_loc = st.selectbox("Choose a Telescope",['JWST','HST','Kepler','Spitzer','TESS','VLT','Gemini','CFHT','ESO 3.6','Keck'])
    with col2:
        to_loc = st.text_input("Hours of Observation: ")

    
    submitted = st.form_submit_button("Add Observation")
    if submitted:
        st.session_state.trips_df = pd.concat([
            st.session_state.trips_df,
            pd.DataFrame([{"Telescope": from_loc, "Hours": to_loc,}])
        ], ignore_index=True)

# --- Display and delete trips ---
if not st.session_state.trips_df.empty:
    st.subheader("Your Observations:")
    for i, row in st.session_state.trips_df.iterrows():
        cols = st.columns([3, 3, 1, 2, 1])
        cols[0].write("Telescope: "+row["Telescope"])
        cols[1].write("Hours of Observation: "+row["Hours"])
        if cols[4].button("🗑️", key=f"delete_{i}"):
            st.session_state.trips_df.drop(i, inplace=True)
            st.session_state.trips_df.reset_index(drop=True, inplace=True)
            st.session_state.delete_trigger += 1  # force rerun
            st.rerun()
else:
    st.info("No observations added yet.")

co2_factors = {
    "JWST": 13.69863014,
    "HST": 4.185692542,
    "Kepler": 0.9236197592,
    "Spitzer": 1.116928552,
    "TESS": 0.4392465753,
    "VLT": 6.160445205,
    "Gemini": 1.110502283,
    "CFHT": 0.9701940639,
    "ESO 3.6": 0.9087671233,
    "Keck": 0.375,
}
# --- Function to calculate CO₂ per row ---
def co2_from_obs(row):
    tel = row['Telescope']
    hour = float(row['Hours'])
    co2_rate = co2_factors.get(tel)
    return pd.Series([float(hour*co2_rate)])

# --- Submit new trips ---
if st.button("Submit Your Observations", key="submit_obs"):
    if st.session_state.trips_df.empty:
        st.warning("Please add at least one observation before submitting!")
    else:
        timestamp = datetime.now().isoformat()
        
        df = st.session_state.trips_df.copy()
        df[['CO2_tonnes']]  = df.apply(co2_from_obs, axis=1)
        df["Timestamp"] = timestamp 

        rows = df[["Timestamp","Telescope","Hours","CO2_tonnes"]].values.tolist()
        safe_append(sheet, rows)

        st.success("✅ Observations submitted! Your CO2 contribution is "+str(round(df["CO2_tonnes"].sum(),2))+" tonnes. For reference, the average Canadian has a contribution of 14.87 CO2 tonnes/year. To reach the goals set by the Paris Agreement of limiting warming to 2 degrees Celsius, the global average yearly emissions per capita should be 3.3 tonnes CO2 by 2030.")
        

        # Clear local trips
        st.session_state.trips_df = pd.DataFrame(columns=["Timestamp", "Telescope", "Hours", "CO2_tonnes"])


# --- Fetch all data from Google Sheet for plotting ---
all_records = load_all_records()
if not all_records.empty:
    co2_per_role = all_records.groupby("Telescope")["CO2_tonnes"].sum().reset_index()
    # Define which telescopes are space vs ground
    space_telescopes = {"JWST", "HST", "Kepler", "Spitzer", "TESS"}
    ground_telescopes = {"VLT", "Gemini", "CFHT", "ESO 3.6", "Keck"}

    # Add a 'type' column
    co2_per_role["type"] = co2_per_role["Telescope"].apply(
        lambda x: "Space" if x in space_telescopes else "Ground"
    )

    # Sort: space first, then ground
    co2_per_role = co2_per_role.sort_values("type")

    # Generate colors
    colors = [telescope_colors.get(t, "gray") for t in co2_per_role["Telescope"]]

    # --- Create subplots ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Bar chart
    axes[0].bar(co2_per_role["Telescope"], co2_per_role["CO2_tonnes"], color=colors)
    axes[0].set_ylabel("CO₂ Emissions (tonnes)")
    axes[0].set_title("Total CO₂ per Telescope (Bar Chart)")
    axes[0].tick_params(axis='x', rotation=45)

    # Pie chart
    axes[1].pie(
        co2_per_role["CO2_tonnes"],
        labels=co2_per_role["Telescope"],
        colors=colors,
        startangle=45,
        counterclock=False
    )
    axes[1].set_title("CO₂ Emission Share per Telescope")

    plt.tight_layout()
    st.pyplot(fig, use_container_width=True)
else:
    st.info("No observations submitted yet.")