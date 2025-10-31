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
import requests
from geopy.geocoders import Nominatim
import streamlit as st
import plotly.graph_objects as go

# --- Inject CSS for fullscreen style ---

geolocator = Nominatim(user_agent="travel_app")


def get_city_coords(city):
    # Try Photon first
    try:
        url = f"https://photon.komoot.io/api/?q={city}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data["features"]:
                lat = data["features"][0]["geometry"]["coordinates"][1]
                lon = data["features"][0]["geometry"]["coordinates"][0]
                return lat, lon
    except:
        pass
    
    # Fallback to Nominatim
    try:
        location = geolocator.geocode(city)
        if location:
            return location.latitude, location.longitude
    except:
        pass

    return None


st.set_page_config(page_title="Institute Travel CO2", layout="wide")
st.title("Institute-Wide CO2 Emissions from Travel")

# --- Role selection ---
role = st.selectbox("Your Role", ["Professor", "Postdoc", "Grad Student", "Staff"])

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
    "Anchorage": (61.2181, -149.9003),
    "Laval": (45.5571125, -73.7211779),
    "Saint-Alexis-des-Monts": (46.462694, -73.143196),
    "Trois-Rivières": (46.3432325, -72.5428485),
    "Sherbrooke":(45.403271, -71.889038)
}

# --- Function to calculate CO₂ per row ---
def calc_co2(row):
    A = city_coords.get(row["From"])
    B = city_coords.get(row["To"])

    if A is None or B is None:
        if A is None:
            lat, lon = get_city_coords(row["From"])#result['geometry']['lat'], result['geometry']['lng']
            A = (lat, lon)

        if B is None:
            lat, lon = get_city_coords(row["From"])
            B = (lat, lon)
        if A is None or B is None:
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

        st.success("✅ Trips submitted! Your CO2 contribution is "+str(round(df["CO2_kg"].values[0],2))+"kg")
        

        # Clear local trips
        st.session_state.trips_df = pd.DataFrame(columns=["From", "To", "Roundtrip", "Mode"])


# --- Fetch all data from Google Sheet for plotting ---
all_records = pd.DataFrame(sheet.get_all_records())
all_records['count'] = (
    all_records.groupby(['From', 'To','Mode'])['To']
      .transform('count')
)
total_co2 = sum(all_records["CO2_kg"])
st.metric("Total CO₂ Emitted (kg)", f"{total_co2:,.0f}")

if not all_records.empty:

    geod = Geod(ellps="WGS84")

    # Role colors
    role_colors = {
        "Professor": "#E74C3C",    # red
        "Postdoc": "#3498DB",      # blue
        "Grad Student": "#27AE60", # green
        "Staff": "#E67E22"         # orange
    }

    # Mode line styles
    linestyles = {
        "Plane": "solid",
        "Train": "dash",
        "Bus": "dot",
        "Car": "dashdot"
    }

    fig = go.Figure()

    # --- Add legend entries manually for roles ---
    for role, color in role_colors.items():
        fig.add_trace(go.Scattergeo(
            lon=[None], lat=[None],
            mode="lines",
            line=dict(color=color, width=4),
            name=f"{role}",
            hoverinfo="none"
        ))

    # --- Add legend entries manually for modes ---
    for mode, dash in linestyles.items():
        fig.add_trace(go.Scattergeo(
            lon=[None], lat=[None],
            mode="lines",
            line=dict(color="#555555", width=3, dash=dash),
            name=f"{mode}",
            hoverinfo="none"
        ))

    for idx, row in all_records.iterrows():

        A = city_coords.get(row["From"])
        B = city_coords.get(row["To"])
        if A is None or B is None:
            try:
                if A is None:
                    lat, lon = get_city_coords(row["From"])
                    A = (lat, lon)

                if B is None:
                    lat, lon = get_city_coords(row["To"])
                    B = (lat, lon)
            except:
                st.warning("The city entered is mispelled, please try again!")

        

        # Create intermediate points
        npts = 50
        intermediate = geod.npts(A[1], A[0], B[1], B[0], npts)
        arc_lons = [A[1]] + [p[0] for p in intermediate] + [B[1]]
        arc_lats = [A[0]] + [p[1] for p in intermediate] + [B[0]]

        color = role_colors.get(row["Role"], "gray")
        width = max(1, row["count"] * 1.5)

        fig.add_trace(go.Scattergeo(
            lon=arc_lons,
            lat=arc_lats,
            mode="lines",
            line=dict(width=width, color=color, dash=linestyles.get(row["Mode"], "solid")),
            opacity=0.65,
            hoverinfo="text",
            text=f"<b>{row['From']} → {row['To']}</b><br>{row['Role']} via {row['Mode']}<br>{row['count']} trip(s)",
            showlegend = False
        ))

        # Endpoints
        fig.add_trace(go.Scattergeo(
            lon=[A[1], B[1]],
            lat=[A[0], B[0]],
            mode="markers",
            marker=dict(size=5, color=color, line=dict(width=1, color="white")),
            hoverinfo="text",
            text=[f"{row['From']} ({row['Role']})", f"{row['To']} ({row['Role']})"],
            showlegend=False
        ))

    # --- Layout ---
    fig.update_layout(
        geo=dict(
            projection_type="natural earth",
            showland=True,
            landcolor="#F5F5F5",
            showocean=True,
            oceancolor="#DCEFFF",
            showcountries=True,
            countrycolor="rgba(100,100,100,0.5)",
            bgcolor="#FFFFFF",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=0.01,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="#DDD",
            borderwidth=1,
            font=dict(size=13)
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=800,
        autosize=True,
        template="plotly_white"
    )

    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

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

