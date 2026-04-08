import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO

# Configurazione Pagina
st.set_page_config(page_title="H2READY - Scouting Tool", layout="wide")

# --- LOGICA DI SCORING (Versione 3.0) ---
def get_base_score(row):
    ateco = str(row.get('codice ateco', '')).replace('.', '').strip()
    prefix = ateco[:2]
    
    # Check 1: Settori HTA Certi
    if prefix in ['24', '19', '20']: return 5, "HTA Priorità Assoluta (RED III / Siderurgia)"
    elif prefix == '23': return 4, "HTA Calore Estremo (Vetro/Cemento)"
    
    # Check 2: Recupero tramite parole chiave (Logica per aziende borderline)
    testo_tecnico = (str(row.get('processo', '')) + " " + str(row.get('note', ''))).lower()
    parole_chiave = ['metano', 'mw', 'forno', 'fusione', 'calore', 'termico', 'ossidazione', 'verniciatura', 'fiamme']
    
    if any(k in testo_tecnico for k in parole_chiave) and prefix in ['25', '26', '27', '28', '33']:
        return 3, "Recupero: Processo termico dichiarato"
    
    # Check 3: Esclusi (Alimentare, Legno, Carta)
    if prefix in ['10', '11', '16', '17', '13', '14']: return 0, "Escluso (Elettrificabile)"
    
    return 0, "Non Classificato / Non Idoneo"

def calculate_total_score(row):
    base, _ = get_base_score(row)
    if base == 0: return 0
    
    dim = str(row.get('dimensione', '')).strip().title()
    mult = 1.5 if dim == 'Grande' else (1.2 if dim == 'Media' else 1.0)
    score = base * mult
    
    # Bonus Strategici
    if str(row.get('aia (si/no)', '')).lower() in ['sì', 'si']: score += 2
    if "z.i." in str(row.get('ubicazione/consorzio', '')).lower() or str(row.get('ubicazione/consorzio', '')).lower() in ['sì', 'si']: score += 3
    if str(row.get('vicinanza south h2 corridor', '')).lower() in ['sì', 'si']: score += 3
    
    return round(score, 1)

# --- GENERATORE DI TEMPLATE EXCEL ---
def generate_template():
    output = BytesIO()
    # Definiamo le 11 colonne esatte CON LE UNITA' DI MISURA
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
    # Dati di esempio (ora i valori di fatturato ed energia sono numeri puri)
    example_data = [
        ["Acciaierie Esempio S.p.A.", "24.10", "Grande", 150, 400, "SÌ", "SÌ", "SÌ", 50000, "Fusione metalli", "Esempio HTA"],
        ["Vetreria Nord S.r.l.", "23.13", "Media", 12, 80, "SÌ", "NO", "SÌ", 15000, "Forni fusori", ""],
        ["Anoxidall S.r.l.", "26.01.30", "Piccola", None, 56, "Z.I. Ponte Rosso", "NO", "Sì", None, "Ossidazione", "Forni a metano 1.9 MW"]
    ]
    df_temp = pd.DataFrame(example_data, columns=cols)
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_temp.to_excel(writer, index=False, sheet_name='Template')
    return output.getvalue()

# --- INTERFACCIA ---
st.title("🚀 H2READY Strategic Scouting Tool")

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
    * **fatturato [M€]** (Opzionale: es. scrivi 12 per 12 milioni di euro)
    * **dipendenti** (Opzionale: numero intero)
    * **ubicazione/consorzio** (Opzionale: scrivi 'SÌ' o 'Z.I.' per bonus)
    * **vicinanza South H2 corridor** (Opzionale: scrivi 'SÌ' per bonus)
    * **AIA (si/no)** (Opzionale: scrivi 'SÌ' per bonus)
    * **consumo energia stimato [MWh]** (Opzionale: numero intero)
    * **processo** e **note** (Opzionali ma fondamentali per recuperare aziende borderline tramite parole chiave come *forno*, *metano*, *MW*).

    ### 3. Logica dello Score
    * **Tier 1 (Priorità Alta):** Aziende HTA con grandi consumi o obblighi RED III.
    * **Tier 2 (Media):** Aziende con processi termici dichiarati ma dimensioni o settori meno critici.
    * **Escluso:** Settori che utilizzano calore a bassa temperatura (<400°C) elettrificabile.
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
        df['tier'] = df['score'].apply(lambda s: "Tier 1 (Alta)" if s >= 9 else ("Tier 2 (Media)" if s >= 5 else "Non Idoneo"))
        
        df_idonee = df[df['score'] > 0].sort_values(by='score', ascending=False)

        # KPI
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Analizzate", len(df))
        c2.metric("Idonee H2", len(df_idonee))
        c3.metric("Tier 1", len(df[df['score'] >= 9]))
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
