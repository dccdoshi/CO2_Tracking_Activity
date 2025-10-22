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
from opencage.geocoder import OpenCageGeocode



key = "59e60896938b4c4b995925c68d07845c"  # Replace this with your real key
geocoder = OpenCageGeocode(key)

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
    "Halifax": (44.648618, -63.5859487),
    "Geneva": (46.2044, 6.1432),
    "Grenoble": (45.1885, 5.7245),
    "La Serena": (-29.9045, -71.2489),
    "Amsterdam": (52.3676, 4.9041),
    "Hamilton": (43.2557, -79.8711),
    "Madrid": (40.4168, -3.7038),
    "Munich": (48.1351, 11.5820),
    "Lyon": (45.7640, 4.8357),
    "Nice": (43.7102, 7.2620),
    "Marseille": (43.2965, 5.3698),
    "Anchorage": (61.2181, -149.9003)
}

# --- Function to calculate CO₂ per row ---
def calc_co2(row):
    A = city_coords.get(row["From"])
    B = city_coords.get(row["To"])

    if A is None or B is None:
        try:
            if A is None:
                result = geocoder.geocode(row["From"])[0]
                lat, lon = result['geometry']['lat'], result['geometry']['lng']
                A = (lat, lon)

            if B is None:
                result = geocoder.geocode(row["To"])[0]
                lat, lon = result['geometry']['lat'], result['geometry']['lng']
                A = (lat, lon)
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

        st.success("✅ Trips submitted! Your CO2 contribution is "+str(df["CO2_kg"])+"kg")
        

        # Clear local trips
        st.session_state.trips_df = pd.DataFrame(columns=["From", "To", "Roundtrip", "Mode"])


# --- Fetch all data from Google Sheet for plotting ---
all_records = pd.DataFrame(sheet.get_all_records())
all_records['count'] = (
    all_records.groupby(['From', 'To','Mode'])['To']
      .transform('count')
)
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

    linestyles = {'Plane': '-', 'Train': '--', 'Bus': ':', 'Car': ':'}

    fig = plt.figure(figsize=(24, 12))
    ax = plt.axes(projection=ccrs.Robinson())
    ax.set_global()
    ax.add_feature(cfeature.LAND, facecolor='honeydew')
    ax.add_feature(cfeature.OCEAN, facecolor='azure')
    ax.add_feature(cfeature.COASTLINE)
    ax.add_feature(cfeature.BORDERS, linestyle=':',color='black')
    ax.gridlines(draw_labels=False)

    geod = Geod(ellps="WGS84")

    for idx, row in all_records.iterrows():

        A = city_coords.get(row["From"])
        B = city_coords.get(row["To"])
        if A is None or B is None:
            try:
                if A is None:
                    result = geocoder.geocode(row["From"])[0]
                    lat, lon = result['geometry']['lat'], result['geometry']['lng']
                    A = (lat, lon)

                if B is None:
                    result = geocoder.geocode(row["To"])[0]
                    lat, lon = result['geometry']['lat'], result['geometry']['lng']
                    B = (lat, lon)
            except:
                st.warning("The city entered is mispelled, please try again!")

        

        # Create intermediate points
        npts = 50
        intermediate = geod.npts(A[1], A[0], B[1], B[0], npts)
        arc_lons = [A[1]] + [p[0] for p in intermediate] + [B[1]]
        arc_lats = [A[0]] + [p[1] for p in intermediate] + [B[0]]

        color = role_colors.get(row["Role"], "black")

        # Plot arc
        ax.plot(arc_lons, arc_lats, transform=ccrs.Geodetic(), color=color, alpha=0.5,lw=row['count']*4,ls=linestyles[row['Mode']])
        # Plot endpoints
        ax.plot(A[1], A[0], 'o', transform=ccrs.Geodetic(), color=color)
        ax.plot(B[1], B[0], 'o', transform=ccrs.Geodetic(), color=color)


    st.pyplot(fig,bbox_inches='tight',width='stretch')

    # Ensure CO2_kg column exists
    if "CO2_kg" not in all_records.columns:
        all_records["CO2_kg"] = all_records.apply(calc_co2, axis=1)
    co2_per_role = all_records.groupby("Role")["CO2_kg"].sum().reset_index()

    # --- Create subplots ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    colors = [role_colors.get(role, "gray") for role in co2_per_role["Role"]]

    # Bar chart
    axes[0].bar(co2_per_role["Role"], co2_per_role["CO2_kg"], color=colors)
    axes[0].set_ylabel("CO₂ Emissions (kg)")
    axes[0].set_title("Total CO₂ per Role (Bar Chart)")
    axes[0].tick_params(axis='x', rotation=45)

    # Pie chart
    axes[1].pie(
        co2_per_role["CO2_kg"],
        labels=co2_per_role["Role"],
        autopct="%1.1f%%",
        colors=colors,
        startangle=90,
        counterclock=False
    )
    axes[1].set_title("CO₂ Emission Share per Role (Pie Chart)")

    plt.tight_layout()
    st.pyplot(fig, use_container_width=True)
else:
    st.info("No trips submitted yet.")

