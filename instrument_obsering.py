import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from pyproj import Geod
import requests

import streamlit as st
import plotly.graph_objects as go
import math
import time
import threading

lock = threading.Lock()

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
st.title("Institute-Wide CO2 Emissions from Travel")

# --- Role selection ---
role = st.selectbox("Your Role", ["Professor", "Postdoc", "Grad Student", "Staff"])

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

if "trips_df" not in st.session_state:
    st.session_state.trips_df = pd.DataFrame(columns=["Telescope", "Hours"])

# --- Add trips form ---
with st.form("add_trip_form"):
    col1, col2, col3, col4 = st.columns([3,3,1,2])
    with col1:
        from_loc = st.selectbox("Choose a Telescope",['ESO 3.6m'])
    with col2:
        to_loc = st.text_input("Hours: ")

    
    submitted = st.form_submit_button("Add Trip")
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
        cols[0].write("From: "+row["Telescope"])
        cols[1].write("To: "+row["Hours"])
        if cols[4].button("🗑️", key=f"delete_{i}"):
            st.session_state.trips_df.drop(i, inplace=True)
            st.session_state.trips_df.reset_index(drop=True, inplace=True)
            st.session_state.delete_trigger += 1  # force rerun
            st.rerun()
else:
    st.info("No trips added yet.")