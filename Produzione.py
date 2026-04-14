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
st.set_page_config(page_title="H2READY - Progettazione e Finanza", layout="wide")

# ==========================================
# DATASET & PESI (NORD/SUD)
# ==========================================
PV_WEIGHTS_NORD = {'Lombardia orientale, area Brescia_NORD': 0.2956, 'Veneto centrale, area Padova_NORD': 0.2313, 'Emilia-Romagna orientale, area Ferrara,pianura_NORD': 0.2213, 'Piemonte meridionale, area Cuneo_NORD': 0.1874, 'Friuli-Venezia Giulia, area Udine_NORD': 0.0644}
PV_WEIGHTS_SUD = {'Puglia, area Lecce_SUD': 0.3241, 'Sicilia interna, area Caltanissetta,Enna_SUD': 0.2117, 'Lazio meridionale, area Latina_SUD': 0.1982, 'Sardegna, area Oristano,Campidano_SUD': 0.1330, 'Campania interna, area Benevento_SUD': 0.1330}
WIND_WEIGHTS_NORD = {'Crinale savonese entroterra ligure_NORD': 0.6020, 'Appennino emiliano, area Monte Cimone_NORD': 0.2239, 'Piemonte sud-occidentale , Cuneese_NORD': 0.0945, 'Veneto orientale , Delta del Po_NORD': 0.0647, 'Valle d’Aosta , area alpina_NORD': 0.0149}
WIND_WEIGHTS_SUD = {'Puglia, area Foggia,Daunia_SUD': 0.3093, 'Sicilia occidentale, area Trapani_SUD': 0.2267, 'Campania, area Benevento,Avellino_SUD': 0.1950, 'Basilicata, area Melfi,Potenza_SUD': 0.1489, 'Calabria, area Crotone,Catanzaro_SUD': 0.1201}

# ==========================================
# FUNZIONI SUPPORTO
# ==========================================
def _serie_pesata(df, pesi_colonne, scala=1.0, clip_upper=1.0):
    serie = sum(pd.to_numeric(df[col], errors='coerce').fillna(0.0) * peso for col, peso in pesi_colonne.items())
    return (serie / scala).clip(lower=0.0, upper=clip_upper).astype(float)

@st.cache_data
def carica_profili(file_pv, file_wind):
    try:
        df_pv = pd.read_csv(file_pv)
        df_wind = pd.read_csv(file_wind)
        return _serie_pesata(df_pv, PV_WEIGHTS_NORD, 1000.0).values[:8760], _serie_pesata(df_pv, PV_WEIGHTS_SUD, 1000.0).values[:8760], \
               _serie_pesata(df_wind, WIND_WEIGHTS_NORD).values[:8760], _serie_pesata(df_wind, WIND_WEIGHTS_SUD).values[:8760], False
    except:
        t = np.arange(8760)
        return np.clip(np.sin(t*np.pi/12),0,1)*0.8, np.clip(np.sin(t*np.pi/12),0,1)*0.9, np.random.rand(8760)*0.5, np.random.rand(8760)*0.7, True

@njit
def simula_h2_plant(pv, wind, ely_mw, batt_mwh, eff_batt=0.90):
    ore = 8760
    ely_usage, batt_soc = np.zeros(ore), np.zeros(ore)
    soc = batt_mwh * 0.2
    sqrt_eff = np.sqrt(eff_batt)
    for t in range(ore):
        avail = pv[t] + wind[t]
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
# SIDEBAR
# ==========================================
st.sidebar.header("🎯 1. Target")
target_h2_kg = st.sidebar.number_input("Target Idrogeno (ton/anno)", 10, 1000000, 1000) * 1000
regione = st.sidebar.selectbox("Zona Climatica", ["Nord Italia", "Sud Italia / Isole"])

st.sidebar.header("⚖️ 2. Mix & Rete")
quota_pv_pct = st.sidebar.slider("Mix: PV vs Eolico (%)", 0, 100, 50)
tipo_connessione = st.sidebar.radio("Tipo di Connessione", ["ON-GRID (Rete)", "OFF-GRID (Isola)"])
distanza_rete_km = st.sidebar.slider("Distanza Cabina (km)", 0.1, 20.0, 2.0) if tipo_connessione == "ON-GRID (Rete)" else 0.0

