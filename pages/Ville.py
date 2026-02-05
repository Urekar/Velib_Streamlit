import json
import pandas as pd
import streamlit as st
from shapely.geometry import shape, Point
import requests
from datetime import datetime

# ----------------------------------------------------
# Streamlit page config
# ----------------------------------------------------
st.set_page_config(page_title="Velib Stats - Departements & Villes")
st.title("Velib Stats - Departements & Villes")
st.set_page_config(page_title="Velib",layout="wide")

# ----------------------------------------------------
# Sidebar
# ----------------------------------------------------
st.sidebar.title("🚲 Vélibstat")
st.sidebar.caption("Créé par [Nicolas](https://www.linkedin.com/in/nicolas-bouttier/)")

# ----------------------------------------------------
# Charger la géolocalisation des communes
# ----------------------------------------------------
with open("./geo-limit/communes.json") as f:
    communes_data = json.load(f)

# Créer un dictionnaire avec les polygones par département
departements_polys = {}
for entry in communes_data:
    # Si l'entrée est une liste, on itère sur ses éléments
    communes_list = entry if isinstance(entry, list) else [entry]

    for commune in communes_list:
        if not isinstance(commune, dict):
            st.warning(f"Entrée invalide : {commune}")
            continue

        departement = commune.get("departement")
        if not departement:
            st.warning(f"Pas de département pour la commune {commune.get('nom', 'Inconnu')}")
            continue

        dep_code = departement.get("code")
        dep_name = departement.get("nom", "Inconnu")

        try:
            poly = shape(commune["contour"])
            departements_polys.setdefault(dep_code, []).append(poly)
        except Exception as e:
            st.warning(f"Erreur création polygone pour {commune['nom']}: {e}")

# Créer un dictionnaire avec les polygones par ville
villes_polys = {}
for entry in communes_data:
    communes_list = entry if isinstance(entry, list) else [entry]

    for commune in communes_list:
        if not isinstance(commune, dict):
            continue

        nom_commune = commune.get("nom")
        if not nom_commune:
            continue

        try:
            poly = shape(commune["contour"])
            villes_polys.setdefault(nom_commune, []).append(poly)
        except Exception as e:
            st.warning(f"Erreur création polygone pour {nom_commune}: {e}")

# ----------------------------------------------------
# Charger les données Vélib
# ----------------------------------------------------
# Status
URL_status = "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_status.json"
data_status = requests.get(URL_status).json()
df_status = pd.DataFrame(data_status["data"]["stations"])

# Extraction ebike / mechanical
def extract_bike_types(x):
    if isinstance(x, list) and len(x) > 0 and isinstance(x[0], dict):
        return {
            "mechanical_available": x[0].get("mechanical", 0),
            "ebike_available": x[1].get("ebike", 0) if len(x) > 1 else 0
        }
    return {"mechanical_available": 0, "ebike_available": 0}

bike_types_df = df_status["num_bikes_available_types"].apply(extract_bike_types).apply(pd.Series)
df_status = pd.concat([df_status.drop(columns=["num_bikes_available_types"]), bike_types_df], axis=1)

# Supprimer colonnes inutiles
df_status = df_status.drop(columns=["station_opening_hours","numBikesAvailable","numDocksAvailable"], errors='ignore')

# Information stations
URL_info = "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_information.json"
data_info = requests.get(URL_info).json()
df_info = pd.DataFrame(data_info["data"]["stations"])
df_info = df_info.drop(columns=["station_opening_hours","rental_methods"], errors='ignore')

# Merge info + status
df = df_status.merge(df_info, on="station_id", suffixes=("_status","_info"))


# ----------------------------------------------------
# Fonction pour trouver le département d'une station
# ----------------------------------------------------
def find_location(lon, lat):
    point = Point(lon, lat)
    
    # Chercher le département
    dep_code = None
    for code, polys in departements_polys.items():
        if any(p.contains(point) for p in polys):
            dep_code = code
            break
    
    # Chercher la ville
    ville_name = None
    for ville, polys in villes_polys.items():
        if any(p.contains(point) for p in polys):
            ville_name = ville
            break
    
    return dep_code, ville_name

# Appliquer sur ton DataFrame
df[["departement_code", "ville"]] = df.apply(
    lambda r: find_location(r["lon"], r["lat"]),
    axis=1,
    result_type="expand"
)

# Filtrer uniquement les stations non localisées
stations_non_localisees = df[df["departement_code"].isna() | df["ville"].isna()]

if not stations_non_localisees.empty:
    st.warning(f"{len(stations_non_localisees)} stations n'ont pas pu être associées à un département ou une ville")
    st.dataframe(stations_non_localisees, use_container_width=True)


# ----------------------------------------------------
# Calcul des métriques par département
# ----------------------------------------------------

metrics = df.groupby("departement_code").agg(
    total_stations=("station_id", "count"),
    working_stations=("is_installed", lambda x: (x==1).sum()),
    total_bikes=("num_bikes_available", "sum"),
    mechanical_bikes=("mechanical_available", "sum"),
    ebikes=("ebike_available", "sum"),
    total_docks=("capacity", "sum")
).reset_index()

# ----------------------------------------------------
# Affichage Streamlit
# ----------------------------------------------------
st.markdown(f"**Dernière mise à jour API Vélib:** {datetime.fromtimestamp(data_status.get('lastUpdatedOther', 0))}")

# Départements
dep_labels = ["75 - Paris", "92 - Hauts-de-Seine", "93 - Seine-Saint-Denis", "94 - Val-de-Marne", "95 - Val-d'Oise"]
dep_values = ["75", "92", "93", "94", "95"]

# Création des onglets pour les départements
tabs = st.tabs(dep_labels)

for tab, dep_code, dep_label in zip(tabs, dep_values, dep_labels):
    with tab:
        villes_unique = df[df["departement_code"]==dep_code]["ville"].unique()
        #On ordonne les noms de villes
        villes_unique = sorted(
            villes_unique, 
            key=lambda x: int(''.join(filter(str.isdigit, x))) if any(c.isdigit() for c in x) else 0
            )
        villes_options = ["Toutes les villes"] + list(villes_unique)
        
        selected_city = st.selectbox(
            f"Filtrez une ville (optionnel)",
            options=villes_options
        )

        # Filtrer les stations selon le département et éventuellement la ville
        stations_filtrees = df[df["departement_code"]==dep_code]
        if selected_city != "Toutes les villes":
            stations_filtrees = stations_filtrees[stations_filtrees["ville"]==selected_city]

        # Affichage de la carte
        st.map(stations_filtrees, zoom=11, use_container_width=True)

        # Calculer les métriques sur le sous-ensemble
        if not stations_filtrees.empty:
            cols = st.columns(3)
            with cols[0]:
                st.metric("📍 Nombre de Stations", len(stations_filtrees))
                st.metric("🚲 Total Bikes", stations_filtrees["num_bikes_available"].sum())
            with cols[1]:
                st.metric("🚦 Stations en service", (stations_filtrees["is_installed"]==1).sum())
                st.metric("⚙️ Mechanical Bikes", stations_filtrees["mechanical_available"].sum())
            with cols[2]:
                st.metric("🅿️ Docks Totaux", stations_filtrees["capacity"].sum())
                st.metric("🔋 E-Bikes", stations_filtrees["ebike_available"].sum())
        else:
            st.warning(f"Aucune donnée pour {selected_city if selected_city != 'Toutes les villes' else dep_label}")

