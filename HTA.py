import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO

# Configurazione Pagina
st.set_page_config(page_title="H2READY - Scouting Tool", layout="wide")

# --- DIZIONARIO ATECO ESTESO CON TEMPERATURE ---
# Mappatura dei codici a 4 cifre basata sui 5 Cluster HTA
ATECO_DESCRIPTIONS = {
    '1910': 'Prodotti della cokeria (1000–1100°C)',
    '1920': 'Raffinazione di prodotti petroliferi (500–900°C)',
    '2011': 'Produzione di gas industriali - SMR (700–900°C)',
    '2012': 'Produzione di coloranti e pigmenti (600–1000°C)',
    '2013': 'Chimica inorganica di base (500–900°C)',
    '2014': 'Chimica organica di base - Cracking (700–1100°C)',
    '2015': 'Fabbricazione di fertilizzanti e composti azotati (700–900°C)',
    '2016': 'Materie plastiche primarie (700–1100°C)',
    '2311': 'Fabbricazione di vetro piano (~1500°C)',
    '2313': 'Fabbricazione di vetro cavo (~1500°C)',
    '2320': 'Fabbricazione di prodotti refrattari (1200–1600°C)',
    '2332': 'Fabbricazione di mattoni e tegole (900–1200°C)',
    '2351': 'Produzione di cemento (1400–1500°C)',
    '2352': 'Produzione di calce e gesso (900–1200°C)',
    '2410': 'Produzione di ferro, acciaio e ferroleghe (1200–1600°C)',
    '2431': 'Trafilatura a freddo (600–1000°C)',
    '2442': 'Produzione di alluminio e semilavorati (660–750°C)',
    '2443': 'Produzione di rame e semilavorati (1000–1200°C)',
    '2444': 'Produzione di altri metalli non ferrosi (400–1200°C)',
    '2451': 'Fusione di ghisa (1200–1400°C)',
    '2452': 'Fusione di acciaio (1400–1600°C)',
    '2453': 'Fusione di metalli leggeri (650–1650°C)',
    '2550': 'Fucinatura, stampaggio e profilatura metalli (900–1200°C)',
    '2561': 'Trattamento e rivestimento dei metalli (500–1100°C)',
    '2562': 'Lavorazioni meccaniche termiche (500–900°C)',
    '3511': 'Produzione energia elettrica da fonti fossili (600–1200°C)',
    '3530': 'Produzione di vapore industriale (500–900°C)',
    '3821': 'Trattamento rifiuti non pericolosi - Incenerimento (850–1100°C)',
    '3822': 'Trattamento rifiuti pericolosi - Incenerimento (1000–1200°C)',
    '3832': 'Recupero rottami metallici (600–1500°C)'
}

# --- LOGICA DI SCORING (Versione 5.0 - RED III & Cluster Termici Avanzati) ---
def get_base_score(row):
    ateco = str(row.get('codice ateco', '')).replace('.', '').strip()
    prefix = ateco[:2]
    testo_tecnico = (str(row.get('processo', '')) + " " + str(row.get('note', ''))).lower()
    
    # ---------------------------------------------------------
    # 1. VERIFICA ESCLUSIONI RED III (Sottoprodotti e Scarti)
    # ---------------------------------------------------------
    if ateco.startswith('2013'): return 0, "Escluso RED III (Sottoprodotto Cloro-Soda)"
    if ateco.startswith('1910'): return 0, "Escluso RED III (Gas di cokeria)"
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
    if ateco.startswith('2011'): return 5, "HTA Priorità Assoluta: Obbligo RED III (Produzione Gas SMR)"
    if ateco.startswith('2014') and 'metanolo' in testo_tecnico: return 5, "HTA Priorità Assoluta: Obbligo RED III (Metanolo)"
    if ateco.startswith('2410') and any(k in testo_tecnico for k in ['dri', 'riduzione diretta']): return 5, "HTA Priorità Assoluta: Obbligo RED III (Siderurgia DRI)"
    
    if ateco.startswith('2410'): return 5, "HTA Siderurgia / Metalli Pesanti (Score Cautelativo)" 
    if ateco.startswith('2014'): return 4, "HTA Chimica di base (Potenziale RED III)"

    # ---------------------------------------------------------
    # 3. I 5 CLUSTER DI TEMPERATURA 
    # ---------------------------------------------------------
    cluster_1 = ['2311', '2313', '2320', '2332', '2351', '2352', '2410', '2442', '2443', '2444', '2451', '2452', '2453']
    if any(ateco.startswith(c) for c in cluster_1): return 4, "Cluster 1: Fusione e Calcinazione (>1000°C)"
        
    cluster_2 = ['1910', '1920', '2011', '2012', '2013', '2014', '2015', '2016']
    if any(ateco.startswith(c) for c in cluster_2): return 4, "Cluster 2: Reazioni Chimiche e Cracking (500-1100°C)"

    cluster_5 = ['3821', '3822', '3832']
    if any(ateco.startswith(c) for c in cluster_5): return 4, "Cluster 5: Gestione Rifiuti e Incenerimento (850-1500°C)"

    cluster_3 = ['2431', '2550', '2561', '2562']
    if any(ateco.startswith(c) for c in cluster_3): return 3, "Cluster 3: Trattamenti Termici e Deformazione (500-1200°C)"

    cluster_4 = ['3511', '3530']
    if any(ateco.startswith(c) for c in cluster_4): return 3, "Cluster 4: Produzione Energia e Vapore (500-1200°C)"

    # ---------------------------------------------------------
    # 4. RECUPERO PAROLE CHIAVE 
    # ---------------------------------------------------------
    parole_chiave = ['metano', 'mw', 'forno', 'fusione', 'calore', 'termico', 'ossidazione', 'verniciatura', 'fiamme', 'incenerimento']
    if any(k in testo_tecnico for k in parole_chiave) and prefix in ['25', '26', '27', '28', '33']:
        return 2, "Recupero: Processo termico dichiarato (Potenzialmente HTA)"
        
    # ---------------------------------------------------------
    # 5. ESCLUSI PER BASSA TEMPERATURA 
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
    
    # Bonus Strategici 
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
    example_data = [
        ["Fertilizzanti FVG S.p.A.", "20.15", "Grande", 250, 600, "Z.I. Aussa Corno", "SÌ", "SÌ", 150000, "Sintesi Ammoniaca", "Target RED III"],
        ["Vetreria Nord S.r.l.", "23.13", "Media", 12, 80, "SÌ", "NO", "SÌ", 15000, "Forni fusori", "Cluster 1"],
        ["Acciaierie Alfa", "24.10", "Grande", 500, 1200, "Z.I. Trieste", "SÌ", "SÌ", 300000, "Altoforno", "Escluso per gas residuo"],
        ["Eco-Inceneritori", "38.21", "Media", 40, 100, "Z.I. Spilimbergo", "NO", "SÌ", 45000, "Termovalorizzazione", "Cluster 5"],
    ]
    df_temp = pd.DataFrame(example_data, columns=cols)
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_temp.to_excel(writer, index=False, sheet_name='Template')
    return output.getvalue()

