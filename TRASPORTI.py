import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DSS Mobilità - Gap Analysis", layout="wide")
st.title("🚗 H2READY: Simulatore Strategico di Flotta")
st.markdown("Integrazione del database Excel con **curve di proiezione tecnologica** (2024-2035) per un'analisi dinamica del TCO e delle Emissioni LCA.")

# --- FUNZIONE DI PULIZIA DATI ---
def clean_val(x):
    if pd.isna(x) or str(x).strip() == "": 
        return 0.0
    s = str(x).replace('€', '').replace('%', '').replace(' ', '').replace(',', '.')
    s = s.replace('[', '').replace(']', '')
    try:
        return float(s)
    except ValueError:
        return 0.0  

# --- FUNZIONE INTERPOLAZIONE ---
def interpolate(year, y_2024, y_2030):
    if year <= 2024: return y_2024
    if year >= 2030: return y_2030
    return y_2024 + (y_2030 - y_2024) * ((year - 2024) / (2030 - 2024))

# --- MENU A TENDINA DA FILE ESTERNO ---
NOME_FILE_MD = "REadMe_Mezzi.md"

if os.path.exists(NOME_FILE_MD):
    # Crea la tendina
    with st.expander("ℹ️ Leggi Istruzioni, Logiche e Assunzioni del Simulatore"):
        # Apre il file, lo legge e lo stampa a schermo come Markdown
        with open(NOME_FILE_MD, "r", encoding="utf-8") as f:
            st.markdown(f.read())
else:
    # Piccolo avviso se il file non è nella stessa cartella
    st.info(f"💡 Suggerimento: Carica il file '{NOME_FILE_MD}' nella stessa cartella per vedere qui le istruzioni.")

# ==========================================
# 1. INTERFACCIA UTENTE (SIDEBAR) 
# ==========================================

with st.sidebar:
    st.header("📂 Caricamento Database")
    NOME_FILE_EXCEL = "Comparison H2 elc FF.xlsx"
    if not os.path.exists(NOME_FILE_EXCEL):
        st.error(f"File '{NOME_FILE_EXCEL}' non trovato nel repository.")
        st.stop()
    
    xl = pd.ExcelFile(NOME_FILE_EXCEL, engine='openpyxl')
    
    st.header("1. Parametri di Missione")
    tipo_veicolo = st.selectbox("Tipo Veicolo", ["Automobile", "Autobus Urbano", "Autobus Extraurbano", "Camion Pesante"])
    km_giornalieri = st.slider("Percorrenza Giornaliera (km)", 10, 1000, 150 if tipo_veicolo == "Automobile" else 250, 10)
    giorni_operativi = st.slider("Giorni Operativi Annui", 200, 365, 300, 5)
    tempo_inattivita = st.slider("Finestra max per Ricarica (Ore)", 0.5, 12.0, 5.0, 0.5)
    
    st.header("2. Dimensionamento Flotta")
    n_veicoli = st.slider("Numero di veicoli da sostituire", 1, 500, 10, help="Definisce le dimensioni della flotta per calcolare fabbisogno energetico totale e investimenti macro.")

    st.header("3. Condizioni Ambientali")
    orografia = st.selectbox("Orografia del percorso", ["Pianura", "Collinare", "Montagna"])
    inverno_rigido = st.checkbox("Clima Invernale Rigido (< 0°C)")
    
    st.header("4. Costi Energetici Iniziali (2024)")
    p_in_benzina = st.number_input("Benzina (€/l)", value=1.90, format="%.2f") if tipo_veicolo == "Automobile" else 0.0
    p_in_diesel = st.number_input("Diesel (€/l)", value=1.80, format="%.2f")
    p_in_el_rete = st.number_input("Elettricità Rete (€/kWh)", value=0.31, format="%.3f")
    p_in_el_fv = st.number_input("Elettricità FV (€/kWh)", value=0.24, format="%.3f")
    p_in_h2_rete = st.number_input("H2 da Rete (€/kg)", value=20.00, format="%.2f")
    p_in_h2_fv = st.number_input("H2 Autoprodotto (€/kg)", value=15.00, format="%.2f")

    st.header("5. Proiezioni Tecnologiche")
    anno_acquisto = st.slider("Anno Previsto di Acquisto", 2024, 2035, 2024)
    anni_utilizzo = st.slider("Ciclo di Vita Utile (Anni)", 5, 30, 10) 

