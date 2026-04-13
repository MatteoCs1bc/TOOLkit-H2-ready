import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="H2READY - Reverse Engineering Spaziale", layout="wide")

# --- DATI DI BASE FOTOVOLTAICO (Esatto dal database utente) ---
# Struttura: Nome: [Potenza Specifica W/m2, Ore Equivalenti base]
# 70 W/m2 = 700 kW/ha
PV_DATA = {
    "A terra (Inseguimento)": {"w_m2": 70.0, "h_eq_base": 1380},
    "Tetto a Falda": {"w_m2": 227.27, "h_eq_base": 1200},
    "Tetto Piano": {"w_m2": 113.64, "h_eq_base": 1200}
}

# Costante energetica
EFF_ELY = 55.0 # kWh per 1 kg di H2

# --- INTERFACCIA LATERALE (INPUTS) ---
with st.sidebar:
    st.header("⚙️ Parametri di Configurazione")
    
    target_h2_ton = st.number_input("🎯 Target Idrogeno (Tonnellate/anno)", min_value=5, max_value=20000, value=100, step=10)
    target_h2_kg = target_h2_ton * 1000
    
    st.markdown("---")
    st.subheader("☀️ Localizzazione Geografica")
    regione = st.selectbox("Seleziona la zona climatica", ["Nord Italia", "Centro Italia", "Sud Italia / Isole"])
    # Moltiplicatori empirici per le ore equivalenti
    moltiplicatore_regione = {"Nord Italia": 1.0, "Centro Italia": 1.15, "Sud Italia / Isole": 1.3}[regione]

    st.markdown("---")
    st.subheader("🔋 Architettura Impianto")
    config_batterie = st.radio(
        "Presenza di Accumulo (BESS):", 
        ["Senza Batterie (Off-grid Diretto)", "Con Batterie (Off-grid Bufferizzato)"]
    )
    
    if "Con Batterie" in config_batterie:
        cf_ore_ely = st.slider("Fattore di Carico Elettrolizzatore (Ore/anno)", 2000, 6000, 4000, step=100, help="Le batterie permettono all'elettrolizzatore di lavorare anche di notte o con nuvole.")
        perdita_batteria = 1.10 # +10% di energia richiesta per compensare le inefficienze di carica/scarica
    else:
        cf_ore_ely = None # Sarà calcolato dinamicamente sulle ore del PV
        perdita_batteria = 1.0 # Nessuna perdita di stoccaggio


# --- MOTORE DI CALCOLO ---
# 1. Energia Pura Necessaria per l'H2
energia_h2_mwh = (target_h2_kg * EFF_ELY) / 1000  # MWh all'anno necessari per l'elettrolisi
energia_pv_richiesta_mwh = energia_h2_mwh * perdita_batteria

# 2. Calcolo Capacità e Superfici per ogni Tecnologia
risultati = []
for nome, dati in PV_DATA.items():
    h_eq_reali = dati["h_eq_base"] * moltiplicatore_regione
    
    # Se non ci sono batterie, l'elettrolizzatore lavora esattamente per le ore equivalenti del PV
    ore_funzionamento_ely = cf_ore_ely if cf_ore_ely else h_eq_reali
    
    # Taglia Elettrolizzatore (MW) = Energia (MWh) / Ore di funzionamento
    potenza_ely_mw = energia_h2_mwh / ore_funzionamento_ely
    
    # Resa del fotovoltaico (MWh all'anno per Ettaro)
    # (W/m2 * 10.000) / 1.000.000 = MW/ha. Moltiplicato per ore = MWh/ha
    potenza_pv_mw_per_ha = (dati["w_m2"] * 10000) / 1000000
    resa_mwh_ha = potenza_pv_mw_per_ha * h_eq_reali
    
    # Ettari necessari = Energia totale richiesta / Resa per Ettaro
    area_ettari = energia_pv_richiesta_mwh / resa_mwh_ha
    
    # Potenza FV Totale (MWp)
    potenza_pv_totale_mwp = area_ettari * potenza_pv_mw_per_ha
    
    risultati.append({
        "Tecnologia PV": nome,
        "Superficie Necessaria (Ettari)": round(area_ettari, 2),
        "Capacità FV (MWp)": round(potenza_pv_totale_mwp, 1),
        "Taglia Elettrolizzatore (MW)": round(potenza_ely_mw, 1),
        "Ore Eq. Locali (h)": round(h_eq_reali, 0)
    })

df_risultati = pd.DataFrame(risultati)

