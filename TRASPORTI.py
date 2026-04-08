import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Configurazione iniziale della pagina
st.set_page_config(page_title="DSS Mobilità - Convenience Check", layout="wide")

# --- FUNZIONI DI INTERPOLAZIONE TECNOLOGICA ---
def interpolate(year, y_2024, y_2030):
    if year <= 2024: return y_2024
    if year >= 2030: return y_2030
    return y_2024 + (y_2030 - y_2024) * ((year - 2024) / (2030 - 2024))

# --- INTERFACCIA UTENTE (SIDEBAR) ---
st.title("🚛 H2READY: TPL & Logistica Convenience Check")
st.markdown("Simulatore dinamico **Elettrico (BEV) vs Idrogeno (FCEV)** basato sui limiti operativi fisici e proiezioni di mercato.")

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
        prezzo_h2_base = st.number_input("Prezzo di Mercato H2 oggi (€/kg)", value=16.0, format="%.2f", help="Prezzo alla pompa, include logistica.")
    else:
        st.info(f"💡 **Modello 55 kWh/kg**\n\nIl costo dell'H2 viene calcolato automaticamente: **55 kWh** per produrre 1 kg di H2 (Costo energia pura: {prezzo_el_base * 55:.2f} €/kg) + l'ammortamento dell'impianto di compressione.")

    st.header("4. Proiezioni Future")
    anno_acquisto = st.slider("Anno Previsto di Acquisto", 2024, 2035, 2024)
    anni_utilizzo = st.slider("Ciclo di Vita Utile (Anni)", 5, 15, 10)

# --- MOTORE DI CALCOLO FISICO ---
consumo_base_bev = {"Autobus Urbano": 1.1, "Autobus Extraurbano": 1.0, "Camion Pesante": 1.4}
limite_peso_tollerato = {"Autobus Urbano": 3000, "Autobus Extraurbano": 4000, "Camion Pesante": 4500}

mult_oro = {"Pianura": 1.0, "Collinare": 1.25, "Montagna": 1.45}
mult_inverno = 1.25 if inverno_rigido else 1.0

# Evoluzione Fisica (Peso e Potenze)
densita_batt = interpolate(anno_acquisto, 0.16, 0.256) 
deroga_peso_ue = interpolate(anno_acquisto, 2000, 4000) 
potenza_ricarica = 1000 if anno_acquisto >= 2028 else 150 # Megawatt charging sbloccato dal 2028

consumo_reale_kwh_km = consumo_base_bev[tipo_veicolo] * mult_oro[orografia] * mult_inverno
fabbisogno_kwh = km_giornalieri * consumo_reale_kwh_km * 1.15 # 15% margine di sicurezza
peso_batteria = fabbisogno_kwh / densita_batt
peso_netto_perso = max(0, peso_batteria - deroga_peso_ue)
tempo_ricarica_h = fabbisogno_kwh / potenza_ricarica


# --- MOTORE ECONOMICO (PREZZI DINAMICI E 55 kWh/kg) ---
costo_batt_kwh = interpolate(anno_acquisto, 210, 100) 
costo_fc_kw = interpolate(anno_acquisto, 330, 210) 

# Costo elettricità base
costo_kwh_el_stimato = interpolate(anno_acquisto, prezzo_el_base, prezzo_el_base * 0.9)

# Logica di prezzo Idrogeno
if "Esterno" in fonte_idrogeno:
    costo_kg_h2_stimato = interpolate(anno_acquisto, prezzo_h2_base, 9.0) # Il mercato logistico H2 scende a ~9€ al 2030
else:
    costo_energia_per_kg = 55.0 * costo_kwh_el_stimato
    ammortamento_impianto_csd = interpolate(anno_acquisto, 4.0, 2.5) # Costo compressione/stoccaggio scende
    costo_kg_h2_stimato = costo_energia_per_kg + ammortamento_impianto_csd

# Calcoli TCO Assoluti
giorni_anno = 300
km_annui = km_giornalieri * giorni_anno

capex_bev = 150000 + (fabbisogno_kwh * costo_batt_kwh)
capex_h2 = 150000 + (200 * costo_fc_kw) + 35000

opex_fuel_bev = km_annui * consumo_reale_kwh_km * costo_kwh_el_stimato * anni_utilizzo
consumo_h2_kg_km = consumo_reale_kwh_km / 15.0 # Efficienza termodinamica rispetto al BEV
opex_fuel_h2 = km_annui * consumo_h2_kg_km * costo_kg_h2_stimato * anni_utilizzo

opex_maint_bev = km_annui * 0.15 * anni_utilizzo
opex_maint_h2 = km_annui * 0.25 * anni_utilizzo

tco_bev = capex_bev + opex_fuel_bev + opex_maint_bev
tco_h2 = capex_h2 + opex_fuel_h2 + opex_maint_h2

# --- CALCOLO DEI DELTA (H2 vs BEV) ---
delta_capex = capex_h2 - capex_bev
delta_fuel = opex_fuel_h2 - opex_fuel_bev
delta_maint = opex_maint_h2 - opex_maint_bev
delta_tco_totale = tco_h2 - tco_bev