km_annui = km_giornalieri * giorni_operativi
total_km_life = km_annui * anni_utilizzo

fossile_name = "Benzina" if tipo_veicolo == "Automobile" else "Diesel"
bev_name = "Elettrico autoprodotto"
h2_name = "Idrogeno autoprodotto"

# ==========================================
# 2. ESTRAZIONE DATI FISICI (EXCEL)
# ==========================================
target_str = {"Automobile": "AUTO", "Camion Pesante": "CAMION", "Autobus Urbano": "AUTOBUS URBANO", "Autobus Extraurbano": "AUTOBUS EXTRAURBANO"}[tipo_veicolo]
nome_foglio = next((f for f in xl.sheet_names if f.upper() == target_str), xl.sheet_names[0])
df_raw = pd.read_excel(xl, sheet_name=nome_foglio, header=None)

dati = []
tecs = ["Benzina", "Diesel", "Elettrico rete", "Elettrico autoprodotto", "Idrogeno Grigio", "Idrogeno rete", "Idrogeno autoprodotto"]

for i in range(2, min(30, len(df_raw))): 
    nome = str(df_raw.iloc[i, 1]).strip()
    if nome in tecs:
        dati.append({
            "Tecnologia": nome, 
            "Autonomia": clean_val(df_raw.iloc[i, 3]),       # D
            "Consumo": clean_val(df_raw.iloc[i, 4]),         # E
            "Eta": clean_val(df_raw.iloc[i, 9]),             # J
            "OPEX_Maint_km": clean_val(df_raw.iloc[i, 22]),  # W (Manutenzione)
            "CAPEX": clean_val(df_raw.iloc[i, 25])           # Z (Costo Veicolo)
        })

df_abs = pd.DataFrame(dati)
if df_abs.empty:
    st.error(f"Errore: Nessun dato trovato nel foglio {nome_foglio}.")
    st.stop()

# ==========================================
# 3. MOTORE DI CALCOLO DINAMICO (LCA & TCO)
# ==========================================
mult_env = {"Pianura": 1.0, "Collinare": 1.25, "Montagna": 1.45}[orografia] * (1.25 if inverno_rigido else 1.0)
conv_factors = {"Benzina": 8.76, "Diesel": 9.91, "Idrogeno": 33.33, "Elettrico": 1.0}

# Fattori Emissioni (WtW)
f_emiss = {"Benzina": 0.33, "Diesel": 0.307, "Elettrico rete": 0.215, "Elettrico autoprodotto": 0.055, "Idrogeno Grigio": 0.330, "Idrogeno rete": 0.387, "Idrogeno autoprodotto": 0.090}

# Emissioni Costruzione Mezzo [kg CO2] (Ciclo intero)
c_emiss = {
    "Automobile": {"Fossile": 6000, "BEV": 12000, "H2": 14000},
    "Autobus Urbano": {"Fossile": 50000, "BEV": 85000, "H2": 95000},
    "Autobus Extraurbano": {"Fossile": 50000, "BEV": 85000, "H2": 95000},
    "Camion Pesante": {"Fossile": 60000, "BEV": 110000, "H2": 125000}
}

m_bev_auto = interpolate(anno_acquisto, 1.0, 1.40) # +40% autonomia al 2030
m_h2_auto = interpolate(anno_acquisto, 1.0, 1.15)  # +15% autonomia al 2030

