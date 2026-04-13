import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configurazione Pagina
st.set_page_config(page_title="H2READY - LCOH & Space Sizing Tool", layout="wide")

# ==========================================
# 1. PARAMETRI E COSTANTI
# ==========================================
EFF_ELY = 55.0  # kWh per 1 kg di H2
ORE_BASE_PV = 1400.0  # Ore equivalenti medie PV 
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
    st.header("⚖️ 2. Mix Energetico")
    quota_pv_pct = st.slider("Mix: Fotovoltaico vs Eolico (%)", 0, 100, 50, step=5, help="100% = Solo PV, 0% = Solo Eolico")
    quota_pv = quota_pv_pct / 100.0
    quota_wind = 1.0 - quota_pv
    
    st.markdown("---")
    st.header("🔋 3. Strategia Accumulo")
    strategia_batt = st.radio(
        "Seleziona configurazione impianto:", 
        ["Senza Accumulo (Direct-Coupled)", "Con Accumulo Ottimizzato BESS"]
    )
    
    st.markdown("---")
    st.header("💶 4. Costi ed Economia")
    cfd_pv = st.slider("CfD Fotovoltaico (€/MWh)", 30.0, 120.0, 60.0, step=5.0)
    cfd_wind = st.slider("CfD Eolico (€/MWh)", 50.0, 150.0, 80.0, step=5.0)
    capex_ely = st.slider("CAPEX Elettrolizzatore (€/kW)", 500, 2000, 1000, step=100)
    capex_batt = st.slider("CAPEX Batterie (€/kWh)", 100, 500, 250, step=10)

# ==========================================
# 3. MOTORE DI CALCOLO MATEMATICO
# ==========================================
# Energia Totale
energia_pura_mwh = (target_h2_kg * EFF_ELY) / 1000.0

if "Con Accumulo" in strategia_batt:
    molt_energia = 1.10 # +10% per perdite accumulo
    energia_totale_mwh = energia_pura_mwh * molt_energia
    # CF Ottimizzato: Il mix rinnovabile viene 'spalmato' dalla batteria
    cf_base_rinnovabile = (quota_pv * 0.16) + (quota_wind * 0.23)
    cf_totale_ely = min(cf_base_rinnovabile * 1.6, 0.70) # Le batterie alzano il CF del 60%, con cap al 70%
    ore_eq_ely = cf_totale_ely * 8760.0
    taglia_ely_mw = energia_totale_mwh / ore_eq_ely
    # Dimensionamento euristico batteria: circa 6 ore della taglia dell'elettrolizzatore per stabilizzare
    taglia_batt_mwh = taglia_ely_mw * 6.0 
else:
    molt_energia = 1.0
    energia_totale_mwh = energia_pura_mwh
    # CF Diretto: L'elettrolizzatore segue passivamente le rinnovabili, tagliando i picchi (circa 90% dell'energia catturata)
    cf_base_rinnovabile = (quota_pv * 0.16) + (quota_wind * 0.23)
    cf_totale_ely = cf_base_rinnovabile * 0.90
    ore_eq_ely = cf_totale_ely * 8760.0
    taglia_ely_mw = energia_totale_mwh / ore_eq_ely
    taglia_batt_mwh = 0.0

# Dimensionamento Rinnovabili
taglia_pv_mw = (energia_totale_mwh * quota_pv) / ORE_BASE_PV if quota_pv > 0 else 0
taglia_wind_mw = (energia_totale_mwh * quota_wind) / ORE_BASE_WIND if quota_wind > 0 else 0

# Consumo di suolo (SOLO PV)
ettari_pv = taglia_pv_mw / RESA_HA_PV

# ==========================================
# 4. CALCOLO ECONOMICO (LCOH €/kg)
# ==========================================
lcoe_mix = (cfd_pv * quota_pv) + (cfd_wind * quota_wind)
costo_energia_kg = (lcoe_mix / 1000.0) * EFF_ELY * molt_energia

capex_ely_totale = taglia_ely_mw * 1000.0 * capex_ely
rata_annua_ely = capex_ely_totale * CRF
costo_ely_kg = rata_annua_ely / target_h2_kg

capex_batt_totale = taglia_batt_mwh * 1000.0 * capex_batt
rata_annua_batt = capex_batt_totale * CRF
costo_batt_kg = rata_annua_batt / target_h2_kg

