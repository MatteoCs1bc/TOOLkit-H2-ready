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
st.set_page_config(page_title="H2READY - LCOH, Sizing & Grid Connection", layout="wide")

# ==========================================
# PESI GEOGRAFICI CURVE MEDIE (Dataset integrati)
# ==========================================
PV_WEIGHTS_NORD = {'Lombardia orientale, area Brescia_NORD': 0.2956, 'Veneto centrale, area Padova_NORD': 0.2313, 'Emilia-Romagna orientale, area Ferrara,pianura_NORD': 0.2213, 'Piemonte meridionale, area Cuneo_NORD': 0.1874, 'Friuli-Venezia Giulia, area Udine_NORD': 0.0644}
PV_WEIGHTS_SUD = {'Puglia, area Lecce_SUD': 0.3241, 'Sicilia interna, area Caltanissetta,Enna_SUD': 0.2117, 'Lazio meridionale, area Latina_SUD': 0.1982, 'Sardegna, area Oristano,Campidano_SUD': 0.1330, 'Campania interna, area Benevento_SUD': 0.1330}
WIND_WEIGHTS_NORD = {'Crinale savonese entroterra ligure_NORD': 0.6020, 'Appennino emiliano, area Monte Cimone_NORD': 0.2239, 'Piemonte sud-occidentale , Cuneese_NORD': 0.0945, 'Veneto orientale , Delta del Po_NORD': 0.0647, 'Valle d’Aosta , area alpina_NORD': 0.0149}
WIND_WEIGHTS_SUD = {'Puglia, area Foggia,Daunia_SUD': 0.3093, 'Sicilia occidentale, area Trapani_SUD': 0.2267, 'Campania, area Benevento,Avellino_SUD': 0.1950, 'Basilicata, area Melfi,Potenza_SUD': 0.1489, 'Calabria, area Crotone,Catanzaro_SUD': 0.1201}

# ==========================================
# FUNZIONI DI SUPPORTO DATI
# ==========================================
def _serie_pesata(df, pesi_colonne, scala=1.0, clip_upper=1.0):
    colonne_mancanti = [col for col in pesi_colonne if col not in df.columns]
    if colonne_mancanti: raise KeyError("Dataset incompleto.")
    serie = sum(pd.to_numeric(df[col], errors='coerce').fillna(0.0) * peso for col, peso in pesi_colonne.items())
    return (serie / scala).clip(lower=0.0, upper=clip_upper).astype(float)

@st.cache_data
def carica_profili_rinnovabili(file_fotovoltaico, file_eolico):
    try:
        df_pv = pd.read_csv(file_fotovoltaico)
        df_pv['time'] = pd.to_datetime(df_pv['time'], errors='coerce')
        df_pv.set_index('time', inplace=True)
        df_wind = pd.read_csv(file_eolico)
        df_wind['time'] = pd.to_datetime(df_wind['time'], errors='coerce')
        df_wind.set_index('time', inplace=True)
        return _serie_pesata(df_pv, PV_WEIGHTS_NORD, 1000.0).values[:8760], _serie_pesata(df_pv, PV_WEIGHTS_SUD, 1000.0).values[:8760], \
               _serie_pesata(df_wind, WIND_WEIGHTS_NORD).values[:8760], _serie_pesata(df_wind, WIND_WEIGHTS_SUD).values[:8760], False
    except:
        t = np.arange(8760)
        pv = np.clip(np.sin((t - 6) * np.pi / 12), 0, 1) * 0.8
        wind = np.clip(0.3 + 0.4 * np.sin(t * np.pi / 72), 0, 1)
        return pv, pv, wind, wind, True

@njit
def simula_h2_plant(pv_array_mw, wind_array_mw, ely_mw, batt_mwh, eff_batt=0.90):
    ore = 8760
    ely_usage, batt_soc = np.zeros(ore), np.zeros(ore)
    soc = batt_mwh * 0.2
    sqrt_eff = np.sqrt(eff_batt)
    for t in range(ore):
        avail = pv_array_mw[t] + wind_array_mw[t]
        if avail >= ely_mw:
            ely_usage[t] = ely_mw
            charge = min(avail - ely_mw, (batt_mwh - soc) / sqrt_eff)
            soc += charge * sqrt_eff
        else:
            discharge = min(ely_mw - avail, soc * sqrt_eff)
            soc -= discharge / sqrt_eff
            ely_usage[t] = avail + discharge
        batt_soc[t] = soc
    return ely_usage, batt_soc