# Proiezioni Riduzione Costo CAPEX 
fabbisogno_kwh = km_giornalieri * df_abs[df_abs['Tecnologia'] == 'Elettrico rete']['Consumo'].values[0] * mult_env * 1.15
fc_kw_stima = {"Automobile": 100, "Autobus Urbano": 200, "Autobus Extraurbano": 200, "Camion Pesante": 300}[tipo_veicolo]
delta_batt_capex = fabbisogno_kwh * (interpolate(anno_acquisto, 210, 100) - 210)
delta_fc_capex = fc_kw_stima * (interpolate(anno_acquisto, 330, 210) - 330)

res = []
for idx, r in df_abs.iterrows():
    t = r['Tecnologia']
    cat = 'BEV' if 'Elettrico' in t else ('H2' if 'Idrogeno' in t else 'Fossile')
    
    # 1. Prezzi Dinamici Carburante (Dai cursori + Trend futuri)
    if t == "Benzina": p_sim = p_in_benzina * interpolate(anno_acquisto, 1.0, 1.1)
    elif t == "Diesel": p_sim = p_in_diesel * interpolate(anno_acquisto, 1.0, 1.1)
    elif t == "Elettrico rete": p_sim = p_in_el_rete * interpolate(anno_acquisto, 1.0, 0.9)
    elif t == "Elettrico autoprodotto": p_sim = p_in_el_fv * interpolate(anno_acquisto, 1.0, 0.9)
    elif t == "Idrogeno Grigio": p_sim = p_in_h2_rete * interpolate(anno_acquisto, 1.0, 0.8)
    elif t == "Idrogeno rete": p_sim = p_in_h2_rete * interpolate(anno_acquisto, 1.0, 0.6)
    elif t == "Idrogeno autoprodotto": p_sim = p_in_h2_fv * interpolate(anno_acquisto, 1.0, 0.7)
    else: p_sim = 0.0

    # 2. Fisica ed Emissioni LCA (Sul ciclo di vita TOTALE)
    aut_ev = r['Autonomia'] * (m_bev_auto if cat=='BEV' else (m_h2_auto if cat=='H2' else 1.0))
    e_prod = c_emiss[tipo_veicolo][cat] / 1000.0 # Tonnellate (fisse per la vita)
    e_fuel = (r['Consumo'] * mult_env * total_km_life * f_emiss[t]) / 1000.0 
    
    # 3. Costi TCO
    divisore = conv_factors["Elettrico"]
    if "Benzina" in t: divisore = conv_factors["Benzina"]
    elif "Diesel" in t: divisore = conv_factors["Diesel"]
    elif "Idrogeno" in t: divisore = conv_factors["Idrogeno"]

    # Calcolo OPEX Fuel guidato dai cursori
    consumo_naturale = (r['Consumo'] * mult_env) / divisore
    fuel_cost = (consumo_naturale * total_km_life) * p_sim
    # Calcolo Maint letto dall'Excel
    mnt_cost = r['OPEX_Maint_km'] * total_km_life
    
    # Sconto CAPEX nel tempo
    if cat == 'BEV': cpx = max(0, r['CAPEX'] + delta_batt_capex)
    elif cat == 'H2': cpx = max(0, r['CAPEX'] + delta_fc_capex)
    else: cpx = r['CAPEX']
    
    res.append({
        "Tecnologia": t, 
        "Categoria_Base": "Elettrico (BEV)" if cat == 'BEV' else ("Idrogeno (FCEV)" if cat == 'H2' else t),
        "Autonomia": aut_ev, "Consumo": r['Consumo'], "Eta": r['Eta'] * 100 if r['Eta'] < 2 else r['Eta'],
        "E_Produzione": e_prod, "E_Carburante": e_fuel,
        "Costo_Veicolo": cpx, "Costo_Manutenzione": mnt_cost, "Costo_Carburante": fuel_cost,
        "TCO_Totale": cpx + mnt_cost + fuel_cost,
        "Consumo_Naturale": consumo_naturale # Salvato per i calcoli di flotta
    })

df_final = pd.DataFrame(res)

