import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from numba import njit

# ==========================================
# CONFIGURAZIONE PAGINA
# ==========================================
st.set_page_config(page_title="H2READY - LCOH & Sizing (Dati Reali)", layout="wide")

# ==========================================
# PESI GEOGRAFICI CURVE MEDIE (Esatti dai tuoi file)
# ==========================================
PV_WEIGHTS_NORD = {
    'Lombardia orientale, area Brescia_NORD': 0.2956,
    'Veneto centrale, area Padova_NORD': 0.2313,
    'Emilia-Romagna orientale, area Ferrara,pianura_NORD': 0.2213,
    'Piemonte meridionale, area Cuneo_NORD': 0.1874,
    'Friuli-Venezia Giulia, area Udine_NORD': 0.0644,
}

PV_WEIGHTS_SUD = {
    'Puglia, area Lecce_SUD': 0.3241,
    'Sicilia interna, area Caltanissetta,Enna_SUD': 0.2117,
    'Lazio meridionale, area Latina_SUD': 0.1982,
    'Sardegna, area Oristano,Campidano_SUD': 0.1330,
    'Campania interna, area Benevento_SUD': 0.1330,
}

WIND_WEIGHTS_NORD = {
    'Crinale savonese entroterra ligure_NORD': 0.6020,
    'Appennino emiliano, area Monte Cimone_NORD': 0.2239,
    'Piemonte sud-occidentale , Cuneese_NORD': 0.0945,
    'Veneto orientale , Delta del Po_NORD': 0.0647,
    'Valle d’Aosta , area alpina_NORD': 0.0149,
}

WIND_WEIGHTS_SUD = {
    'Puglia, area Foggia,Daunia_SUD': 0.3093,
    'Sicilia occidentale, area Trapani_SUD': 0.2267,
    'Campania, area Benevento,Avellino_SUD': 0.1950,
    'Basilicata, area Melfi,Potenza_SUD': 0.1489,
    'Calabria, area Crotone,Catanzaro_SUD': 0.1201,
}

DEFAULT_PV_NORD_SHARE = 48.0
DEFAULT_WIND_NORD_SHARE = 1.6

# ==========================================
# FUNZIONI DI SUPPORTO DATI
# ==========================================
def _serie_pesata(df, pesi_colonne, scala=1.0, clip_upper=1.0):
    colonne_mancanti = [col for col in pesi_colonne if col not in df.columns]
    if colonne_mancanti:
        raise KeyError("Nel dataset mancano le colonne: " + ", ".join(colonne_mancanti))
    serie = sum(pd.to_numeric(df[col], errors='coerce').fillna(0.0) * peso for col, peso in pesi_colonne.items())
    serie = (serie / scala).clip(lower=0.0)
    if clip_upper is not None:
        serie = serie.clip(upper=clip_upper)
    return serie.astype(float)

@st.cache_data
def carica_profili_rinnovabili(file_fotovoltaico, file_eolico):
    try:
        df_pv = pd.read_csv(file_fotovoltaico)
        df_pv['time'] = pd.to_datetime(df_pv['time'], errors='coerce')
        df_pv = df_pv.dropna(subset=['time']).copy()
        df_pv.set_index('time', inplace=True)

        df_wind = pd.read_csv(file_eolico)
        df_wind['time'] = pd.to_datetime(df_wind['time'], errors='coerce')
        df_wind = df_wind.dropna(subset=['time']).copy()
        df_wind.set_index('time', inplace=True)
        
        # Taglio esatto a 8760 ore per sicurezza (anni non bisestili)
        pv_nord = _serie_pesata(df_pv, PV_WEIGHTS_NORD, scala=1.0).values[:8760] # rimosso scala=1000 se i CSV sono in CF da 0 a 1
        pv_sud = _serie_pesata(df_pv, PV_WEIGHTS_SUD, scala=1.0).values[:8760]
        wind_nord = _serie_pesata(df_wind, WIND_WEIGHTS_NORD, scala=1.0).values[:8760]
        wind_sud = _serie_pesata(df_wind, WIND_WEIGHTS_SUD, scala=1.0).values[:8760]
        
        return pv_nord, pv_sud, wind_nord, wind_sud, False
    except Exception as e:
        # Fallback curve fittizie in caso di errore
        t = np.arange(8760)
        pv_finto = np.clip(np.sin((t - 6) * np.pi / 12), 0, 1) * 0.8
        wind_finto = np.clip(0.3 + 0.4 * np.sin(t * np.pi / 72), 0, 1)
        return pv_finto, pv_finto, wind_finto, wind_finto, True

