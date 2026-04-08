import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="DSS Mobilità Comuni", page_icon="🚗", layout="wide")
st.title("🚗 DSS Comuni: Analisi Completa Flotta")

# Legge il file README.md e lo visualizza in un menu a tendina
if os.path.exists("REadMe_Mezzi.md"):
    with st.expander("ℹ️ Leggi Istruzioni, Limiti e Assunzioni"):
        with open("REadMe_Mezzi.md", "r", encoding="utf-8") as f:
            st.markdown(f.read())

NOME_FILE_EXCEL = "Comparison H2 elc FF.xlsx" 

if not os.path.exists(NOME_FILE_EXCEL):
    st.error(f"❌ File '{NOME_FILE_EXCEL}' non trovato.")
    st.stop()

try:
    xl = pd.ExcelFile(NOME_FILE_EXCEL, engine='openpyxl')
    categoria_utente = st.sidebar.selectbox("🚌 Seleziona Flotta", ["AUTO", "CAMION", "AUTOBUS URBANO", "AUTOBUS EXTRAURBANO"])
    nome_foglio = next((f for f in xl.sheet_names if f.upper() == categoria_utente), xl.sheet_names[0])
    
    df_raw = pd.read_excel(xl, sheet_name=nome_foglio, header=None, engine='openpyxl')

    def clean_val(x):
        if pd.isna(x) or str(x).strip() == "": return 0.0
        s = str(x).replace('€', '').replace('%', '').replace(' ', '').replace(',', '.')
        try: return float(s)
        except: return 0.0

    # --- 1. ESTRAZIONE DATI BASE (Le tue 7 Tecnologie!) ---
    dati_finali = []
    tecnologie_cercate = ["Benzina", "Diesel", "Elettrico rete", "Elettrico autoprodotto", 
                          "Idrogeno Grigio", "Idrogeno rete", "Idrogeno autoprodotto"]

    for i in range(min(25, len(df_raw))):
        nome_tec = str(df_raw.iloc[i, 1]).strip() # Colonna B
        match_tec = next((t for t in tecnologie_cercate if t.lower() == nome_tec.lower()), None)
        
        if match_tec:
            try:
                dati_finali.append({
                    "Tecnologia": match_tec,
                    "Autonomia": clean_val(df_raw.iloc[i, 3]),        # D
                    "Consumo": clean_val(df_raw.iloc[i, 4]),          # E
                    "Eta_WtW": clean_val(df_raw.iloc[i, 9]),          # J 
                    "En_Primaria_Base": clean_val(df_raw.iloc[i, 13]),# N 
                    "Emiss_Annue_Q": clean_val(df_raw.iloc[i, 16]),   # Q 
                    "Emiss_Costruz": clean_val(df_raw.iloc[i, 17]),   # R 
                    "Maint_km": clean_val(df_raw.iloc[i, 22]),        # W 
                    "CAPEX_Totale": clean_val(df_raw.iloc[i, 25])     # Z 
                })
            except Exception:
                continue

    if not dati_finali:
        st.error("Nessun dato trovato.")
        st.stop()

    df_clean = pd.DataFrame(dati_finali)
    df_clean['Tecnologia'] = pd.Categorical(df_clean['Tecnologia'], categories=tecnologie_cercate, ordered=True)
    df_clean = df_clean.sort_values('Tecnologia')

    # --- 2. LETTURA COSTI FUEL E CONVERSIONE (B20:F26) ---
    st.sidebar.divider()
    st.sidebar.header("⚡ Costi Carburante")
    
    costi_input_kwh = {} 
    
    def get_unit(t):
        t_low = t.lower()
        if "benzina" in t_low or "diesel" in t_low: return "[€/l]"
        if "idrogeno" in t_low: return "[€/kg]"
        return "[€/kWh]"

    riga_prezzi = 19
    for r in range(12, len(df_raw)):
        if str(df_raw.iloc[r, 1]).strip() == "Benzina":
            riga_prezzi = r
            break
            
    for r in range(riga_prezzi, riga_prezzi + 7):
        try:
            label = str(df_raw.iloc[r, 1]).strip()
            match_label = next((t for t in tecnologie_cercate if t.lower() in label.lower() or label.lower() in t.lower()), label)
            
            val_natura = clean_val(df_raw.iloc[r, 2]) # Colonna C (es. 1.9 €/l)
            val_kwh_excel = clean_val(df_raw.iloc[r, 5]) # Colonna F (es. 0.22 €/kWh)
            
            if val_natura > 0:
                fattore = val_kwh_excel / val_natura
            else:
                if "benzina" in match_label.lower(): fattore = 0.22 / 1.9
                elif "diesel" in match_label.lower(): fattore = 0.18 / 1.8
                elif "idrogeno" in match_label.lower(): fattore = 0.03 # 0.06/2
                else: fattore = 1.0
                
            etichetta_ui = f"{match_label} {get_unit(match_label)}"
            
            user_val = st.sidebar.number_input(etichetta_ui, value=val_natura, format="%.3f")
            costi_input_kwh[match_label] = user_val * fattore
        except:
            pass

    # --- 3. PARAMETRI UTENTE ---
    st.sidebar.divider()
    st.sidebar.header("⚙️ Parametri Flotta (C16, C17)")
    
    km_annui = st.sidebar.slider("Percorrenza Annua (km/y)", 5000, 100000, 15000, step=1000)
    lifetime = st.sidebar.slider("Anni di Utilizzo (y)", 1, 20, 10, step=1)
    km_totali = km_annui * lifetime
    
    st.sidebar.metric(label="Percorrenza Totale [km]", value=f"{km_totali:,}".replace(',', '.'))
    
    KM_BASE_EXCEL = 15000 

    # --- 4. IL MOTORE MATEMATICO ---
    def esegui_calcoli(row):
        t = row["Tecnologia"]
        p_fuel = next((v for k, v in costi_input_kwh.items() if k.lower() in t.lower()), 0.20)
        
        fuel_annuo = row["Consumo"] * km_annui * p_fuel         
        maint_annuo = row["Maint_km"] * km_annui                 
        capex_annuo = row["CAPEX_Totale"] / lifetime             
        
        fuel_totale = fuel_annuo * lifetime
        maint_totale = maint_annuo * lifetime
        
        costo_annuo_tot = fuel_annuo + maint_annuo + capex_annuo
        costo_tot_life = fuel_totale + maint_totale + row["CAPEX_Totale"] 
        
        en_primaria = row["En_Primaria_Base"] * (km_annui / KM_BASE_EXCEL) 
        emiss_annue = row["Emiss_Annue_Q"] * (km_annui / KM_BASE_EXCEL)    
        
        emiss_totali_tons = (row["Emiss_Costruz"] + (emiss_annue * lifetime)) / 1000
        
        return pd.Series([
            fuel_annuo, maint_annuo, capex_annuo, costo_annuo_tot,
            fuel_totale, maint_totale, costo_tot_life,
            en_primaria, emiss_annue, emiss_totali_tons
        ])

    df_clean[['OPEx_Fuel_y', 'OPEx_Maint_y', 'CAPEx_y', 'Costo_Annuo_Tot',
              'OPEx_Fuel_Tot', 'OPEx_Maint_Tot', 'Costo_Totale',
              'En_Primaria_y', 'Emiss_Annue', 'Emiss_Tot_Tons']] = df_clean.apply(esegui_calcoli, axis=1)

    # --- 5. VISUALIZZAZIONE RISULTATI BASE ---
    st.divider()
    st.header("📊 Analisi Parametri Principali")
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1. Autonomia [km]")
        fig1 = px.bar(df_clean, x="Tecnologia", y="Autonomia", color="Tecnologia")
        st.plotly_chart(fig1, use_container_width=True)
    with c2:
        st.subheader("2. Consumo [kWh/km]")
        fig2 = px.bar(df_clean, x="Tecnologia", y="Consumo", color="Tecnologia")
        st.plotly_chart(fig2, use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("3. Efficienza WtW (η) [-]")
        df_clean["Eta_Percent"] = df_clean["Eta_WtW"] * 100 if df_clean["Eta_WtW"].mean() < 2 else df_clean["Eta_WtW"]
        fig3 = px.bar(df_clean, x="Tecnologia", y="Eta_Percent", color="Tecnologia", text_auto='.1f')
        fig3.update_layout(yaxis_title="Rendimento %")
        st.plotly_chart(fig3, use_container_width=True)
    with c4:
        st.subheader("4. Energia Primaria [kWh/anno]")
        fig4 = px.bar(df_clean, x="Tecnologia", y="En_Primaria_y", color="Tecnologia")
        st.plotly_chart(fig4, use_container_width=True)

    c7, c8 = st.columns(2)
    with c7:
        st.subheader("5. Costo Annuo [€/anno]")
        df_plot_y = df_clean.melt(id_vars="Tecnologia", value_vars=['CAPEx_y', 'OPEx_Maint_y', 'OPEx_Fuel_y'], 
                                  var_name="Voce", value_name="Euro")
        df_plot_y["Voce"] = df_plot_y["Voce"].replace({'CAPEx_y':'CAPEx (Acquisto)', 'OPEx_Maint_y':'OPEx (Manut)', 'OPEx_Fuel_y':'OPEx (Fuel)'})
        fig7 = px.bar(df_plot_y, x="Tecnologia", y="Euro", color="Voce", barmode='stack',
                      color_discrete_sequence=["#0068C9", "#FFA421", "#FF4B4B"])
        st.plotly_chart(fig7, use_container_width=True)
        
    with c8:
        st.subheader("6. Costo Totale (TCO) [€]")
        df_clean['CAPEx_Totale_Bar'] = df_clean['CAPEX_Totale']
        df_plot_tot = df_clean.melt(id_vars="Tecnologia", value_vars=['CAPEx_Totale_Bar', 'OPEx_Maint_Tot', 'OPEx_Fuel_Tot'], 
                                    var_name="Voce", value_name="Euro")
        df_plot_tot["Voce"] = df_plot_tot["Voce"].replace({'CAPEx_Totale_Bar':'CAPEx (Acquisto)', 'OPEx_Maint_Tot':'OPEx (Manut)', 'OPEx_Fuel_Tot':'OPEx (Fuel)'})
        fig8 = px.bar(df_plot_tot, x="Tecnologia", y="Euro", color="Voce", barmode='stack',
                      color_discrete_sequence=["#0068C9", "#FFA421", "#FF4B4B"])
        st.plotly_chart(fig8, use_container_width=True)


    # --- 6. CONFRONTO DIRETTO VS DIESEL (BASELINE) ---
    st.divider()
    st.header("🆚 Confronto Diretto vs DIESEL (Baseline)")
    st.write("I grafici sottostanti mostrano lo **scostamento (Delta)** delle diverse tecnologie rispetto al veicolo Diesel. Una barra positiva indica un valore superiore al Diesel, una barra negativa indica un valore inferiore (risparmio o riduzione).")

    if not df_clean[df_clean['Tecnologia'] == 'Diesel'].empty:
        diesel_data = df_clean[df_clean['Tecnologia'] == 'Diesel'].iloc[0]

        # Calcolo dei Delta matematici rispetto al Diesel
        df_clean['Delta_Autonomia'] = df_clean['Autonomia'] - diesel_data['Autonomia']
        df_clean['Delta_Consumo'] = df_clean['Consumo'] - diesel_data['Consumo']
        df_clean['Delta_Eta'] = df_clean['Eta_Percent'] - (diesel_data['Eta_WtW'] * 100 if diesel_data['Eta_WtW'] < 2 else diesel_data['Eta_WtW'])
        df_clean['Delta_Emiss'] = df_clean['Emiss_Tot_Tons'] - diesel_data['Emiss_Tot_Tons']

        # Grafici Autonomia e Consumo
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.subheader("A. Scostamento Autonomia [km]")
            fig_da = px.bar(df_clean, x="Tecnologia", y="Delta_Autonomia", color="Tecnologia", text_auto='.0f')
            fig_da.add_hline(y=0, line_dash="dash", line_color="black", annotation_text="DIESEL BASELINE")
            fig_da.update_layout(yaxis_title="km di differenza vs Diesel", showlegend=False)
            st.plotly_chart(fig_da, use_container_width=True)
            
        with col_d2:
            st.subheader("B. Scostamento Consumo [kWh/km]")
            fig_dc = px.bar(df_clean, x="Tecnologia", y="Delta_Consumo", color="Tecnologia", text_auto='.2f')
            fig_dc.add_hline(y=0, line_dash="dash", line_color="black", annotation_text="DIESEL BASELINE")
            fig_dc.update_layout(yaxis_title="kWh/km di differenza vs Diesel", showlegend=False)
            st.plotly_chart(fig_dc, use_container_width=True)

        # Grafici Efficienza ed Emissioni Dettagliate
        col_d3, col_d4 = st.columns(2)
        with col_d3:
            st.subheader("C. Delta Efficienza (WtW) [%]")
            fig_de = px.bar(df_clean, x="Tecnologia", y="Delta_Eta", color="Tecnologia", text_auto='.1f')
            fig_de.add_hline(y=0, line_dash="dash", line_color="black", annotation_text="DIESEL BASELINE")
            fig_de.update_layout(yaxis_title="Punti Percentuali vs Diesel", showlegend=False)
            st.plotly_chart(fig_de, use_container_width=True)

        with col_d4:
            st.subheader("D. Scomposizione Emissioni (CAPEX vs OPEX) [tCO2]")
            # Creazione dataset impilato per le emissioni
            df_clean['Emiss_Costruzione_Tons'] = df_clean['Emiss_Costruz'] / 1000
            df_clean['Emiss_Operative_Tons'] = (df_clean['Emiss_Annue'] * lifetime) / 1000
            
            df_emiss = df_clean.melt(id_vars="Tecnologia", 
                                     value_vars=['Emiss_Costruzione_Tons', 'Emiss_Operative_Tons'],
                                     var_name="Fase", value_name="tCO2")
            df_emiss['Fase'] = df_emiss['Fase'].replace({'Emiss_Costruzione_Tons': 'Costruzione Mezzo (CAPEX)', 
                                                         'Emiss_Operative_Tons': 'Carburante e Uso (OPEX)'})

            fig_dem = px.bar(df_emiss, x="Tecnologia", y="tCO2", color="Fase", barmode='stack',
                             color_discrete_sequence=["#8E8E8E", "#D62728"]) # Grigio per costruzione, Rosso per carburante
            
            # Linea di riferimento delle emissioni totali del Diesel
            fig_dem.add_hline(y=diesel_data['Emiss_Tot_Tons'], line_dash="dash", line_width=2, 
                              line_color="black", annotation_text=f"Totale Diesel ({diesel_data['Emiss_Tot_Tons']:.0f} tCO2)")
            fig_dem.update_layout(yaxis_title="Tonnellate CO2 Totali (Ciclo di Vita)")
            st.plotly_chart(fig_dem, use_container_width=True)
    else:
        st.warning("⚠️ Tecnologia 'Diesel' non presente per la categoria selezionata: impossibile generare il confronto base.")

    # --- TABELLA DATI ---
    st.divider()
    st.subheader("📋 Data Table Completa")
    st.dataframe(df_clean[["Tecnologia", "Autonomia", "Consumo", "Eta_WtW", "Costo_Annuo_Tot", "Costo_Totale", "Emiss_Tot_Tons"]].style.format({
        "Autonomia": "{:,.0f} km",
        "Consumo": "{:.3f} kWh/km",
        "Eta_WtW": "{:.1%}",
        "Costo_Annuo_Tot": "€ {:,.0f}",
        "Costo_Totale": "€ {:,.0f}",
        "Emiss_Tot_Tons": "{:,.1f} t"
    }), use_container_width=True)

except Exception as e:
    st.error(f"Errore di Elaborazione: {e}")
