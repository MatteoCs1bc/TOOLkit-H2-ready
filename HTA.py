import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO

# Configurazione Pagina
st.set_page_config(page_title="H2READY - Scouting Tool", layout="wide")

# --- LOGICA DI SCORING (Versione 4.0 - RED III & Mappa Termica) ---
def get_base_score(row):
    # Pulizia del codice ATECO (es. 23.51 diventa 2351)
    ateco = str(row.get('codice ateco', '')).replace('.', '').strip()
    prefix = ateco[:2]
    
    testo_tecnico = (str(row.get('processo', '')) + " " + str(row.get('note', ''))).lower()
    
    # ---------------------------------------------------------
    # 1. VERIFICA ESCLUSIONI RED III (Sottoprodotti e Scarti)
    # ---------------------------------------------------------
    if ateco.startswith('2013'): return 0, "Escluso RED III (Sottoprodotto Cloro-Soda)"
    if ateco.startswith('1910'): return 0, "Escluso RED III (Gas di cokeria)"
    # L'ATECO 20.14 è escluso se produce plastica/etilene, 24.10 se usa altoforno
    if ateco.startswith('2014') and any(k in testo_tecnico for k in ['cracking', 'plastica', 'etilene']): 
        return 0, "Escluso RED III (Coprodotto Steam Cracking)"
    if ateco.startswith('2410') and any(k in testo_tecnico for k in ['altoforno', 'gas residuo']):
        return 0, "Escluso RED III (Gas di altoforno)"
    if ateco.startswith('1920') and any(k in testo_tecnico for k in ['benzina', 'diesel']):
        return 0, "Escluso RED III (Raffinazione trasporti)"
    
    # ---------------------------------------------------------
    # 2. VERIFICA TARGET PRIMARI RED III (Obbligo Idrogeno Verde)
    # ---------------------------------------------------------
    if ateco.startswith('2015'): return 5, "HTA Priorità Assoluta: Obbligo RED III (Fertilizzanti/NH3)"
    if ateco.startswith('2011'): return 5, "HTA Priorità Assoluta: Obbligo RED III (Produzione Gas)"
    if ateco.startswith('2014') and 'metanolo' in testo_tecnico: return 5, "HTA Priorità Assoluta: Obbligo RED III (Metanolo)"
    if ateco.startswith('2410') and any(k in testo_tecnico for k in ['dri', 'riduzione diretta']): return 5, "HTA Priorità Assoluta: Obbligo RED III (Siderurgia DRI)"
    
    if ateco.startswith('2410'): return 5, "HTA Siderurgia / Metalli Pesanti (Score Cautelativo)" # Siderurgia generica
    if ateco.startswith('2014'): return 4, "HTA Chimica di base (Potenziale RED III)"

    # ---------------------------------------------------------
    # 3. CLUSTER TEMPERATURA (Calore di Processo)
    # ---------------------------------------------------------
    calore_estremo = ['2311', '2313', '2320', '2332', '2351', '2352', '2451', '2452', '2453', '3822', '3832']
    if any(ateco.startswith(c) for c in calore_estremo):
        return 4, "HTA Calore Estremo (1000 - 1600°C) - Fusione e Calcinazione"
        
    calore_alto = ['2442', '2443', '2444', '1920', '2012', '2016', '2431', '2550', '2561', '2562', '3511', '3530', '3821']
    if any(ateco.startswith(c) for c in calore_alto):
        return 3, "HTA Calore Alto (500 - 1000°C) - Trattamenti/Chimica"

    # ---------------------------------------------------------
    # 4. RECUPERO PAROLE CHIAVE (Processi termici non classificati)
    # ---------------------------------------------------------
    parole_chiave = ['metano', 'mw', 'forno', 'fusione', 'calore', 'termico', 'ossidazione', 'verniciatura', 'fiamme', 'incenerimento']
    if any(k in testo_tecnico for k in parole_chiave) and prefix in ['25', '26', '27', '28', '33']:
        return 2, "Recupero: Processo termico dichiarato (Potenzialmente HTA)"
        
    # ---------------------------------------------------------
    # 5. ESCLUSI PER BASSA TEMPERATURA (Elettrificabili)
    # ---------------------------------------------------------
    if prefix in ['10', '11', '13', '14', '15', '16', '17', '31', '32']:
        return 0, "Escluso (Calore a bassa temperatura, elettrificabile)"
        
    return 0, "Non Classificato / Non Idoneo"

