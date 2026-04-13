import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="H2READY - Reverse Engineering Spazio-Economico", layout="wide")

# --- COSTANTI E DATI TECNICI ---
EFF_ELY = 55.0  # kWh per 1 kg di H2
PREMIUM_BATTERIA_EKG = 1.50  # Costo forfettario LCOS batteria in €/kg H2
MOLTIPLICATORE_OPEX_STOCCAGGIO = 1.20  # +20% per stoccaggio, compressione e OPEX

# [Potenza Specifica W/m2, Ore Eq Base Nord]
TECH_DATA = {
    "PV a Terra (Tracker)": {"w_m2": 70.0, "h_eq_base": 1380},
    "PV Tetto Piano (Capannoni)": {"w_m2": 113.64, "h_eq_base": 1200},
    "Eolico (Area del Parco)": {"w_m2": 5.0, "h_eq_base": 1800}
}

# --- INTERFACCIA LATERALE ---
with st.sidebar:
    st.header("🎯 1. Target e Localizzazione")
    target_h2_ton = st.number_input("Target Idrogeno (Tonnellate/anno)", min_value=10, max_value=20000, value=500, step=50)
    target_h2_kg = target_h2_ton * 1000
    
    regione = st.selectbox("Zona Climatica", ["Nord Italia", "Centro Italia", "Sud Italia / Isole"])
    molt_regione = {"Nord Italia": 1.0, "Centro Italia": 1.15, "Sud Italia / Isole": 1.3}[regione]

    st.markdown("---")
    st.header("⚖️ 2. Mix Energetico")
    tipo_pv = st.radio("Scegli tecnologia Fotovoltaica:", ["PV a Terra (Tracker)", "PV Tetto Piano (Capannoni)"])
    
    quota_pv_pct = st.slider("Mix Fotovoltaico vs Eolico (%)", min_value=0, max_value=100, value=50, step=5, 
                             help="100% = Solo Fotovoltaico. 0% = Solo Eolico. Valori intermedi = Impianto Ibrido.")
    quota_pv = quota_pv_pct / 100.0
    quota_wind = 1.0 - quota_pv

    st.markdown("---")
    st.header("🔋 3. Architettura e Costi (CfD)")
    config_batterie = st.radio("Presenza di Accumulo (BESS):", ["Senza Batterie (Direct-Coupled)", "Con Batterie (Buffered)"])
    
    cfd_pv = st.slider("CfD Fotovoltaico (€/MWh)", 30.0, 150.0, 60.0, step=5.0)
    cfd_wind = st.slider("CfD Eolico (€/MWh)", 50.0, 180.0, 80.0, step=5.0)


# --- MOTORE DI CALCOLO ---
# 1. Energia Richiesta
perdita_batteria = 1.10 if "Con" in config_batterie else 1.0
energia_h2_pura_mwh = (target_h2_kg * EFF_ELY) / 1000
energia_totale_richiesta_mwh = energia_h2_pura_mwh * perdita_batteria

# Quota energia per fonte
energia_pv_mwh = energia_totale_richiesta_mwh * quota_pv
energia_wind_mwh = energia_totale_richiesta_mwh * quota_wind

# 2. Rese e Superfici
h_eq_pv = TECH_DATA[tipo_pv]["h_eq_base"] * molt_regione
h_eq_wind = TECH_DATA["Eolico (Area del Parco)"]["h_eq_base"] * molt_regione

# Resa in MWh per Ettaro: (W/m2 * 10000 / 1000000) * Ore
resa_ha_pv = (TECH_DATA[tipo_pv]["w_m2"] * 10000 / 1000000) * h_eq_pv
resa_ha_wind = (TECH_DATA["Eolico (Area del Parco)"]["w_m2"] * 10000 / 1000000) * h_eq_wind

ettari_pv = energia_pv_mwh / resa_ha_pv if resa_ha_pv > 0 and energia_pv_mwh > 0 else 0.0
ettari_wind = energia_wind_mwh / resa_ha_wind if resa_ha_wind > 0 and energia_wind_mwh > 0 else 0.0

# 3. Taglia Elettrolizzatore
if "Con" in config_batterie:
    taglia_ely_mw = energia_h2_pura_mwh / 4000.0  # CF forzato a 4000h grazie alle batterie
else:
    # CF ibrido stimato (media pesata delle ore)
    ore_mix = (h_eq_pv * quota_pv) + (h_eq_wind * quota_wind)
    taglia_ely_mw = energia_totale_richiesta_mwh / ore_mix if ore_mix > 0 else 0.0

# 4. Calcolo Economico LCOH
# Costo medio ponderato dell'energia (€/MWh)
lcoe_blended = (cfd_pv * quota_pv) + (cfd_wind * quota_wind)

# Costo energia pura per 1 kg di H2
costo_energia_per_kg = (lcoe_blended / 1000) * EFF_ELY * perdita_batteria

# Aggiunta premio batteria
costo_batteria_per_kg = PREMIUM_BATTERIA_EKG if "Con" in config_batterie else 0.0

