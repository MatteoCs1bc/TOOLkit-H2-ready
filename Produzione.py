import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# Configurazione Pagina
st.set_page_config(page_title="H2READY - LCOH & Space Sizing Tool", layout="wide")

# ==========================================
# 1. PARAMETRI E COSTANTI
# ==========================================
EFF_ELY = 55.0  # kWh per 1 kg di H2
ORE_BASE_PV = 1400.0  # Ore equivalenti medie PV (Nord/Centro)
ORE_BASE_WIND = 2000.0  # Ore equivalenti medie Eolico
RESA_HA_PV = 0.7  # MW per Ettaro (PV Tracker)
WACC = 0.05
VITA_UTILE = 20
CRF = (WACC * (1 + WACC)**VITA_UTILE) / ((1 + WACC)**VITA_UTILE - 1)

# ==========================================
# 2. INTERFACCIA LATERALE (INPUTS)
# ==========================================
with st.sidebar:
    st.header("🎯 1. Target di Produzione")
    target_h2_ton = st.slider("Target Idrogeno (ton/anno)", 10, 5000, 500, step=10)
    target_h2_kg = target_h2_ton * 1000
    
    st.markdown("---")
    st.header("⚖️ 2. Mix e Accumulo")
    quota_pv_pct = st.slider("Mix: Fotovoltaico vs Eolico (%)", 0, 100, 50, step=5, help="100% = Solo PV, 0% = Solo Eolico")
    quota_pv = quota_pv_pct / 100.0
    quota_wind = 1.0 - quota_pv
    
    ore_accumulo = st.slider("Ore di Accumulo Batteria", 0, 12, 4, step=1, help="Capacità della batteria rispetto all'elettrolizzatore. 0 = Senza batterie.")
    
    st.markdown("---")
    st.header("💶 3. Costi ed Economia")
    cfd_pv = st.slider("CfD Fotovoltaico (€/MWh)", 30.0, 120.0, 60.0, step=5.0)
    cfd_wind = st.slider("CfD Eolico (€/MWh)", 50.0, 150.0, 80.0, step=5.0)
    capex_ely = st.slider("CAPEX Elettrolizzatore (€/kW)", 500, 2000, 1000, step=100)
    capex_batt = st.slider("CAPEX Batterie (€/kWh)", 100, 500, 250, step=10)

# ==========================================
# 3. MOTORE DI CALCOLO MATEMATICO
# ==========================================
# Perdita di stoccaggio
efficienza_batteria = 0.90
molt_energia = 1.0 if ore_accumulo == 0 else (1.0 / efficienza_batteria)

# Energia Totale
energia_pura_mwh = (target_h2_kg * EFF_ELY) / 1000.0
energia_totale_mwh = energia_pura_mwh * molt_energia

# Calcolo Capacity Factor (CF) Elettrolizzatore
cf_pv_base = ORE_BASE_PV / 8760.0
cf_wind_base = ORE_BASE_WIND / 8760.0
cf_mix = (quota_pv * cf_pv_base) + (quota_wind * cf_wind_base)

# La batteria estende il CF (Logica statistica semplificata per reverse engineering)
cf_aggiuntivo_batt = ore_accumulo * 0.025  # Circa +2.5% CF per ogni ora di accumulo
cf_totale_ely = min(cf_mix + cf_aggiuntivo_batt, 0.75) # Cap al 75% per manutenzioni e limiti fisici
ore_eq_ely = cf_totale_ely * 8760.0

# Dimensionamento Impianti (MW)
taglia_ely_mw = energia_totale_mwh / ore_eq_ely
taglia_batt_mwh = taglia_ely_mw * ore_accumulo

taglia_pv_mw = (energia_totale_mwh * quota_pv) / ORE_BASE_PV if quota_pv > 0 else 0
taglia_wind_mw = (energia_totale_mwh * quota_wind) / ORE_BASE_WIND if quota_wind > 0 else 0

