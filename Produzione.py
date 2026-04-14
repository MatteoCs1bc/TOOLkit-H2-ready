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
# PESI GEOGRAFICI CURVE MEDIE
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
        
        pv_nord = _serie_pesata(df_pv, PV_WEIGHTS_NORD, scala=1000.0, clip_upper=1.0).values[:8760] 
        pv_sud = _serie_pesata(df_pv, PV_WEIGHTS_SUD, scala=1000.0, clip_upper=1.0).values[:8760]
        
        wind_nord = _serie_pesata(df_wind, WIND_WEIGHTS_NORD, scala=1.0, clip_upper=1.0).values[:8760]
        wind_sud = _serie_pesata(df_wind, WIND_WEIGHTS_SUD, scala=1.0, clip_upper=1.0).values[:8760]
        
        return pv_nord, pv_sud, wind_nord, wind_sud, False
    except Exception as e:
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
    soc = batt_mwh * 0.2  
    sqrt_eff = np.sqrt(eff_batt)
    
    for t in range(ore):
        avail = pv_array_mw[t] + wind_array_mw[t]
        
        if avail >= ely_mw:
            ely_usage[t] = ely_mw
            excess = avail - ely_mw
            charge_cap = (batt_mwh - soc) / sqrt_eff
            charge = min(excess, charge_cap)
            soc += charge * sqrt_eff
        else:
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
target_h2_ton = st.sidebar.number_input(
    "Target Idrogeno (ton/anno)", 
    min_value=10, 
    max_value=1000000, 
    value=1000, 
    step=100,
    help="Inserisci direttamente il numero o usa le freccette"
)
target_h2_kg = target_h2_ton * 1000

st.sidebar.header("🗺️ 2. Localizzazione Geografica")
regione = st.sidebar.selectbox("Zona Climatica", ["Nord Italia", "Sud Italia / Isole"])

st.sidebar.header("⚖️ 3. Mix Tecnologico")
quota_pv_pct = st.sidebar.slider("Mix: Fotovoltaico vs Eolico (%)", 0, 100, 50, step=5, help="100=Solo PV, 0=Solo Eolico")
quota_pv = quota_pv_pct / 100.0
quota_wind = 1.0 - quota_pv

st.sidebar.header("🔋 4. Architettura Accumulo")
strategia_batt = st.sidebar.radio("Seleziona configurazione impianto:", ["Senza Accumulo", "Con Accumulo Ottimizzato BESS"])
limite_batt_pv = st.sidebar.slider("Limite max Batteria (x MW Fotovoltaico)", 0.0, 5.0, 3.0, step=0.5, help="Limita la taglia massima della batteria a un multiplo della taglia del fotovoltaico.")

st.sidebar.header("💶 5. Costi Economici (CfD / CAPEX)")
cfd_pv = st.sidebar.slider("CfD Fotovoltaico (€/MWh)", 30.0, 120.0, 60.0, step=5.0)
cfd_wind = st.sidebar.slider("CfD Eolico (€/MWh)", 50.0, 150.0, 80.0, step=5.0)
capex_ely = st.sidebar.slider("CAPEX Elettrolizzatore (€/kW)", 500, 2000, 1000, step=100)
capex_batt = st.sidebar.slider("CAPEX Batterie (€/kWh)", 100, 500, 150, step=10)

st.sidebar.header("💰 6. Mercato e Rientro")
prezzo_vendita_h2 = st.sidebar.slider("Prezzo Vendita H2 (€/kg)", 2.0, 20.0, 8.0, step=0.5, help="Prezzo a cui venderai l'idrogeno o valore del metano sostituito.")

# ==========================================
# ESECUZIONE SIMULAZIONE H2
# ==========================================
cartella_script = os.path.dirname(os.path.abspath(__file__))
file_pv = os.path.join(cartella_script, "dataset_fotovoltaico_produzione.csv")
file_wind = os.path.join(cartella_script, "dataset_eolico_produzione.csv")

pv_n, pv_s, w_n, w_s, fallback = carica_profili_rinnovabili(file_pv, file_wind)
if fallback:
    st.error("⚠️ File CSV non trovati. Verranno usati dati fittizi.")

if regione == "Nord Italia":
    array_pv_1mw = pv_n
    array_wind_1mw = w_n
else:
    array_pv_1mw = pv_s
    array_wind_1mw = w_s

