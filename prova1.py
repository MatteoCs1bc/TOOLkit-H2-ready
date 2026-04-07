import streamlit as st
import pandas as pd
import numpy as np

# Configurazione della pagina
st.set_page_config(page_title="H2READY Scouting Tool", layout="wide")

# Funzione per mappare il punteggio base ATECO e il relativo Tag
def get_ateco_score(ateco_code):
    # Gestione valori nulli
    if pd.isna(ateco_code):
        return 0, "Dato ATECO mancante"
        
    # Prende le prime due cifre (es. da "24.10" prende "24")
    ateco_str = str(ateco_code).split('.')[0][:2] 
    
    if ateco_str in ['24', '19', '20']:
        return 5, "HTA Priorità Assoluta (>800°C o Feedstock)"
    elif ateco_str == '23':
        return 4, "HTA Calore Estremo (>400°C)"
    elif ateco_str in ['17', '10', '16', '13', '14']:
        return 0, "Escluso (Elettrificabile/Bassa Temp)"
    else:
        return 0, "Non classificato come HTA"

# Funzione per calcolare il punteggio totale della singola azienda
def calculate_score(row):
    # 1. Punteggio Base ATECO (Obbligatorio)
    base_score, _ = get_ateco_score(row.get('Codice ATECO'))
    
    # REGOLA FERREA: Se il processo è elettrificabile o assente, score = 0
    if base_score == 0:
        return 0
        
    # 2. Moltiplicatore Dimensione (Obbligatorio)
    dim_val = row.get('Dimensione', 'Piccola')
    if pd.isna(dim_val):
        dim_val = 'Piccola' # Default se manca il dato
        
    dim = str(dim_val).strip().title()
    moltiplicatore = 1.0
    if dim == 'Grande':
        moltiplicatore = 1.5
    elif dim == 'Media':
        moltiplicatore = 1.2
        
    score = base_score * moltiplicatore
    
    # 3. Bonus Aggregazione Consortile (Opzionale)
    # Verifica se la colonna esiste e se il valore non è nullo
    if 'Ubicazione/Consorzio' in row and not pd.isna(row['Ubicazione/Consorzio']):
        if str(row['Ubicazione/Consorzio']).strip().upper() == 'SÌ':
            score += 3
            
    # 4. Bonus Dorsale PCI (South H2 Corridor) (Opzionale)
    if 'Vicinanza South H2 Corridor' in row and not pd.isna(row['Vicinanza South H2 Corridor']):
        if str(row['Vicinanza South H2 Corridor']).strip().upper() == 'SÌ':
            score += 3
            
    return round(score, 1)

# Funzione per assegnare il Tier
def assign_tier(score):
    if score == 0:
        return "Non Idoneo"
    elif score >= 10.0: 
        return "Tier 1 - Priorità Alta"
    elif score >= 7.0:
        return "Tier 2 - Media"
    else:
        return "Tier 3 - Bassa"

# --- INTERFACCIA STREAMLIT ---
st.title("🔍 H2READY: Tool di Scouting Industriale (A.1)")
st.markdown("**Parola d'ordine: IDROGENO SOLO DOVE ALTRIMENTI NON ELETTRIFICABILE!**")

st.info("Carica il database aziendale. Colonne minime richieste: Nome Azienda, Codice ATECO, Dimensione.")

uploaded_file = st.file_uploader("Carica il database aziendale (Formato .xlsx o .csv)", type=["xlsx", "csv"])

if uploaded_file is not None:
    try:
        # Lettura file (supporta sia excel che csv)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        df.columns = df.columns.str.strip()
        
        # Controlli di sicurezza SOLO sulle colonne base
        required_cols = ['Nome Azienda', 'Codice ATECO', 'Dimensione']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.error(f"Errore: Nel file mancano le colonne obbligatorie: {', '.join(missing_cols)}")
            st.stop()
            
        # Calcolo dei punteggi (gestisce automaticamente le colonne opzionali mancanti)
        df['Score Strategico'] = df.apply(calculate_score, axis=1)
        df['Analisi Processo'] = df['Codice ATECO'].apply(lambda x: get_ateco_score(x)[1])
        df['Classificazione'] = df['Score Strategico'].apply(assign_tier)
        
        # Ordinamento
        df_sorted = df.sort_values(by='Score Strategico', ascending=False)
        
        st.success("Analisi completata con successo! (Le colonne opzionali vuote o mancanti sono state ignorate).")
        
        # Metriche
        col1, col2, col3 = st.columns(3)
        col1.metric("Totale Aziende Analizzate", len(df_sorted))
        col2.metric("Aziende Tier 1 (Priorità H2)", len(df_sorted[df_sorted['Classificazione'] == 'Tier 1 - Priorità Alta']))
        col3.metric("Aziende Escluse (Elettrificabili)", len(df_sorted[df_sorted['Classificazione'] == 'Non Idoneo']))
        
        # Visualizzazione Tabella
        st.write("### Risultati dello Scouting")
        st.dataframe(
            df_sorted.style.applymap(
                lambda x: 'background-color: #d4edda; color: black' if x == 'Tier 1 - Priorità Alta' 
                else ('background-color: #f8d7da; color: black' if x == 'Non Idoneo' else ''),
                subset=['Classificazione']
            ),
            use_container_width=True
        )
        
        # Download
        csv = df_sorted.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Scarica i risultati in CSV",
            data=csv,
            file_name='scouting_h2ready_risultati.csv',
            mime='text/csv',
        )
            
    except Exception as e:
        st.error(f"Si è verificato un errore durante l'elaborazione del file: {e}")