# ==========================================
# 4. DASHBOARD: VERDETTO E GAP ANALYSIS
# ==========================================
tco_fossile = df_final[df_final['Tecnologia'] == fossile_name]['TCO_Totale'].values[0]
tco_bev = df_final[df_final['Tecnologia'] == bev_name]['TCO_Totale'].values[0]
tco_h2 = df_final[df_final['Tecnologia'] == h2_name]['TCO_Totale'].values[0]

densita_batt = interpolate(anno_acquisto, 0.16, 0.256)
tempo_ric = fabbisogno_kwh / (1000 if (anno_acquisto >= 2028 and tipo_veicolo != "Automobile") else 150)
peso_batt = fabbisogno_kwh / densita_batt
lim_peso = {"Automobile": 400, "Autobus Urbano": 3000, "Autobus Extraurbano": 4000, "Camion Pesante": 4500}[tipo_veicolo]
peso_netto_perso = peso_batt if tipo_veicolo == "Automobile" else max(0, peso_batt - interpolate(anno_acquisto, 2000, 4000))

sem_peso = "🟢 OK" if peso_netto_perso <= lim_peso * 0.7 else ("🟡 ATTENZIONE" if peso_netto_perso <= lim_peso else "🔴 CRITICO")
sem_tempo = "🟢 OK" if tempo_ric <= tempo_inattivita * 0.8 else ("🟡 ATTENZIONE" if tempo_ric <= tempo_inattivita else "🔴 CRITICO")

st.subheader("📋 Verdetto di Fattibilità Operativa")
if tipo_veicolo in ["Autobus Urbano", "Automobile"] and km_giornalieri <= 200:
    st.success("### 🟢 VERDETTO IMMEDIATO: VANTAGGIO ASSOLUTO BEV (Elettrico)")
    st.write(f"Per impieghi urbani, i veicoli a batteria dominano in termini di parità economica e tecnica. Idrogeno ingiustificato.")
else:
    vince_h2 = "🔴 CRITICO" in sem_peso or "🔴 CRITICO" in sem_tempo or tco_h2 < (tco_bev * 0.9)
    if vince_h2: 
        st.error("### 🔵 L'IDROGENO È LA SCELTA STRATEGICA MIGLIORE")
        st.write("L'elettrico fallisce i requisiti fisici o risulta economicamente svantaggioso a causa delle max-batterie.")
    else: 
        st.success("### 🟢 L'ELETTRICO (BEV) È FATTIBILE E PIÙ ECONOMICO")
        st.write("La tecnologia a batteria copre la missione offrendo un Costo Totale (TCO) inferiore.")

st.markdown("### 🚦 Analisi dei Limiti Fisici Elettrici (BEV)")
c1, c2, c3 = st.columns(3)
c1.metric("Peso Batteria Richiesta", f"{peso_batt:,.0f} kg", "Critico" if peso_netto_perso > lim_peso else "OK", delta_color="inverse")
c2.metric("Tempo Ricarica Richiesto", f"{tempo_ric:.1f} h", f"vs {tempo_inattivita}h disponibili", delta_color="inverse" if tempo_ric > tempo_inattivita else "normal")
c3.metric("Delta Costo H2 vs BEV", f"€ {tco_h2 - tco_bev:,.0f}", f"{(tco_h2 - tco_bev)/total_km_life:,.2f} €/km", delta_color="inverse" if tco_h2 > tco_bev else "normal")

st.divider()
st.header("💰 Strategia Incentivi & Gap Analysis")
st.write(f"Confronto rispetto al veicolo **{fossile_name}** per l'intero ciclo di vita.")

col_i1, col_i2 = st.columns(2)
with col_i1:
    gap_bev = tco_bev - tco_fossile
    st.subheader(f"Elettrico ({bev_name})")
    st.metric("Gap TCO Totale", f"€ {gap_bev:,.0f}", delta_color="inverse")
    st.metric("Gap al Chilometro", f"€ {gap_bev/total_km_life:,.3f} /km", delta_color="inverse")