def calculate_total_score(row):
    base, _ = get_base_score(row)
    if base == 0: return 0
    
    # Moltiplicatore Dimensionale
    dim = str(row.get('dimensione', '')).strip().title()
    mult = 1.5 if dim == 'Grande' else (1.2 if dim == 'Media' else 1.0)
    score = base * mult
    
    # Bonus Strategici Logistici e Normativi
    if str(row.get('aia (si/no)', '')).lower() in ['sì', 'si', 'yes', 'y']: score += 2
    if "z.i." in str(row.get('ubicazione/consorzio', '')).lower() or str(row.get('ubicazione/consorzio', '')).lower() in ['sì', 'si', 'yes']: score += 3
    if str(row.get('vicinanza south h2 corridor', '')).lower() in ['sì', 'si', 'yes', 'y']: score += 3
    
    return round(score, 1)

# --- GENERATORE DI TEMPLATE EXCEL ---
def generate_template():
    output = BytesIO()
    cols = [
        "nome azienda", 
        "Codice ateco", 
        "dimensione", 
        "fatturato [M€]", 
        "dipendenti", 
        "ubicazione/consorzio", 
        "vicinanza South H2 corridor", 
        "AIA (si/no)", 
        "consumo energia stimato [MWh]", 
        "processo", 
        "note"
    ]
    # Dati di esempio calibrati sulle nuove regole
    example_data = [
        ["Fertilizzanti FVG S.p.A.", "20.15", "Grande", 250, 600, "Z.I. Aussa Corno", "SÌ", "SÌ", 150000, "Sintesi Ammoniaca", "Target RED III"],
        ["Vetreria Nord S.r.l.", "23.13", "Media", 12, 80, "SÌ", "NO", "SÌ", 15000, "Forni fusori a 1500°C", "Cluster 1 Estremo"],
        ["Acciaierie Alfa", "24.10", "Grande", 500, 1200, "Z.I. Trieste", "SÌ", "SÌ", 300000, "Altoforno", "Escluso per gas residuo"],
        ["Meccanica Beta", "25.61", "Piccola", 5, 25, "Z.I. Ponte Rosso", "NO", "NO", 2000, "Trattamento termico", "Forni a metano"],
    ]
    df_temp = pd.DataFrame(example_data, columns=cols)
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_temp.to_excel(writer, index=False, sheet_name='Template')
    return output.getvalue()

# --- INTERFACCIA ---
st.title("🚀 H2READY Strategic Scouting Tool - Modulo HTA & RED III")

# Sezione Istruzioni e Download Template
with st.expander("📖 ISTRUZIONI E PREPARAZIONE FILE (Leggi qui prima di iniziare)", expanded=True):
    st.markdown("""
    ### 1. Requisiti del File di Input
    Il file deve essere in formato **.xlsx (Excel)** o **.csv**. Per garantire il corretto funzionamento e la pulizia dei dati, scarica e compila il template qui sotto.
    """)
    
    # Tasto Download Template
    template_bin = generate_template()
    st.download_button(
        label="📥 Scarica il Template Excel (11 colonne)",
        data=template_bin,
        file_name="template_h2ready.xlsx",
        mime="application/vnd.ms-excel"
    )

    st.markdown("""
    ### 2. Struttura delle Colonne
    Il tool cerca esattamente queste intestazioni. **Nota:** Inserisci solo numeri puri nelle colonne con l'unità di misura!
    * **nome azienda** (Obbligatorio)
    * **Codice ateco** (Obbligatorio: formato 23.51 o 2351)
    * **dimensione** (Obbligatorio: Grande, Media o Piccola)
    * **ubicazione/consorzio**, **vicinanza South H2 corridor**, **AIA (si/no)** (Opzionale: scrivi 'SÌ' o 'Z.I.' per bonus)
    * **processo** e **note** (Opzionali ma **FONDAMENTALI** per applicare i criteri RED III. Ad esempio, specifica se un'acciaieria usa tecnologia *DRI* o *Altoforno*, oppure usa parole come *forno* o *metano* per identificare trattamenti termici minori).

    ### 3. Logica dello Score (Aggiornata)
    * **Tier 1 (Priorità Alta):** Settori con **Obblighi RED III** (Fertilizzanti, Metanolo, Siderurgia DRI) e settori a **Calore Estremo** (1000-1600°C, es. Vetro e Cemento).
    * **Tier 2 (Media):** Settori a **Calore Alto** (500-1000°C, es. Trattamenti termici metalli, forgiatura).
    * **Escluso:** Sottoprodotti esentati dalla direttiva RED III e settori a bassa temperatura (Alimentare, Legno) che possono essere facilmente elettrificati.
    """)