costo_parziale_kg = costo_energia_kg + costo_ely_kg + costo_batt_kg
costo_opex_stoccaggio_kg = costo_parziale_kg * 0.20

lcoh_finale = costo_parziale_kg + costo_opex_stoccaggio_kg

# ==========================================
# 5. SIMULAZIONE PROFILO ANNUALE (8760 ORE -> COMPRESSO A 876 STEP PER PERFORMANCE)
# ==========================================
@st.cache_data
def genera_profilo_annuale(pv_mw, wind_mw, ely_mw, batt_max_mwh):
    """Genera un profilo sintetico di 8760 ore (campionato ogni 10 ore per velocità di render)"""
    steps = 876
    t = np.arange(steps) * 10 # Ore da 0 a 8760
    
    # PV: Ciclo diurno + Stagionalità (Picco estate, basso inverno)
    pv_curve = np.maximum(0, np.sin(t * np.pi/12 - np.pi/2)) * (1 + 0.3*np.cos(t*np.pi/4380 - np.pi)) * pv_mw * 1.5
    
    # Wind: Più casuale, leggermente più forte d'inverno
    wind_curve = np.maximum(0, 0.5 + 0.4*np.sin(t*np.pi/72) + 0.3*np.cos(t*np.pi/4380)) * wind_mw * 1.2
    
    ren_tot = pv_curve + wind_curve
    
    ely_usage = np.zeros(steps)
    batt_soc = np.zeros(steps)
    soc_current = batt_max_mwh * 0.5 # Parte a metà carica
    
    # Simula logica di accumulo
    for i in range(steps):
        avail = ren_tot[i]
        
        if batt_max_mwh > 0:
            if avail >= ely_mw:
                ely_usage[i] = ely_mw
                excess = avail - ely_mw
                charge = min(excess, batt_max_mwh - soc_current)
                soc_current += charge
            else:
                deficit = ely_mw - avail
                discharge = min(deficit, soc_current)
                soc_current -= discharge
                ely_usage[i] = avail + discharge
        else:
            ely_usage[i] = min(avail, ely_mw)
            
        batt_soc[i] = soc_current
        
    return pd.DataFrame({
        'Ora': t, 
        'Fotovoltaico': pv_curve, 
        'Eolico': wind_curve,
        'Rinnovabile Totale': ren_tot, 
        'Elettrolizzatore': ely_usage, 
        'Batteria_MWh': batt_soc
    })

df_annuale = genera_profilo_annuale(taglia_pv_mw, taglia_wind_mw, taglia_ely_mw, taglia_batt_mwh)

# ==========================================
# 6. DASHBOARD E GRAFICI
# ==========================================
st.title("🏭 Simulatore H2: Dimensionamento, Suolo e LCOH (Profilo 8760h)")

# --- KPI PRINCIPALI ---
st.markdown("### 📊 Metriche di Progetto")
c1, c2, c3, c4 = st.columns(4)
c1.metric("LCOH Finale", f"€ {lcoh_finale:.2f} / kg")
c2.metric("Taglia Elettrolizzatore", f"{taglia_ely_mw:.1f} MW", help=f"Capacity Factor: {cf_totale_ely*100:.1f}%")
if taglia_batt_mwh > 0:
    c3.metric("Taglia Batteria (BESS)", f"{taglia_batt_mwh:.1f} MWh")
else:
    c3.metric("Taglia Batteria (BESS)", "0.0 MWh")
c4.metric("Consumo Suolo PV", f"{ettari_pv:,.1f} Ettari")

st.markdown("---")

# --- GRAFICO ANNUALE 8760h ---
st.markdown("### ⏱️ Profilo Operativo Annuale (8760 Ore)")
st.markdown("Mostra l'interazione tra le fonti rinnovabili (Aree) e il funzionamento dell'elettrolizzatore (Linea Rossa) durante l'anno.")

fig_orario = make_subplots(specs=[[{"secondary_y": True}]])

# Aree Rinnovabili
fig_orario.add_trace(go.Scatter(x=df_annuale['Ora'], y=df_annuale['Fotovoltaico'], fill='tozeroy', mode='none', name='Fotovoltaico', fillcolor='rgba(255, 193, 7, 0.4)'), secondary_y=False)
fig_orario.add_trace(go.Scatter(x=df_annuale['Ora'], y=df_annuale['Eolico'], fill='tonexty', mode='none', name='Eolico', fillcolor='rgba(3, 169, 244, 0.4)'), secondary_y=False)

