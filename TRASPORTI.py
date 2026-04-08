    st.header("2. Approvvigionamento Energia")
    fonte_elettricita = st.radio("Sorgente Elettricità (BEV e Elettrolizzatore)", ["Da Rete", "Autoprodotta (es. FV Deposito)"])
    prezzo_el_base = st.number_input("Prezzo Elettricità (€/kWh)", value=0.22 if "Rete" in fonte_elettricita else 0.08, format="%.3f")
    
    fonte_idrogeno = st.radio("Sorgente Idrogeno (FCEV)", ["Acquisto Esterno (Carro Bombolaio)", "Autoprodotto (Elettrolizzatore + HRS)"])
    
    if "Esterno" in fonte_idrogeno:
        prezzo_h2_base = st.number_input("Prezzo di Mercato H2 oggi (€/kg)", value=16.0, format="%.2f")
    else:
        st.info(f"💡 **Modello 55 kWh/kg**\n\nIl costo dell'idrogeno viene calcolato automaticamente: **55 kWh** per produrre 1 kg di H2 (Costo energia: {prezzo_el_base * 55:.2f} €/kg) + i costi fissi dell'impianto di compressione (CSD).")

    st.header("3. Proiezioni Future")
    anno_acquisto = st.slider("Anno Previsto di Acquisto", 2024, 2035, 2024)
    anni_utilizzo = st.slider("Ciclo di Vita Utile (Anni)", 5, 15, 10)

# --- MOTORE FISICO ---
consumo_base_bev = {"Autobus Urbano": 1.1, "Autobus Extraurbano": 1.0, "Camion Pesante": 1.4}
densita_batt = interpolate(anno_acquisto, 0.16, 0.256)
costo_batt_kwh = interpolate(anno_acquisto, 210, 100)
costo_fc_kw = interpolate(anno_acquisto, 330, 210)

fabbisogno_kwh = km_giornalieri * consumo_base_bev[tipo_veicolo] * 1.15

# --- MOTORE ECONOMICO (PREZZI DINAMICI E 55 kWh/kg) ---

# 1. Costo elettricità base
costo_kwh_el_stimato = interpolate(anno_acquisto, prezzo_el_base, prezzo_el_base * 0.9) # Leggero calo costi el.

# 2. Logica di prezzo Idrogeno
if "Esterno" in fonte_idrogeno:
    # Mercato esterno: scende dal prezzo attuale a un realistico 9.0 €/kg al 2030 (taglio costi logistica)
    costo_kg_h2_stimato = interpolate(anno_acquisto, prezzo_h2_base, 9.0) 
else:
    # AUTOPRODUZIONE (La regola dei 55 kWh/kg)
    costo_energia_per_kg = 55.0 * costo_kwh_el_stimato
    # Ammortamento Elettrolizzatore e Compressione a 350/700 bar (scende col tempo)
    ammortamento_impianto_csd = interpolate(anno_acquisto, 4.0, 2.5) # €/kg
    costo_kg_h2_stimato = costo_energia_per_kg + ammortamento_impianto_csd

# Calcoli TCO Assoluti
giorni_anno = 300
km_annui = km_giornalieri * giorni_anno

capex_bev = 150000 + (fabbisogno_kwh * costo_batt_kwh)
capex_h2 = 150000 + (200 * costo_fc_kw) + 35000

opex_fuel_bev = km_annui * consumo_base_bev[tipo_veicolo] * costo_kwh_el_stimato * anni_utilizzo
consumo_h2_kg_km = consumo_base_bev[tipo_veicolo] / 15.0
opex_fuel_h2 = km_annui * consumo_h2_kg_km * costo_kg_h2_stimato * anni_utilizzo

opex_maint_bev = km_annui * 0.15 * anni_utilizzo
opex_maint_h2 = km_annui * 0.25 * anni_utilizzo

tco_bev = capex_bev + opex_fuel_bev + opex_maint_bev
tco_h2 = capex_h2 + opex_fuel_h2 + opex_maint_h2

# ... [IL RESTO DEL CODICE PER I DELTA E IL GRAFICO WATERFALL RIMANE IDENTICO] ...
