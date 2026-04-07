import streamlit as st
import pandas as pd
import numpy as np

# Configurazione della pagina
st.set_page_config(page_title="H2READY Scouting Tool", layout="wide")

# Funzione per mappare il punteggio base ATECO e il relativo Tag
def get_ateco_score(ateco_code):
    if pd.isna(ateco_code):
        return 0, "Dato ATECO mancante"
        
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
    base_score, _ = get_ateco_score(row.get('Codice ATECO'))
    
    if base_score == 0:
        return 0
        
    dim_val = row.get('Dimensione', 'Piccola')
    if pd.isna(dim_val):
        dim_val = 'Piccola' 
        
    dim = str(dim_val).strip().title()
    moltiplicatore = 1.0
    if dim == 'Grande':
        moltiplicatore = 1.5
    elif dim == 'Media':
        moltiplicatore = 1.2
        
    score = base_score * moltiplicatore
    
    if 'Ubicazione/Consorzio' in row and not pd.isna(row['Ubicazione/Consorzio']):
        if str(row['Ubicazione/Consorzio']).strip().upper() == 'SÌ':
            score += 3
            
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

# --- SEZIONE ESPANDIBILE: GUIDA ALL'UTILIZZO ---
with st.expander("📚 Guida all'Utilizzo: Scopri come funziona l'algoritmo e come preparare i dati", expanded=False):
    st.markdown("""
    Benvenuto nel **Tool di Scouting Industriale H2READY**. Questo strumento è progettato per supportare le Amministrazioni Comunali nell'identificazione delle aziende del proprio territorio che presentano il maggior potenziale strategico per la transizione verso l'idrogeno verde.

    Il sistema si basa sul principio della **neutralità tecnologica**: l'idrogeno viene considerato una priorità esclusivamente per i settori "Hard-to-Abate" (HTA), ovvero dove le temperature di processo superano i 400°C o dove l'idrogeno è impiegato come materia prima. Per tutti i settori con processi a bassa/media temperatura, l'elettrificazione (es. pompe di calore) rimane la soluzione più efficiente ed economica.

    ### 1. Come funziona l'algoritmo di Scoring (I Pesi)
    Il tool calcola automaticamente uno "Score Strategico" per ogni azienda caricata, assegnandola a una fascia di priorità (Tier) basandosi su tre parametri fondamentali:

    **A. Il Peso del Settore (Codice ATECO) - *Fattore Obbligatorio***
    Il motore di calcolo analizza le prime due cifre del Codice ATECO dell'azienda per determinarne l'idoneità termica o chimica all'uso dell'idrogeno:
    * **Priorità Assoluta (Score Base: 5 Punti):** ATECO 24.x (Siderurgia e Metallurgia) e ATECO 19.x/20.x (Chimica e Raffinazione).
    * **Priorità Alta (Score Base: 4 Punti):** ATECO 23.x (Minerali Non Metalliferi: Cemento, Vetro, Ceramica).
    * **ESCLUSIONE (Score: 0 Punti):** ATECO 10.x, 11.x, 16.x, 13.x, 14.x, 17.x (Alimentare, Legno, Carta, Tessile). Processi a bassa/media temperatura elettrificabili.

    **B. Il Moltiplicatore Dimensionale - *Fattore Obbligatorio***
    Le aziende di maggiori dimensioni hanno tipicamente una maggiore capacità di sostenere investimenti infrastrutturali (CAPEX).
    * **Grande Impresa:** x1.5 | **Media Impresa:** x1.2 | **Piccola Impresa:** x1.0

    **C. I Bonus Strategici e Territoriali - *Fattori Opzionali***
    * **Aggregazione Consortile (+3 Punti):** L'appartenenza a Consorzi di Sviluppo Economico facilita la condivisione delle infrastrutture.
    * **South H2 Corridor (+3 Punti):** La vicinanza al futuro gasdotto transnazionale (PCI) garantisce un'opzione di approvvigionamento strategico.

    ### 2. Classificazione dei Risultati (Tier)
    * 🟢 **Tier 1 - Priorità Alta (Score ≥ 10.0):** Aziende ideali per i tavoli tecnici strategici H2READY e studi di pre-fattibilità.
    * 🟡 **Tier 2 - Media (Score 7.0 - 9.9):** Aziende con buon potenziale, da coinvolgere in logiche di distretto.
    * 🔴 **Non Idoneo / Tier 3:** Settori elettrificabili o con punteggi insufficienti.

    ### 3. Come strutturare il file Excel / CSV di Input
    Affinché il tool funzioni correttamente, il file caricato **DEVE** avere l'intestazione esattamente come mostrata qui sotto. 
    *(Nota: le prime tre colonne sono obbligatorie. Le altre possono essere lasciate vuote, ma il nome della colonna deve essere presente).*
    """)

    # Tabella di Esempio (Esattamente come nell'immagine)
    df_esempio = pd.DataFrame({
        "Nome Azienda": ["Acciaierie Friulane S.p.A.", "Vetreria Esempio S.r.l."],
        "Codice ATECO": ["24.10", "23"],
        "Dimensione": ["Grande", "Media"],
        "Fatturato (€)": [50000000, 12000000],
        "# Dipendenti": [250, 45],
        "Ubicazione/Consorzio": ["SÌ", "NO"],
        "Vicinanza South H2 Corridor": ["NO", "SÌ"]
    })
    
    st.dataframe(df_esempio, hide_index=True, use_container_width=True)
    st.caption("*Suggerimento: Prepara il tuo file Excel copiando esattamente queste 7 intestazioni di colonna.*")

# --- SEZIONE DI CARICAMENTO FILE ---
st.info("Carica il database aziendale. Colonne minime richieste: Nome Azienda, Codice ATECO, Dimensione.")

uploaded_file = st.file_uploader("Carica il database aziendale (Formato .xlsx o .csv)", type=["xlsx", "csv"])

if uploaded_file is not None:
    try:
        # Lettura file
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        df.columns = df.columns.str.strip()
        
        # Controlli di sicurezza
        required_cols = ['Nome Azienda', 'Codice ATECO', 'Dimensione']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.error(f"Errore: Nel file mancano le colonne obbligatorie: {', '.join(missing_cols)}")
            st.stop()
            
        # Calcolo
        df['Score Strategico'] = df.apply(calculate_score, axis=1)
        df['Analisi Processo'] = df['Codice ATECO'].apply(lambda x: get_ateco_score(x)[1])
        df['Classificazione'] = df['Score Strategico'].apply(assign_tier)
        
        df_sorted = df.sort_values(by='Score Strategico', ascending=False)
        
        st.success("Analisi completata con successo! (Le colonne opzionali vuote o mancanti sono state ignorate).")
        
        # Metriche
        col1, col2, col3 = st.columns(3)
        col1.metric("Totale Aziende Analizzate", len(df_sorted))
        col2.metric("Aziende Tier 1 (Priorità H2)", len(df_sorted[df_sorted['Classificazione'] == 'Tier 1 - Priorità Alta']))
        col3.metric("Aziende Escluse (Elettrificabili)", len(df_sorted[df_sorted['Classificazione'] == 'Non Idoneo']))
        
        # Visualizzazione Tabella Risultati
        st.write("### Risultati dello Scouting")
        st.dataframe(
            df_sorted.style.map(
                lambda x: 'background-color: #d4edda; color: black' if x == 'Tier 1 - Priorità Alta' 
                else ('background-color: #f8d7da; color: black' if x == 'Non Idoneo' else ''),
                subset=['Classificazione']
            ),
            use_container_width=True,
            hide_index=True
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
