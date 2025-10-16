import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.title("🌍 Institute Travel CO₂ Awareness App")

# --- Streamlit Google Sheets connection ---
SHEET_KEY = "1Zc4THpM4lFkQ2jOmi5mbn_U0eqHK3DBgLF86qH-JCms"  # The part of your Sheet URL between /d/ and /edit

@st.cache_resource
def connect_to_gsheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_KEY).sheet1
    return sheet

sheet = connect_to_gsheet()

# --- Form inputs ---
role = st.selectbox("Your role", ["Professor", "Postdoc", "Grad Student", "Staff"])
flights_europe = st.number_input("How many times have you flown to Europe?", min_value=0, step=1)
flights_usa = st.number_input("How many times have you flown to USA?", min_value=0, step=1)

st.header("Trips within Europe")
eu_trips = st.data_editor(pd.DataFrame(columns=["From", "To", "Mode"]), num_rows="dynamic", key="eu_trips")

st.header("Trips within Canada")
ca_trips = st.data_editor(pd.DataFrame(columns=["From", "To", "Mode"]), num_rows="dynamic", key="ca_trips")

st.header("Trips within USA or non-flight travel")
us_trips = st.data_editor(pd.DataFrame(columns=["From", "To", "Mode"]), num_rows="dynamic", key="us_trips")

st.header("Other international trips")
other_trips = st.data_editor(pd.DataFrame(columns=["From", "To", "Mode"]), num_rows="dynamic", key="other_trips")

# --- Submit button ---
if st.button("Submit"):
    timestamp = datetime.now().isoformat()
    
    # Combine all trips
    combined_trips = pd.concat([
        eu_trips.assign(Region="Europe", Flights_Europe=flights_europe, Flights_USA=flights_usa),
        ca_trips.assign(Region="Canada", Flights_Europe=flights_europe, Flights_USA=flights_usa),
        us_trips.assign(Region="USA/Other", Flights_Europe=flights_europe, Flights_USA=flights_usa),
        other_trips.assign(Region="Other International", Flights_Europe=flights_europe, Flights_USA=flights_usa)
    ], ignore_index=True)
    
    # Add Role and Timestamp
    combined_trips["Role"] = role
    combined_trips["Timestamp"] = timestamp

    # --- Write to Google Sheet ---
    # Convert DataFrame to list of lists
    rows = combined_trips[["Timestamp", "Role", "Flights_Europe", "Flights_USA", "Region", "From", "To", "Mode"]].values.tolist()
    sheet.append_rows(rows)
    
    st.success("✅ Your travel data has been submitted!")
    st.write(combined_trips)