st.sidebar.header("🔋 3. Accumulo BESS")
strategia_batt = st.sidebar.radio("Configurazione:", ["Senza Accumulo", "Con Accumulo BESS"])
limite_batt_pv = st.sidebar.slider("Limite Batteria (x MW PV)", 0.0, 5.0, 3.0)

st.sidebar.header("💶 4. Costi (CfD / CAPEX)")
cfd_pv = st.sidebar.slider("CfD PV (€/MWh)", 30.0, 120.0, 60.0)
cfd_wind = st.sidebar.slider("CfD Eolico (€/MWh)", 30.0, 150.0, 80.0)
capex_ely = st.sidebar.slider("CAPEX Ely (€/kW)", 500, 2000, 1000)
capex_batt = st.sidebar.slider("CAPEX BESS (€/kWh)", 100, 500, 150)

st.sidebar.header("🛢️ 5. Stoccaggio H2")
perc_stoccaggio = st.sidebar.slider("Volume Stoccaggio (% Prod. Annua)", 0.0, 50.0, 1.0)
capex_stocc_kg = st.sidebar.slider("CAPEX Serbatoi (€/kg)", 100, 1500, 600)

st.sidebar.header("🗜️ 6. Compressione")
profilo_comp = st.sidebar.selectbox("Tipo", ["Standard (500 bar)", "Booster (700 bar)"])
inc_comp, cons_comp = (0.24, 2.23) if "Standard" in profilo_comp else (0.42, 4.11)

st.sidebar.header("💰 7. Mercato")
prezzo_h2 = st.sidebar.slider("Prezzo Vendita H2 (€/kg)", 2.0, 20.0, 8.0)

# ==========================================
# LOGICA DI CALCOLO
# ==========================================
p_n, p_s, w_n, w_s, fallback = carica_profili("dataset_fotovoltaico_produzione.csv", "dataset_eolico_produzione.csv")
arr_pv, arr_wind = (p_n, w_n) if regione == "Nord Italia" else (p_s, w_s)

eff_sistema = 55.0 + cons_comp
ely_b, batt_b = (0.6, 6.0) if "Accumulo" in strategia_batt else (1.0, 0.0)

res_base, _ = simula_h2_plant(arr_pv*(quota_pv_pct/100), arr_wind*(1-quota_pv_pct/100), ely_b, batt_b)
molt = ((target_h2_kg * eff_sistema)/1000.0) / np.sum(res_base) if np.sum(res_base) > 0 else 0

taglia_pv, taglia_wind, taglia_ely = (quota_pv_pct/100)*molt, (1-quota_pv_pct/100)*molt, ely_b*molt
taglia_batt = min(batt_b * molt, taglia_pv * limite_batt_pv)

ely_usage, batt_soc = simula_h2_plant(arr_pv*taglia_pv, arr_wind*taglia_wind, taglia_ely, taglia_batt)

prod_pv_gwh = np.sum(arr_pv*taglia_pv) / 1000
prod_wind_gwh = np.sum(arr_wind*taglia_wind) / 1000
energia_assorbita = np.sum(ely_usage)
energia_sprecata = (np.sum(arr_pv*taglia_pv) + np.sum(arr_wind*taglia_wind)) - energia_assorbita

# Finanza analitica
WACC, VITA = 0.05, 20
CRF = (WACC * (1+WACC)**VITA) / ((1+WACC)**VITA - 1)

c_ely = taglia_ely * 1000 * capex_ely
c_batt = taglia_batt * 1000 * capex_batt
c_stocc = (target_h2_kg * perc_stoccaggio/100) * capex_stocc_kg
c_comp = (inc_comp * target_h2_kg) / CRF
c_grid = 0.0
taglia_connessione = taglia_pv + taglia_wind
if tipo_connessione == "ON-GRID (Rete)":
    c_grid = (730000 + 300000*distanza_rete_km) if taglia_connessione > 6 else (8000 + 155000*distanza_rete_km)

