import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DSS Mobilità - Gap Analysis", layout="wide")
st.title("🚗 H2READY: Convenience Check & Strategia Incentivi")
st.markdown("Valutazione operativa e analisi del **Gap di Finanziamento** basata sui dati strutturali del database Excel.")

# --- FUNZIONE DI PULIZIA DATI ---
def clean_val(x):
    """Estrae i numeri in modo sicuro dalle celle Excel, ignorando unità di misura come [€/km]."""
    if pd.isna(x) or str(x).strip() == "": 
        return 0.0
    s = str(x).replace('€', '').replace('%', '').replace(' ', '').replace(',', '.')
    s = s.replace('[', '').replace(']', '')
    try: return float(s)
    except ValueError: return 0.0  

# --- FUNZIONE INTERPOLAZIONE ---
def interpolate(year, y_2024, y_2030):
    if year <= 2024: return y_2024
    if year >= 2030: return y_2030
    return y_2024 + (y_2030 - y_2024) * ((year - 2024) / (2030 - 2024))

# ==========================================
# 1. INTERFACCIA UTENTE (SIDEBAR) E LETTURA EXCEL
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
    
    st.header("2. Condizioni Ambientali")
    orografia = st.selectbox("Orografia del percorso", ["Pianura", "Collinare", "Montagna"])
    inverno_rigido = st.checkbox("Clima Invernale Rigido (< 0°C)")
    
    st.header("3. Sorgenti Energetiche")
    fonte_elettricita = st.radio("Sorgente Elettricità", ["Rete Pubblica", "Autoprodotta (FV)"])
    fonte_idrogeno = st.radio("Sorgente Idrogeno", ["Idrogeno Grigio", "Idrogeno da Rete", "Idrogeno Autoprodotto"])
    
    st.header("4. Proiezioni Future")
    anno_acquisto = st.slider("Anno Previsto di Acquisto", 2024, 2035, 2024)
    anni_utilizzo = st.slider("Ciclo di Vita Utile (Anni)", 5, 20, 10)

km_annui = km_giornalieri * giorni_operativi
total_km_life = km_annui * anni_utilizzo
mult_env = {"Pianura": 1.0, "Collinare": 1.25, "Montagna": 1.45}[orografia] * (1.25 if inverno_rigido else 1.0)

# Mappatura Nomi per estrazione Excel
fossile_name = "Benzina" if tipo_veicolo == "Automobile" else "Diesel"
bev_name = "Elettrico autoprodotto" if "FV" in fonte_elettricita else "Elettrico rete"
h2_name = "Idrogeno Grigio" if "Grigio" in fonte_idrogeno else ("Idrogeno rete" if "Rete" in fonte_idrogeno else "Idrogeno autoprodotto")

# ==========================================
# 2. ESTRAZIONE DIRETTA DATI EXCEL (COLONNE U, W, Z)
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
            "Autonomia": clean_val(df_raw.iloc[i, 3]),     # D
            "Consumo": clean_val(df_raw.iloc[i, 4]),       # E
            "Eta": clean_val(df_raw.iloc[i, 9]),           # J
            "OPEX_Fuel_km": clean_val(df_raw.iloc[i, 20]), # U (Costo Carburante €/km)
            "OPEX_Maint_km": clean_val(df_raw.iloc[i, 22]),# W (Costo Manutenzione €/km)
            "CAPEX": clean_val(df_raw.iloc[i, 25])         # Z (Costo Acquisto €)
        })

df_abs = pd.DataFrame(dati)

if df_abs.empty:
    st.error(f"Errore: Nessun dato trovato nel foglio {nome_foglio}.")
    st.stop()

# ==========================================
# 3. MOTORE CALCOLO TCO (FEDELE ALL'EXCEL)
# ==========================================
res = []
# Parametri Base per LCA
f_emiss = {"Benzina": 0.33, "Diesel": 0.307, "Elettrico rete": 0.215, "Elettrico autoprodotto": 0.055, "Idrogeno Grigio": 0.330, "Idrogeno rete": 0.387, "Idrogeno autoprodotto": 0.090}
c_emiss = {"Automobile": {"Fossile": 6000, "BEV": 12000, "H2": 14000}, "Autobus Urbano": {"Fossile": 50000, "BEV": 85000, "H2": 95000}, "Autobus Extraurbano": {"Fossile": 50000, "BEV": 85000, "H2": 95000}, "Camion Pesante": {"Fossile": 60000, "BEV": 110000, "H2": 125000}}
m_emiss_km = {"Fossile": 0.05, "BEV": 0.03, "H2": 0.04}
m_bev = interpolate(anno_acquisto, 1.0, 1.40)
m_h2 = interpolate(anno_acquisto, 1.0, 1.15)

for idx, r in df_abs.iterrows():
    t = r['Tecnologia']
    cat = 'BEV' if 'Elettrico' in t else ('H2' if 'Idrogeno' in t else 'Fossile')
    
    # Fisica e LCA
    aut_ev = r['Autonomia'] * (m_bev if cat=='BEV' else (m_h2 if cat=='H2' else 1.0))
    e_prod = c_emiss[tipo_veicolo][cat] / 1000
    e_man = (m_emiss_km[cat] * total_km_life) / 1000
    # Le emissioni operative salgono se ci sono colline (mult_env)
    e_fuel = (r['Consumo'] * mult_env * total_km_life * f_emiss[t]) / 1000 
    
    # TCO Esatto dalle Colonne U, W, Z
    cpx = r['CAPEX']
    mnt = r['OPEX_Maint_km'] * total_km_life
    # I costi carburante si adeguano all'orografia (mult_env) basandosi sul €/km dell'Excel
    fuel = r['OPEX_Fuel_km'] * mult_env * total_km_life
    
    res.append({
        "Tecnologia": t, 
        "Categoria_Base": "Elettrico (BEV)" if cat == 'BEV' else ("Idrogeno (FCEV)" if cat == 'H2' else t),
        "Autonomia": aut_ev, "Consumo": r['Consumo'], "Eta": r['Eta'] * 100 if r['Eta'] < 2 else r['Eta'],
        "E_Produzione": e_prod, "E_Manutenzione": e_man, "E_Carburante": e_fuel,
        "Costo_Veicolo": cpx, "Costo_Manutenzione": mnt, "Costo_Carburante": fuel,
        "TCO_Totale": cpx + mnt + fuel
    })