if "Con Accumulo" in strategia_batt:
    ely_base_mw = 0.6  
    batt_base_mwh = ely_base_mw * 6.0  
else:
    ely_base_mw = 1.0  
    batt_base_mwh = 0.0

pv_base_array = array_pv_1mw * quota_pv
wind_base_array = array_wind_1mw * quota_wind

ely_usage_base, _ = simula_h2_plant(pv_base_array, wind_base_array, ely_base_mw, batt_base_mwh)
energia_prodotta_base = np.sum(ely_usage_base)

EFF_ELY = 55.0  # kWh/kg
energia_target_mwh = (target_h2_kg * EFF_ELY) / 1000.0

moltiplicatore_scala = energia_target_mwh / energia_prodotta_base if energia_prodotta_base > 0 else 0

taglia_pv_mw = quota_pv * moltiplicatore_scala
taglia_wind_mw = quota_wind * moltiplicatore_scala
taglia_ely_mw = ely_base_mw * moltiplicatore_scala

# Calcolo taglia batterie con limite PV
taglia_batt_mwh_teorica = batt_base_mwh * moltiplicatore_scala
limite_assoluto_batt_mwh = taglia_pv_mw * limite_batt_pv
taglia_batt_mwh = min(taglia_batt_mwh_teorica, limite_assoluto_batt_mwh)

# Riesecuzione simulazione esatta
pv_final_array = array_pv_1mw * taglia_pv_mw
wind_final_array = array_wind_1mw * taglia_wind_mw
ely_usage_final, batt_soc_final = simula_h2_plant(pv_final_array, wind_final_array, taglia_ely_mw, taglia_batt_mwh)

# Risultati Tecnici
energia_pv_totale = np.sum(pv_final_array)
energia_wind_totale = np.sum(wind_final_array)
energia_rinnovabile_totale = energia_pv_totale + energia_wind_totale
energia_assorbita = np.sum(ely_usage_final)
energia_sprecata = energia_rinnovabile_totale - energia_assorbita

ore_funzionamento_eq = energia_assorbita / taglia_ely_mw if taglia_ely_mw > 0 else 0
cf_ely_percentuale = (ore_funzionamento_eq / 8760.0) * 100 if taglia_ely_mw > 0 else 0
curtailment_percentuale = (energia_sprecata / energia_rinnovabile_totale) * 100 if energia_rinnovabile_totale > 0 else 0
ettari_pv = taglia_pv_mw / 0.7  

# LCOH
WACC = 0.05
VITA = 20
CRF = (WACC * (1 + WACC)**VITA) / ((1 + WACC)**VITA - 1)

costo_energia_pv_totale = energia_pv_totale * cfd_pv
costo_energia_wind_totale = energia_wind_totale * cfd_wind
costo_energia_kg = (costo_energia_pv_totale + costo_energia_wind_totale) / target_h2_kg

costo_ely_kg = (taglia_ely_mw * 1000.0 * capex_ely * CRF) / target_h2_kg
costo_batt_kg = (taglia_batt_mwh * 1000.0 * capex_batt * CRF) / target_h2_kg

costo_parziale = costo_energia_kg + costo_ely_kg + costo_batt_kg
costo_opex_stoccaggio = costo_parziale * 0.20  
lcoh_finale = costo_parziale + costo_opex_stoccaggio

# ==========================================
# DASHBOARD E GRAFICI
# ==========================================
st.title("🏭 H2 Reverse Engineering: Sizing Ottimale e Payback")

# --- MENU A TENDINA (README INTEGRATO) ---
with st.expander("🛠️ Clicca qui per il Menù Metodologico e le Istruzioni"):
    st.markdown("""
    ### Come funziona il Reverse Engineering?
    L'obiettivo non è dire "quanto idrogeno produce il mio impianto", ma il contrario: l'utente inserisce la **domanda** (Target Idrogeno in ton/anno) e il codice calcola a ritroso:
    1. I Megawatt esatti di Fotovoltaico ed Eolico necessari.
    2. La taglia dell'Elettrolizzatore.
    3. La capacità del sistema di accumulo (BESS) per stabilizzare la produzione.

    ### La Logica Economica (Modello CfD PPA)
    * **CAPEX:** Il Comune o l'azienda investe *solo* nell'infrastruttura di trasformazione (Elettrolizzatore) e stoccaggio (Batterie). 
    * **OPEX:** L'energia rinnovabile (Fotovoltaico ed Eolico) viene acquistata tramite un PPA a prezzo fisso (i cursori CfD €/MWh).
    * **Payback:** Sottraendo ai ricavi di vendita l'intero OPEX energetico e i costi di manutenzione (3% del CAPEX totale).
    """)