# Consumo di suolo (SOLO PV)
ettari_pv = taglia_pv_mw / RESA_HA_PV

# ==========================================
# 4. CALCOLO ECONOMICO (LCOH €/kg)
# ==========================================
# 4.1 Costo Energia (LCOE Ponderato * Consumo Specifico)
lcoe_mix = (cfd_pv * quota_pv) + (cfd_wind * quota_wind)
costo_energia_kg = (lcoe_mix / 1000.0) * EFF_ELY * molt_energia

# 4.2 Costo CAPEX Elettrolizzatore spalmato sui kg
capex_ely_totale = taglia_ely_mw * 1000.0 * capex_ely
rata_annua_ely = capex_ely_totale * CRF
costo_ely_kg = rata_annua_ely / target_h2_kg

# 4.3 Costo CAPEX Batterie spalmato sui kg
capex_batt_totale = taglia_batt_mwh * 1000.0 * capex_batt
rata_annua_batt = capex_batt_totale * CRF
costo_batt_kg = rata_annua_batt / target_h2_kg

# 4.4 Ricarico OPEX, Compressione e Stoccaggio (+20%)
costo_parziale_kg = costo_energia_kg + costo_ely_kg + costo_batt_kg
costo_opex_stoccaggio_kg = costo_parziale_kg * 0.20

lcoh_finale = costo_parziale_kg + costo_opex_stoccaggio_kg

# ==========================================
# 5. SIMULAZIONE ORARIA SINTETICA (72 ORE)
# ==========================================
def simula_profilo_tipo(pv_mw, wind_mw, ely_mw, batt_max_mwh):
    """Simula 72 ore per mostrare la logica di dispacciamento"""
    t = np.arange(72)
    # Sole: onda sinusoidale solo di giorno
    pv_curve = np.clip(np.sin((t - 6) * np.pi / 12), 0, 1) * pv_mw
    # Vento: mix di sinusoidi e rumore
    wind_curve = (np.sin(t * np.pi / 24) * 0.5 + 0.5 + np.random.normal(0, 0.1, 72)) * wind_mw * 0.4
    wind_curve = np.clip(wind_curve, 0, wind_mw)
    
    ren_tot = pv_curve + wind_curve
    
    ely_usage = np.zeros(72)
    batt_soc = np.zeros(72)
    soc_current = batt_max_mwh * 0.2 # Parte al 20%
    
    for i in range(72):
        avail_energy = ren_tot[i]
        
        # 1. Alimenta Ely
        if avail_energy >= ely_mw:
            ely_usage[i] = ely_mw
            excess = avail_energy - ely_mw
            # Carica batteria
            charge = min(excess, batt_max_mwh - soc_current)
            soc_current += charge
        else:
            # 2. Scarica batteria se manca energia
            deficit = ely_mw - avail_energy
            discharge = min(deficit, soc_current)
            soc_current -= discharge
            ely_usage[i] = avail_energy + discharge
            
        batt_soc[i] = soc_current
        
    return pd.DataFrame({'Ora': t, 'Rinnovabile (PV+Wind)': ren_tot, 'Uso Elettrolizzatore': ely_usage, 'SoC Batteria (MWh)': batt_soc})

df_orario = simula_profilo_tipo(taglia_pv_mw, taglia_wind_mw, taglia_ely_mw, taglia_batt_mwh)

# ==========================================
# 6. DASHBOARD E GRAFICI
# ==========================================
st.title("🏭 Simulatore H2: Sizing, Suolo e LCOH (Reverse Engineering)")

# KPI
st.markdown("### 📊 Metriche di Progetto")
c1, c2, c3, c4 = st.columns(4)
c1.metric("LCOH Finale", f"€ {lcoh_finale:.2f} / kg")
c2.metric("Taglia Elettrolizzatore", f"{taglia_ely_mw:.1f} MW")
c3.metric("CF Elettrolizzatore", f"{cf_totale_ely*100:.1f} %")
c4.metric("Consumo Suolo PV", f"{ettari_pv:,.1f} Ettari")