df_final = pd.DataFrame(res)

# Estrazione dei 3 profili attivi per Semaforo e Gap Analysis
tco_fossile = df_final[df_final['Tecnologia'] == fossile_name]['TCO_Totale'].values[0]
tco_bev = df_final[df_final['Tecnologia'] == bev_name]['TCO_Totale'].values[0]
tco_h2 = df_final[df_final['Tecnologia'] == h2_name]['TCO_Totale'].values[0]

# Valutazione Limiti Fisici (Semaforo)
densita_batt = interpolate(anno_acquisto, 0.16, 0.256)
cons_reale_bev = df_final[df_final['Tecnologia'] == bev_name]['Consumo'].values[0] * mult_env
fabbisogno_kwh = km_giornalieri * cons_reale_bev * 1.15
peso_batt = fabbisogno_kwh / densita_batt
tempo_ric = fabbisogno_kwh / (1000 if (anno_acquisto >= 2028 and tipo_veicolo != "Automobile") else 150)

lim_peso = {"Automobile": 400, "Autobus Urbano": 3000, "Autobus Extraurbano": 4000, "Camion Pesante": 4500}[tipo_veicolo]
peso_netto_perso = peso_batt if tipo_veicolo == "Automobile" else max(0, peso_batt - interpolate(anno_acquisto, 2000, 4000))
sem_peso = "🟢 OK" if peso_netto_perso <= lim_peso * 0.7 else ("🟡 ATTENZIONE" if peso_netto_perso <= lim_peso else "🔴 CRITICO")
sem_tempo = "🟢 OK" if tempo_ric <= tempo_inattivita * 0.8 else ("🟡 ATTENZIONE" if tempo_ric <= tempo_inattivita else "🔴 CRITICO")

# ==========================================
# 4. DASHBOARD: VERDETTO E GAP ANALYSIS
# ==========================================
st.subheader("📋 Verdetto di Fattibilità Operativa")
if tipo_veicolo in ["Autobus Urbano", "Automobile"] and km_giornalieri <= 200:
    st.success("### 🟢 VERDETTO IMMEDIATO: VANTAGGIO ASSOLUTO BEV (Elettrico)")
    st.write(f"Per impieghi come {tipo_veicolo.lower()} su percorsi brevi, i veicoli a batteria dominano in termini di parità economica e tecnica.")
else:
    vince_h2 = "🔴 CRITICO" in sem_peso or "🔴 CRITICO" in sem_tempo or tco_h2 < (tco_bev * 0.9)
    if vince_h2: 
        st.error("### 🔵 L'IDROGENO È LA SCELTA STRATEGICA MIGLIORE")
        st.write("L'elettrico fallisce i requisiti fisici (limiti di peso o ricarica) o risulta troppo costoso.")
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

# Dati filtrati per Autonomia e Consumo (Solo 3 Barre)
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
    st.subheader("B. Consumo Fisico [kWh/km]")
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
    df_melt_e = df_final.melt(id_vars="Tecnologia", value_vars=['E_Produzione', 'E_Manutenzione', 'E_Carburante'], var_name="Fase", value_name="tCO2")
    df_melt_e['Fase'] = df_melt_e['Fase'].replace({'E_Produzione': 'Costruzione', 'E_Manutenzione': 'Manutenzione', 'E_Carburante': 'Carburante/Uso'})
    f4 = px.bar(df_melt_e, x="Tecnologia", y="tCO2", color="Fase", barmode='stack', color_discrete_sequence=["#8E8E8E", "#FF7F0E", "#D62728"])
    f4.add_hline(y=(diesel_val['E_Produzione'] + diesel_val['E_Manutenzione'] + diesel_val['E_Carburante']), line_dash="dash", line_color="black")
    st.plotly_chart(f4, use_container_width=True)

# Nuovo Grafico TCO per tutte e 7 le Tecnologie
st.divider()
st.subheader("E. Costo Totale di Proprietà (TCO) Spacchettato [€]")
df_melt_c = df_final.melt(id_vars="Tecnologia", value_vars=['Costo_Veicolo', 'Costo_Manutenzione', 'Costo_Carburante'], var_name="Voce", value_name="Euro")
df_melt_c['Voce'] = df_melt_c['Voce'].replace({'Costo_Veicolo': 'Acquisto Mezzo (CAPEX)', 'Costo_Manutenzione': 'Manutenzione (OPEX)', 'Costo_Carburante': 'Carburante (OPEX)'})

f5 = px.bar(df_melt_c, x="Tecnologia", y="Euro", color="Voce", barmode='stack', color_discrete_sequence=["#0068C9", "#FFA421", "#2CA02C"])
f5.add_hline(y=tco_fossile, line_dash="dash", line_color="black", annotation_text=f"Baseline {fossile_name}")
f5.update_layout(yaxis_title="Euro (€) nel Ciclo di Vita")
st.plotly_chart(f5, use_container_width=True)