# --- KPI PRINCIPALI ---
st.markdown("### 📊 Metriche di Progetto")
c1, c2, c3 = st.columns(3)
c1.metric("LCOH Finale", f"€ {lcoh_finale:.2f} / kg")
c2.metric("Taglia Elettrolizzatore", f"{taglia_ely_mw:,.1f} MW")
c3.metric("CF Elettrolizzatore", f"{cf_ely_percentuale:.1f} %", f"{ore_funzionamento_eq:,.0f} h/anno", delta_color="off")

st.markdown("<br>", unsafe_allow_html=True)

c4, c5, c6 = st.columns(3)
c4.metric("Taglia Batteria (BESS)", f"{taglia_batt_mwh:,.1f} MWh")
c5.metric("Curtailment (Energia Persa)", f"{energia_sprecata:,.0f} MWh", f"-{curtailment_percentuale:.1f}% dell'energia prodotta", delta_color="inverse")
c6.metric("Consumo Suolo PV", f"{ettari_pv:,.1f} ha", "Tracker Monoassiale")

st.markdown("---")
st.markdown("### ⚡ Generazione Rinnovabile")
col_rin_1, col_rin_2, col_rin_3, col_rin_4 = st.columns(4)
col_rin_1.metric("PV Installato", f"{taglia_pv_mw:,.1f} MW")
col_rin_2.metric("Produzione PV", f"{energia_pv_totale/1000:,.2f} GWh/y")
col_rin_3.metric("Eolico Installato", f"{taglia_wind_mw:,.1f} MW")
col_rin_4.metric("Produzione Eolico", f"{energia_wind_totale/1000:,.2f} GWh/y")

st.markdown("---")

# --- GRAFICO 8760H ---
st.markdown("### ⏱️ Profilo Operativo Annuale (8760 Ore)")
df_8760 = pd.DataFrame({
    'Ora': np.arange(8760),
    'PV': pv_final_array,
    'Eolico': wind_final_array,
    'Elettrolizzatore': ely_usage_final,
    'Batteria_SOC': batt_soc_final
})

fig_8760 = make_subplots(specs=[[{"secondary_y": True}]])
fig_8760.add_trace(go.Scattergl(x=df_8760['Ora'], y=df_8760['PV'], mode='lines', name='PV', line=dict(color='#FFC107', width=1.5)), secondary_y=False)
fig_8760.add_trace(go.Scattergl(x=df_8760['Ora'], y=df_8760['Eolico'], mode='lines', name='Eolico', line=dict(color='#03A9F4', width=1.5)), secondary_y=False)
fig_8760.add_trace(go.Scattergl(x=df_8760['Ora'], y=df_8760['Elettrolizzatore'], mode='lines', name='Elettrolizzatore', line=dict(color='#D32F2F', width=2)), secondary_y=False)
if taglia_batt_mwh > 0:
    fig_8760.add_trace(go.Scattergl(x=df_8760['Ora'], y=df_8760['Batteria_SOC'], mode='lines', name='Batteria (SOC orario)', line=dict(color='#4CAF50', width=2)), secondary_y=True)

fig_8760.update_layout(xaxis_title="Ore dell'anno", hovermode="x unified", height=500, margin=dict(l=0, r=0, t=30, b=0))
fig_8760.update_yaxes(title_text="Potenza (MW)", secondary_y=False)
if taglia_batt_mwh > 0:
    fig_8760.update_yaxes(title_text="SOC Batteria (MWh)", secondary_y=True)

st.plotly_chart(fig_8760, use_container_width=True)

st.markdown("---")

# --- ANALISI FINANZIARIA & GRAFICI ---
st.markdown("### 💶 Sostenibilità Economica e Analisi dei Flussi di Cassa")

# Calcoli Finanziari
capex_totale_h2 = (taglia_ely_mw * 1000 * capex_ely) + (taglia_batt_mwh * 1000 * capex_batt)
opex_energia_annuale = costo_energia_pv_totale + costo_energia_wind_totale
opex_manutenzione_annuale = capex_totale_h2 * 0.03 # 3% O&M su ELY e BATT
opex_totale_annuale = opex_energia_annuale + opex_manutenzione_annuale

