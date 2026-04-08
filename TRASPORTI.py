import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Configurazione
st.set_page_config(page_title="DSS Mobilità - Convenience Check", layout="wide")

# --- FUNZIONI DI INTERPOLAZIONE TECNOLOGICA ---
# Questa funzione calcola come cambiano i valori in base all'anno (es. batterie più leggere al 2030)
def interpolate(year, y_2024, y_2030):
    if year <= 2024: return y_2024
    if year >= 2030: return y_2030
    return y_2024 + (y_2030 - y_2024) * ((year - 2024) / (2030 - 2024))

# --- INTERFACCIA UTENTE (SIDEBAR) ---
st.title("🚛 H2READY: TPL & Logistica Convenience Check")
st.markdown("Simulatore dinamico **Elettrico (BEV) vs Idrogeno (FCEV)** basato sui limiti operativi fisici e proiezioni tecnologiche di mercato.")

with st.sidebar:
    st.header("1. Parametri di Missione")
    tipo_veicolo = st.selectbox("Tipo Veicolo", ["Autobus Urbano", "Autobus Extraurbano", "Camion Pesante"])
    km_giornalieri = st.slider("Percorrenza Giornaliera (km)", 50, 1000, 250, 10)
    tempo_inattivita = st.slider("Finestra max per Ricarica (Ore continue)", 0.5, 12.0, 5.0, 0.5)
    
    st.header("2. Condizioni Ambientali")
    orografia = st.selectbox("Orografia del percorso", ["Pianura", "Collinare", "Montagna"])
    inverno_rigido = st.checkbox("Clima Invernale Rigido (< 0°C)", help="Attiva il riscaldamento intensivo che drena la batteria")
    
    st.header("3. Proiezioni Future")
    anno_acquisto = st.slider("Anno Previsto di Acquisto", 2024, 2035, 2024)
    anni_utilizzo = st.slider("Ciclo di Vita Utile (Anni)", 5, 15, 10)

# --- MOTORE DI CALCOLO FISICO/ECONOMICO ---

# 1. Costanti di base
consumo_base_bev = {"Autobus Urbano": 1.1, "Autobus Extraurbano": 1.0, "Camion Pesante": 1.4} # kWh/km
limite_peso_tollerato = {"Autobus Urbano": 3000, "Autobus Extraurbano": 4000, "Camion Pesante": 4500} # kg aggiuntivi max accettabili

# Moltiplicatori ambientali
mult_oro = {"Pianura": 1.0, "Collinare": 1.25, "Montagna": 1.45}
mult_inverno = 1.25 if inverno_rigido else 1.0

# 2. Evoluzione Tecnologica (La "Magia" dell'algoritmo)
densita_batt = interpolate(anno_acquisto, 0.16, 0.256) # Passa da 160 Wh/kg a 256 Wh/kg
deroga_peso_ue = interpolate(anno_acquisto, 2000, 4000) # Deroga europea sul peso green
costo_batt_kwh = interpolate(anno_acquisto, 210, 100) # Crollo costi batterie €/kWh
costo_fc_kw = interpolate(anno_acquisto, 330, 210) # Crollo costi fuel cell €/kW
potenza_ricarica = 1000 if anno_acquisto >= 2028 else 150 # kW (Megawatt charging sbloccato dal 2028)

costo_kwh_el = 0.22 # €/kWh rete
costo_kg_h2 = interpolate(anno_acquisto, 12.0, 6.0) # Prezzo H2 alla pompa (€/kg)

# 3. Calcoli Operativi BEV
consumo_reale_kwh_km = consumo_base_bev[tipo_veicolo] * mult_oro[orografia] * mult_inverno
fabbisogno_kwh = km_giornalieri * consumo_reale_kwh_km * 1.15 # 15% di buffer di sicurezza
peso_batteria = fabbisogno_kwh / densita_batt
peso_netto_perso = max(0, peso_batteria - deroga_peso_ue)
tempo_ricarica_h = fabbisogno_kwh / potenza_ricarica

# 4. Calcoli Economici (TCO)
giorni_anno = 300
km_annui = km_giornalieri * giorni_anno

# CAPEX
capex_bev = 150000 + (fabbisogno_kwh * costo_batt_kwh)
capex_h2 = 150000 + (200 * costo_fc_kw) + 35000 # Glider + FuelCell 200kW + Serbatoi H2

# OPEX
opex_fuel_bev_annuo = km_annui * consumo_reale_kwh_km * costo_kwh_el
consumo_h2_kg_km = consumo_reale_kwh_km / 15.0 # Equazione semplificata di conversione efficienza
opex_fuel_h2_annuo = km_annui * consumo_h2_kg_km * costo_kg_h2

maint_bev_annuo = km_annui * 0.15
maint_h2_annuo = km_annui * 0.25

tco_bev = capex_bev + ((opex_fuel_bev_annuo + maint_bev_annuo) * anni_utilizzo)
tco_h2 = capex_h2 + ((opex_fuel_h2_annuo + maint_h2_annuo) * anni_utilizzo)