# --- LOGICA SEMAFORI FISICI ---
sem_peso = "🟢 OK" if peso_netto_perso <= limite_peso_tollerato[tipo_veicolo] * 0.7 else ("🟡 ATTENZIONE" if peso_netto_perso <= limite_peso_tollerato[tipo_veicolo] else "🔴 CRITICO")
sem_tempo = "🟢 OK" if tempo_ricarica_h <= tempo_inattivita * 0.8 else ("🟡 ATTENZIONE" if tempo_ricarica_h <= tempo_inattivita else "🔴 CRITICO")

# --- VISUALIZZAZIONE DASHBOARD ---

# ECCEZIONE REGOLA AUREA: Urbano Leggero/Breve
if tipo_veicolo == "Autobus Urbano" and km_giornalieri <= 200:
    st.success("### 🟢 VERDETTO IMMEDIATO: VANTAGGIO ASSOLUTO BEV (Elettrico)")
    st.write("Per percorsi urbani inferiori a 200 km, i veicoli a batteria hanno già raggiunto la parità economica e tecnica. L'idrogeno per questo specifico impiego risulta sovradimensionato ed economicamente inefficiente.")
    st.stop()

# VERDETTO COMPLESSO
st.markdown("---")
st.subheader("📋 Verdetto di Fattibilità Operativa")

vince_h2 = "🔴 CRITICO" in sem_peso or "🔴 CRITICO" in sem_tempo or tco_h2 < (tco_bev * 0.9)

if vince_h2:
    st.error("### 🔵 L'IDROGENO È LA SCELTA STRATEGICA MIGLIORE")
    st.write("L'elettrico a batterie fallisce i requisiti minimi di operatività fisica o risulta significativamente più costoso nel lungo periodo.")
else:
    st.success("### 🟢 L'ELETTRICO (BEV) È FATTIBILE E PIÙ ECONOMICO")
    st.write("La tecnologia BEV riesce a coprire la missione richiesta e offre un Costo Totale di Proprietà (TCO) inferiore.")

# SEMAFORI FISICI
st.markdown("### 🚦 Analisi dei Colli di Bottiglia Elettrici (BEV)")
col1, col2 = st.columns(2)

with col1:
    st.info(f"**⚖️ Carico Utile (Payload)**\n\nStato: **{sem_peso}**")
    st.write(f"Peso Batteria Richiesta: **{peso_batteria:,.0f} kg**")

with col2:
    st.info(f"**⏱️ Tempi di Ricarica**\n\nStato: **{sem_tempo}**")
    st.write(f"Tempo Necessario: **{tempo_ricarica_h:.1f} ore**")

# DASHBOARD ECONOMICA E DELTA
st.markdown("---")
st.subheader("💶 Analisi degli Scostamenti Economici (Delta TCO)")
st.write("Confronto diretto: quanto l'Idrogeno (FCEV) impatta sulle casse rispetto all'Elettrico (BEV).")

c1, c2, c3, c4 = st.columns(4)
c1.metric("TCO Elettrico (BEV)", f"€ {tco_bev:,.0f}")
c2.metric("TCO Idrogeno (FCEV)", f"€ {tco_h2:,.0f}")

delta_color = "inverse" if delta_tco_totale > 0 else "normal"
c3.metric("Delta TCO (Extra-costo H2)", f"€ {delta_tco_totale:,.0f}", delta=f"{delta_tco_totale:,.0f} € rispetto a BEV", delta_color=delta_color)
c4.metric("Prezzi Energia Simulati", f"{costo_kwh_el_stimato:.2f} €/kWh", f"{costo_kg_h2_stimato:.2f} €/kg H2", delta_color="off")

# GRAFICO WATERFALL
st.markdown("#### Da dove deriva l'extra-costo (o il risparmio)?")

fig_waterfall = go.Figure(go.Waterfall(
    name = "20", orientation = "v",
    measure = ["relative", "relative", "relative", "total"],
    x = ["Delta CAPEX (Veicolo)", "Delta Energia (Fuel)", "Delta Manutenzione", "Delta TCO Totale"],
    textposition = "outside",
    text = [f"€ {delta_capex:,.0f}", f"€ {delta_fuel:,.0f}", f"€ {delta_maint:,.0f}", f"€ {delta_tco_totale:,.0f}"],
    y = [delta_capex, delta_fuel, delta_maint, delta_tco_totale],
    connector = {"line":{"color":"rgb(63, 63, 63)"}},
    decreasing = {"marker":{"color":"#2ca02c"}}, # Verde se H2 fa risparmiare
    increasing = {"marker":{"color":"#d62728"}}, # Rosso se H2 costa di più
    totals = {"marker":{"color":"#1f77b4"}}
))

fig_waterfall.update_layout(title="Scomposizione del Delta TCO (Valori positivi = Idrogeno costa di più)", showlegend=False)
st.plotly_chart(fig_waterfall, use_container_width=True)
