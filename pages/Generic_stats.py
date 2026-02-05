import pandas as pd
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account
from datetime import timedelta
import pytz

# ====================================================
# CONFIG STREAMLIT
# ====================================================
st.set_page_config(
    page_title="Vélibstat – Indicateurs",
    layout="wide"
)

st.title("Vélibstat – Tableau de bord des trajets")
st.caption(
    "Données issues de l’open data "
    "[Vélib Métropole](https://www.velib-metropole.fr/donnees-open-data-gbfs-du-service-velib-metropole)"
)

# ====================================================
# BIGQUERY CLIENT
# ====================================================

credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"]
)
client = bigquery.Client(
    credentials=credentials,
    project=credentials.project_id
)

# ====================================================
# LOAD DATA – 30 DERNIERS JOURS
# ====================================================
@st.cache_data(ttl=24 * 60 * 60)
def load_data():
    query = """
        SELECT
            bike_id,
            is_electric,
            start_station_id,
            start_station_name,
            end_station_id,
            end_station_name,
            start_time,
            end_time,
            duration_sec,
            duration_min,
            distance_km,
            avg_speed_kmh
        FROM `projet-velib-474009.velib_bronze.fact_velib_trips`
        WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    """
    df = client.query(query).to_dataframe()
    return df

df = load_data()

# ====================================================
# PÉRIODE (PILLS)
# ====================================================
st.header("Période analysée")

horizon_map = {
    "Jour N-1": 1,
    "1 semaine": 7,
    "2 semaines": 14,
    "3 semaines": 21,
    "4 semaines": 30,
}

periode_label = st.pills(
    label="",
    options=list(horizon_map.keys()),
    default="1 semaine"
)

utc = pytz.UTC
today = pd.Timestamp.now(tz=utc).normalize()
start_date = today - timedelta(days=horizon_map[periode_label])
df = df[df["start_time"] >= start_date]

# ====================================================
# PRÉ-CALCULS
# ====================================================
df["date"] = df["start_time"].dt.date

# ====================================================
# INDICATEURS GLOBAUX
# ====================================================
st.header("Indicateurs Vélib")

bike_counts = (
    df.groupby("bike_id")
    .size()
    .reset_index(name="nb_trips")
    .sort_values("nb_trips", ascending=False)
)

top_bike = bike_counts.iloc[0]
longest_trip = df.sort_values("duration_min", ascending=False).iloc[0]

cols = st.columns(6)
cols[0].metric("Vélo le plus utilisé", top_bike["bike_id"])
cols[1].metric("Nb utilisations", int(top_bike["nb_trips"]))
cols[2].metric("Nombre de vélos", bike_counts.shape[0])
cols[3].metric("Durée moyenne", f"{df['duration_min'].mean():.1f} min")
cols[4].metric("Durée médiane", f"{df['duration_min'].median():.1f} min")
cols[5].metric("Trajet le plus long", f"{longest_trip['duration_min']:.0f} min")

# ====================================================
# ACTIVITÉ DES STATIONS
# ====================================================
st.header("Activité des stations")

station_out = (
    df.groupby(["start_station_id", "start_station_name"])
    .size()
    .reset_index(name="nb_out")
)

station_in = (
    df.groupby(["end_station_id", "end_station_name"])
    .size()
    .reset_index(name="nb_in")
)

stations = (
    station_out
    .merge(
        station_in,
        left_on="start_station_id",
        right_on="end_station_id",
        how="outer"
    )
    .fillna(0)
)

stations["total_activity"] = stations["nb_out"] + stations["nb_in"]

col1, col2 = st.columns(2)

with col1:
    st.subheader("Stations les plus actives")
    st.dataframe(
        stations.sort_values("total_activity", ascending=False)
        .head(10)[["start_station_name", "nb_out", "nb_in", "total_activity"]],
        use_container_width=True
    )