# ==========================================
# MOTORE DI SIMULAZIONE (NUMBA FAST)
# ==========================================
@njit
def simula_h2_plant(pv_array_mw, wind_array_mw, ely_mw, batt_mwh, eff_batt=0.90):
    ore = 8760
    ely_usage = np.zeros(ore)
    batt_soc = np.zeros(ore)
    soc = batt_mwh * 0.2  # Partenza al 20%
    sqrt_eff = np.sqrt(eff_batt)
    
    for t in range(ore):
        avail = pv_array_mw[t] + wind_array_mw[t]
        
        if avail >= ely_mw:
            ely_usage[t] = ely_mw
            excess = avail - ely_mw
            # Carica batteria
            charge_cap = (batt_mwh - soc) / sqrt_eff
            charge = min(excess, charge_cap)
            soc += charge * sqrt_eff
        else:
            # Scarica batteria
            deficit = ely_mw - avail
            discharge_cap = soc * sqrt_eff
            discharge = min(deficit, discharge_cap)
            soc -= discharge / sqrt_eff
            ely_usage[t] = avail + discharge
            
        batt_soc[t] = soc
        
    return ely_usage, batt_soc

# ==========================================
# INTERFACCIA LATERALE
# ==========================================
st.sidebar.header("🎯 1. Target")
target_h2_ton = st.sidebar.slider("Target Idrogeno (ton/anno)", 10, 5000, 500, step=10)
target_h2_kg = target_h2_ton * 1000

st.sidebar.header("🗺️ 2. Mix Geografico (Nord/Sud)")
quota_pv_nord_pct = st.sidebar.slider("% Fotovoltaico al NORD", 0.0, 100.0, DEFAULT_PV_NORD_SHARE, step=1.0)
quota_wind_nord_pct = st.sidebar.slider("% Eolico al NORD", 0.0, 100.0, DEFAULT_WIND_NORD_SHARE, step=1.0)
pv_nord_share = quota_pv_nord_pct / 100.0
wind_nord_share = quota_wind_nord_pct / 100.0

st.sidebar.header("⚖️ 3. Mix Tecnologico")
quota_pv_pct = st.sidebar.slider("Mix: Fotovoltaico vs Eolico (%)", 0, 100, 50, step=5, help="100=Solo PV, 0=Solo Eolico")
quota_pv = quota_pv_pct / 100.0
quota_wind = 1.0 - quota_pv

st.sidebar.header("🔋 4. Architettura Accumulo")
strategia_batt = st.sidebar.radio("Seleziona configurazione impianto:", ["Senza Accumulo", "Con Accumulo Ottimizzato BESS"])

st.sidebar.header("💶 5. Costi Economici (CfD / CAPEX)")
cfd_pv = st.sidebar.slider("CfD Fotovoltaico (€/MWh)", 30.0, 120.0, 60.0, step=5.0)
cfd_wind = st.sidebar.slider("CfD Eolico (€/MWh)", 50.0, 150.0, 80.0, step=5.0)
capex_ely = st.sidebar.slider("CAPEX Elettrolizzatore (€/kW)", 500, 2000, 1000, step=100)
capex_batt = st.sidebar.slider("CAPEX Batterie (€/kWh)", 100, 500, 250, step=10)


# ==========================================
# ESECUZIONE SIMULAZIONE H2
# ==========================================
cartella_script = os.path.dirname(os.path.abspath(__file__))
file_pv = os.path.join(cartella_script, "dataset_fotovoltaico_produzione.csv")
file_wind = os.path.join(cartella_script, "dataset_eolico_produzione.csv")

pv_n, pv_s, w_n, w_s, fallback = carica_profili_rinnovabili(file_pv, file_wind)
if fallback:
    st.error("⚠️ File CSV non trovati. Controlla che si chiamino esattamente 'dataset_fotovoltaico_produzione.csv' e 'dataset_eolico_produzione.csv' e siano nella stessa cartella.")

