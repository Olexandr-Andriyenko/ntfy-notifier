import streamlit as st
import ntfy_main
import pandas as pd

st.title("DataSmart Point Aktien Battle")
st.write(
    "Vergleiche die tägliche Kursentwicklung der ausgewählten Aktien "
    "und finde den Gewinner des Tages."
    )

# Konfigurationen laden:
try:
    config = ntfy_main.load_config(ntfy_main.CONFIG_FILE)
except Exception as error:
    st.error(f"Konfiguration konnte nicht geladen werden: {error}")
    st.stop()

players = config["players"]
ntfy_config = config.get("ntfy", {})
battle_name = config.get("battle_name", "Aktien-Battle")

# Ergebnisse für spätre Streamlit Neuläufe speichern:
if "results" not in st.session_state:
    st.session_state["results"] = []
if "errors" not in st.session_state:
    st.session_state["errors"] = []
    
# Seitenleiste
with st.sidebar:
    st.header("Battle Informationen")
    st.write(f"**Teilnehmer:** {len(players)}")
    st.divider()
    st.subheader("Teilnehmer")
    for player in players:
        st.write(
            f"**{player['name']}** - {player['ticker']}"
        )
    st.divider()
    
    if ntfy_config.get("enabled", False):
        st.success("ntfy ist aktiviert")
    else:
        st.warning("ntfy ist deaktiviert")

# Battle Starten
if st.button(
    "Battle starten",
    use_container_width=True,
    type="primary"
):
    with st.spinner("Kursdaten werden geladen..."):
        results, errors = ntfy_main.run_battle(players)
    
    st.session_state["results"] = results
    st.session_state["errors"] = errors
    
results = st.session_state["results"]
errors = st.session_state["errors"]

# Fehler anzeigen
if errors:
    with st.expander("Nicht ausgewertete Teilnehemr"):
        for errir in errors:
            st.warning(error)

# Noch kein Battle gestartet
if not results:
    st.info("Klicke auf 'Battle starten' um die aktuellen Kursdaten abzurufen.")
    st.stop()

winner = results[0]
last_place = results[-1]

st.divider()
st.subheader("Ergebnis der aktuellen Runde")

column1, column2 = st.columns(2)
with column1:
    st.metric(
        label="Gewinner",
        value=winner["player"],
        delta=f"{winner['change_percent']:.2f} %"
    )

with column2:
    st.metric(
        label="Gewinner-Aktie",
        value=winner["ticker"],
        delta=f"Kurs $ {round(winner['current_price'] - winner['previous_price'], 2)}"
    )

# Rangliste vorbereiten:
ranking_data = []
for rank, result in enumerate(results, start=1):
    ranking_data.append(
        {
            "Rang": rank,
            "Spieler": result["player"],
            "Ticker": result["ticker"],
            "Vorheriger Kurs": round(result["previous_price"], 2), 
            "Aktueller Kurs": round(result["current_price"], 2), 
            "Veränderung (%)": round(result["change_percent"], 2),
            "Marktstand": result["market_date"]
        }
    )

ranking_df = pd.DataFrame(ranking_data)
st.dataframe(ranking_df, hide_index=True)

st.subheader("Kursveränderung")
chart_data = ranking_df.set_index("Spieler")[["Veränderung (%)"]]
st.bar_chart(chart_data)
st.divider()

# Push Nachricht versenden
if st.button("Gewinner per ntfy senden", use_container_width=True):
    success, message = ntfy_main.send_winner_notification(winner, ntfy_config)
    if success:
        st.success(message)
    else:
        st.error(message)