with col2:
    st.subheader("Stations les moins actives")
    st.dataframe(
        stations.sort_values("total_activity")
        .head(10)[["start_station_name", "nb_out", "nb_in", "total_activity"]],
        use_container_width=True
    )

# ====================================================
# ÉVOLUTIONS TEMPORELLES
# ====================================================
st.header("Évolutions temporelles")

trips_per_day = (
    df.groupby(["date", "is_electric"])
    .size()
    .unstack(fill_value=0)
)

distance_per_day = (
    df.groupby(["date", "is_electric"])["distance_km"]
    .sum()
    .unstack(fill_value=0)
)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Trajets / jour (élec vs méca)")
    with st.container(border=True):
        st.line_chart(trips_per_day)

with col2:
    st.subheader("Distance totale / jour (élec vs méca)")
    with st.container(border=True):
        st.line_chart(distance_per_day)

# ====================================================
# VÉLOS ÉLECTRIQUES VS MÉCANIQUES (INDICATEURS)
# ====================================================
st.header("Vélos électriques vs mécaniques")

total_trips = df["is_electric"].value_counts()
total_distance = df.groupby("is_electric")["distance_km"].sum()
median_speed_type = df.groupby("is_electric")["avg_speed_kmh"].median()

cols = st.columns(3)

cols[0].metric(
    "Nombre total de trajets",
    f"Élec: {total_trips.get(True,0)} | Méca: {total_trips.get(False,0)}"
)

cols[1].metric(
    "Distance totale (km)",
    f"Élec: {total_distance.get(True,0):,.1f} | Méca: {total_distance.get(False,0):,.1f}"
)

cols[2].metric(
    "Vitesse médiane (km/h)",
    f"Élec: {median_speed_type.get(True,0):.1f} | Méca: {median_speed_type.get(False,0):.1f}"
)


# ====================================================
# PROFILS D’UTILISATION
# ====================================================
st.header("Profils d’utilisation")

hourly_profile = (
    df.groupby(df["start_time"].dt.hour)
    .size()
)

duration_bins = pd.cut(
    df["duration_min"],
    bins=[0, 5, 15, 30, 1000],
    labels=["<5 min", "5–15 min", "15–30 min", ">30 min"]
)

duration_dist = duration_bins.value_counts().sort_index()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Répartition horaire")
    with st.container(border=True):
        st.bar_chart(hourly_profile)

with col2:
    st.subheader("Durée des trajets")
    with st.container(border=True):
        st.bar_chart(duration_dist)
# ====================================================
# DISTANCE, VITESSE & TRAJETS COURTS
# ====================================================
st.header("Distance, vitesse et trajets courts")

avg_distance = df["distance_km"].mean()
median_distance = df["distance_km"].median()

avg_speed = df["avg_speed_kmh"].mean()
median_speed = df["avg_speed_kmh"].median()

short_trips = df[df["duration_min"] < 5]
prop_short_trips = 100 * short_trips.shape[0] / df.shape[0]

cols = st.columns(6)
cols[0].metric("Distance moyenne", f"{avg_distance:.2f} km")
cols[1].metric("Distance médiane", f"{median_distance:.2f} km")
cols[2].metric("Vitesse moyenne", f"{avg_speed:.2f} km/h")
cols[3].metric("Vitesse médiane", f"{median_speed:.2f} km/h")

# ====================================================
# TOP 10 TRAJETS
# ====================================================
st.header("Top 10 trajets")

station_pairs = (
    df.groupby(["start_station_name", "end_station_name"])
    .size()
    .reset_index(name="nb_trips")
    .sort_values("nb_trips", ascending=False)
)

st.dataframe(station_pairs.head(10), use_container_width=True)

# ----------------------------------------------------
# Sidebar
# ----------------------------------------------------
st.sidebar.title("🚲 Vélibstat")
st.sidebar.caption("Créé par [Nicolas](https://www.linkedin.com/in/nicolas-bouttier/)")

