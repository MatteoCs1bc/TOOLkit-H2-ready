import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DSS Mobilità - Gap Analysis", layout="wide")
st.title("🚗 H2READY: Convenience Check & Strategia Incentivi")
st.markdown("Valutazione fisica, economica e analisi del **Gap di Finanziamento** per la transizione della flotta.")

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

# --- FUNZIONI DI INTERPOLAZIONE ---
def interpolate(year, y_2024, y_2030):
    if year <= 2024: return y_2024
    if year >= 2030: return y_2030
    return y_2024 + (y_2030 - y_2024) * ((year - 2024) / (2030 - 2024))

# --- INTERFACCIA UTENTE (SIDEBAR) ---
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
    
    st.header("3. Approvvigionamento Energia")
    prezzo_el_base = st.number_input("Prezzo Elettricità (€/kWh)", value=0.22, format="%.3f")
    prezzo_h2_base = st.number_input("Prezzo Mercato H2 oggi (€/kg)", value=16.0, format="%.2f")
    prezzo_diesel = st.number_input("Prezzo Diesel (€/l)", value=1.75, format="%.2f")
    prezzo_benzina = st.number_input("Prezzo Benzina (€/l)", value=1.85, format="%.2f")

    st.header("4. Proiezioni Future")
    anno_acquisto = st.slider("Anno Previsto di Acquisto", 2024, 2035, 2024)
    anni_utilizzo = st.slider("Ciclo di Vita Utile (Anni)", 5, 20, 10)

km_annui = km_giornalieri * giorni_operativi
total_km_life = km_annui * anni_utilizzo

# ==========================================
# MOTORE FISICO ED ECONOMICO (SIMULATORE)
# ==========================================

params = {
    "Automobile": {"glider": 25000, "fc_kw": 100, "tank_cost": 5000, "maint_bev": 0.03, "maint_h2": 0.05, "maint_fossile": 0.065, "cons_bev": 0.18, "cons_fossile": 0.06, "lim_peso": 400},
    "Autobus Urbano": {"glider": 150000, "fc_kw": 200, "tank_cost": 35000, "maint_bev": 0.15, "maint_h2": 0.25, "maint_fossile": 0.30, "cons_bev": 1.1, "cons_fossile": 0.35, "lim_peso": 3000},
    "Autobus Extraurbano": {"glider": 150000, "fc_kw": 200, "tank_cost": 35000, "maint_bev": 0.15, "maint_h2": 0.25, "maint_fossile": 0.30, "cons_bev": 1.0, "cons_fossile": 0.30, "lim_peso": 4000},
    "Camion Pesante": {"glider": 120000, "fc_kw": 300, "tank_cost": 45000, "maint_bev": 0.15, "maint_h2": 0.25, "maint_fossile": 0.25, "cons_bev": 1.4, "cons_fossile": 0.33, "lim_peso": 4500}
}
p = params[tipo_veicolo]
mult_env = {"Pianura": 1.0, "Collinare": 1.25, "Montagna": 1.45}[orografia] * (1.25 if inverno_rigido else 1.0)

# Fisica BEV
densita_batt = interpolate(anno_acquisto, 0.16, 0.256)
cons_reale_bev = p["cons_bev"] * mult_env
fabbisogno_kwh = km_giornalieri * cons_reale_bev * 1.15
peso_batt = fabbisogno_kwh / densita_batt
tempo_ric = fabbisogno_kwh / (1000 if (anno_acquisto >= 2028 and tipo_veicolo != "Automobile") else 150)

# Economia Simulatori Rapidi
costo_batt = interpolate(anno_acquisto, 210, 100)
costo_fc = interpolate(anno_acquisto, 330, 210)
prezzo_h2_sim = interpolate(anno_acquisto, prezzo_h2_base, 8.0)
prezzo_el_sim = interpolate(anno_acquisto, prezzo_el_base, prezzo_el_base * 0.9)

tco_bev = (p["glider"] + fabbisogno_kwh * costo_batt) + (total_km_life * (cons_reale_bev * prezzo_el_sim + p["maint_bev"]))
tco_h2 = (p["glider"] + p["fc_kw"] * costo_fc + p["tank_cost"]) + (total_km_life * ((cons_reale_bev/15.0) * prezzo_h2_sim + p["maint_h2"]))