# Subtotale prima dei ricarichi
subtotale_lcoh = costo_energia_per_kg + costo_batteria_per_kg

# LCOH Finale (+20% per stoccaggio, compressione, opex)
lcoh_finale = subtotale_lcoh * MOLTIPLICATORE_OPEX_STOCCAGGIO
markup_20_pct_valore = lcoh_finale - subtotale_lcoh


# --- DASHBOARD VISIVA ---
st.title("🔄 H2READY - Reverse Engineering Spazio-Economico")
st.markdown(f"**Obiettivo:** Produrre **{target_h2_kg:,.0f} kg/anno** di Idrogeno Verde (Costo energetico fisso: 55 kWh/kg).")

# KPI PRINCIPALI
col1, col2, col3, col4 = st.columns(4)
col1.metric("LCOH Stimato (€/kg)", f"€ {lcoh_finale:.2f}")
col2.metric("Superficie Totale Richiesta", f"{ettari_pv + ettari_wind:,.1f} Ettari")
col3.metric("Taglia Elettrolizzatore", f"{taglia_ely_mw:.1f} MW")
col4.metric("Energia Totale Generata", f"{energia_totale_richiesta_mwh:,.0f} MWh/y")

st.markdown("---")

# GRAFICI SCOMPOSIZIONE
col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("🗺️ Consumo di Suolo (Ettari)")
    df_suolo = pd.DataFrame({
        "Tecnologia": [tipo_pv, "Eolico (Area Parco)"],
        "Ettari": [ettari_pv, ettari_wind]
    })
    # Rimuovi righe a 0 per pulizia grafica
    df_suolo = df_suolo[df_suolo["Ettari"] > 0]
    
    if not df_suolo.empty:
        fig_suolo = px.pie(df_suolo, values='Ettari', names='Tecnologia', hole=0.5,
                           color='Tecnologia', 
                           color_discrete_map={tipo_pv: '#FFB300', "Eolico (Area Parco)": '#1E88E5'})
        fig_suolo.update_traces(textposition='inside', textinfo='value+label')
        st.plotly_chart(fig_suolo, use_container_width=True)
        
        st.info("💡 **Nota sull'Eolico:** Gli ettari indicati rappresentano l'**Area del Parco** (distanziamento pale per evitare ombre aerodinamiche). Il suolo effettivamente impermeabilizzato dalle fondamenta è inferiore al 3% di quest'area.")
    else:
        st.warning("Nessuna tecnologia selezionata.")

with col_g2:
    st.subheader("💶 Scomposizione Costo LCOH (€/kg)")
    
    # Dati per il Waterfall o Bar chart
    df_costi = pd.DataFrame({
        "Voce di Costo": ["Energia Rinnovabile", "Ammortamento Batterie", "+20% (Stocc/Compr/OPEX)"],
        "Costo (€/kg)": [costo_energia_per_kg, costo_batteria_per_kg, markup_20_pct_valore]
    })
    
    fig_costi = go.Figure(go.Waterfall(
        name = "LCOH", orientation = "v",
        measure = ["relative", "relative", "relative", "total"],
        x = ["Costo Energia (CfD)", "Costo Batterie", "Stoccaggio & OPEX", "LCOH FINALE"],
        textposition = "outside",
        text = [f"€{costo_energia_per_kg:.2f}", f"€{costo_batteria_per_kg:.2f}", f"€{markup_20_pct_valore:.2f}", f"€{lcoh_finale:.2f}"],
        y = [costo_energia_per_kg, costo_batteria_per_kg, markup_20_pct_valore, lcoh_finale],
        connector = {"line":{"color":"rgb(63, 63, 63)"}},
        decreasing = {"marker":{"color":"#ef553b"}},
        increasing = {"marker":{"color":"#00cc96"}},
        totals = {"marker":{"color":"#1f77b4"}}
    ))
    
    fig_costi.update_layout(showlegend=False, yaxis_title="€ / kg H2")
    st.plotly_chart(fig_costi, use_container_width=True)
    
    st.caption("Il costo finale è calcolato convertendo il CfD in €/kg (base 55 kWh/kg), sommando un eventuale premio per l'accumulo e maggiorando il totale del 20% per spese di compressione e gestione impianto.")

# DATI TABELLARI DETTAGLIATI
with st.expander("📊 Vedi Dettaglio Dati e Capacità Impianti (MW)"):
    df_dettaglio = pd.DataFrame({
        "Parametro": ["Quota Energia (%)", "Energia da produrre (MWh/y)", "Ore Equivalenti (h/y)", "Potenza Impianto Necessaria (MW)"],
        tipo_pv: [f"{quota_pv*100:.0f}%", f"{energia_pv_mwh:,.0f}", f"{h_eq_pv:,.0f}", f"{energia_pv_mwh/h_eq_pv if h_eq_pv>0 else 0:.1f}"],
        "Eolico": [f"{quota_wind*100:.0f}%", f"{energia_wind_mwh:,.0f}", f"{h_eq_wind:,.0f}", f"{energia_wind_mwh/h_eq_wind if h_eq_wind>0 else 0:.1f}"]
    })
    st.table(df_dettaglio)