# Generazione profili bilanciati NORD/SUD 
array_pv_1mw = (pv_n * pv_nord_share) + (pv_s * (1.0 - pv_nord_share))
array_wind_1mw = (w_n * wind_nord_share) + (w_s * (1.0 - wind_nord_share))

# Dimensionamento Base (Sizing Logico su 1 MW)
if "Con Accumulo" in strategia_batt:
    ely_base_mw = 0.6  # Elettrolizzatore sottomensionato per usare CF alto
    batt_base_mwh = ely_base_mw * 6.0  # Circa 6 ore di batteria
else:
    ely_base_mw = 1.0  # Direct coupled
    batt_base_mwh = 0.0

pv_base_array = array_pv_1mw * quota_pv
wind_base_array = array_wind_1mw * quota_wind

# Test su 1 MW combinato per trovare il fattore di scala
ely_usage_base, _ = simula_h2_plant(pv_base_array, wind_base_array, ely_base_mw, batt_base_mwh)
energia_prodotta_base = np.sum(ely_usage_base)

# Calcolo del target energetico
EFF_ELY = 55.0  # kWh/kg
energia_target_mwh = (target_h2_kg * EFF_ELY) / 1000.0

if energia_prodotta_base > 0:
    moltiplicatore_scala = energia_target_mwh / energia_prodotta_base
else:
    moltiplicatore_scala = 0

# Taglie definitive
taglia_pv_mw = quota_pv * moltiplicatore_scala
taglia_wind_mw = quota_wind * moltiplicatore_scala
taglia_ely_mw = ely_base_mw * moltiplicatore_scala
taglia_batt_mwh = batt_base_mwh * moltiplicatore_scala

# Riesecuzione simulazione esatta (8760 ore)
pv_final_array = array_pv_1mw * taglia_pv_mw
wind_final_array = array_wind_1mw * taglia_wind_mw
ely_usage_final, batt_soc_final = simula_h2_plant(pv_final_array, wind_final_array, taglia_ely_mw, taglia_batt_mwh)

# Risultati Tecnici
energia_rinnovabile_totale = np.sum(pv_final_array) + np.sum(wind_final_array)
energia_assorbita = np.sum(ely_usage_final)
energia_sprecata = energia_rinnovabile_totale - energia_assorbita
cf_ely = energia_assorbita / (taglia_ely_mw * 8760.0) if taglia_ely_mw > 0 else 0
ettari_pv = taglia_pv_mw / 0.7  # Ipotesi standard Tracker

# Calcolo Economico (LCOH)
WACC = 0.05
VITA = 20
CRF = (WACC * (1 + WACC)**VITA) / ((1 + WACC)**VITA - 1)

lcoe_mix = (cfd_pv * quota_pv) + (cfd_wind * quota_wind)
# Costo energia: Paghiamo TUTTA la rinnovabile generata (incluso il curtailment)
costo_energia_kg = (energia_rinnovabile_totale * lcoe_mix) / target_h2_kg

costo_ely_kg = (taglia_ely_mw * 1000.0 * capex_ely * CRF) / target_h2_kg
costo_batt_kg = (taglia_batt_mwh * 1000.0 * capex_batt * CRF) / target_h2_kg

costo_parziale = costo_energia_kg + costo_ely_kg + costo_batt_kg
costo_opex_stoccaggio = costo_parziale * 0.20  # +20% ricarico fisso
lcoh_finale = costo_parziale + costo_opex_stoccaggio

# ==========================================
# DASHBOARD E GRAFICI
# ==========================================
st.title("🏭 H2 Reverse Engineering: Dati Orari Reali e Sizing Ottimale")

# KPI PRINCIPALI
c1, c2, c3, c4 = st.columns(4)
c1.metric("LCOH Finale", f"€ {lcoh_finale:.2f} / kg")
c2.metric("Taglia Elettrolizzatore", f"{taglia_ely_mw:.1f} MW", f"CF: {cf_ely*100:.1f}%")
c3.metric("Taglia Batteria", f"{taglia_batt_mwh:.1f} MWh")
c4.metric("Consumo Suolo PV", f"{ettari_pv:,.1f} ha", "Tracker 0.7 MW/ha")

