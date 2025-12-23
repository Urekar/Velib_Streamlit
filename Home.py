import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# ----------------------------------------------------
# Configuration Streamlit
# ----------------------------------------------------
st.set_page_config(page_title="Vélibstat", layout="wide")
st.title("Vélibstat 🚲")

# ----------------------------------------------------
# Présentation
# ----------------------------------------------------
st.markdown("""
Bienvenue sur **Vélibstat** !  

Explorez en temps réel l'état des stations Vélib' à Paris grâce aux données ouvertes de l’API Velib Metropole.  
Découvrez combien de stations sont opérationnelles, combien de vélos mécaniques ou électriques sont disponibles, et où vous pouvez trouver une place libre pour vos trajets.  

Les chiffres ci-dessous sont mis à jour automatiquement, et la carte vous montre l'emplacement exact de chaque station.  

Les données proviennent de l'[API ouverte Vélib’](https://www.velib-metropole.fr/donnees-open-data-gbfs-du-service-velib-metropole).
""")


# ----------------------------------------------------
# Récupération des données station_status.json
# ----------------------------------------------------
URL_status = "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_status.json"
response = requests.get(URL_status)
data = response.json()
stations = data["data"]["stations"]
df = pd.DataFrame(stations)

# Extraction vélos mécaniques / électriques
def extract_bike_types(x):
    if isinstance(x, list) and len(x) > 0 and isinstance(x[0], dict):
        return {
            "vélo_mécanique_disponible": x[0].get("mechanical", None),
            "vélo_électrique_disponible": x[1].get("ebike", None),
        }
    return {"vélo_mécanique_disponible": None, "vélo_électrique_disponible": None}

bike_types_df = df["num_bikes_available_types"].apply(extract_bike_types).apply(pd.Series)
df = pd.concat([df.drop(columns=["num_bikes_available_types"]), bike_types_df], axis=1)
df = df.drop(columns=["station_opening_hours","numBikesAvailable","numDocksAvailable"])

# Statistiques principales
nb_bikes_available = df["num_bikes_available"].sum()
nb_mechanical_available = df["vélo_mécanique_disponible"].sum()
nb_ebike_available = df["vélo_électrique_disponible"].sum()
nb_docks_available = df["num_docks_available"].sum()
nb_stations = df["station_id"].nunique()
nb_stations_available = df.loc[df["is_installed"] == 1, "station_id"].nunique()
refresh = datetime.fromtimestamp(data["lastUpdatedOther"])

# ----------------------------------------------------
# Récupération des données station_information.json
# ----------------------------------------------------
URL_info = "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_information.json"
response_info = requests.get(URL_info)
data_info = response_info.json()
stations_info = data_info["data"]["stations"]
df_info = pd.DataFrame(stations_info)
df_info = df_info.drop(columns=["station_opening_hours","rental_methods"])
capacité_totale = df_info["capacity"].sum()

# ----------------------------------------------------
# Section indicateurs
# ----------------------------------------------------
st.subheader("📊 Indicateurs principaux")
st.markdown(f"**Dernière mise à jour des données:** {refresh}")

cols = st.columns(7)
cols[0].metric("📍 Nombre total de stations", nb_stations)
cols[1].metric("🚦 Stations en service", nb_stations_available)
cols[2].metric("🏋️‍♂️ Nombre total d’emplacements", capacité_totale)
cols[3].metric("🅿️ Emplacements libres", nb_docks_available)
cols[4].metric("🚲 Vélos disponibles", nb_bikes_available)
cols[5].metric("⚙️ Vélos mécaniques", nb_mechanical_available)
cols[6].metric("🔋 Vélos électriques", nb_ebike_available)

# ----------------------------------------------------
# Section carte
# ----------------------------------------------------
st.subheader("🗺️ Carte des stations")
st.map(df_info, zoom=10)

# ----------------------------------------------------
# Section tableaux
# ----------------------------------------------------
st.subheader("📋 Informations détaillées - Velib API")

cols_table = st.columns(2)
with cols_table[0]:
    st.dataframe(df, use_container_width=True)
with cols_table[1]:
    st.dataframe(df_info, use_container_width=True)

# ----------------------------------------------------
# Sidebar
# ----------------------------------------------------
st.sidebar.title("❄️ Snowflake Cheatsheet 📄")
st.sidebar.caption("Créé par un [Amateur Pas Doué](https://www.linkedin.com/in/siavash-yasini/)")

with st.sidebar.expander("Voir mes autres applications Streamlit"):
    st.caption("streamliTissues: [App](https://tissues.streamlit.app/) 🎈")
    st.caption("Sophisticated Palette: [App](https://sophisticated-palette.streamlit.app/) 🎈,  [Blog Post](https://blog.streamlit.io/create-a-color-palette-from-any-image/) 📝")
    st.caption("Wordler: [App](https://wordler.streamlit.app/) 🎈,  [Blog Post](https://blog.streamlit.io/the-ultimate-wordle-cheat-sheet/) 📝")
    st.caption("Koffee of the World: [App](https://koffee.streamlit.app/) 🎈")