prezzo_f_base = prezzo_benzina if tipo_veicolo == "Automobile" else prezzo_diesel
tco_fossile = (p["glider"] * 0.8) + (total_km_life * (p["cons_fossile"] * mult_env * prezzo_f_base + p["maint_fossile"]))

# Semafori
peso_netto_perso = peso_batt if tipo_veicolo == "Automobile" else max(0, peso_batt - interpolate(anno_acquisto, 2000, 4000))
sem_peso = "🟢 OK" if peso_netto_perso <= p["lim_peso"] * 0.7 else ("🟡 ATTENZIONE" if peso_netto_perso <= p["lim_peso"] else "🔴 CRITICO")
sem_tempo = "🟢 OK" if tempo_ric <= tempo_inattivita * 0.8 else ("🟡 ATTENZIONE" if tempo_ric <= tempo_inattivita else "🔴 CRITICO")

# ==========================================
# DASHBOARD: VERDETTO E METRICHE
# ==========================================
st.subheader("📋 Verdetto di Fattibilità Operativa")
if tipo_veicolo in ["Autobus Urbano", "Automobile"] and km_giornalieri <= 200:
    st.success("### 🟢 VERDETTO IMMEDIATO: VANTAGGIO ASSOLUTO BEV (Elettrico)")
    st.write(f"Per impieghi come {tipo_veicolo.lower()} su percorsi brevi, i veicoli a batteria dominano in termini di parità economica e tecnica. L'idrogeno qui è uno spreco di risorse.")
else:
    vince_h2 = "🔴 CRITICO" in sem_peso or "🔴 CRITICO" in sem_tempo or tco_h2 < (tco_bev * 0.9)
    if vince_h2: 
        st.error("### 🔵 L'IDROGENO È LA SCELTA STRATEGICA MIGLIORE")
        st.write("L'elettrico a batterie fallisce i requisiti minimi di operatività fisica (limiti di peso o tempi di ricarica lenti) o risulta troppo costoso a causa dei mega-pacchi batteria necessari.")
    else: 
        st.success("### 🟢 L'ELETTRICO (BEV) È FATTIBILE E PIÙ ECONOMICO")
        st.write("Nonostante le difficoltà, la tecnologia a batteria riesce a coprire la missione richiesta nei tempi previsti, offrendo un Costo Totale (TCO) inferiore.")

st.markdown("### 🚦 Analisi dei Limiti Fisici Elettrici (BEV)")
c1, c2, c3 = st.columns(3)
c1.metric("Peso Batteria", f"{peso_batt:,.0f} kg", "Critico" if peso_netto_perso > p["lim_peso"] else "OK", delta_color="inverse")
c2.metric("Tempo Ricarica", f"{tempo_ric:.1f} h", f"vs {tempo_inattivita}h sosta", delta_color="inverse" if tempo_ric > tempo_inattivita else "normal")
c3.metric("Delta H2 vs BEV", f"€ {tco_h2 - tco_bev:,.0f}", f"{(tco_h2 - tco_bev)/total_km_life:,.2f} €/km", delta_color="inverse" if tco_h2 > tco_bev else "normal")

# ==========================================
# STRATEGIA INCENTIVI (GAP ANALYSIS)
# ==========================================
st.divider()
st.header("💰 Strategia Incentivi & Gap Analysis")
st.write(f"Confronto rispetto al veicolo **{('Benzina' if tipo_veicolo == 'Automobile' else 'Diesel')}** per l'intero ciclo di vita.")

col_i1, col_i2 = st.columns(2)
with col_i1:
    gap_bev = tco_bev - tco_fossile
    st.subheader("Elettrico (BEV)")
    st.metric("Gap TCO Totale", f"€ {gap_bev:,.0f}", delta_color="inverse")
    st.metric("Gap al Chilometro", f"€ {gap_bev/total_km_life:,.3f} /km", delta_color="inverse")

