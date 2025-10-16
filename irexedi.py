import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from geopy.distance import geodesic
import matplotlib.pyplot as plt

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
        mode = st.selectbox("Mode", ["Plane", "Train", "Car", "Bus", "Other"])
    
    submitted = st.form_submit_button("Add Trip")
    if submitted:
        st.session_state.trips_df = pd.concat([
            st.session_state.trips_df,
            pd.DataFrame([{"From": from_loc, "To": to_loc, "Roundtrip": roundtrip, "Mode": mode}])
        ], ignore_index=True)

st.subheader("Trips added")
st.dataframe(st.session_state.trips_df)

# --- CO₂ factors ---
co2_factors = {
    "Plane": 0.25,
    "Train": 0.05,
    "Car": 0.20,
    "Bus": 0.10,
    "Other": 0.15
}

# --- Submit all trips and calculate CO₂ ---
if st.button("Submit all trips"):
    if st.session_state.trips_df.empty:
        st.warning("Please add at least one trip before submitting!")
    else:
        timestamp = datetime.now().isoformat()
        df = st.session_state.trips_df.copy()
        df["Role"] = role
        df["Timestamp"] = timestamp

        # Calculate distances & CO₂
        def calc_co2(row):
            try:
                loc1 = geodesic(row["From"], row["To"]).km
            except:
                loc1 = 500  # fallback if geopy can't resolve
            distance = loc1
            if row["Roundtrip"]:
                distance *= 2
            return distance * co2_factors.get(row["Mode"], 0.15)

        df["CO2_kg"] = df.apply(calc_co2, axis=1)

        # Append rows to Google Sheet
        rows = df[["Timestamp","Role","From","To","Roundtrip","Mode","CO2_kg"]].values.tolist()
        sheet.append_rows(rows)

        st.success("✅ Trips submitted!")

        # --- Plot CO₂ per role ---
        all_data = pd.DataFrame(sheet.get_all_records())
        co2_per_role = all_data.groupby("Role")["CO2_kg"].sum().reset_index()

        fig, ax = plt.subplots()
        ax.bar(co2_per_role["Role"], co2_per_role["CO2_kg"], color="skyblue")
        ax.set_ylabel("CO₂ Emissions (kg)")
        ax.set_title("Total CO₂ per Role")
        st.pyplot(fig)

        # Clear local trips
        st.session_state.trips_df = pd.DataFrame(columns=["From", "To", "Roundtrip", "Mode"])