# Linea Elettrolizzatore
fig_orario.add_trace(go.Scatter(x=df_annuale['Ora'], y=df_annuale['Elettrolizzatore'], mode='lines', name='Elettrolizzatore (MW)', line=dict(color='#D32F2F', width=2)), secondary_y=False)

# Linea Batteria (Asse Secondario)
if taglia_batt_mwh > 0:
    fig_orario.add_trace(go.Scatter(x=df_annuale['Ora'], y=df_annuale['Batteria_MWh'], mode='lines', name='Stato Batteria (MWh)', line=dict(color='#4CAF50', dash='dot', width=2)), secondary_y=True)

fig_orario.update_layout(
    xaxis_title="Ore dell'anno (0-8760)", 
    hovermode="x unified",
    height=450,
    margin=dict(l=0, r=0, t=30, b=0)
)
fig_orario.update_yaxes(title_text="Potenza (MW)", secondary_y=False)
if taglia_batt_mwh > 0:
    fig_orario.update_yaxes(title_text="Energia Accumulata (MWh)", secondary_y=True, range=[0, taglia_batt_mwh*1.1])

st.plotly_chart(fig_orario, use_container_width=True)

st.markdown("---")

# --- SCOMPOSIZIONE LCOH E CAPACITA' ---
col_g1, col_g2 = st.columns(2)

with col_g1:
    st.markdown("### 💶 Scomposizione Costo (LCOH)")
    df_costi = pd.DataFrame({
        "Componente": ["Costo Energia", "CAPEX Elettrolizzatore", "CAPEX Batterie", "OPEX & Stoccaggio (+20%)"],
        "€/kg": [costo_energia_kg, costo_ely_kg, costo_batt_kg, costo_opex_stoccaggio_kg]
    })
    fig_costi = go.Figure(data=[
        go.Bar(name='Costo', x=['LCOH Totale'], y=[costo_energia_kg], marker_color='#2E7D32', text=f"Energia: €{costo_energia_kg:.2f}", textposition='inside'),
        go.Bar(name='Costo', x=['LCOH Totale'], y=[costo_ely_kg], marker_color='#1565C0', text=f"CAPEX Ely: €{costo_ely_kg:.2f}", textposition='inside'),
        go.Bar(name='Costo', x=['LCOH Totale'], y=[costo_batt_kg], marker_color='#F9A825', text=f"CAPEX Batt: €{costo_batt_kg:.2f}", textposition='inside'),
        go.Bar(name='Costo', x=['LCOH Totale'], y=[costo_opex_stoccaggio_kg], marker_color='#424242', text=f"OPEX: €{costo_opex_stoccaggio_kg:.2f}", textposition='inside')
    ])
    fig_costi.update_layout(barmode='stack', showlegend=False, yaxis_title="€ / kg H2", height=400)
    st.plotly_chart(fig_costi, use_container_width=True)

with col_g2:
    st.markdown("### 🏗️ Capacità Installata (MW)")
    df_cap = pd.DataFrame({
        "Tecnologia": ["Fotovoltaico", "Eolico", "Elettrolizzatore"],
        "MW": [taglia_pv_mw, taglia_wind_mw, taglia_ely_mw]
    })
    fig_cap = px.bar(df_cap, x="Tecnologia", y="MW", color="Tecnologia", text_auto=".1f",
                     color_discrete_sequence=['#FFC107', '#03A9F4', '#D32F2F'])
    fig_cap.update_layout(showlegend=False, yaxis_title="Megawatt (MW)", height=400)
    st.plotly_chart(fig_cap, use_container_width=True)

# Note finali
st.info("💡 **Dinamica Economica:** Selezionando 'Con Accumulo Ottimizzato', il sistema dimensiona automaticamente una batteria in grado di alzare il Capacity Factor dell'elettrolizzatore. Questo riduce drasticamente la taglia (e il CAPEX) dell'elettrolizzatore necessario, ammortizzando il costo aggiuntivo delle batterie e abbassando il costo finale dell'idrogeno.")