# --- DASHBOARD VISIVA ---
st.title("🔄 H2READY - Reverse Engineering Spaziale")
st.markdown(f"**Obiettivo:** Produrre **{target_h2_kg:,.0f} kg/anno** di Idrogeno Verde (Costo energetico: 55 kWh/kg).")

# Metriche Globali
st.subheader("⚡ Fabbisogno Energetico Base")
c1, c2 = st.columns(2)
c1.metric("Energia Totale da Produrre", f"{energia_pv_richiesta_mwh:,.0f} MWh/anno", help="Include eventuali perdite di accumulo se configurate.")
c2.metric("Impatto Accumulo", "+10% Energia" if "Con Batterie" in config_batterie else "0% (Diretto)")

st.markdown("---")

# Visualizzazione Risultati (Focus sugli Ettari)
st.subheader("🗺️ Mappatura del Consumo di Suolo e Impianti")

col_grafico, col_tabella = st.columns([1, 1.2])

with col_grafico:
    fig = px.bar(df_risultati, x='Tecnologia PV', y='Superficie Necessaria (Ettari)', 
                 title="Quanti Ettari mi servono?",
                 text_auto='.1f', color='Tecnologia PV',
                 color_discrete_sequence=['#FF8F00', '#1565C0', '#42A5F5'])
    
    # Aggiungo la linea rossa per evidenziare la soglia di 1 Ettaro
    fig.add_hline(y=1.0, line_dash="dash", line_color="red", annotation_text="Soglia 1 ha")
    fig.update_layout(showlegend=False, yaxis_title="Ettari (ha)")
    st.plotly_chart(fig, use_container_width=True)

with col_tabella:
    st.markdown("<br>", unsafe_allow_html=True)
    st.dataframe(df_risultati[['Tecnologia PV', 'Superficie Necessaria (Ettari)', 'Capacità FV (MWp)', 'Taglia Elettrolizzatore (MW)']], 
                 hide_index=True, use_container_width=True)
    
    # Alert se si superano grandi superfici
    max_ha = df_risultati['Superficie Necessaria (Ettari)'].max()
    if max_ha > 1.0:
        st.warning(f"⚠️ **Nota Dimensionale:** Per produrre {target_h2_ton} ton/anno con impianti a terra servono ben **{df_risultati.iloc[0]['Superficie Necessaria (Ettari)']} ettari**. È un progetto di scala industriale (Utility Scale).")
    else:
        st.info("🌱 La superficie richiesta per questo target è inferiore a 1 ettaro.")

st.markdown("---")

# Spiegazione Tecnica della Capacità (Batterie vs No Batterie)
with st.expander("🔍 Perché la Taglia dell'Elettrolizzatore cambia? (Analisi Capacità)"):
    if "Con Batterie" in config_batterie:
        st.markdown(f"""
        Hai scelto l'opzione **Con Batterie**. 
        In questa configurazione l'elettrolizzatore non deve fare tutto il lavoro nelle poche ore in cui c'è il sole. 
        Le batterie immagazzinano l'energia fotovoltaica e la rilasciano lentamente.
        * L'elettrolizzatore lavora per **{cf_ore_ely} ore all'anno**.
        * **Vantaggio:** Ti basta comprare un elettrolizzatore più piccolo (**{df_risultati.iloc[0]['Taglia Elettrolizzatore (MW)']} MW**), risparmiando enormemente sui costi di acquisto (CAPEX).
        * **Svantaggio:** Devi installare circa il 10% di fotovoltaico in più per coprire l'energia che si disperde scaldando le batterie.
        """)
    else:
        st.markdown(f"""
        Hai scelto l'opzione **Senza Batterie**.
        In questa configurazione l'elettrolizzatore è attaccato direttamente ai pannelli (Direct-Coupled) e si accende e spegne con il sole.
        * L'elettrolizzatore lavora pochissimo, solo per **{df_risultati.iloc[0]['Ore Eq. Locali (h)']} ore all'anno**.
        * **Svantaggio (Problema di Capacità):** Per riuscire a produrre le tue {target_h2_ton} tonnellate in così poco tempo, dovrai comprare un elettrolizzatore gigantesco (**{df_risultati.iloc[0]['Taglia Elettrolizzatore (MW)']} MW**). Questo distruggerà il business case dell'impianto a causa dell'altissimo costo di investimento (CAPEX).
        * **Vantaggio:** Non perdi energia nei cicli di carica/scarica delle batterie.
        """)
