import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from geopy.distance import geodesic
import matplotlib.pyplot as plt
from geopy.geocoders import Nominatim


st.title("🌍 Institute Travel CO₂ Awareness App")

# --- Role selection ---
role = st.selectbox("Your role", ["Professor", "Postdoc", "Grad Student", "Staff"])

# --- Google Sheets connection ---
SHEET_KEY = "1Zc4THpM4lFkQ2jOmi5mbn_U0eqHK3DBgLF86qH-JCms"

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

# --- Initialize trip dataframe ---
if "trips_df" not in st.session_state:
    st.session_state.trips_df = pd.DataFrame(columns=["From", "To", "Roundtrip", "Mode"])

# --- Add trips form ---
with st.form("add_trip_form"):
    col1, col2, col3, col4 = st.columns([3,3,1,2])
    with col1:
        from_loc = st.text_input("From")
    with col2:
        to_loc = st.text_input("To")
    with col3:
        roundtrip = st.checkbox("Roundtrip")
    with col4:
        mode = st.selectbox("Mode", ["Plane", "Train", "Car", "Bus"])
    
    submitted = st.form_submit_button("Add Trip")
    if submitted:
        st.session_state.trips_df = pd.concat([
            st.session_state.trips_df,
            pd.DataFrame([{"From": from_loc, "To": to_loc, "Roundtrip": roundtrip, "Mode": mode}])
        ], ignore_index=True)

st.subheader("Trips added (this session)")
st.dataframe(st.session_state.trips_df)

# --- CO₂ factors ---
co2_factors = {
    "Plane": 0.254,
    "Train": 0.02,
    "Car": 0.2,
    "Bus": 0.07
}

# --- Function to calculate CO₂ per row ---
def calc_co2(row):
    try:
        geolocator = Nominatim(user_agent="city_distance_app")

        # Get city coordinates
        city1 = geolocator.geocode(row["From"])
        city2 = geolocator.geocode(row["To"])

        # Extract latitude and longitude
        coords_1 = (city1.latitude, city1.longitude)
        coords_2 = (city2.latitude, city2.longitude)

        # Calculate distance (in kilometers)
        distance = geodesic(coords_1, coords_2).kilometers
    except:
        st.warning("The city entered is mispelled, please try again!")  # fallback if geopy can't resolve
    if row["Roundtrip"]:
        distance *= 2
    co2_rate = co2_factors.get(row["Mode"])
    if distance>1000 and row["Mode"]=="Plane":
        co2_rate = 0.1
    return distance * co2_rate

# --- Fetch all data from Google Sheet for plotting ---
all_records = pd.DataFrame(sheet.get_all_records())

if not all_records.empty:
    # Ensure CO2_kg column exists
    if "CO2_kg" not in all_records.columns:
        all_records["CO2_kg"] = all_records.apply(calc_co2, axis=1)
    co2_per_role = all_records.groupby("Role")["CO2_kg"].sum().reset_index()

    # Plot
    fig, ax = plt.subplots()
    ax.bar(co2_per_role["Role"], co2_per_role["CO2_kg"], color="skyblue")
    ax.set_ylabel("CO₂ Emissions (kg)")
    ax.set_title("Total CO₂ per Role (from all submissions)")
    st.pyplot(fig)
else:
    st.info("No trips submitted yet.")

# --- Submit new trips ---
if st.button("Submit all trips"):
    if st.session_state.trips_df.empty:
        st.warning("Please add at least one trip before submitting!")
    else:
        timestamp = datetime.now().isoformat()
        df = st.session_state.trips_df.copy()
        df["Role"] = role
        df["Timestamp"] = timestamp
        df["CO2_kg"] = df.apply(calc_co2, axis=1)

        rows = df[["Timestamp","Role","From","To","Roundtrip","Mode","CO2_kg"]].values.tolist()
        sheet.append_rows(rows)

        st.success("✅ Trips submitted!")

        # Clear local trips
        st.session_state.trips_df = pd.DataFrame(columns=["From", "To", "Roundtrip", "Mode"])