st.markdown("---")

col_g1, col_g2 = st.columns(2)

with col_g1:
    st.markdown("### 💶 Scomposizione Costo (LCOH)")
    df_costi = pd.DataFrame({
        "Componente": ["Costo Energia (CfD)", "CAPEX Elettrolizzatore", "CAPEX Batterie", "OPEX & Stoccaggio (+20%)"],
        "€/kg": [costo_energia_kg, costo_ely_kg, costo_batt_kg, costo_opex_stoccaggio_kg]
    })
    fig_costi = px.bar(df_costi, x="Componente", y="€/kg", color="Componente", text_auto=".2f",
                       color_discrete_sequence=['#2E7D32', '#1565C0', '#F9A825', '#424242'])
    fig_costi.update_layout(showlegend=False, yaxis_title="€ / kg H2")
    st.plotly_chart(fig_costi, use_container_width=True)

with col_g2:
    st.markdown("### 🏗️ Dimensionamento Impianti (MW)")
    df_cap = pd.DataFrame({
        "Tecnologia": ["Fotovoltaico (MW)", "Eolico (MW)", "Elettrolizzatore (MW)"],
        "Capacità": [taglia_pv_mw, taglia_wind_mw, taglia_ely_mw]
    })
    fig_cap = px.bar(df_cap, x="Tecnologia", y="Capacità", color="Tecnologia", text_auto=".1f",
                     color_discrete_sequence=['#FFB300', '#81D4FA', '#AB47BC'])
    fig_cap.update_layout(showlegend=False, yaxis_title="Megawatt (MW)")
    st.plotly_chart(fig_cap, use_container_width=True)

st.markdown("---")
st.markdown("### ⏱️ Simulazione Oraria di Dispacciamento (72 Ore Tipo)")
st.markdown("Questo grafico mostra la logica dinamica: l'energia rinnovabile (area verde) alimenta l'elettrolizzatore (linea rossa). Quando l'energia scarseggia, la batteria si scarica per mantenere l'elettrolizzatore in funzione, alzando il Capacity Factor.")

fig_orario = go.Figure()
fig_orario.add_trace(go.Scatter(x=df_orario['Ora'], y=df_orario['Rinnovabile (PV+Wind)'], fill='tozeroy', name='Rinnovabile (PV+Eolico)', line=dict(color='#81C784')))
fig_orario.add_trace(go.Scatter(x=df_orario['Ora'], y=df_orario['Uso Elettrolizzatore'], mode='lines', name='Carico Elettrolizzatore', line=dict(color='#D32F2F', width=3)))
if ore_accumulo > 0:
    fig_orario.add_trace(go.Scatter(x=df_orario['Ora'], y=df_orario['SoC Batteria (MWh)'], mode='lines', name='Stato Batteria (MWh)', line=dict(color='#FBC02D', dash='dot')))

fig_orario.update_layout(xaxis_title="Ora", yaxis_title="Potenza / Energia", hovermode="x unified")
st.plotly_chart(fig_orario, use_container_width=True)

# Note finali
with st.expander("📌 Dettagli Metodologici"):
    st.write("""
    - **LCOH:** Il calcolo include l'ammortamento (CRF 5% su 20 anni) dei CAPEX calcolati sulle capacità richieste per raggiungere il target.
    - **Capacity Factor (CF):** L'aggiunta di batterie e l'integrazione eolica aumentano il CF. Un CF più alto permette di installare un elettrolizzatore più piccolo (riducendo il CAPEX), ma richiede energia extra per compensare le inefficienze di ricarica.
    - **Consumo di Suolo:** Calcolato esclusivamente per la quota Fotovoltaica (impostato a 0.7 MW per Ettaro).
    """)
