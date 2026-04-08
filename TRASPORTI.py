import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DSS Mobilità - Gap Analysis", layout="wide")
st.title("🚗 H2READY: Convenience Check & Strategia Incentivi")
st.markdown("Valutazione fisica, economica e analisi del **Gap di Finanziamento** per la transizione della flotta.")

# Legge il file README se presente
if os.path.exists("REadMe_Mezzi.md"):
    with st.expander("ℹ️ Leggi Istruzioni, Limiti e Assunzioni"):
        with open("REadMe_Mezzi.md", "r", encoding="utf-8") as f:
            st.markdown(f.read())

# --- FUNZIONI DI INTERPOLAZIONE ---
def interpolate(year, y_2024, y_2030):
    if year <= 2024: return y_2024
    if year >= 2030: return y_2030
    return y_2024 + (y_2030 - y_2024) * ((year - 2024) / (2030 - 2024))

# --- INTERFACCIA UTENTE (SIDEBAR) ---
with st.sidebar:
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
    anni_utilizzo = st.slider("Ciclo di Vita Utile (Anni)", 5, 15, 10)

km_annui = km_giornalieri * giorni_operativi
total_km_life = km_annui * anni_utilizzo

# ==========================================
# MOTORE FISICO ED ECONOMICO
# ==========================================

# Parametri Veicoli (Assunzioni Ingegneristiche)
params = {
    "Automobile": {"glider": 25000, "fc_kw": 100, "tank_cost": 5000, "maint_bev": 0.03, "maint_h2": 0.05, "maint_fossile": 0.05, "cons_bev": 0.18, "cons_fossile": 0.06, "lim_peso": 400},
    "Autobus Urbano": {"glider": 150000, "fc_kw": 200, "tank_cost": 35000, "maint_bev": 0.15, "maint_h2": 0.25, "maint_fossile": 0.30, "cons_bev": 1.1, "cons_fossile": 0.35, "lim_peso": 3000},
    "Autobus Extraurbano": {"glider": 150000, "fc_kw": 200, "tank_cost": 35000, "maint_bev": 0.15, "maint_h2": 0.25, "maint_fossile": 0.30, "cons_bev": 1.0, "cons_fossile": 0.30, "lim_peso": 4000},
    "Camion Pesante": {"glider": 120000, "fc_kw": 300, "tank_cost": 45000, "maint_bev": 0.15, "maint_h2": 0.25, "maint_fossile": 0.25, "cons_bev": 1.4, "cons_fossile": 0.33, "lim_peso": 4500}
}
p = params[tipo_veicolo]

# Correzioni Ambientali
mult_env = {"Pianura": 1.0, "Collinare": 1.25, "Montagna": 1.45}[orografia] * (1.25 if inverno_rigido else 1.0)

# 1. Calcoli Elettrico (BEV)
densita_batt = interpolate(anno_acquisto, 0.16, 0.256)
cons_reale_bev = p["cons_bev"] * mult_env
fabbisogno_kwh = km_giornalieri * cons_reale_bev * 1.15
peso_batt = fabbisogno_kwh / densita_batt
tempo_ric = fabbisogno_kwh / (1000 if (anno_acquisto >= 2028 and tipo_veicolo != "Automobile") else 150)

# 2. Economia
costo_batt = interpolate(anno_acquisto, 210, 100)
costo_fc = interpolate(anno_acquisto, 330, 210)
prezzo_h2_sim = interpolate(anno_acquisto, prezzo_h2_base, 8.0)
prezzo_el_sim = interpolate(anno_acquisto, prezzo_el_base, prezzo_el_base * 0.9)

tco_bev = (p["glider"] + fabbisogno_kwh * costo_batt) + (total_km_life * (cons_reale_bev * prezzo_el_sim + p["maint_bev"]))
tco_h2 = (p["glider"] + p["fc_kw"] * costo_fc + p["tank_cost"]) + (total_km_life * ((cons_reale_bev/15) * prezzo_h2_sim + p["maint_h2"]))

# Baseline Fossile
prezzo_f_base = prezzo_benzina if tipo_veicolo == "Automobile" else prezzo_diesel
tco_fossile = (p["glider"] * 0.8) + (total_km_life * (p["cons_fossile"] * mult_env * prezzo_f_base + p["maint_fossile"]))

# ==========================================
# DASHBOARD METRICHE
# ==========================================
st.subheader("🚦 Stato Operativo e Confronto TCO")
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Peso Batteria", f"{peso_batt:,.0f} kg", "Critico" if peso_batt > p["lim_peso"] else "OK")
with c2:
    st.metric("Tempo Ricarica", f"{tempo_ric:.1f} h", f"vs {tempo_inattivita}h sosta")
with c3:
    diff_h2_bev = tco_h2 - tco_bev
    st.metric("Delta H2 vs BEV", f"€ {diff_h2_bev:,.0f}", f"{diff_h2_bev/total_km_life:,.2f} €/km")

# ==========================================
# STRATEGIA INCENTIVI (GAP ANALYSIS)
# ==========================================
st.divider()
st.header("💰 Strategia Incentivi & Gap Analysis")
st.write(f"Differenza di costo rispetto al veicolo **{('Benzina' if tipo_veicolo == 'Automobile' else 'Diesel')}** per l'intero ciclo di vita.")