ricavi_annuali = target_h2_kg * prezzo_vendita_h2
cash_flow_netto = ricavi_annuali - opex_totale_annuale
payback_anni = (capex_totale_h2 / cash_flow_netto) if cash_flow_netto > 0 else float('inf')

col_fin1, col_fin2, col_fin3, col_fin4 = st.columns(4)
col_fin1.metric("CAPEX Iniziale", f"€ {capex_totale_h2/1e6:,.2f} MLN")
col_fin2.metric("OPEX Annuale (Energia+O&M)", f"€ {opex_totale_annuale/1e6:,.2f} MLN")
col_fin3.metric("Ricavi Annuali (Vendita)", f"€ {ricavi_annuali/1e6:,.2f} MLN")

if cash_flow_netto > 0:
    col_fin4.metric("Tempo di Rientro", f"{payback_anni:,.1f} Anni")
else:
    col_fin4.metric("Tempo di Rientro", "In Perdita", delta_color="inverse")

# Grafici Finanziari
col_graf1, col_graf2 = st.columns(2)

with col_graf1:
    # Grafico a Barre: Entrate vs Uscite
    df_voci = pd.DataFrame({
        "Categoria": ["CAPEX (Investimento Anno 0)", "OPEX (Spesa Annuale)", "Ricavi (Entrata Annuale)", "Cash Flow Netto (Annuale)"],
        "Valore": [-capex_totale_h2, -opex_totale_annuale, ricavi_annuali, cash_flow_netto],
        "Tipo": ["Uscita (Rosso)", "Uscita (Rosso)", "Entrata (Verde)", "Netto (Blu)"]
    })
    
    fig_voci = px.bar(df_voci, x="Categoria", y="Valore", color="Tipo", text_auto=".2s",
                      color_discrete_map={"Uscita (Rosso)": "#D32F2F", "Entrata (Verde)": "#388E3C", "Netto (Blu)": "#1976D2"},
                      title="Ripartizione Voci Finanziarie (€)")
    fig_voci.update_layout(showlegend=False, yaxis_title="Euro (€)")
    st.plotly_chart(fig_voci, use_container_width=True)

with col_graf2:
    # Grafico Lineare: Flusso di Cassa Cumulato
    anni_array = np.arange(0, VITA + 1)
    flussi_array = np.full(VITA + 1, cash_flow_netto)
    flussi_array[0] = -capex_totale_h2  # Anno 0 solo investimenti, no operatività
    flusso_cumulato = np.cumsum(flussi_array)
    
    df_cashflow = pd.DataFrame({'Anno': anni_array, 'Flusso Cumulato': flusso_cumulato})
    
    fig_cumulato = go.Figure()
    fig_cumulato.add_trace(go.Scatter(x=df_cashflow['Anno'], y=df_cashflow['Flusso Cumulato'], 
                                      mode='lines+markers', name='Cash Flow',
                                      line=dict(color='#1976D2', width=3)))
    # Aggiungo la linea dello zero (Break-even point)
    fig_cumulato.add_hline(y=0, line_dash="dash", line_color="#D32F2F", annotation_text="Break-Even (Pareggio)")
    
    fig_cumulato.update_layout(title="Andamento Flusso di Cassa Cumulato (Payback)",
                               xaxis_title="Anno di Esercizio", yaxis_title="Euro (€)")
    st.plotly_chart(fig_cumulato, use_container_width=True)

# Messaggio finale di stato
if cash_flow_netto < 0:
    st.error("⚠️ **Progetto in perdita strutturale:** I ricavi dalla vendita dell'idrogeno non riescono a coprire nemmeno l'OPEX (acquisto energia e manutenzione). È necessario ridurre il costo dell'energia (CfD) o aumentare il prezzo di vendita dell'H2.")
elif payback_anni > VITA:
    st.warning(f"⚠️ **Rientro troppo lungo:** Il progetto genera cassa, ma il tempo di rientro ({payback_anni:.1f} anni) supera la vita utile dell'impianto ({VITA} anni). È indispensabile ottenere un bando a fondo perduto (es. PNRR) per abbattere il CAPEX iniziale.")
else:
    st.success(f"✅ **Progetto Bancabile:** Il sistema raggiunge il pareggio finanziario in {payback_anni:.1f} anni. Ottimo scenario per la presentazione a investitori o delibere comunali.")