# --- LOGICA SEMAFORI ---
sem_peso = "🟢 OK" if peso_netto_perso <= limite_peso_tollerato[tipo_veicolo] * 0.7 else ("🟡 ATTENZIONE" if peso_netto_perso <= limite_peso_tollerato[tipo_veicolo] else "🔴 CRITICO")
sem_tempo = "🟢 OK" if tempo_ricarica_h <= tempo_inattivita * 0.8 else ("🟡 ATTENZIONE" if tempo_ricarica_h <= tempo_inattivita else "🔴 CRITICO")
sem_tco = "🟢 VANTAGGIOSO" if tco_bev < tco_h2 else "🔴 SVANTAGGIOSO"

# --- VISUALIZZAZIONE DASHBOARD ---

# ECCEZIONE REGOLA AUREA: Urbano Leggero/Breve
if tipo_veicolo == "Autobus Urbano" and km_giornalieri <= 200:
    st.success("### 🟢 VERDETTO IMMEDIATO: VANTAGGIO ASSOLUTO BEV (Elettrico)")
    st.write("Per percorsi urbani inferiori a 200 km, i veicoli a batteria hanno già raggiunto la parità economica e tecnica. L'idrogeno per questo specifico impiego risulta sovradimensionato ed economicamente inefficiente.")
    st.stop() # Ferma il rendering del resto

# VERDETTO COMPLESSO
st.markdown("---")
st.subheader("📋 Verdetto di Fattibilità Operativa")

vince_h2 = "🔴 CRITICO" in sem_peso or "🔴 CRITICO" in sem_tempo or tco_h2 < (tco_bev * 0.9)

if vince_h2:
    st.error("### 🔵 L'IDROGENO È LA SCELTA STRATEGICA MIGLIORE")
    st.write("L'elettrico a batterie fallisce i requisiti minimi di operatività (o a causa del peso eccessivo delle batterie che annulla il carico utile, o per l'impossibilità di ricaricare il mezzo nei tempi previsti dai turni).")
else:
    st.success("### 🟢 L'ELETTRICO (BEV) È FATTIBILE E PIÙ ECONOMICO")
    st.write("Nonostante le difficoltà, la tecnologia BEV riesce a coprire la missione richiesta e offre un Costo Totale di Proprietà (TCO) inferiore.")

# SEMAFORI FISICI (Colonne)
st.markdown("### 🚦 Analisi dei Colli di Bottiglia Elettrici (BEV)")
col1, col2, col3 = st.columns(3)

with col1:
    st.info(f"**⚖️ Carico Utile (Payload)**\n\nStato: **{sem_peso}**")
    st.write(f"Peso Batteria Richiesta: **{peso_batteria:,.0f} kg**")
    st.caption(f"Capacità: {fabbisogno_kwh:,.0f} kWh. Con l'evoluzione al {anno_acquisto}, la densità è {densita_batt:.2f} kWh/kg.")

with col2:
    st.info(f"**⏱️ Tempi di Ricarica**\n\nStato: **{sem_tempo}**")
    st.write(f"Tempo Necessario: **{tempo_ricarica_h:.1f} ore**")
    st.caption(f"Potenza caricatore stimata: {potenza_ricarica} kW. Finestra disponibile: {tempo_inattivita}h.")

with col3:
    st.info(f"**💶 TCO (Costo Totale su {anni_utilizzo} anni)**\n\nStato BEV: **{sem_tco}**")
    st.write(f"TCO BEV: **€ {tco_bev:,.0f}**")
    st.caption(f"TCO Idrogeno: € {tco_h2:,.0f}. Entrambi includono CAPEX, energia e manutenzione.")


# GRAFICO TCO CONFRONTO
st.markdown("---")
st.subheader("📊 Analisi Total Cost of Ownership (TCO)")
df_tco = pd.DataFrame({
    "Tecnologia": ["Elettrico (BEV)", "Elettrico (BEV)", "Elettrico (BEV)", "Idrogeno (FCEV)", "Idrogeno (FCEV)", "Idrogeno (FCEV)"],
    "Voce di Costo": ["1. Acquisto (CAPEX)", "2. Energia (Fuel)", "3. Manutenzione", "1. Acquisto (CAPEX)", "2. Energia (Fuel)", "3. Manutenzione"],
    "Valore (€)": [capex_bev, opex_fuel_bev_annuo * anni_utilizzo, maint_bev_annuo * anni_utilizzo,
                   capex_h2, opex_fuel_h2_annuo * anni_utilizzo, maint_h2_annuo * anni_utilizzo]
})

fig = px.bar(df_tco, x="Tecnologia", y="Valore (€)", color="Voce di Costo", barmode="stack", 
             color_discrete_sequence=["#1f77b4", "#ff7f0e", "#2ca02c"])
fig.update_layout(yaxis_title="Euro (€)")
st.plotly_chart(fig, use_container_width=True)
