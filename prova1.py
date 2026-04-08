import streamlit as st
import pandas as pd
import numpy as np

# Configurazione della pagina
st.set_page_config(page_title="H2READY Scouting Tool", layout="wide")

# --- FUNZIONI DI LOGICA E SCORING ---

def analyze_h2_potential(ateco_code, dimensione):
    """Analisi ATECO per Tool A.1 (Calore) e A.2 (RED III)"""
    if pd.isna(ateco_code):
        return 0, "Non Classificato", "N/D", "N/D"
        
    ateco_str = str(ateco_code).split('.')[0]
    ateco_2_cifre = ateco_str[:2]
    
    # 1. MATERIA PRIMA (RED III) - Tool A.2
    if ateco_2_cifre in ['19', '20']:
        tipo = "MATERIA PRIMA (RED III)"
        score = 5
        stima = "Altissimo (Feedstock)" if str(dimensione).lower() == 'grande' else "Alto/Medio"
        nota = "Obbligo 42% rinnovabile al 2030."
        return score, tipo, stima, nota

    # 2. CALORE ESTREMO (>800°C) - Tool A.1
    elif ateco_2_cifre == '24':
        return 5, "CALORE ESTREMO (>800°C)", "Alto", "Siderurgia/Metallurgia (Processo DRI)"
        
    # 3. CALORE ALTO (>400°C) - Tool A.1
    elif ateco_2_cifre == '23':
        return 4, "CALORE ALTO (>400°C)", "Medio/Alto", "Vetro/Cemento/Ceramica"

    # 4. ESCLUSIONI
    elif ateco_2_cifre in ['17', '10', '11', '16', '13', '14']:
        return 0, "ESCLUSO (Elettrificabile)", "Basso", "Processi <400°C. Target: Pompe di calore."
    
    return 0, "Non Classificato", "N/D", "Settore non in target primario."

def calculate_total_score(row):
    """Calcola lo score finale includendo i nuovi parametri (AIA, Consortium, Corridor)"""
    base_score, _, _, _ = analyze_h2_potential(row.get('Codice ateco'), row.get('dimensione'))
    
    if base_score == 0:
        return 0
        
    # Moltiplicatore Dimensione
    dim = str(row.get('dimensione', 'Piccola')).strip().title()
    mult = 1.5 if dim == 'Grande' else (1.2 if dim == 'Media' else 1.0)
    
    score = base_score * mult
    
    # Bonus AIA (Autorizzazione Integrata Ambientale)
    if 'AIA (si/no)' in row and str(row['AIA (si/no)']).strip().upper() == 'SÌ':
        score += 2
    
    # Bonus Consorzio
    if 'ubicazione/consorzio' in row and str(row['ubicazione/consorzio']).strip().upper() == 'SÌ':
        score += 3
            
    # Bonus Corridor
    if 'vicinanza South H2 corridor' in row and str(row['vicinanza South H2 corridor']).strip().upper() == 'SÌ':
        score += 3
            
    return round(score, 1)

# --- INTERFACCIA STREAMLIT ---
st.title("🔍 H2READY: Tool di Scouting Industriale Integrato")
st.markdown("**Valutazione Calore di Processo (A.1) e Conformità RED III (A.2)**")

