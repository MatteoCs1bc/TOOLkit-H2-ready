import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DSS Mobilità - Convenience Check", layout="wide")
st.title("🚛 H2READY: TPL & Logistica Convenience Check")
st.markdown("Simulatore dinamico **Elettrico (BEV) vs Idrogeno (FCEV)** basato sui limiti fisici e proiezioni di mercato, integrato con analisi emissioni.")

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
    tipo_veicolo = st.selectbox("Tipo Veicolo", ["Autobus Urbano", "Autobus Extraurbano", "Camion Pesante"])
    km_giornalieri = st.slider("Percorrenza Giornaliera (km)", 50, 1000, 250, 10)
    tempo_inattivita = st.slider("Finestra max per Ricarica (Ore continue)", 0.5, 12.0, 5.0, 0.5)
    
    st.header("2. Condizioni Ambientali")
    orografia = st.selectbox("Orografia del percorso", ["Pianura", "Collinare", "Montagna"])
    inverno_rigido = st.checkbox("Clima Invernale Rigido (< 0°C)")
    
    st.header("3. Approvvigionamento Energia")
    fonte_elettricita = st.radio("Sorgente Elettricità (BEV e Elettrolizzatore)", ["Da Rete Pubblica", "Autoprodotta (es. FV Deposito)"])
    prezzo_el_base = st.number_input("Prezzo Elettricità (€/kWh)", value=0.22 if "Rete" in fonte_elettricita else 0.08, format="%.3f")
    
    fonte_idrogeno = st.radio("Sorgente Idrogeno (FCEV)", ["Acquisto Esterno (Carro Bombolaio)", "Autoprodotto (Elettrolizzatore locale)"])
    
    if "Esterno" in fonte_idrogeno:
        prezzo_h2_base = st.number_input("Prezzo Mercato H2 oggi (€/kg)", value=16.0, format="%.2f")
    else:
        st.info(f"💡 **Modello 55 kWh/kg**: {prezzo_el_base * 55:.2f} €/kg (Solo energia) + CSD.")

    st.header("4. Proiezioni Future")
    anno_acquisto = st.slider("Anno Previsto di Acquisto", 2024, 2035, 2024)
    anni_utilizzo = st.slider("Ciclo di Vita Utile (Anni)", 5, 15, 10)

# ==========================================
# PARTE 1: MOTORE FISICO & DASHBOARD TCO (BEV vs H2)
# ==========================================
consumo_base_bev = {"Autobus Urbano": 1.1, "Autobus Extraurbano": 1.0, "Camion Pesante": 1.4}
limite_peso_tollerato = {"Autobus Urbano": 3000, "Autobus Extraurbano": 4000, "Camion Pesante": 4500}

mult_oro = {"Pianura": 1.0, "Collinare": 1.25, "Montagna": 1.45}
mult_inverno = 1.25 if inverno_rigido else 1.0

densita_batt = interpolate(anno_acquisto, 0.16, 0.256) 
deroga_peso_ue = interpolate(anno_acquisto, 2000, 4000) 
potenza_ricarica = 1000 if anno_acquisto >= 2028 else 150 

consumo_reale_kwh_km = consumo_base_bev[tipo_veicolo] * mult_oro[orografia] * mult_inverno
fabbisogno_kwh = km_giornalieri * consumo_reale_kwh_km * 1.15 
peso_batteria = fabbisogno_kwh / densita_batt
peso_netto_perso = max(0, peso_batteria - deroga_peso_ue)
tempo_ricarica_h = fabbisogno_kwh / potenza_ricarica

costo_batt_kwh = interpolate(anno_acquisto, 210, 100) 
costo_fc_kw = interpolate(anno_acquisto, 330, 210) 
costo_kwh_el_stimato = interpolate(anno_acquisto, prezzo_el_base, prezzo_el_base * 0.9)

if "Esterno" in fonte_idrogeno:
    costo_kg_h2_stimato = interpolate(anno_acquisto, prezzo_h2_base, 9.0)
