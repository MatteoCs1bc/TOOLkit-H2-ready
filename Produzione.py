import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="H2READY - Reverse Engineering Spaziale", layout="wide")

# --- DATI DI BASE FOTOVOLTAICO ---
# Struttura: Nome: [Potenza Specifica W/m2, Ore Equivalenti base]
PV_DATA = {
    "A terra (Fisso)": {"w_m2": 60.0, "h_eq_base": 1200},
    "A terra (Inseguimento)": {"w_m2": 70.0, "h_eq_base": 1380},
    "Tetto a Falda": {"w_m2": 227.27, "h_eq_base": 1200},
    "Tetto Piano": {"w_m2": 113.64, "h_eq_base": 1200}
}

# --- INTERFACCIA LATERALE (INPUTS) ---
with st.sidebar:
    st.header("⚙️ Parametri di Configurazione")
    
    target_h2_ton = st.number_input("🎯 Target Produzione Idrogeno (Tonnellate/anno)", min_value=10, max_value=10000, value=500, step=50)
    
    st.markdown("---")
    st.subheader("⚡ Elettrolizzatore")
    # L'efficienza tipica è 50-55 kWh per kg di H2
    eff_ely = st.slider("Consumo Specifico Elettrolizzatore (kWh/kg H2)", min_value=45.0, max_value=65.0, value=55.0, step=1.0)
    
    # CF in ore (8760 = 100%)
    cf_ore = st.slider("Fattore di Carico (CF) Elettrolizzatore (Ore/anno)", min_value=1000, max_value=8000, value=3000, step=100, 
                       help="Quante ore all'anno lavorerà l'impianto? (Se usi solo FV sarà circa 1200-1500. Se usi rete/batterie puoi alzarlo)")
    
    st.markdown("---")
    st.subheader("☀️ Localizzazione Geografica")
    regione = st.selectbox("Seleziona la zona climatica", ["Nord Italia", "Centro Italia", "Sud Italia / Isole"])
    
    # Moltiplicatori empirici per le ore equivalenti
    moltiplicatore_regione = {"Nord Italia": 1.0, "Centro Italia": 1.15, "Sud Italia / Isole": 1.3}[regione]

# --- MOTORE DI CALCOLO ---
# 1. Fabbisogno Energetico
energia_totale_mwh = (target_h2_ton * 1000 * eff_ely) / 1000  # MWh all'anno
potenza_ely_mw = energia_totale_mwh / cf_ore

# 2. Calcolo Superfici
risultati = []
for nome, dati in PV_DATA.items():
    h_eq_reali = dati["h_eq_base"] * moltiplicatore_regione
    # Resa in kWh per metro quadro = (W/m2 / 1000) * ore_equivalenti
    resa_kwh_m2 = (dati["w_m2"] / 1000) * h_eq_reali
    
    # Area necessaria in m2 = Energia totale (kWh) / Resa (kWh/m2)
    area_m2 = (energia_totale_mwh * 1000) / resa_kwh_m2
    area_ettari = area_m2 / 10000
    
    # Potenza Fotovoltaica necessaria (MWp)
    potenza_pv_mwp = (area_m2 * dati["w_m2"]) / 1000000
    
    risultati.append({
        "Tecnologia": nome,
        "Resa (kWh/m²)": round(resa_kwh_m2, 1),
        "Potenza FV Necessaria (MWp)": round(potenza_pv_mwp, 1),
        "Superficie (m²)": round(area_m2, 0),
        "Superficie (Ettari)": round(area_ettari, 2)
    })

df_risultati = pd.DataFrame(risultati)

# --- DASHBOARD VISIVA ---
st.title("🔄 H2READY - Tool di Reverse Engineering Spaziale")
st.markdown("A partire da un target di produzione di idrogeno, calcola l'impatto sul consumo di suolo e il dimensionamento dell'elettrolizzatore.")

# KPI Principali
st.subheader("🏭 Dimensionamento Impianto Base")
col1, col2, col3 = st.columns(3)
col1.metric("Energia Rinnovabile Necessaria", f"{energia_totale_mwh:,.0f} MWh/anno")
col2.metric("Potenza Elettrolizzatore Stimata", f"{potenza_ely_mw:,.1f} MW", help=f"Calcolata su un utilizzo di {cf_ore} ore/anno.")
col3.metric("Fattore di Carico Elettrolizzatore", f"{(cf_ore/8760)*100:.1f} %")

st.markdown("---")
st.subheader(f"🗺️ Fabbisogno di Superficie in {regione}")

# Split per visualizzazione
c_grafico, c_tabella = st.columns([1.5, 1])

with c_grafico:
    # Grafico a barre per gli ettari
    fig = px.bar(df_risultati, x='Tecnologia', y='Superficie (Ettari)', 
                 title="Consumo di Suolo / Superficie Tetti (in Ettari)",
                 text_auto='.1f', color='Tecnologia',
                 color_discrete_sequence=['#8D6E63', '#5D4037', '#1E88E5', '#42A5F5'])
    fig.update_layout(showlegend=False, yaxis_title="Ettari (ha)")
    st.plotly_chart(fig, use_container_width=True)

with c_tabella:
    st.markdown("<br>", unsafe_allow_html=True)
    st.dataframe(df_risultati[['Tecnologia', 'Potenza FV Necessaria (MWp)', 'Superficie (Ettari)']], hide_index=True, use_container_width=True)

st.info("💡 **Nota Termodinamica:** Se il CF dell'elettrolizzatore che hai impostato è superiore alle ore equivalenti del fotovoltaico (es. CF impostato a 4000h, ma il FV produce solo per 1200h), il sistema presume che tu stia integrando l'energia mancante dalla rete elettrica o tramite PPA (Power Purchase Agreement) da altri impianti.")

# Approfondimento tecnico
with st.expander("📊 Dettaglio Dati Fisici Utilizzati"):
    st.table(df_risultati[['Tecnologia', 'Resa (kWh/m²)', 'Superficie (m²)', 'Potenza FV Necessaria (MWp)']])