col_i1, col_i2 = st.columns(2)
with col_i1:
    gap_bev = tco_bev - tco_fossile
    st.subheader("Elettrico (BEV)")
    st.metric("Gap TCO Totale", f"€ {gap_bev:,.0f}", delta_color="inverse")
    st.metric("Gap al Chilometro", f"€ {gap_bev/total_km_life:,.3f} /km")
    st.caption("Se negativo, l'elettrico è già più conveniente.")

with col_i2:
    gap_h2 = tco_h2 - tco_fossile
    st.subheader("Idrogeno (FCEV)")
    st.metric("Gap TCO Totale", f"€ {gap_h2:,.0f}", delta_color="inverse")
    st.metric("Gap al Chilometro", f"€ {gap_h2/total_km_life:,.3f} /km")
    st.caption("Include extra-costo carburante e tecnologia FC.")

# ==========================================
# ANALISI VALORI ASSOLUTI (LCA & TECNICA)
# ==========================================
st.divider()
st.header("📊 Analisi Valori Assoluti (Ciclo di Vita)")

NOME_FILE_EXCEL = "Comparison H2 elc FF.xlsx"
if os.path.exists(NOME_FILE_EXCEL):
    try:
        xl = pd.ExcelFile(NOME_FILE_EXCEL, engine='openpyxl')
        foglio = {"Automobile": "AUTO", "Camion Pesante": "CAMION", "Autobus Urbano": "AUTOBUS URBANO", "Autobus Extraurbano": "AUTOBUS EXTRAURBANO"}[tipo_veicolo]
        df_raw = pd.read_excel(xl, sheet_name=foglio, header=None)
        
        # Filtro e pulizia
        dati = []
        tecs = ["Benzina", "Diesel", "Elettrico rete", "Elettrico autoprodotto", "Idrogeno Grigio", "Idrogeno rete", "Idrogeno autoprodotto"]
        for i in range(25):
            nome = str(df_raw.iloc[i, 1]).strip()
            if nome in tecs:
                dati.append({"Tecnologia": nome, "Autonomia": float(str(df_raw.iloc[i, 3]).replace(',','.')), "Consumo": float(str(df_raw.iloc[i, 4]).replace(',','.')), "Eta": float(str(df_raw.iloc[i, 9]).replace(',','.'))})
        
        df_abs = pd.DataFrame(dati)
        
        # Emissioni LCA (Fattori Utente)
        f_emiss = {"Benzina": 0.33, "Diesel": 0.307, "Elettrico rete": 0.215, "Elettrico autoprodotto": 0.055, "Idrogeno Grigio": 0.330, "Idrogeno rete": 0.387, "Idrogeno autoprodotto": 0.090}
        c_emiss = {"Automobile": {"Fossile": 6, "BEV": 12, "H2": 14}, "Autobus Urbano": {"Fossile": 50, "BEV": 85, "H2": 95}, "Autobus Extraurbano": {"Fossile": 50, "BEV": 85, "H2": 95}, "Camion Pesante": {"Fossile": 60, "BEV": 110, "H2": 125}}[tipo_veicolo]
        
        # Evoluzione Autonomia
        m_bev = interpolate(anno_acquisto, 1.0, 1.40)
        m_h2 = interpolate(anno_acquisto, 1.0, 1.15)

        res = []
        for idx, r in df_abs.iterrows():
            t = r['Tecnologia']
            cat = 'BEV' if 'Elettrico' in t else ('H2' if 'Idrogeno' in t else 'Fossile')
            
            # Autonomia Evoluta
            aut = r['Autonomia'] * (m_bev if cat=='BEV' else (m_h2 if cat=='H2' else 1.0))
            
            # Emissioni Scomposte
            e_prod = c_emiss[cat]
            e_man = ({"Fossile":0.05, "BEV":0.03, "H2":0.04}[cat] * total_km_life)/1000
            e_fuel = (r['Consumo'] * total_km_life * f_emiss[t])/1000
            
            res.append({"Tecnologia": t, "Autonomia": aut, "Consumo": r['Consumo'], "E_Prod": e_prod, "E_Man": e_man, "E_Fuel": e_fuel, "Eta": r['Eta']*100 if r['Eta']<2 else r['Eta']})
        
        df_final = pd.DataFrame(res)
        diesel_val = df_final[df_final['Tecnologia'] == ('Benzina' if tipo_veicolo=="Automobile" else 'Diesel')].iloc[0]

        # Plotting
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.subheader("A. Autonomia Massima [km]")
            f1 = px.bar(df_final, x="Tecnologia", y="Autonomia", color="Tecnologia")
            f1.add_hline(y=diesel_val['Autonomia'], line_dash="dash", line_color="black")
            st.plotly_chart(f1, use_container_width=True)
        with col_g2:
            st.subheader("B. Emissioni LCA Totali [tCO2]")
            f2 = px.bar(df_final.melt(id_vars="Tecnologia", value_vars=['E_Prod', 'E_Man', 'E_Fuel']), x="Tecnologia", y="value", color="variable", barmode='stack', color_discrete_sequence=["#8E8E8E", "#FF7F0E", "#D62728"])
            f2.add_hline(y=diesel_val['E_Prod']+diesel_val['E_Man']+diesel_val['E_Fuel'], line_dash="dash", line_color="black")
            st.plotly_chart(f2, use_container_width=True)

    except Exception as e:
        st.error(f"Errore caricamento dati Excel: {e}")
