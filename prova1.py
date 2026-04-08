import streamlit as st
import pandas as pd
import numpy as np

# Configurazione della pagina
st.set_page_config(page_title="H2READY Scouting Tool", layout="wide")

# --- FUNZIONI DI LOGICA E SCORING ---

def analyze_h2_potential(ateco_code, dimensione):
    """
    Analizza il codice ATECO e la dimensione per determinare:
    1. Il tipo di utilizzo (Termico o Materia Prima/RED III).
    2. Lo Score Base.
    3. Una stima qualitativa del consumo potenziale.
    """
    if pd.isna(ateco_code):
        return 0, "Non Classificato", "N/D", "N/D"
        
    ateco_str = str(ateco_code).split('.')[0]
    ateco_2_cifre = ateco_str[:2]
    ateco_4_cifre = ateco_str[:4] if len(ateco_str) >= 4 else ateco_str
    
    # 1. Analisi HTA Feedstock (Obbligo RED III) - Tool A.2
    if ateco_2_cifre in ['19', '20']:
        tipo_uso = "MATERIA PRIMA (RED III)"
        score_base = 5
        
        # Stima del consumo basata sulla dimensione
        if dim_multiplier(dimensione) == 1.5:
            stima_consumo = "Altissimo (> 5.000 t/anno H2)"
        elif dim_multiplier(dimensione) == 1.2:
            stima_consumo = "Alto (1.000 - 5.000 t/anno H2)"
        else:
            stima_consumo = "Medio (< 1.000 t/anno H2)"
            
        dettaglio = "Sostituzione Idrogeno Grigio. Obbligo 42% RFNBO al 2030."
        if ateco_4_cifre == '2015':
            dettaglio = "Produzione Fertilizzanti. Altissimo potenziale off-taker."
            
        return score_base, tipo_uso, stima_consumo, dettaglio

    # 2. Analisi HTA Termico - Tool A.1
    elif ateco_2_cifre == '24':
        tipo_uso = "CALORE ESTREMO (>800°C)"
        score_base = 5
        stima_consumo = "Alto (Sostituzione Metano/Carbone)"
        return score_base, tipo_uso, stima_consumo, "Siderurgia/Metallurgia (Potenziale processo DRI)"
        
    elif ateco_2_cifre == '23':
        tipo_uso = "CALORE ALTO (>400°C)"
        score_base = 4
        stima_consumo = "Medio/Alto (Sostituzione Metano)"
        
        if ateco_4_cifre == '2351':
             dettaglio = "Cemento (Forni rotativi >1400°C)"
        elif ateco_4_cifre in ['2311', '2313']:
             dettaglio = "Vetro (Fusione >1500°C)"
        else:
             dettaglio = "Ceramica/Laterizi (Possibile blending H2/Metano)"
        return score_base, tipo_uso, stima_consumo, dettaglio

    # 3. Esclusioni (Elettrificabili)
    elif ateco_2_cifre in ['17', '10', '11', '16', '13', '14']:
        return 0, "ESCLUSO (Elettrificabile)", "Basso", "Processi <400°C. Valutare Pompe di Calore."
    
    else:
        return 0, "Non Classificato", "N/D", "Settore non in target primario."

def dim_multiplier(dim_val):
    if pd.isna(dim_val):
        return 1.0
    dim = str(dim_val).strip().title()
    if dim == 'Grande': return 1.5
    elif dim == 'Media': return 1.2
    else: return 1.0

def calculate_total_score(row):
    score_base, _, _, _ = analyze_h2_potential(row.get('Codice ATECO'), row.get('Dimensione'))
    
    if score_base == 0:
        return 0
        
    score = score_base * dim_multiplier(row.get('Dimensione'))
    
    if 'Ubicazione/Consorzio' in row and not pd.isna(row['Ubicazione/Consorzio']):
        if str(row['Ubicazione/Consorzio']).strip().upper() == 'SÌ':
            score += 3
            
    if 'Vicinanza South H2 Corridor' in row and not pd.isna(row['Vicinanza South H2 Corridor']):
        if str(row['Vicinanza South H2 Corridor']).strip().upper() == 'SÌ':
            score += 3
            
    return round(score, 1)

def assign_tier(score):
    if score == 0: return "Non Idoneo"
    elif score >= 10.0: return "Tier 1 - Priorità Alta"
    elif score >= 7.0: return "Tier 2 - Media"
    else: return "Tier 3 - Bassa"