st.markdown("---")

# GRAFICO 8760H (Usiamo Scattergl per alte prestazioni con tanti punti)
st.markdown("### ⏱️ Profilo Operativo Annuale (8760 Ore)")
st.markdown("Generato processando istante per istante i profili meteo reali. Il curtailment si verifica quando PV+Vento superano la linea rossa e la batteria è piena.")

df_8760 = pd.DataFrame({
    'Ora': np.arange(8760),
    'Fotovoltaico': pv_final_array,
    'Eolico': wind_final_array,
    'Elettrolizzatore': ely_usage_final,
    'Batteria_SoC': batt_soc_final
})

fig_8760 = make_subplots(specs=[[{"secondary_y": True}]])
fig_8760.add_trace(go.Scattergl(x=df_8760['Ora'], y=df_8760['Fotovoltaico'], fill='tozeroy', mode='none', name='PV', fillcolor='rgba(255, 193, 7, 0.4)'), secondary_y=False)
fig_8760.add_trace(go.Scattergl(x=df_8760['Ora'], y=df_8760['Eolico'], fill='tonexty', mode='none', name='Eolico', fillcolor='rgba(3, 169, 244, 0.4)'), secondary_y=False)
fig_8760.add_trace(go.Scattergl(x=df_8760['Ora'], y=df_8760['Elettrolizzatore'], mode='lines', name='Elettrolizzatore (MW)', line=dict(color='#D32F2F', width=1)), secondary_y=False)
if taglia_batt_mwh > 0:
    fig_8760.add_trace(go.Scattergl(x=df_8760['Ora'], y=df_8760['Batteria_SoC'], mode='lines', name='SoC Batteria (MWh)', line=dict(color='#4CAF50', dash='dot', width=1)), secondary_y=True)

fig_8760.update_layout(xaxis_title="Ore dell'anno", hovermode="x unified", height=450, margin=dict(l=0, r=0, t=30, b=0))
fig_8760.update_yaxes(title_text="Potenza (MW)", secondary_y=False)
if taglia_batt_mwh > 0:
    fig_8760.update_yaxes(title_text="Energia in Batteria (MWh)", secondary_y=True)

st.plotly_chart(fig_8760, use_container_width=True)

st.markdown("---")

col_g1, col_g2 = st.columns(2)

with col_g1:
    st.markdown("### 💶 Scomposizione LCOH (€/kg)")
    df_costi = pd.DataFrame({
        "Componente": ["Costo Energia (PV+Wind)", "CAPEX Elettrolizzatore", "CAPEX Batterie", "OPEX & Stoccaggio (+20%)"],
        "Costo": [costo_energia_kg, costo_ely_kg, costo_batt_kg, costo_opex_stoccaggio]
    })
    fig_costi = px.bar(df_costi, x="Componente", y="Costo", color="Componente", text_auto=".2f", color_discrete_sequence=['#2E7D32', '#1565C0', '#F9A825', '#424242'])
    fig_costi.update_layout(showlegend=False, yaxis_title="€ / kg H2", height=400)
    st.plotly_chart(fig_costi, use_container_width=True)

with col_g2:
    st.markdown("### 🏗️ Scomposizione Capacità Installata (MW)")
    df_cap = pd.DataFrame({
        "Asset": ["Fotovoltaico (MW)", "Eolico (MW)", "Elettrolizzatore (MW)"],
        "Valore": [taglia_pv_mw, taglia_wind_mw, taglia_ely_mw]
    })
    fig_cap = px.bar(df_cap, x="Asset", y="Valore", color="Asset", text_auto=".1f", color_discrete_sequence=['#FFC107', '#03A9F4', '#D32F2F'])
    fig_cap.update_layout(showlegend=False, yaxis_title="Megawatt (MW)", height=400)
    st.plotly_chart(fig_cap, use_container_width=True)

st.caption(f"⚠️ **Nota Tecnica:** A causa del profilo climatico impostato, per produrre il target richiesto si genera un **curtailment annuo** (energia verde persa) pari a **{energia_sprecata:,.0f} MWh**.")