else:
    costo_energia_per_kg = 55.0 * costo_kwh_el_stimato
    ammortamento_impianto_csd = interpolate(anno_acquisto, 4.0, 2.5) 
    costo_kg_h2_stimato = costo_energia_per_kg + ammortamento_impianto_csd

km_annui = km_giornalieri * 300
capex_bev = 150000 + (fabbisogno_kwh * costo_batt_kwh)
capex_h2 = 150000 + (200 * costo_fc_kw) + 35000

opex_fuel_bev = km_annui * consumo_reale_kwh_km * costo_kwh_el_stimato * anni_utilizzo
consumo_h2_kg_km = consumo_reale_kwh_km / 15.0 
opex_fuel_h2 = km_annui * consumo_h2_kg_km * costo_kg_h2_stimato * anni_utilizzo

opex_maint_bev = km_annui * 0.15 * anni_utilizzo
opex_maint_h2 = km_annui * 0.25 * anni_utilizzo

tco_bev = capex_bev + opex_fuel_bev + opex_maint_bev
tco_h2 = capex_h2 + opex_fuel_h2 + opex_maint_h2

delta_capex = capex_h2 - capex_bev
delta_fuel = opex_fuel_h2 - opex_fuel_bev
delta_maint = opex_maint_h2 - opex_maint_bev
delta_tco_totale = tco_h2 - tco_bev

sem_peso = "🟢 OK" if peso_netto_perso <= limite_peso_tollerato[tipo_veicolo] * 0.7 else ("🟡 ATTENZIONE" if peso_netto_perso <= limite_peso_tollerato[tipo_veicolo] else "🔴 CRITICO")
sem_tempo = "🟢 OK" if tempo_ricarica_h <= tempo_inattivita * 0.8 else ("🟡 ATTENZIONE" if tempo_ricarica_h <= tempo_inattivita else "🔴 CRITICO")

if tipo_veicolo == "Autobus Urbano" and km_giornalieri <= 200:
    st.success("### 🟢 VERDETTO IMMEDIATO: VANTAGGIO ASSOLUTO BEV (Elettrico)")
    st.write("Per percorsi urbani inferiori a 200 km, i veicoli a batteria hanno già raggiunto la parità economica e tecnica.")