capex_tot = c_ely + c_batt + c_stocc + c_comp + c_grid
opex_en = (np.sum(arr_pv*taglia_pv)*cfd_pv) + (np.sum(arr_wind*taglia_wind)*cfd_wind)
opex_maint = capex_tot * 0.03
lcoh = (opex_en + opex_maint + (capex_tot * CRF)) / target_h2_kg
ricavi = target_h2_kg * prezzo_h2
payback = capex_tot / (ricavi - opex_en - opex_maint) if (ricavi - opex_en - opex_maint) > 0 else 99

# ==========================================
# INTERFACCIA GRAFICA
# ==========================================
st.title("🏭 H2READY - Dashboard Tecnica & Finanziaria")

# ALERT ADDIZIONALITA'
st.warning("""
⚠️ **AVVISO ADDIZIONALITÀ (RED III / Atto Delegato UE):** Dal 2030, per essere classificato come 'Verde' (RFNBO), l'idrogeno prodotto dovrà rispettare il principio di **addizionalità**: l'elettrolizzatore potrà utilizzare solo energia FER prodotta da nuovi impianti non incentivati, con obbligo di correlazione oraria e geografica. Il presente modello simula già l'assetto PPA/CfD conforme a tali scenari futuri.
""")

# LETTURA FILE README AUTOMATICA
with st.expander("🛠️ SPIEGAZIONE CODICE E METODOLOGIA PASSO-PASSO"):
    try:
        cartella = os.path.dirname(os.path.abspath(__file__))
        percorso_md = os.path.join(cartella, "README_produzione.md")
        with open(percorso_md, "r", encoding="utf-8") as f:
            testo_md = f.read()
        st.markdown(testo_md)
    except FileNotFoundError:
        st.warning("⚠️ File 'README_produzione.md' non trovato.")

# --- SEZIONE 1: IMPIANTO E PRODUZIONE H2 ---
st.subheader("⚙️ Dati Impianto Idrogeno")
t1, t2, t3, t4 = st.columns(4)
t1.metric("Taglia Elettrolizzatore", f"{taglia_ely:,.1f} MW", f"Efficienza: {eff_sistema:.1f} kWh/kg")
t2.metric("Funzionamento Annuo", f"{(energia_assorbita/taglia_ely):,.0f} h/y", f"Capacity Factor: {(energia_assorbita/(taglia_ely*8760)*100):.1f}%")
t3.metric("Stoccaggio H2 (Massa)", f"{(target_h2_kg * perc_stoccaggio/100)/1000:,.1f} ton", f"{perc_stoccaggio}% della prod. annua")
t4.metric("Consumo Suolo PV", f"{taglia_pv/0.7:,.1f} ha", "Inseguimento Monoassiale")

st.markdown("---")

# --- SEZIONE 2: GENERAZIONE RINNOVABILE E BESS ---
st.subheader("⚡ Generazione Rinnovabile e Accumulo (Contratti PPA/CfD)")
r1, r2, r3, r4 = st.columns(4)
r1.metric("PV Installato (MW)", f"{taglia_pv:,.1f} MW")
r2.metric("Energia PV Acquistata", f"{prod_pv_gwh:,.2f} GWh/y")
r3.metric("Eolico Installato (MW)", f"{taglia_wind:,.1f} MW")
r4.metric("Energia Eolico Acquistata", f"{prod_wind_gwh:,.2f} GWh/y")

st.markdown("<br>", unsafe_allow_html=True)
b1, b2, b3, b4 = st.columns(4)
b1.metric("Capacità BESS (Accumulo)", f"{taglia_batt:,.1f} MWh")
b2.metric("Energia Persa (Curtailment)", f"{energia_sprecata/1000:,.2f} GWh/y", f"-{(energia_sprecata/(prod_pv_gwh*1000 + prod_wind_gwh*1000)*100):.1f}%", delta_color="inverse")
if tipo_connessione == "ON-GRID (Rete)":
    b3.metric("Allaccio Rete", f"{distanza_rete_km} km", f"{'AT' if taglia_connessione > 6 else 'MT'}")