# ==========================================
# INTERFACCIA SIDEBAR
# ==========================================
st.sidebar.header("🎯 1. Target")
target_h2_kg = st.sidebar.number_input("Target Idrogeno (ton/anno)", 10, 1000000, 1000) * 1000
regione = st.sidebar.selectbox("Zona Climatica", ["Nord Italia", "Sud Italia / Isole"])

st.sidebar.header("⚖️ 2. Mix Tecnologico & Rete")
quota_pv_pct = st.sidebar.slider("Mix: PV vs Eolico (%)", 0, 100, 50)
quota_pv = quota_pv_pct / 100.0
tipo_connessione = st.sidebar.radio("Tipo di Connessione", ["ON-GRID (Allaccio Rete)", "OFF-GRID (Isola)"])
distanza_rete_km = 0.0
if tipo_connessione == "ON-GRID (Allaccio Rete)":
    distanza_rete_km = st.sidebar.slider("Distanza dalla Cabina Primaria (km)", 0.1, 20.0, 2.0)

st.sidebar.header("🔋 3. Accumulo BESS")
strategia_batt = st.sidebar.radio("Configurazione:", ["Senza Accumulo", "Con Accumulo BESS"])
limite_batt_pv = st.sidebar.slider("Limite Batteria (x MW PV)", 0.0, 5.0, 3.0)

st.sidebar.header("💶 4. Parametri Economici")
cfd_pv = st.sidebar.slider("CfD Fotovoltaico (€/MWh)", 30.0, 120.0, 60.0)
cfd_wind = st.sidebar.slider("CfD Eolico (€/MWh)", 50.0, 150.0, 80.0)
capex_ely = st.sidebar.slider("CAPEX Elettrolizzatore (€/kW)", 500, 2000, 1000)
capex_batt = st.sidebar.slider("CAPEX Batterie (€/kWh)", 100, 500, 150)

st.sidebar.header("🗜️ 5. Compressione & Mercato")
profilo_comp = st.sidebar.selectbox("Compressione", ["Standard (fino 500 bar)", "Booster / Pressione Costante"])
prezzo_vendita_h2 = st.sidebar.slider("Prezzo Vendita H2 (€/kg)", 2.0, 20.0, 8.0)

# ==========================================
# CALCOLO SIZING
# ==========================================
pv_n, pv_s, w_n, w_s, _ = carica_profili_rinnovabili("dataset_fotovoltaico_produzione.csv", "dataset_eolico_produzione.csv")
array_pv, array_wind = (pv_n, w_n) if regione == "Nord Italia" else (pv_s, w_s)

ely_base_mw = 0.6 if "Con Accumulo" in strategia_batt else 1.0
batt_base_mwh = ely_base_mw * 6.0 if "Con Accumulo" in strategia_batt else 0.0

# Efficienza sistema (Elettrolisi + Compressione)
consumo_comp = 2.23 if "Standard" in profilo_comp else 4.11
eff_sistema = 55.0 + consumo_comp

ely_usage_base, _ = simula_h2_plant(array_pv * quota_pv, array_wind * (1-quota_pv), ely_base_mw, batt_base_mwh)
moltiplicatore = ((target_h2_kg * eff_sistema) / 1000.0) / np.sum(ely_usage_base) if np.sum(ely_usage_base) > 0 else 0

taglia_pv, taglia_wind, taglia_ely = quota_pv * moltiplicatore, (1-quota_pv) * moltiplicatore, ely_base_mw * moltiplicatore
taglia_batt = min(batt_base_mwh * moltiplicatore, taglia_pv * limite_batt_pv)

# Simulazione finale
ely_usage, batt_soc = simula_h2_plant(array_pv * taglia_pv, array_wind * taglia_wind, taglia_ely, taglia_batt)

# ==========================================
# ANALISI ALLACCIAMENTO RETE (e-distribuzione 2025)
# ==========================================
capex_connessione = 0.0
label_tensione = "N/A"
potenza_totale_mw = taglia_pv + taglia_wind

if tipo_connessione == "ON-GRID (Allaccio Rete)":
    if potenza_totale_mw < 6.0:
        # Connessione Media Tensione (MT) - Pag. 115 Guide
        label_tensione = "Media Tensione (MT)"
        costo_scomparto = 8000 # Allestimento cabina consegna (8.1 k€ arrotondato)
        costo_km = 155000 # Cavo interrato su strada asfaltata Al 185 (155 k€/km)
        capex_connessione = costo_scomparto + (costo_km * distanza_rete_km)
    else:
        # Connessione Alta Tensione (AT) - Pag. 15 Guide
        label_tensione = "Alta Tensione (AT - 150kV)"
        costo_stallo = 730000 # Stallo Linea AT AIS (730 k€)
        costo_km = 300000 # Linea Aerea Singola Terna (300 k€/km)
        capex_connessione = costo_stallo + (costo_km * distanza_rete_km)