with col_i2:
    gap_h2 = tco_h2 - tco_fossile
    st.subheader(f"Idrogeno ({h2_name})")
    st.metric("Gap TCO Totale", f"€ {gap_h2:,.0f}", delta_color="inverse")
    st.metric("Gap al Chilometro", f"€ {gap_h2/total_km_life:,.3f} /km", delta_color="inverse")

# ==========================================
# 5. GRAFICI VALORI ASSOLUTI
# ==========================================
st.divider()
st.header("📊 Analisi Valori Assoluti (TCO & LCA)")

df_base = df_final[df_final['Categoria_Base'].isin([fossile_name, 'Elettrico (BEV)', 'Idrogeno (FCEV)'])].drop_duplicates(subset=['Categoria_Base'])
diesel_val = df_final[df_final['Tecnologia'] == fossile_name].iloc[0]

col_g1, col_g2 = st.columns(2)
with col_g1:
    st.subheader("A. Autonomia Massima [km]")
    f1 = px.bar(df_base, x="Categoria_Base", y="Autonomia", color="Categoria_Base", text_auto='.0f')
    f1.add_hline(y=diesel_val['Autonomia'], line_dash="dash", line_color="black")
    f1.update_layout(showlegend=False, xaxis_title="")
    st.plotly_chart(f1, use_container_width=True)
    
with col_g2:
    st.subheader("B. Consumo [kWh/km]")
    f2 = px.bar(df_base, x="Categoria_Base", y="Consumo", color="Categoria_Base", text_auto='.2f')
    f2.add_hline(y=diesel_val['Consumo'], line_dash="dash", line_color="black")
    f2.update_layout(showlegend=False, xaxis_title="")
    st.plotly_chart(f2, use_container_width=True)

col_g3, col_g4 = st.columns(2)
with col_g3:
    st.subheader("C. Efficienza Globale WtW [%]")
    f3 = px.bar(df_final, x="Tecnologia", y="Eta", color="Tecnologia", text_auto='.1f')
    f3.add_hline(y=diesel_val['Eta'], line_dash="dash", line_color="black")
    f3.update_layout(showlegend=False, yaxis_title="Rendimento %")
    st.plotly_chart(f3, use_container_width=True)

with col_g4:
    st.subheader("D. Emissioni LCA Totali [tCO2]")
    df_melt_e = df_final.melt(id_vars="Tecnologia", value_vars=['E_Produzione', 'E_Carburante'], var_name="Fase", value_name="tCO2")
    df_melt_e['Fase'] = df_melt_e['Fase'].replace({'E_Produzione': 'Costruzione', 'E_Carburante': 'Carburante/Uso'})
    f4 = px.bar(df_melt_e, x="Tecnologia", y="tCO2", color="Fase", barmode='stack', color_discrete_sequence=["#8E8E8E", "#D62728"])
    f4.add_hline(y=(diesel_val['E_Produzione'] + diesel_val['E_Carburante']), line_dash="dash", line_color="black")
    st.plotly_chart(f4, use_container_width=True)

# Grafico TCO per tutte le Tecnologie
st.divider()
st.subheader("E. Costo Totale di Proprietà (TCO) Spacchettato [€]")
df_melt_c = df_final.melt(id_vars="Tecnologia", value_vars=['Costo_Veicolo', 'Costo_Manutenzione', 'Costo_Carburante'], var_name="Voce", value_name="Euro")
df_melt_c['Voce'] = df_melt_c['Voce'].replace({'Costo_Veicolo': 'Acquisto Mezzo (CAPEX)', 'Costo_Manutenzione': 'Manutenzione (OPEX)', 'Costo_Carburante': 'Carburante (OPEX)'})

f5 = px.bar(df_melt_c, x="Tecnologia", y="Euro", color="Voce", barmode='stack', color_discrete_sequence=["#0068C9", "#FFA421", "#2CA02C"])
f5.add_hline(y=tco_fossile, line_dash="dash", line_color="black", annotation_text=f"Baseline {fossile_name}")
f5.update_layout(yaxis_title="Euro (€) nel Ciclo di Vita")
st.plotly_chart(f5, use_container_width=True)