# --- INTERFACCIA ---
st.title("🚀 H2READY Strategic Scouting Tool - Modulo HTA & RED III")

with st.expander("📖 ISTRUZIONI E PREPARAZIONE FILE", expanded=True):
    st.markdown("""
    ### 1. Requisiti del File di Input
    Il file deve essere in formato **.xlsx (Excel)** o **.csv**. 
    """)
    template_bin = generate_template()
    st.download_button(
        label="📥 Scarica il Template Excel",
        data=template_bin,
        file_name="template_h2ready.xlsx",
        mime="application/vnd.ms-excel"
    )

    st.markdown("""
    ### 2. Struttura delle Colonne
    Il tool cerca esattamente queste intestazioni:
    * **nome azienda** | **Codice ateco** | **dimensione** (Grande/Media/Piccola)
    * **ubicazione/consorzio** | **vicinanza South H2 corridor** | **AIA (si/no)** * **processo** e **note** (Fondamentali per identificare forni, metano o eccezioni RED III).
    """)

st.markdown("---")

# --- CARICAMENTO E DASHBOARD ---
uploaded_file = st.file_uploader("Carica il database compilato", type=["xlsx", "csv"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df.columns = df.columns.str.strip().str.lower()
        
        df['score'] = df.apply(calculate_total_score, axis=1)
        df['tipo'] = df.apply(lambda r: get_base_score(r)[1], axis=1)
        df['tier'] = df['score'].apply(lambda s: "Tier 1 (Alta)" if s >= 8 else ("Tier 2 (Media)" if s > 0 else "Non Idoneo"))
        
        df_idonee = df[df['score'] > 0].sort_values(by='score', ascending=False)

        # KPI
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Analizzate", len(df))
        c2.metric("Idonee H2", len(df_idonee))
        c3.metric("Tier 1", len(df[df['score'] >= 8]))
        c4.metric("Non Idonee", len(df[df['score'] == 0]))

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
                            st.write(f"📏 **Dimensione:** {str(row.get('dimensione', 'N/D')).title()}") # <--- AGGIUNTO QUI!
                            st.write(f"🏭 **Profilo:** {row['tipo']}")
                            
                            # --- RECUPERO DESCRIZIONE ATECO E TEMPERATURE ---
                            codice_originale = str(row.get('codice ateco', 'N/D'))
                            codice_pulito = codice_originale.replace('.', '').strip()[:4]
                            descrizione_estesa = ATECO_DESCRIPTIONS.get(codice_pulito, "Descrizione non disponibile")
                            
                            st.write(f"⚙️ **ATECO {codice_originale}:** *{descrizione_estesa}*")
                            
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

        with st.expander("📂 Database Completo"):
            st.dataframe(df.sort_values(by='score', ascending=False), use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Errore: Assicurati che le colonne siano corrette. Dettaglio: {e}")
