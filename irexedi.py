import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from google.oauth2.service_account import Credentials
import gspread
import plotly.express as px
import time

# --- Streamlit page setup ---
st.set_page_config(page_title="Institute Travel CO₂ Awareness", layout="wide")
st.title("🌍 Institute Travel CO₂ Awareness App")

st.write("""
This tool estimates and visualizes the CO₂ emissions from our work-related travel.  
Fill in your trip details below — results update collectively for everyone in real time!
""")

# --- Google Sheets connection setup ---
SHEET_NAME = "Institute_CO2_Travel_Data"

@st.cache_resource
def connect_to_gsheet():
    # Load Google Cloud credentials from Streamlit secrets (see setup instructions below)
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    return sheet

sheet = connect_to_gsheet()

# --- Emission factors (kg CO₂ per passenger-km) ---
factors = {
    "Flight (short <1000 km)": 0.255,
    "Flight (long >1000 km)": 0.150,
    "Train": 0.041,
    "Car (solo)": 0.192,
    "Bus": 0.105,
    "Remote (virtual)": 0.001,
}

# --- Helper functions ---
geolocator = Nominatim(user_agent="co2_app")

@st.cache_data(show_spinner=False)
def get_coords(city):
    loc = geolocator.geocode(city)
    return (loc.latitude, loc.longitude) if loc else (None, None)

def calc_distance(from_city, to_city):
    f_latlon = get_coords(from_city)
    t_latlon = get_coords(to_city)
    if None in f_latlon or None in t_latlon:
        return None
    return geodesic(f_latlon, t_latlon).km

# --- Input form ---
st.header("✈️ Add your trip")

with st.form("trip_form"):
    name = st.text_input("Your name (optional)")
    from_city = st.text_input("Departure city")
    to_city = st.text_input("Destination city")
    mode = st.selectbox("Travel mode", list(factors.keys()))
    round_trip = st.checkbox("Round trip?", value=True)
    trips = st.number_input("Number of trips per year", 1, 50, 1)
    submitted = st.form_submit_button("Add Trip")

    if submitted and from_city and to_city:
        dist = calc_distance(from_city, to_city)
        if dist:
            factor = factors[mode]
            dist_adj = dist * (2 if round_trip else 1)
            total = dist_adj * factor * trips
            new_row = [
                name or "Anonymous",
                from_city,
                to_city,
                mode,
                "Yes" if round_trip else "No",
                trips,
                round(dist_adj, 1),
                round(total, 1),
                time.strftime("%Y-%m-%d %H:%M:%S")
            ]
            sheet.append_row(new_row)
            st.success(f"Added! {round(total,1)} kg CO₂ for this route.")
        else:
            st.warning("Could not find one or both cities — please check spelling.")

# --- Display results ---
st.header("📊 Current Results")

data = pd.DataFrame(sheet.get_all_records())

if len(data) == 0:
    st.info("No trips added yet.")
else:
    st.dataframe(data, use_container_width=True)

    total_co2 = data["Total_CO2_kg"].sum()
    st.metric("Total institute CO₂ emissions (kg)", f"{total_co2:,.1f}")

    # Summaries
    mode_summary = data.groupby("Mode")["Total_CO2_kg"].sum().reset_index()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Emissions by Travel Mode")
        fig1 = px.bar(mode_summary, x="Mode", y="Total_CO2_kg", color="Mode",
                      title="CO₂ Emissions by Travel Mode", text_auto=".0f")
        st.plotly_chart(fig1, use_container_width=True)
    with col2:
        st.subheader("Mode Breakdown")
        fig2 = px.pie(mode_summary, values="Total_CO2_kg", names="Mode", title="Share of Total Emissions")
        st.plotly_chart(fig2, use_container_width=True)

# --- Download results ---
st.download_button(
    label="⬇️ Download data as CSV",
    data=data.to_csv(index=False).encode("utf-8"),
    file_name="institute_travel_emissions.csv",
    mime="text/csv"
)
