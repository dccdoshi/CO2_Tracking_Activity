import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from geopy.distance import geodesic
import matplotlib.pyplot as plt
from geopy.geocoders import Nominatim
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from pyproj import Geod

st.set_page_config(page_title="Institute Travel CO2", layout="wide")
st.title("Institute-Wide CO2 Emissions from Travel")

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

city_coords = {
    "Santiago": (-33.4489, -70.6693),
    "Toronto": (43.6532, -79.3832),
    "Paris": (48.8566, 2.3522),
    "New York": (40.7128, -74.0060),
    "London": (51.5074, -0.1278),
    "Montreal": (45.5031824, -73.5698065),
    "Lisbon": (38.7077507, -9.1365919),
    "Porto": (41.1502195, -8.6103497),
    "Halifax": (44.648618, -63.5859487)
    # Add more cities as needed
}

# --- Function to calculate CO₂ per row ---
def calc_co2(row):
    geolocator = Nominatim(user_agent="travel_co2_app")
    A = city_coords.get(row["From"])
    B = city_coords.get(row["To"])

    if A is None or B is None:
        try:
            if A is None:
                loc_from = geolocator.geocode(row["From"])
                A = (loc_from.longitude, loc_from.latitude)

            if B is None:
                loc_to = geolocator.geocode(row["To"])
                B = (loc_to.longitude, loc_to.latitude)
        except:
            st.warning("The city entered is mispelled, please try again!")

    # Calculate distance (in kilometers)
    distance = geodesic(A, B).kilometers
    co2_rate = co2_factors.get(row["Mode"])
    if distance>1000 and row["Mode"]=="Plane":
        co2_rate = 0.1
    if row["Roundtrip"]:
        distance *= 2
    return distance * co2_rate

# --- Fetch all data from Google Sheet for plotting ---
all_records = pd.DataFrame(sheet.get_all_records())

if not all_records.empty:

    # Geolocator
    geolocator = Nominatim(user_agent="travel_co2_app")

    # Map colors per role
    role_colors = {
        "Professor": "red",
        "Postdoc": "blue",
        "Grad Student": "green",
        "Staff": "orange"
    }

    fig = plt.figure(figsize=(24, 12))
    ax = plt.axes(projection=ccrs.Robinson())
    ax.set_global()
    ax.add_feature(cfeature.LAND, facecolor='lightgrey')
    ax.add_feature(cfeature.OCEAN, facecolor='white')
    ax.add_feature(cfeature.COASTLINE)
    ax.add_feature(cfeature.BORDERS, linestyle=':')
    ax.gridlines(draw_labels=False)

    geod = Geod(ellps="WGS84")

    for idx, row in all_records.iterrows():

        A = city_coords.get(row["From"])
        B = city_coords.get(row["To"])
        print(A, B)
        if A is None or B is None:
            print("here", A, B)
            try:
                if A is None:
                    print("A is none")
                    loc_from = geolocator.geocode(row["From"])
                    A = (loc_from.longitude, loc_from.latitude)

                if B is None:
                    print("B is none",row["To"])
                    loc_to = geolocator.geocode("Cairo")
                    print(loc_to)
                    B = (loc_to.longitude, loc_to.latitude)
                    print(B)
            except:
                st.warning("The city entered is mispelled, please try again!")

        

        # Create intermediate points
        npts = 50
        intermediate = geod.npts(A[0], A[1], B[0], B[1], npts)
        arc_lons = [A[0]] + [p[0] for p in intermediate] + [B[0]]
        arc_lats = [A[1]] + [p[1] for p in intermediate] + [B[1]]

        color = role_colors.get(row["Role"], "black")

        # Plot arc
        ax.plot(arc_lons, arc_lats, transform=ccrs.Geodetic(), color=color, alpha=0.5,lw=4)
        # Plot endpoints
        ax.plot(A[0], A[1], 'o', transform=ccrs.Geodetic(), color=color)
        ax.plot(B[0], B[1], 'o', transform=ccrs.Geodetic(), color=color)


    st.pyplot(fig,bbox_inches='tight',use_container_width=True)

    # Ensure CO2_kg column exists
    if "CO2_kg" not in all_records.columns:
        all_records["CO2_kg"] = all_records.apply(calc_co2, axis=1)
    co2_per_role = all_records.groupby("Role")["CO2_kg"].sum().reset_index()

    # Plot
    fig, ax = plt.subplots(figsize=(10,10))
    ax.bar(co2_per_role["Role"], co2_per_role["CO2_kg"], color="skyblue")
    ax.set_ylabel("CO₂ Emissions (kg)")
    ax.set_title("Total CO₂ per Role (from all submissions)")
    st.pyplot(fig,use_container_width=False)
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

