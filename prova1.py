import streamlit as st
import pandas as pd
import numpy as np

# Configurazione della pagina
st.set_page_config(page_title="H2READY Scouting Tool", layout="wide")

# --- LOGICA DI SCORING REVISIONATA ---

def get_base_score(row):
    """Determina il punteggio base analizzando ATECO e Note Tecniche"""
    ateco = str(row.get('codice ateco', '')).replace('.', '').strip()
    prefix = ateco[:2]
    
    # Check 1: Settori HTA Certi
    if prefix in ['24', '19', '20']:
        return 5, "HTA Priorità Assoluta (RED III / Siderurgia)"
    elif prefix == '23':
        return 4, "HTA Calore Estremo (Vetro/Cemento)"
    
    # Check 2: Recupero tramite parole chiave (per aziende come Anoxidall)
    # Analizziamo le colonne 'processo' e 'note'
    testo_tecnico = (str(row.get('processo', '')) + " " + str(row.get('note', ''))).lower()
    parole_chiave = ['metano', 'mw', 'forno', 'fusione', 'calore', 'termico', 'ossidazione', 'verniciatura']
    
    if any(keyword in testo_tecnico for keyword in parole_chiave):
        # Se troviamo parole chiave termiche in settori borderline (es. 25, 26, 28)
        if prefix in ['25', '26', '27', '28', '33']:
            return 3, "Recupero: Processo termico dichiarato (nonostante ATECO)"
        return 1, "Potenziale basso: Verificare processo elettrificabile"

    # Check 3: Settori Esclusi (Carta, Alimentare, Legno)
    if prefix in ['10', '11', '16', '17', '13', '14']:
        return 0, "Escluso: Elettrificabile (Bassa Temp)"
    
    return 0, "Non Classificato / Non Idoneo"

def calculate_total_score(row):
    base_score, _ = get_base_score(row)
    if base_score == 0:
        return 0
        
    # Moltiplicatore Dimensione
    dim = str(row.get('dimensione', 'Piccola')).strip().title()
    mult = 1.5 if dim == 'Grande' else (1.2 if dim == 'Media' else 1.0)
    score = base_score * mult
    
    # Bonus vari (AIA, Consorzio, Corridor)
    if str(row.get('aia (si/no)', '')).strip().lower() in ['sì', 'si']:
        score += 2
    if str(row.get('ubicazione/consorzio', '')).strip().lower() in ['sì', 'si'] or "z.i." in str(row.get('ubicazione/consorzio', '')).lower():
        score += 3
    if str(row.get('vicinanza south h2 corridor', '')).strip().lower() in ['sì', 'si']:
        score += 3
            
    return round(score, 1)

# --- INTERFACCIA ---
st.title("🔍 H2READY: Tool di Scouting Industriale")

with st.expander("📚 Istruzioni per l'Excel"):
    st.write("Il file deve contenere queste colonne (non importa se maiuscole o minuscole):")
    st.code("nome azienda, codice ateco, dimensione, ubicazione/consorzio, vicinanza south h2 corridor, aia (si/no), processo, note")

uploaded_file = st.file_uploader("Carica il file Excel o CSV", type=["xlsx", "csv"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        
        # PULIZIA COLONNE: fondamentale per far funzionare il .get()
        df.columns = df.columns.str.strip().str.lower()
        
        # Calcolo Risultati
        df['score_strategico'] = df.apply(calculate_total_score, axis=1)
        df['analisi_tecnica'] = df.apply(lambda r: get_base_score(r)[1], axis=1)
        
        # Tiering
        df['classificazione'] = df['score_strategico'].apply(
            lambda s: "Tier 1 - Priorità Alta" if s >= 9 else ("Tier 2 - Media" if s >= 5 else "Non Idoneo")
        )

        # Tabella Risultati
        df_display = df.sort_values(by='score_strategico', ascending=False)
        
        st.subheader("Risultati dello Scouting")
        st.dataframe(
            df_display.style.map(
                lambda x: 'background-color: #d4edda; color: black' if x == 'Tier 1 - Priorità Alta' 
                else ('background-color: #f8d7da; color: black' if x == 'Non Idoneo' else ''),
                subset=['classificazione']
            ),
            use_container_width=True, hide_index=True
        )
        
        st.download_button("📥 Scarica Report CSV", df_display.to_csv(index=False), "report_h2.csv")

    except Exception as e:
        st.error(f"Errore tecnico: {e}")
