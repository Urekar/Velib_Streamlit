import streamlit as st
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

# ----------------------------------------------------
# BigQuery client
# ----------------------------------------------------
key_path = "/home/nicolas/Streamlit-app/gcp_sa_key/streamlit-to-gcp-sa.json"
credentials = service_account.Credentials.from_service_account_file(key_path)
client = bigquery.Client(
    credentials=credentials,
    project=credentials.project_id
)

# ----------------------------------------------------
# Page config
# ----------------------------------------------------
st.set_page_config(page_title="Velib – Top vélos", layout="wide")
st.title("Velib – Top vélos")

# ----------------------------------------------------
# Horizon de période et pills
# ----------------------------------------------------
horizon_map = {
    "Jour N-1": 1,
    "7 jours": 7,
    "14 jours": 14
}

periode_label = st.pills("Choisir la période", options=list(horizon_map.keys()), default="Jour N-1")
days = horizon_map[periode_label]

# ----------------------------------------------------
# Chargement des trajets et stations
# ----------------------------------------------------
@st.cache_data(ttl=12*60*60)
def load_trips(days):
    query = f"""
    SELECT
        bike_id,
        start_station_id,
        end_station_id,
        start_time,
        end_time,
        duration_min,
        distance_km
    FROM `projet-velib-474009.velib_bronze.fact_velib_trips`
    WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
    """
    return client.query(query).to_dataframe()

@st.cache_data(ttl=12*60*60)
def load_dim_station():
    query = """
    SELECT station_id, station_name, latitude, longitude
    FROM `projet-velib-474009.velib_bronze.dim_station`
    """
    return client.query(query).to_dataframe()

df_trips = load_trips(days)
df_dim_station = load_dim_station()

# ----------------------------------------------------
# Ajouter noms et coordonnées des stations
# ----------------------------------------------------
df_trips = df_trips.merge(
    df_dim_station.rename(columns={
        "station_id": "start_station_id",
        "station_name": "start_station_name",
        "latitude": "start_lat",
        "longitude": "start_lon"
    }), on="start_station_id", how="left"
)

df_trips = df_trips.merge(
    df_dim_station.rename(columns={
        "station_id": "end_station_id",
        "station_name": "end_station_name",
        "latitude": "end_lat",
        "longitude": "end_lon"
    }), on="end_station_id", how="left"
)

# ----------------------------------------------------
# Top vélo par nombre de trajets
# ----------------------------------------------------
trips_per_bike = df_trips.groupby("bike_id").size().reset_index(name="nb_trips")
top_bike_trips = trips_per_bike.sort_values("nb_trips", ascending=False).iloc[0]

# ----------------------------------------------------
# Trajet le plus long en km
# ----------------------------------------------------
df_longest_trip = df_trips.sort_values("distance_km", ascending=False).iloc[0]

# ----------------------------------------------------
# Fonction pour afficher une section avec fond foncé
# ----------------------------------------------------
def display_dark_section(title, content):
    st.markdown(f"""
        <div style="
            background-color: #1f2937; 
            color: #ffffff;             
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
        ">
            <div style="font-weight:bold; font-size:16px; margin-bottom:10px;">{title}</div>
            <div>{content}</div>
        </div>
    """, unsafe_allow_html=True)


# ----------------------------------------------------
# Affichage empilé
# ----------------------------------------------------
content_top_trips = f"""
Vélo ID: {top_bike_trips['bike_id']}<br>
Nombre de trajets: {top_bike_trips['nb_trips']}
"""
display_dark_section("Vélo avec le plus de trajets", content_top_trips)

content_longest_trip = f"""
Vélo ID: {df_longest_trip['bike_id']}<br>
Distance: {df_longest_trip['distance_km']} km<br>
Durée: {df_longest_trip['duration_min']} minutes<br>
Départ: {df_longest_trip['start_station_name']} à {df_longest_trip['start_time']}<br>
Arrivée: {df_longest_trip['end_station_name']} à {df_longest_trip['end_time']}
"""
display_dark_section("Trajet le plus long (en km)", content_longest_trip)

# ----------------------------------------------------
# Map du trajet le plus long
# ----------------------------------------------------
map_data = pd.DataFrame([
    {"lat": df_longest_trip['start_lat'], "lon": df_longest_trip['start_lon'], "station": "Départ"},
    {"lat": df_longest_trip['end_lat'], "lon": df_longest_trip['end_lon'], "station": "Arrivée"}
])
st.map(map_data)