else:
    b3.metric("Connessione Rete", "OFF-GRID", "Isola")
b4.metric("Consumo Compressione", f"{cons_comp:,.2f} kWh/kg", profilo_comp)

# --- GRAFICO 8760 ---
st.markdown("---")
st.markdown("### ⏱️ Profilo Operativo Orario (Simulazione 8760h)")
df_8760 = pd.DataFrame({'PV': arr_pv*taglia_pv, 'Eolico': arr_wind*taglia_wind, 'Ely': ely_usage, 'SOC': batt_soc})
fig_8760 = make_subplots(specs=[[{"secondary_y": True}]])
fig_8760.add_trace(go.Scattergl(y=df_8760['PV'], name="PV (MW)", line=dict(color='#FFC107', width=1)), secondary_y=False)
fig_8760.add_trace(go.Scattergl(y=df_8760['Eolico'], name="Eolico (MW)", line=dict(color='#03A9F4', width=1)), secondary_y=False)
fig_8760.add_trace(go.Scattergl(y=df_8760['Ely'], name="Assorbimento Totale (MW)", line=dict(color='#D32F2F', width=2)), secondary_y=False)
fig_8760.add_trace(go.Scattergl(y=df_8760['SOC'], name="BESS SOC (MWh)", line=dict(color='#4CAF50', dash='dash')), secondary_y=True)
st.plotly_chart(fig_8760, use_container_width=True)

# --- ANALISI FINANZIARIA ---
st.markdown("---")
st.subheader("💶 Analisi Finanziaria e Ripartizione CAPEX")
f1, f2, f3, f4 = st.columns(4)
f1.metric("LCOH (Costo H2)", f"€ {lcoh:.2f} / kg")
f2.metric("CAPEX Investimento", f"€ {capex_tot/1e6:.2f} MLN")
f3.metric("Tempo di Rientro", f"{payback:.1f} Anni" if payback < 50 else "In Perdita")
f4.metric("Ricavi Annuali", f"€ {ricavi/1e6:.2f} MLN/y")

c_fin1, c_fin2 = st.columns([1, 1])
with c_fin1:
    st.markdown("**Scomposizione Investimento Iniziale (CAPEX)**")
    df_pie = pd.DataFrame({
        'Voce': ['Elettrolizzatore', 'Batterie (BESS)', 'Stoccaggio H2', 'Compressione', 'Allaccio Rete'],
        'Valore': [c_ely, c_batt, c_stocc, c_comp, c_grid]
    })
    df_pie = df_pie[df_pie['Valore'] > 0]
    fig_pie = px.pie(df_pie, values='Valore', names='Voce', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig_pie, use_container_width=True)

with c_fin2:
    st.markdown("**Dettaglio Analitico Costi**")
    items = [
        {"Voce": "Elettrolizzatore", "Costo (€)": f"{c_ely:,.0f}", "Quota %": f"{(c_ely/capex_tot*100):.1f}%"},
        {"Voce": "Batterie BESS", "Costo (€)": f"{c_batt:,.0f}", "Quota %": f"{(c_batt/capex_tot*100):.1f}%"},
        {"Voce": "Stoccaggio H2 (Massa)", "Costo (€)": f"{c_stocc:,.0f}", "Quota %": f"{(c_stocc/capex_tot*100):.1f}%"},
        {"Voce": "Compressione (Potenza)", "Costo (€)": f"{c_comp:,.0f}", "Quota %": f"{(c_comp/capex_tot*100):.1f}%"},
        {"Voce": "Connessione Rete", "Costo (€)": f"{c_grid:,.0f}", "Quota %": f"{(c_grid/capex_tot*100):.1f}%"},
    ]
    st.table(pd.DataFrame(items))

# DISCLAIMER FINALE
st.markdown("---")
st.error(f"""
**NOTA METODOLOGICA:** Il modello adotta un approccio conservativo. L'energia viene prodotta tramite mix FER e acquistata tramite CfD per stabilizzare l'OPEX. 
**Esclusi:** Acquisizione terreni, permessi burocratici e trasporti stradali.
""")