with col_i2:
    gap_h2 = tco_h2 - tco_fossile
    st.subheader("Idrogeno (FCEV)")
    st.metric("Gap TCO Totale", f"€ {gap_h2:,.0f}", delta_color="inverse")
    st.metric("Gap al Chilometro", f"€ {gap_h2/total_km_life:,.3f} /km", delta_color="inverse")

# ==========================================
# ANALISI VALORI ASSOLUTI E GRAFICI DA EXCEL
# ==========================================
st.divider()
st.header("📊 Analisi Valori Assoluti (Ciclo di Vita e TCO)")

try:
    target_str = {"Automobile": "AUTO", "Camion Pesante": "CAMION", "Autobus Urbano": "AUTOBUS URBANO", "Autobus Extraurbano": "AUTOBUS EXTRAURBANO"}[tipo_veicolo]
    nome_foglio = next((f for f in xl.sheet_names if f.upper() == target_str), xl.sheet_names[0])
    df_raw = pd.read_excel(xl, sheet_name=nome_foglio, header=None)
    
    dati = []
    tecs = ["Benzina", "Diesel", "Elettrico rete", "Elettrico autoprodotto", "Idrogeno Grigio", "Idrogeno rete", "Idrogeno autoprodotto"]
    
    for i in range(2, min(30, len(df_raw))): 
        nome = str(df_raw.iloc[i, 1]).strip()
        if nome in tecs:
            dati.append({"Tecnologia": nome, "Autonomia": clean_val(df_raw.iloc[i, 3]), "Consumo": clean_val(df_raw.iloc[i, 4]), "Eta": clean_val(df_raw.iloc[i, 9])})
    
    df_abs = pd.DataFrame(dati)
    
    # Costanti LCA ed Economiche
    f_emiss = {"Benzina": 0.33, "Diesel": 0.307, "Elettrico rete": 0.215, "Elettrico autoprodotto": 0.055, "Idrogeno Grigio": 0.330, "Idrogeno rete": 0.387, "Idrogeno autoprodotto": 0.090}
    c_emiss = {"Automobile": {"Fossile": 6000, "BEV": 12000, "H2": 14000}, "Autobus Urbano": {"Fossile": 50000, "BEV": 85000, "H2": 95000}, "Autobus Extraurbano": {"Fossile": 50000, "BEV": 85000, "H2": 95000}, "Camion Pesante": {"Fossile": 60000, "BEV": 110000, "H2": 125000}}
    m_emiss_km = {"Fossile": 0.05, "BEV": 0.03, "H2": 0.04}
    
    # Prezzi standardizzati e CONVERSIONE FATTORI (kWh -> natural units)
    prezzi_std = {
        "Benzina": prezzo_benzina, "Diesel": prezzo_diesel,
        "Elettrico rete": prezzo_el_base, "Elettrico autoprodotto": prezzo_el_base * 0.4, 
        "Idrogeno Grigio": 10.0, "Idrogeno rete": prezzo_h2_base, "Idrogeno autoprodotto": (55.0 * prezzo_el_base) + 2.5
    }
    
    # Fattori di conversione per trasformare i kWh/km del tuo Excel in Litri o Kg
    conv_kwh_to_nat = {
        "Benzina": 8.76,    # 1 Litro = 8.76 kWh
        "Diesel": 9.91,     # 1 Litro = 9.91 kWh
        "Idrogeno": 33.33,  # 1 Kg = 33.33 kWh
        "Elettrico": 1.0    # 1 kWh = 1 kWh
    }

    m_bev = interpolate(anno_acquisto, 1.0, 1.40)
    m_h2 = interpolate(anno_acquisto, 1.0, 1.15)

    res = []
    for idx, r in df_abs.iterrows():
        t = r['Tecnologia']
        cat = 'BEV' if 'Elettrico' in t else ('H2' if 'Idrogeno' in t else 'Fossile')
        
        # Identifica il fattore di conversione in base alla stringa
        divisore = conv_kwh_to_nat["Elettrico"]
        if "Benzina" in t: divisore = conv_kwh_to_nat["Benzina"]
        elif "Diesel" in t: divisore = conv_kwh_to_nat["Diesel"]
        elif "Idrogeno" in t: divisore = conv_kwh_to_nat["Idrogeno"]

        # Consumo in unità naturale (l/km, kg/km, kWh/km)
        consumo_naturale = r['Consumo'] / divisore
        
        # Fisica & LCA
        aut_ev = r['Autonomia'] * (m_bev if cat=='BEV' else (m_h2 if cat=='H2' else 1.0))
        e_prod = c_emiss[tipo_veicolo][cat] / 1000
        e_man = (m_emiss_km[cat] * total_km_life) / 1000
        e_fuel = (r['Consumo'] * total_km_life * f_emiss[t]) / 1000
        
        # TCO Spacchettato Corretto
        if cat == 'Fossile': cpx = p["glider"] * 0.8
        elif cat == 'BEV': cpx = p["glider"] + fabbisogno_kwh * costo_batt
        else: cpx = p["glider"] + p["fc_kw"] * costo_fc + p["tank_cost"]
        
        mnt = p[f"maint_{cat.lower()}"] * total_km_life
        
        # Costo Carburante reale = (Consumo Unità Naturale * km totali) * Prezzo alla pompa
        fuel_cost = (consumo_naturale * total_km_life) * prezzi_std[t]
        
        res.append({
            "Tecnologia": t, "Categoria_Base": "Elettrico (BEV)" if cat == 'BEV' else ("Idrogeno (FCEV)" if cat == 'H2' else t),
            "Autonomia": aut_ev, "Consumo": r['Consumo'], "Eta": r['Eta'] * 100 if r['Eta'] < 2 else r['Eta'],
            "E_Produzione": e_prod, "E_Manutenzione": e_man, "E_Carburante": e_fuel,
            "Costo_Veicolo": cpx, "Costo_Manutenzione": mnt, "Costo_Carburante": fuel_cost
        })
    
    df_final = pd.DataFrame(res)
    
    # Filtro base per Autonomia e Consumo
    baseline_tec = 'Benzina' if tipo_veicolo == "Automobile" else 'Diesel'
    df_base = df_final[df_final['Categoria_Base'].isin([baseline_tec, 'Elettrico (BEV)', 'Idrogeno (FCEV)'])].drop_duplicates(subset=['Categoria_Base'])
    diesel_val = df_final[df_final['Tecnologia'] == baseline_tec].iloc[0]

    # --- PLOTTING ---
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("A. Autonomia Massima [km]")
        f1 = px.bar(df_base, x="Categoria_Base", y="Autonomia", color="Categoria_Base", text_auto='.0f')
        f1.add_hline(y=diesel_val['Autonomia'], line_dash="dash", line_color="black")
        f1.update_layout(showlegend=False, xaxis_title="")
        st.plotly_chart(f1, use_container_width=True)
        
    with col_g2:
        st.subheader("B. Consumo [kWh/km, l/km, kg/km]")
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

    # TCO Spacchettato per tutte le tecnologie
    st.divider()
    st.subheader("E. Costo Totale di Proprietà Spacchettato [€]")
    df_melt_c = df_final.melt(id_vars="Tecnologia", value_vars=['Costo_Veicolo', 'Costo_Manutenzione', 'Costo_Carburante'], var_name="Voce", value_name="Euro")
    df_melt_c['Voce'] = df_melt_c['Voce'].replace({'Costo_Veicolo': 'Acquisto Mezzo (CAPEX)', 'Costo_Manutenzione': 'Manutenzione (OPEX)', 'Costo_Carburante': 'Carburante (OPEX)'})
    
    f5 = px.bar(df_melt_c, x="Tecnologia", y="Euro", color="Voce", barmode='stack', color_discrete_sequence=["#0068C9", "#FFA421", "#2CA02C"])
    tot_foss_cost = diesel_val['Costo_Veicolo'] + diesel_val['Costo_Manutenzione'] + diesel_val['Costo_Carburante']
    f5.add_hline(y=tot_foss_cost, line_dash="dash", line_color="black", annotation_text="Baseline Fossile")
    f5.update_layout(yaxis_title="Euro (€) nel Ciclo di Vita")
    st.plotly_chart(f5, use_container_width=True)

except Exception as e:
    st.error(f"Errore caricamento dati Excel: {e}")