st.markdown("---")

# --- CARICAMENTO E DASHBOARD ---
uploaded_file = st.file_uploader("Carica il database compilato", type=["xlsx", "csv"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        # Normalizzazione nomi colonne per la logica interna
        df.columns = df.columns.str.strip().str.lower()
        
        # Calcoli
        df['score'] = df.apply(calculate_total_score, axis=1)
        df['tipo'] = df.apply(lambda r: get_base_score(r)[1], axis=1)
        # Soglie aggiornate: Il punteggio max base ora è 5*1.5 + 2 + 3 + 3 = 15.5
        df['tier'] = df['score'].apply(lambda s: "Tier 1 (Alta)" if s >= 8 else ("Tier 2 (Media)" if s > 0 else "Non Idoneo"))
        
        df_idonee = df[df['score'] > 0].sort_values(by='score', ascending=False)

        # KPI
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Analizzate", len(df))
        c2.metric("Idonee H2", len(df_idonee))
        c3.metric("Tier 1", len(df[df['score'] >= 8]))
        c4.metric("Non Idonee", len(df[df['score'] == 0]))

        # Galleria Risultati
        st.markdown("### 🏢 Analisi Dettagliata Aziende Selezionate")
        if not df_idonee.empty:
            cols_per_row = 3
            for i in range(0, len(df_idonee), cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < len(df_idonee):
                        row = df_idonee.iloc[i + j]
                        with cols[j]:
                            header = f" {row['nome azienda']}"
                            if "Tier 1" in row['tier']: st.success(f"### {header}")
                            else: st.warning(f"### {header}")
                            
                            st.write(f"🏆 **Score:** {row['score']} ({row['tier']})")
                            st.write(f"🏭 **Profilo:** {row['tipo']}")
                            st.write(f"⚙️ **ATECO:** {row.get('codice ateco', 'N/D')}")
                            
                            note_txt = str(row.get('note', '')).strip()
                            if note_txt.lower() != 'nan' and note_txt:
                                st.caption(f"📝 {note_txt}")
                            st.markdown("---")
        else:
            st.info("Nessuna azienda idonea trovata.")

        # Grafici
        col_a, col_b = st.columns(2)
        with col_a:
            st.plotly_chart(px.pie(df, names='tier', color='tier', title="Distribuzione Tier",
                                   color_discrete_map={'Tier 1 (Alta)':'#1B5E20', 'Tier 2 (Media)':'#F9A825', 'Non Idoneo':'#B71C1C'}), use_container_width=True)
        with col_b:
            if not df_idonee.empty:
                st.plotly_chart(px.bar(df_idonee.head(10).sort_values('score'), x='score', y='nome azienda', orientation='h', title="Top 10 Potenziali Off-takers"), use_container_width=True)

        # Tabella di controllo
        with st.expander("📂 Database Completo"):
            st.dataframe(df.sort_values(by='score', ascending=False), use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Errore: Assicurati che le colonne siano corrette. Dettaglio: {e}")
