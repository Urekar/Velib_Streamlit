import pandas as pd
import streamlit as st
import requests
from datetime import timedelta
from google.cloud import bigquery
from google.oauth2 import service_account
import pytz

# ----------------------------------------------------
# Streamlit page config
# ----------------------------------------------------
st.set_page_config(page_title="Velib Stats - Station", layout="wide")
st.title("Velib Stats - Station")

# ----------------------------------------------------
# Charger les données Vélib temps réel (API)
# ----------------------------------------------------
URL_status = "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_status.json"
data_status = requests.get(URL_status).json()
df_status = pd.DataFrame(data_status["data"]["stations"])

def extract_bike_types(x):
    mechanical = 0
    ebike = 0
    if isinstance(x, list):
        for item in x:
            if isinstance(item, dict):
                mechanical += item.get("mechanical", 0)
                ebike += item.get("ebike", 0)
    return {"mechanical_available": mechanical, "ebike_available": ebike}

bike_types_df = df_status["num_bikes_available_types"].apply(extract_bike_types).apply(pd.Series)
df_status = pd.concat([df_status.drop(columns=["num_bikes_available_types"]), bike_types_df], axis=1)
df_status = df_status.drop(columns=["station_opening_hours", "numBikesAvailable", "numDocksAvailable"], errors="ignore")

# ----------------------------------------------------
# Infos stations
# ----------------------------------------------------
URL_info = "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_information.json"
data_info = requests.get(URL_info).json()
df_info = pd.DataFrame(data_info["data"]["stations"])
df_info = df_info.drop(columns=["station_opening_hours", "rental_methods"], errors="ignore")

# Merge info + status
df = df_status.merge(df_info, on="station_id", suffixes=("_status", "_info"))

# ----------------------------------------------------
# Sélection station
# ----------------------------------------------------
station_names = ["Toutes les stations"] + sorted(df["name"].unique())
selected_station = st.selectbox("Sélectionnez une station", options=station_names)

if selected_station != "Toutes les stations":
    df_filtered = df[df["name"] == selected_station].copy()
else:
    df_filtered = df.copy()

# ----------------------------------------------------
# INDICATEURS TEMPS RÉEL (API)
# ----------------------------------------------------
st.subheader("Indicateurs temps réel")

total_mechanical = int(df_filtered["mechanical_available"].sum())
total_ebike = int(df_filtered["ebike_available"].sum())
total_capacity = int(df_filtered["capacity"].sum())
free_docks = max(total_capacity - total_mechanical - total_ebike, 0)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("🚲 Vélos mécaniques", total_mechanical)
with col2:
    st.metric("⚡ Vélos électriques", total_ebike)
with col3:
    st.metric("🅿️ Bornes libres", f"{free_docks} / {total_capacity}")

# ----------------------------------------------------
# Carte
# ----------------------------------------------------
st.map(df_filtered, zoom=11, use_container_width=True)

# ----------------------------------------------------
# Client BigQuery
# ----------------------------------------------------
key_path = "/home/nicolas/Streamlit-app/gcp_sa_key/streamlit-to-gcp-sa.json"
credentials = service_account.Credentials.from_service_account_file(key_path)
client = bigquery.Client(credentials=credentials, project=credentials.project_id)

# ----------------------------------------------------
# Filtre temporel
# ----------------------------------------------------
st.header("Filtre temporel")
horizon_map = {"Jour N-1":1, "7 derniers jours":7}

periode_label = st.pills("Choisir la période", options=list(horizon_map.keys()), default="Jour N-1")
days = horizon_map[periode_label]

utc = pytz.UTC
today = pd.Timestamp.now(tz=utc).normalize()
start_date = today - timedelta(days=days)

# ----------------------------------------------------
# Query par station + période
# ----------------------------------------------------
@st.cache_data(ttl=1800, show_spinner="Chargement historique BigQuery…")
def load_station_history(station_id: int, days: int):
    query = f"""
    SELECT 
        file_date, 
        nb_bike,
        nb_ebike,
        nb_bike_blocked_to_collect,
        nb_bike_blocked_to_fix
    FROM `projet-velib-474009.velib_bronze.fact_station_status`
    WHERE station_id = {station_id}
      AND file_date >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
    ORDER BY file_date
    """
    df = client.query(query).to_dataframe()
    df = df.sort_values("file_date").set_index("file_date")
    return df

if selected_station != "Toutes les stations":
    station_id = df_filtered["stationCode_info"].iloc[0]
    df_bg = load_station_history(station_id, days)
else:
    df_bg = pd.DataFrame()  # vide si toutes les stations

# ----------------------------------------------------
# Graphiques
# ----------------------------------------------------
st.header("Évolution des vélos libres")
if selected_station != "Toutes les stations":
    if not df_bg.empty:
        st.line_chart(
            df_bg[["nb_bike","nb_ebike"]].rename(
                columns={"nb_bike":"Mécaniques libres","nb_ebike":"Électriques libres"}
            )
        )
    else:
        st.warning("Aucune donnée disponible pour cette période ou station.")
else:
    st.info("Sélectionnez une station pour afficher le graphique.")

# ----------------------------------------------------
# Graphiques vélos à réparer / à enlever avec sous-titre par graphique
# ----------------------------------------------------
st.header("Vélos à réparer / à enlever")
if selected_station != "Toutes les stations":
    if not df_bg.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Vélos à réparer")
            st.line_chart(df_bg["nb_bike_blocked_to_fix"])
        with col2:
            st.subheader("Vélos à enlever")
            st.line_chart(df_bg["nb_bike_blocked_to_collect"])
    else:
        st.warning("Aucune donnée disponible pour cette période ou station.")
else:
    st.info("Sélectionnez une station pour afficher ces graphiques.")