# --- INTERFACCIA STREAMLIT ---
st.title("🔍 H2READY: Tool di Scouting Industriale Integrato (A.1 & A.2)")
st.markdown("**Analisi del Potenziale Termico e di Materia Prima (RED III)**")

# --- SEZIONE ESPANDIBILE: GUIDA ALL'UTILIZZO ---
with st.expander("📚 Guida all'Utilizzo: Scopri come funziona l'algoritmo e come preparare i dati", expanded=False):
    st.markdown("""
    Benvenuto nel **Tool di Scouting Industriale H2READY**. Questo strumento supporta le Amministrazioni Comunali nell'identificazione delle aziende con il maggior potenziale strategico per la transizione verso l'idrogeno verde[cite: 1799, 1800].

    ### ⚠️ Parola d'ordine: IDROGENO SOLO DOVE ALTRIMENTI NON ELETTRIFICABILE!
    Il sistema segue il principio della **neutralità tecnologica**: l'idrogeno è una priorità esclusivamente per i settori **"Hard-to-Abate" (HTA)**, dove le temperature superano i 400°C o dove la molecola serve come reagente chimico[cite: 1814, 1827]. Per processi a bassa/media temperatura (es. essiccazione, vapore a bassa pressione), l'elettrificazione diretta è la soluzione più efficiente[cite: 1814, 1828].

    ---

    ### 1. Classificazione dei Settori Industriali (Codici ATECO)
    Il tool analizza il codice ATECO per distinguere tra usi termici e chimici:

    #### **A. Materia Prima e Feedstock (Tool A.2 - Obbligo RED III)**
    * **ATECO 19.x (Raffinazione) e 20.x (Chimica di base):** L'idrogeno è usato come reagente per produrre ammoniaca, metanolo o per la desolforazione[cite: 1879, 1880]. 
    * **Obiettivo:** Sostituire l'idrogeno "grigio" (fossile) con idrogeno verde per rispettare l'obbligo europeo di raggiungere il **42% di idrogeno rinnovabile entro il 2030**[cite: 2152, 2153].
    * **Punteggio Base:** **5 Punti**.

    #### **B. Calore di Processo ad Alta Temperatura (Tool A.1)**
    * **ATECO 24.x (Siderurgia e Metallurgia):** Processi di fusione e forgiatura che superano gli 800°C e arrivano oltre i 1.500°C[cite: 1869, 1870]. L'idrogeno può anche sostituire il carbone come agente riducente[cite: 1873].
    * **ATECO 23.x (Minerali Non Metalliferi):** Produzione di **Cemento** (cottura clinker a 1.450°C), **Vetro** (fusione a 1.600°C) e **Ceramica** (cottura sopra i 400°C)[cite: 1875, 1877].
    * **Punteggio Base:** **5 Punti** (24.x) o **4 Punti** (23.x).

    #### **C. Aree di Esclusione (Elettrificabili)**
    * **ATECO 10.x/11.x (Alimentare), 16.x (Legno), 17.x (Carta), 13.x/14.x (Tessile):** Utilizzano calore a bassa/media temperatura (sotto i 400°C)[cite: 1883, 1884]. Questi settori sono **esclusi** dallo scouting idrogeno poiché l'elettrificazione è prioritaria[cite: 1885].
    * **Punteggio Base:** **0 Punti**.

    ---

    ### 2. Calcolo dello Score e Classificazione (Tier)
    Il punteggio finale di ogni azienda viene calcolato come segue:
    1.  **Punteggio Base ATECO** moltiplicato per la dimensione aziendale:
        * **Grande Impresa:** x1.5 (maggiore capacità CAPEX e pressione ETS/CBAM)[cite: 2432, 2433].
        * **Media Impresa:** x1.2.
        * **Piccola Impresa:** x1.0.
    2.  **Bonus Strategici:**
        * **Aggregazione Consortile (+3 Punti):** Aziende in Consorzi (es. ZIPR, COSEF) che possono aggregare la domanda[cite: 1921].
        * **South H2 Corridor (+3 Punti):** Vicinanza alla futura dorsale PCI Mazara-Tarvisio[cite: 2328, 2404].

    #### **Risultato Finale:**
    * 🟢 **Tier 1 - Priorità Alta (Score ≥ 10.0):** Candidati ideali per progetti pilota e studi di pre-fattibilità tecnica[cite: 1802].
    * 🟡 **Tier 2 - Media (Score 7.0 - 9.9):** Aziende con potenziale per sinergie di distretto.
    * 🔴 **Non Idoneo / Tier 3:** Settori elettrificabili o punteggi insufficienti.

    ---

    ### 3. Struttura del file Excel di Input
    Il file deve contenere le seguenti intestazioni (le prime tre sono obbligatorie):
    """)

    # Tabella visiva della struttura Excel
    df_guida = pd.DataFrame({
        "Nome Azienda": ["Acciaierie Friulane S.p.A.", "Chimica Isontina S.r.l.", "Mobili & Design"],
        "Codice ATECO": ["24.10", "20.14", "16.23"],
        "Dimensione": ["Grande", "Media", "Media"],
        "Fatturato (€)": [120000000, 12000000, 8000000],
        "# Dipendenti": [450, 65, 55],
        "Ubicazione/Consorzio": ["SÌ", "SÌ", "NO"],
        "Vicinanza South H2 Corridor": ["SÌ", "SÌ", "NO"]
    })
    st.dataframe(df_guida, hide_index=True, use_container_width=True)
    st.caption("*Le colonne opzionali vuote verranno ignorate dal sistema senza interrompere l'analisi.*")