# ==========================================
# 6. ANALISI DI FLOTTA E FABBISOGNO
# ==========================================
st.divider()
st.header(f"🏢 F. Analisi Macro: Transizione Flotta Intera ({n_veicoli} veicoli)")
st.write("Aggregazione del fabbisogno energetico e dei costi annui. Questo cruscotto evidenzia la differenza tra caricare le batterie prelevando dalla rete e produrre idrogeno verde tramite elettrolizzatori (Efficienza: ~55 kWh per kg di H2).")

# Dati di base estratti per i calcoli di flotta
row_bev = df_final[df_final['Tecnologia'] == bev_name].iloc[0]
row_h2 = df_final[df_final['Tecnologia'] == h2_name].iloc[0]

# Consumi totali annui
cons_annuo_bev_kwh = row_bev['Consumo_Naturale'] * km_annui * n_veicoli
cons_annuo_h2_kg = row_h2['Consumo_Naturale'] * km_annui * n_veicoli
energia_elettrolizzatore_annua = cons_annuo_h2_kg * 55.0  # Fabbisogno per produrre H2 (kWh)

# Calcolo costi macro (Annuali e Investimento)
capex_flotta_bev = row_bev['Costo_Veicolo'] * n_veicoli
opex_flotta_bev_annuo = (row_bev['Costo_Manutenzione'] + row_bev['Costo_Carburante']) / anni_utilizzo * n_veicoli

capex_flotta_h2 = row_h2['Costo_Veicolo'] * n_veicoli
opex_flotta_h2_annuo = (row_h2['Costo_Manutenzione'] + row_h2['Costo_Carburante']) / anni_utilizzo * n_veicoli

col_f1, col_f2 = st.columns(2)

with col_f1:
    st.subheader("🔋 Scenario 100% BEV")
    st.metric("Fabbisogno Elettrico Diretto", f"{cons_annuo_bev_kwh / 1000:,.1f} MWh/anno", "Energia per la ricarica batterie")
    st.metric("CAPEX Veicoli (Investimento)", f"€ {capex_flotta_bev / 1e6:,.2f} MLN")
    st.metric("OPEX Annuo (Energia + Maint.)", f"€ {opex_flotta_bev_annuo / 1000:,.0f} k")

with col_f2:
    st.subheader("🛢️ Scenario 100% Idrogeno")
    st.metric("Massa di H2 Consumata", f"{cons_annuo_h2_kg / 1000:,.1f} ton/anno")
    st.metric("Fabbisogno Elettrico per H2 (FER)", f"{energia_elettrolizzatore_annua / 1000:,.1f} MWh/anno", f"Differenza WtW vs BEV: +{(energia_elettrolizzatore_annua - cons_annuo_bev_kwh)/1000:,.1f} MWh", delta_color="inverse")
    st.metric("CAPEX Veicoli (Investimento)", f"€ {capex_flotta_h2 / 1e6:,.2f} MLN")
    st.metric("OPEX Annuo (Energia + Maint.)", f"€ {opex_flotta_h2_annuo / 1000:,.0f} k")

st.info("""
**💡 Attenzione agli oneri infrastrutturali non inclusi (Infrastruttura di Ricarica/Rifornimento):**
Ai costi dei mezzi fisici andrà sempre sommata la costruzione dell'infrastruttura. 
* **BEV:** Da ~€ 2.000 (Wallbox lente) a oltre € 80.000 per ogni colonnina Fast/Ultra-Fast dedicata ai mezzi pesanti.
* **H2 (FCEV):** La realizzazione di una HRS (Hydrogen Refueling Station) ad alta pressione richiede un CAPEX elevato che solitamente oscilla tra **1 e 3+ Milioni di €** in funzione dei kg erogati al giorno.
""")