# ==========================================
# CALCOLO FINANZIARIO
# ==========================================
WACC, VITA = 0.05, 20
CRF = (WACC * (1 + WACC)**VITA) / ((1 + WACC)**VITA - 1)
incidenza_comp = 0.24 if "Standard" in profilo_comp else 0.42

capex_ely_tot = taglia_ely * 1000 * capex_ely
capex_batt_tot = taglia_batt * 1000 * capex_batt
capex_comp_tot = (incidenza_comp * target_h2_kg) / CRF
capex_totale = capex_ely_tot + capex_batt_tot + capex_comp_tot + capex_connessione

opex_energia = (np.sum(array_pv * taglia_pv) * cfd_pv) + (np.sum(array_wind * taglia_wind) * cfd_wind)
opex_manutenzione = capex_totale * 0.03
ricavi = target_h2_kg * prezzo_vendita_h2
lcoh = (opex_energia + opex_manutenzione + (capex_totale * CRF)) / target_h2_kg

# ==========================================
# DASHBOARD RISULTATI
# ==========================================
st.title("🏭 H2 Ready: Sizing & Financial Advisor")
with st.expander("🛠️ Metodologia e Costi Allacciamento e-distribuzione"):
    st.markdown(f"""
    I costi di connessione sono estratti dalla **Guida e-distribuzione Ed. Ottobre 2025**:
    * **MT (< 6MW):** Cavo interrato Al 185mm² (155k€/km) + Cabina Consegna (8k€).
    * **AT (> 6MW):** Linea Aerea 150kV (300k€/km) + Stallo AIS in Cabina Primaria (730k€).
    """)

m1, m2, m3, m4 = st.columns(4)
m1.metric("LCOH", f"€ {lcoh:.2f} / kg")
m2.metric("CAPEX Connessione", f"€ {capex_connessione/1e3:,.0f} k")
m3.metric("Tensione Allaccio", label_tensione)
m4.metric("Distanza Rete", f"{distanza_rete_km} km")

st.markdown("---")

# --- SEZIONE ALLACCIAMENTO ---
st.subheader("🔗 Analisi Allacciamento alla Rete")
c_alt1, c_alt2 = st.columns(2)
with c_alt1:
    st.info(f"""
    **Dettaglio Tecnico:**
    * Potenza da connettere: **{potenza_totale_mw:.2f} MW**
    * Tipologia linea: {'Cavo Interrato' if potenza_totale_mw < 6 else 'Elettrodotto Aereo'}
    * Costo Infrastruttura di Rete: € {capex_connessione:,.0f}
    """)
with c_alt2:
    if tipo_connessione == "OFF-GRID (Isola)":
        st.warning("⚠️ Modalità Isola: CAPEX Connessione azzerato, ma rischio elevato di curtailment energetico.")
    else:
        st.success("✅ Connessione On-Grid inclusa nel Business Case.")

# --- FINANZA ---
st.markdown("---")
st.subheader("💶 Sostenibilità Economica (Payback)")
cash_flow = ricavi - (opex_energia + opex_manutenzione)
payback = capex_totale / cash_flow if cash_flow > 0 else float('inf')

f1, f2, f3, f4 = st.columns(4)
f1.metric("CAPEX Totale", f"€ {capex_totale/1e6:,.2f} MLN")
f2.metric("Ricavi Annuali", f"€ {ricavi/1e6:,.2f} MLN")
f3.metric("OPEX Annuale", f"€ {(opex_energia+opex_manutenzione)/1e6:,.2f} MLN")
f4.metric("Payback Period", f"{payback:.1f} Anni" if payback < 50 else "Mai")

# Grafico Flusso Cumulato
anni = np.arange(0, 21)
flusso_cum = np.cumsum([-capex_totale] + [cash_flow]*20)
fig_fin = go.Figure()
fig_fin.add_trace(go.Scatter(x=anni, y=flusso_cum, mode='lines+markers', name="Cash Flow Cumulato", line=dict(color='#1976D2')))
fig_fin.add_hline(y=0, line_dash="dash", line_color="red")
fig_fin.update_layout(title="Andamento Finanziario (20 anni)", xaxis_title="Anno", yaxis_title="Euro (€)")
st.plotly_chart(fig_fin, use_container_width=True)

st.error("""
**⚠️ DISCLAIMER FINALE**
I costi di connessione sono basati su medie nazionali. Condizioni orografiche complesse, attraversamenti autostradali o necessità di nuove Cabine Primarie complete (costo ~5-7 M€) non sono incluse e richiedono uno studio di rete specifico da parte del distributore.
""")