st.info("Carica il database aziendale. Colonne minime: Nome Azienda, Codice ATECO, Dimensione.")

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
            
        # Elaborazione Dati
        df['Score Strategico'] = df.apply(calculate_total_score, axis=1)
        df['Classificazione'] = df['Score Strategico'].apply(assign_tier)
        
        # Applica l'analisi dettagliata (spacchetta i risultati della funzione in nuove colonne)
        analisi_results = df.apply(lambda row: analyze_h2_potential(row['Codice ATECO'], row['Dimensione']), axis=1)
        df['Tipo Utilizzo H2'] = [res[1] for res in analisi_results]
        df['Stima Consumo Potenziale'] = [res[2] for res in analisi_results]
        df['Dettaglio Tecnico / Normativo'] = [res[3] for res in analisi_results]
        
        # Ordinamento per Score
        df_sorted = df.sort_values(by='Score Strategico', ascending=False)
        
        st.success("Analisi completata! Le aziende sono state classificate per potenziale Termico e obblighi RED III.")
        
        # Metriche
        col1, col2, col3 = st.columns(3)
        col1.metric("Totale Aziende Analizzate", len(df_sorted))
        
        # Conta le aziende soggette a RED III (Feedstock)
        aziende_red3 = len(df_sorted[df_sorted['Tipo Utilizzo H2'] == "MATERIA PRIMA (RED III)"])
        col2.metric("Aziende con Obbligo RED III", aziende_red3)
        
        col3.metric("Aziende Tier 1 (Priorità Totale)", len(df_sorted[df_sorted['Classificazione'] == 'Tier 1 - Priorità Alta']))
        
        # --- VISUALIZZAZIONE TABELLA ---
        st.write("### Risultati dello Scouting Strategico")
        
        # Riorganizzo le colonne per una lettura più chiara
        colonne_da_mostrare = [
            'Nome Azienda', 'Codice ATECO', 'Dimensione', 
            'Classificazione', 'Score Strategico', 
            'Tipo Utilizzo H2', 'Stima Consumo Potenziale', 'Dettaglio Tecnico / Normativo'
        ]
        
        # Mostro solo le colonne che esistono nel df originale + le nuove calcolate
        colonne_finali = [col for col in colonne_da_mostrare if col in df_sorted.columns]
        
        st.dataframe(
            df_sorted[colonne_finali].style.map(
                lambda x: 'background-color: #d4edda; color: black; font-weight: bold' if x == 'Tier 1 - Priorità Alta' 
                else ('background-color: #fff3cd; color: black' if x == 'Tier 2 - Media' 
                else ('background-color: #f8d7da; color: black' if x == 'Non Idoneo' else '')),
                subset=['Classificazione']
            ).map(
                # Evidenzio visivamente le aziende RED III per distinguerle da quelle termiche
                lambda x: 'color: #004085; font-weight: bold' if x == 'MATERIA PRIMA (RED III)' else '',
                subset=['Tipo Utilizzo H2']
            ),
            use_container_width=True,
            hide_index=True
        )
        
        # Download
        csv = df_sorted.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Scarica Database Analizzato (CSV)",
            data=csv,
            file_name='h2ready_analisi_completa.csv',
            mime='text/csv',
        )
            
    except Exception as e:
        st.error(f"Si è verificato un errore durante l'elaborazione: {e}")