# --- SEZIONE ESPANDIBILE: GUIDA ALL'UTILIZZO ---
with st.expander("📚 Guida all'Utilizzo e Struttura File Excel", expanded=False):
    st.markdown("""
    ### Logica di Analisi
    Il tool identifica le aziende dove l'idrogeno è insostituibile:
    1. **Materia Prima (RED III):** Chimica e Raffinazione (Obbligo normativo 2030).
    2. **Calore Estremo:** Siderurgia, Vetro e Cemento (Temperature >400°C).
    3. **Esclusione:** Alimentare, Carta e Legno (Processi elettrificabili).

    ### Struttura del file di ingresso (11 Colonne)
    Per funzionare correttamente, il file Excel/CSV deve avere le seguenti intestazioni (anche se alcune celle sono vuote):
    """)
    
    # Esempio tabella con 11 colonne
    df_guida = pd.DataFrame({
        "nome azienda": ["Esempio Acciai S.p.A.", "Chimica Bio S.r.l.", "Legno Arredo S.n.c."],
        "Codice ateco": ["24.10", "20.14", "16.23"],
        "dimensione": ["Grande", "Media", "Piccola"],
        "fatturato": ["150M", "12M", "2M"],
        "dipendenti": [400, 50, 12],
        "ubicazione/consorzio": ["SÌ", "SÌ", "NO"],
        "vicinanza South H2 corridor": ["SÌ", "NO", "NO"],
        "AIA (si/no)": ["SÌ", "SÌ", "NO"],
        "consumo energia stimato": ["Alto", "Medio", "Basso"],
        "processo": ["Fusione", "Reazione", "Essiccazione"],
        "note": ["Target primario", "Obbligo RED III", "Elettrificabile"]
    })
    st.dataframe(df_guida, hide_index=True)
    st.caption("Nota: Le colonne 'nome azienda', 'Codice ateco' e 'dimensione' sono obbligatorie per il calcolo.")

# --- CARICAMENTO FILE ---
st.info("Carica il database. Assicurati che le intestazioni corrispondano alla guida sopra.")
uploaded_file = st.file_uploader("Scegli un file Excel o CSV", type=["xlsx", "csv"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        
        # Pulizia colonne (case insensitive e senza spazi)
        df.columns = df.columns.str.strip()
        
        # Verifica colonne minime
        min_cols = ['nome azienda', 'Codice ateco', 'dimensione']
        if not all(c in df.columns for c in min_cols):
            st.error(f"Errore: Il file deve contenere almeno: {min_cols}")
            st.stop()

        # Calcoli
        df['Score Strategico'] = df.apply(calculate_total_score, axis=1)
        
        # Generazione analisi dettagliata
        analisi = df.apply(lambda r: analyze_h2_potential(r['Codice ateco'], r['dimensione']), axis=1)
        df['Tipo Utilizzo H2'] = [x[1] for x in analisi]
        df['Stima Consumo'] = [x[2] for x in analisi]
        df['Dettaglio Tecnico/Normativo'] = [x[3] for x in analisi]
        
        # Tiering
        df['Classificazione'] = df['Score Strategico'].apply(
            lambda s: "Tier 1 - Priorità Alta" if s >= 10 else ("Tier 2 - Media" if s >= 7 else "Non Idoneo")
        )

        # Metriche
        c1, c2, c3 = st.columns(3)
        c1.metric("Aziende Analizzate", len(df))
        c2.metric("Target RED III", len(df[df['Tipo Utilizzo H2'] == "MATERIA PRIMA (RED III)"]))
        c3.metric("Priorità Alta (Tier 1)", len(df[df['Classificazione'] == "Tier 1 - Priorità Alta"]))

        # Visualizzazione
        st.write("### Database Analizzato")
        
        # Ordiniamo per score
        df_sorted = df.sort_values(by='Score Strategico', ascending=False)
        
        # Colorazione
        def style_rows(row):
            if row['Classificazione'] == "Tier 1 - Priorità Alta":
                return ['background-color: #d4edda'] * len(row)
            if row['Classificazione'] == "Non Idoneo":
                return ['background-color: #f8d7da'] * len(row)
            return [''] * len(row)

        st.dataframe(
            df_sorted.style.apply(style_rows, axis=1),
            use_container_width=True,
            hide_index=True
        )

        # Download
        st.download_button("📥 Scarica Risultati (CSV)", df_sorted.to_csv(index=False), "h2ready_scouting.csv", "text/csv")

    except Exception as e:
        st.error(f"Errore durante l'analisi: {e}")