else:
    st.subheader("📋 Verdetto di Fattibilità Operativa")
    vince_h2 = "🔴 CRITICO" in sem_peso or "🔴 CRITICO" in sem_tempo or tco_h2 < (tco_bev * 0.9)
    if vince_h2: st.error("### 🔵 L'IDROGENO È LA SCELTA STRATEGICA MIGLIORE")
    else: st.success("### 🟢 L'ELETTRICO (BEV) È FATTIBILE E PIÙ ECONOMICO")

    st.markdown("### 🚦 Analisi dei Colli di Bottiglia Elettrici (BEV)")
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**⚖️ Carico Utile (Payload)**\n\nStato: **{sem_peso}**")
        st.write(f"Peso Batteria Richiesta: **{peso_batteria:,.0f} kg**")
    with col2:
        st.info(f"**⏱️ Tempi di Ricarica**\n\nStato: **{sem_tempo}**")
        st.write(f"Tempo Necessario: **{tempo_ricarica_h:.1f} ore**")

    st.markdown("### 💶 Analisi degli Scostamenti Economici (Delta TCO)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("TCO Elettrico (BEV)", f"€ {tco_bev:,.0f}")
    c2.metric("TCO Idrogeno (FCEV)", f"€ {tco_h2:,.0f}")
    c3.metric("Delta TCO (Extra-costo H2)", f"€ {delta_tco_totale:,.0f}", delta=f"{delta_tco_totale:,.0f} € rispetto a BEV", delta_color="inverse" if delta_tco_totale > 0 else "normal")
    c4.metric("Prezzi Energia Simulati", f"{costo_kwh_el_stimato:.2f} €/kWh", f"{costo_kg_h2_stimato:.2f} €/kg H2", delta_color="off")

    fig_waterfall = go.Figure(go.Waterfall(
        name = "20", orientation = "v", measure = ["relative", "relative", "relative", "total"],
        x = ["Delta CAPEX (Veicolo)", "Delta Energia (Fuel)", "Delta Manutenzione", "Delta TCO Totale"],
        textposition = "outside",
        text = [f"€ {delta_capex:,.0f}", f"€ {delta_fuel:,.0f}", f"€ {delta_maint:,.0f}", f"€ {delta_tco_totale:,.0f}"],
        y = [delta_capex, delta_fuel, delta_maint, delta_tco_totale],
        connector = {"line":{"color":"rgb(63, 63, 63)"}},
        decreasing = {"marker":{"color":"#2ca02c"}}, increasing = {"marker":{"color":"#d62728"}}, totals = {"marker":{"color":"#1f77b4"}}
    ))
    st.plotly_chart(fig_waterfall, use_container_width=True)

# ==========================================
# PARTE 2: CONFRONTO GLOBALE VS DIESEL (DA EXCEL)
# ==========================================
st.divider()
st.header("🆚 Confronto di Tutte le Tecnologie vs DIESEL (Baseline)")
st.write("I grafici sottostanti estraggono i dati base dal file Excel e mostrano lo scostamento delle diverse motorizzazioni rispetto al Diesel tradizionale.")

NOME_FILE_EXCEL = "Comparison H2 elc FF.xlsx"
if not os.path.exists(NOME_FILE_EXCEL):
    st.warning(f"⚠️ Impossibile generare i grafici di confronto: File '{NOME_FILE_EXCEL}' non trovato nel repository.")
else:
    try:
        xl = pd.ExcelFile(NOME_FILE_EXCEL, engine='openpyxl')
        # Mappatura Sidebar -> Foglio Excel
        foglio_target = "CAMION" if tipo_veicolo == "Camion Pesante" else ("AUTOBUS URBANO" if tipo_veicolo == "Autobus Urbano" else "AUTOBUS EXTRAURBANO")
        nome_foglio = next((f for f in xl.sheet_names if f.upper() == foglio_target), xl.sheet_names[0])
        
        df_raw = pd.read_excel(xl, sheet_name=nome_foglio, header=None, engine='openpyxl')

        def clean_val(x):
            if pd.isna(x) or str(x).strip() == "": return 0.0
            try: return float(str(x).replace('€', '').replace('%', '').replace(' ', '').replace(',', '.'))
            except: return 0.0

        dati_finali = []
        tecnologie_cercate = ["Benzina", "Diesel", "Elettrico rete", "Elettrico autoprodotto", "Idrogeno Grigio", "Idrogeno rete", "Idrogeno autoprodotto"]

        for i in range(min(25, len(df_raw))):
            nome_tec = str(df_raw.iloc[i, 1]).strip()
            match_tec = next((t for t in tecnologie_cercate if t.lower() == nome_tec.lower()), None)
            if match_tec:
                dati_finali.append({
                    "Tecnologia": match_tec,
                    "Autonomia": clean_val(df_raw.iloc[i, 3]),
                    "Consumo": clean_val(df_raw.iloc[i, 4]),
                    "Eta_WtW": clean_val(df_raw.iloc[i, 9]),
                    "Emiss_Annue_Q": clean_val(df_raw.iloc[i, 16]),
                    "Emiss_Costruz": clean_val(df_raw.iloc[i, 17])
                })

        df_clean = pd.DataFrame(dati_finali)
        
        if not df_clean[df_clean['Tecnologia'] == 'Diesel'].empty:
            diesel_data = df_clean[df_clean['Tecnologia'] == 'Diesel'].iloc[0]

            df_clean['Delta_Autonomia'] = df_clean['Autonomia'] - diesel_data['Autonomia']
            df_clean['Delta_Consumo'] = df_clean['Consumo'] - diesel_data['Consumo']
            df_clean['Eta_Percent'] = df_clean['Eta_WtW'] * 100 if df_clean['Eta_WtW'].mean() < 2 else df_clean['Eta_WtW']
            diesel_eta = diesel_data['Eta_WtW'] * 100 if diesel_data['Eta_WtW'] < 2 else diesel_data['Eta_WtW']
            df_clean['Delta_Eta'] = df_clean['Eta_Percent'] - diesel_eta
            
            # Ricalcolo emissioni in base ai km della sidebar
            KM_BASE_EXCEL = 15000 
            df_clean['Emiss_Costruzione_Tons'] = df_clean['Emiss_Costruz'] / 1000
            df_clean['Emiss_Operative_Tons'] = (df_clean['Emiss_Annue_Q'] * (km_annui / KM_BASE_EXCEL) * anni_utilizzo) / 1000
            df_clean['Emiss_Tot_Tons'] = df_clean['Emiss_Costruzione_Tons'] + df_clean['Emiss_Operative_Tons']
            diesel_emiss_tot = df_clean[df_clean['Tecnologia'] == 'Diesel'].iloc[0]['Emiss_Tot_Tons']

            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.subheader("A. Scostamento Autonomia [km]")
                fig_da = px.bar(df_clean, x="Tecnologia", y="Delta_Autonomia", color="Tecnologia", text_auto='.0f')
                fig_da.add_hline(y=0, line_dash="dash", line_color="black", annotation_text="DIESEL BASELINE")
                fig_da.update_layout(yaxis_title="km vs Diesel", showlegend=False)
                st.plotly_chart(fig_da, use_container_width=True)
                
            with col_d2:
                st.subheader("B. Scostamento Consumo [kWh/km]")
                fig_dc = px.bar(df_clean, x="Tecnologia", y="Delta_Consumo", color="Tecnologia", text_auto='.2f')
                fig_dc.add_hline(y=0, line_dash="dash", line_color="black", annotation_text="DIESEL BASELINE")
                fig_dc.update_layout(yaxis_title="kWh/km vs Diesel", showlegend=False)
                st.plotly_chart(fig_dc, use_container_width=True)

            col_d3, col_d4 = st.columns(2)
            with col_d3:
                st.subheader("C. Delta Efficienza (WtW) [%]")
                fig_de = px.bar(df_clean, x="Tecnologia", y="Delta_Eta", color="Tecnologia", text_auto='.1f')
                fig_de.add_hline(y=0, line_dash="dash", line_color="black", annotation_text="DIESEL BASELINE")
                fig_de.update_layout(yaxis_title="Punti % vs Diesel", showlegend=False)
                st.plotly_chart(fig_de, use_container_width=True)

            with col_d4:
                st.subheader("D. Emissioni Totali (CAPEX vs OPEX)")
                df_emiss = df_clean.melt(id_vars="Tecnologia", value_vars=['Emiss_Costruzione_Tons', 'Emiss_Operative_Tons'],
                                         var_name="Fase", value_name="tCO2")
                df_emiss['Fase'] = df_emiss['Fase'].replace({'Emiss_Costruzione_Tons': 'Costruzione Mezzo', 'Emiss_Operative_Tons': 'Carburante/Uso'})

                fig_dem = px.bar(df_emiss, x="Tecnologia", y="tCO2", color="Fase", barmode='stack', color_discrete_sequence=["#8E8E8E", "#D62728"])
                fig_dem.add_hline(y=diesel_emiss_tot, line_dash="dash", line_width=2, line_color="black", annotation_text=f"Diesel ({diesel_emiss_tot:.0f} tCO2)")
                fig_dem.update_layout(yaxis_title="Tonnellate CO2")
                st.plotly_chart(fig_dem, use_container_width=True)
        else:
            st.warning("⚠️ Dati Diesel non trovati nel foglio.")
    except Exception as e:
        st.error(f"Errore nella lettura dell'Excel: {e}")
