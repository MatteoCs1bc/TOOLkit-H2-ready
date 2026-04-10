import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO

# Configurazione Pagina
st.set_page_config(page_title="H2READY - Scouting Tool (Efficienza Termodinamica)", layout="wide")

# --- DIZIONARIO ATECO ESTESO CON TEMPERATURE E SETTORI ---
ATECO_DESCRIPTIONS = {
    '1910': 'Prodotti della cokeria',
    '1920': 'Raffinazione di prodotti petroliferi (Feedstock)',
    '2011': 'Produzione di gas industriali - SMR',
    '2012': 'Produzione di coloranti e pigmenti',
    '2013': 'Chimica inorganica di base (Cloro-Soda)',
    '2014': 'Chimica organica di base (Metanolo/Cracking)',
    '2015': 'Fabbricazione di fertilizzanti (Ammoniaca)',
    '2016': 'Materie plastiche primarie',
    '2311': 'Fabbricazione di vetro piano (~1500°C)',
    '2313': 'Fabbricazione di vetro cavo (~1500°C)',
    '2320': 'Fabbricazione di prodotti refrattari',
    '2332': 'Fabbricazione di mattoni e tegole',
    '2351': 'Produzione di cemento',
    '2352': 'Produzione di calce e gesso',
    '2410': 'Produzione di ferro, acciaio (DRI / Altoforno)',
    '2431': 'Trafilatura a freddo',
    '2442': 'Produzione di alluminio e semilavorati',
    '2443': 'Produzione di rame e semilavorati',
    '2444': 'Produzione di altri metalli non ferrosi',
    '2451': 'Fusione di ghisa',
    '2452': 'Fusione di acciaio',
    '2453': 'Fusione di metalli leggeri',
    '2550': 'Fucinatura, stampaggio e profilatura metalli',
    '2561': 'Trattamento e rivestimento dei metalli',
    '2562': 'Lavorazioni meccaniche termiche',
    '3511': 'Produzione energia elettrica',
    '3530': 'Produzione di vapore industriale',
    '3821': 'Trattamento rifiuti (Incenerimento)',
    '3822': 'Trattamento rifiuti pericolosi',
    '3832': 'Recupero rottami metallici'
}

# --- LOGICA DI SCORING (Versione 6.0 - Neutralità Tecnologica & Termodinamica) ---
def get_base_score(row):
    ateco = str(row.get('codice ateco', '')).replace('.', '').strip()
    prefix = ateco[:2]
    testo_tecnico = (str(row.get('processo', '')) + " " + str(row.get('note', ''))).lower()
    
    # ---------------------------------------------------------
    # 1. SPRECO TERMODINAMICO E NON NECESSARI (Score 0)
    # ---------------------------------------------------------
    if prefix in ['35']: 
        return 0, "Produzione Energia/Vapore", "🔴 NON NECESSARIO: Spreco termodinamico. Elettrificare, usare pompe di calore o biomasse."
    if prefix in ['38']: 
        return 0, "Gestione Rifiuti", "🔴 NON NECESSARIO: Waste-to-Hydrogen possibile per produzione, ma spreco come consumo."
    if prefix in ['41', '42', '43'] or ateco.startswith('63'): 
        return 0, "Edilizia/Data Center", "🔴 NON NECESSARIO: Calore a bassa temp. / Elettricità pura. Elettrificazione diretta."
    if ateco.startswith('2011'): 
        return 0, "Produzione Gas (SMR)", "🔴 NON NECESSARIO COME INPUT: L'impianto inquina e va sostituito con elettrolisi."
    if ateco.startswith('2013') or ateco.startswith('1910'): 
        return 0, "Sottoprodotto Industriale", "🔴 NON NECESSARIO: Idrogeno di scarto (Cloro-soda/Cokeria), escluso da quote RED III."

    # ---------------------------------------------------------
    # 2. ASSOLUTAMENTE NECESSARIO (Feedstock / Agente Riducente)
    # ---------------------------------------------------------
    if ateco.startswith('2015') or ateco.startswith('2014') or ateco.startswith('1920'):
        # Filtro steam cracking per la 20.14
        if 'etilene' in testo_tecnico or 'plastica' in testo_tecnico:
            return 0, "Sottoprodotto Cracking", "🔴 NON NECESSARIO: H2 di scarto da Steam Cracking."
        return 5, "Chimica/Raffinazione (Feedstock)", "🟢 ASSOLUTAMENTE NECESSARIO: H2 richiesto chimicamente come materia prima. Obbligo RED III."
    
    if ateco.startswith('2410') and any(k in testo_tecnico for k in ['dri', 'riduzione diretta']):
        return 5, "Siderurgia (Ciclo DRI)", "🟢 ASSOLUTAMENTE NECESSARIO: H2 insostituibile come agente riducente per il minerale di ferro."

    # ---------------------------------------------------------
    # 3. NECESSARIO PER LIMITI FISICI (Calore Estremo)
    # ---------------------------------------------------------
    if ateco.startswith('2311') or ateco.startswith('2313'):
        return 4.5, "Fusione Vetro (Grandi Impianti)", "🟢 NECESSARIO: Difficile elettrificare forni fusori >80t/g per limiti fisici degli elettrodi."

    # ---------------------------------------------------------
    # 4. OPZIONALE / COMPETIZIONE (Calcinazione)
    # ---------------------------------------------------------
    if ateco in ['2351', '2352', '2320', '2332']:
        return 3, "Calcinazione (Cemento/Ceramica/Calce)", "🟡 OPZIONALE: Elevata competizione economica con Biometano e CSS (Combustibili Solidi Secondari)."

    # ---------------------------------------------------------
    # 5. ALERT ELETTRIFICAZIONE (Trattamenti Termici)
    # ---------------------------------------------------------
    trattamenti = ['2431', '2550', '2561', '2562']
    if any(ateco.startswith(c) for c in trattamenti):
        return 2, "Trattamenti Termici e Deformazione", "🟠 ALERT ELETTRIFICAZIONE: Valutare forni a induzione elettrica. H2 giustificato solo per tempra/atmosfera chimica."

    # Siderurgia e metalli generica (Alto calore, no DRI specificato)
    if prefix == '24':
        return 3.5, "Metallurgia / Fusione secondaria", "🟡 OPZIONALE: Valutare Forni Elettrici ad Arco (EAF) prima dell'Idrogeno."

    # Recupero Keyword per aziende borderline
    parole_chiave = ['metano', 'mw', 'forno', 'fusione', 'calore', 'termico', 'ossidazione', 'fiamme']
    if any(k in testo_tecnico for k in parole_chiave) and prefix in ['25', '26', '27', '28', '33']:
        return 1.5, "Processo termico generico", "🟠 ALERT ELETTRIFICAZIONE: Processo borderline, prioritizzare elettrificazione termica."

    return 0, "Non Classificato / Non Idoneo", "🔴 NON NECESSARIO: Processo assente o a bassa temperatura (elettrificabile)."

def calculate_total_score(row):
    base, _, _ = get_base_score(row) # Ora spacchetta 3 valori
    if base == 0: return 0
    
    dim = str(row.get('dimensione', '')).strip().title()
    mult = 1.5 if dim == 'Grande' else (1.2 if dim == 'Media' else 1.0)
    score = base * mult
    
    if str(row.get('aia (si/no)', '')).lower() in ['sì', 'si', 'yes', 'y']: score += 2
    if "z.i." in str(row.get('ubicazione/consorzio', '')).lower() or str(row.get('ubicazione/consorzio', '')).lower() in ['sì', 'si', 'yes']: score += 3
    if str(row.get('vicinanza south h2 corridor', '')).lower() in ['sì', 'si', 'yes', 'y']: score += 3
    
    return round(score, 1)

# --- GENERATORE DI TEMPLATE EXCEL ---
def generate_template():
    output = BytesIO()
    cols = [
        "nome azienda", "Codice ateco", "dimensione", "fatturato [M€]", 
        "dipendenti", "ubicazione/consorzio", "vicinanza South H2 corridor", 
        "AIA (si/no)", "consumo energia stimato [MWh]", "processo", "note"
    ]
    # Dati di esempio progettati per testare i vari verdetti termodinamici
    example_data = [
        ["Fertilizzanti FVG S.p.A.", "20.15", "Grande", 250, 600, "Z.I. Aussa Corno", "SÌ", "SÌ", 150000, "Sintesi Ammoniaca", "Target RED III"],
        ["Vetreria Nord S.r.l.", "23.13", "Grande", 80, 150, "SÌ", "NO", "SÌ", 45000, "Forni fusori", ">100t/giorno"],
        ["Cementi Rossi", "23.51", "Grande", 120, 200, "NO", "SÌ", "SÌ", 80000, "Calcinazione", "Uso attuale CSS e Petcoke"],
        ["Forgiatura Meccanica", "25.50", "Media", 15, 40, "Z.I. Maniago", "NO", "NO", 5000, "Riscaldo billette", "Forni a gas naturale"],
        ["Cartiere del Friuli", "35.30", "Grande", 60, 100, "SÌ", "NO", "SÌ", 25000, "Produzione vapore", "Caldaia a metano"],
    ]
    df_temp = pd.DataFrame(example_data, columns=cols)
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_temp.to_excel(writer, index=False, sheet_name='Template')
    return output.getvalue()

# --- INTERFACCIA ---
st.title("🚀 H2READY Scouting Tool - Filtro Termodinamico & RED III")

with st.expander("📖 METODOLOGIA: LA NEUTRALITÀ TECNOLOGICA (Leggi prima di iniziare)", expanded=True):
    st.markdown("""
    Questo tool non premia il semplice "uso di alte temperature", ma valuta la **necessità chimica e termodinamica** dell'idrogeno rispetto all'elettrificazione.
    
    ### I Verdetti del Tool:
    * 🟢 **Assolutamente Necessario:** L'idrogeno è materia prima (Fertilizzanti, Metanolo, Raffinazione) o Agente Riducente (Siderurgia DRI). Nessuna alternativa possibile.
    * 🟢 **Necessario (Limiti Fisici):** Grandi forni fusori (Vetro) dove la densità di energia impedisce l'elettrificazione massiva.
    * 🟡 **Opzionale / Competizione:** Settori (Cemento, Calce) dove l'idrogeno compete a svantaggio economico con Biometano e CSS (Rifiuti).
    * 🟠 **Alert Elettrificazione:** Trattamenti termici (Tempra, Fucinatura) dove tecnologie come l'**induzione elettrica** sono oggi più efficienti ed economiche dell'H2.
    * 🔴 **Spreco Termodinamico (Non Idonei):** Produzione di vapore, energia di rete, edilizia o data center. Bruciare idrogeno qui è uno spreco; si usa l'elettrificazione diretta o pompe di calore.
    """)
    
    template_bin = generate_template()
    st.download_button(
        label="📥 Scarica il Template Excel di Test",
        data=template_bin, file_name="template_h2ready.xlsx", mime="application/vnd.ms-excel"
    )

st.markdown("---")

# --- CARICAMENTO E DASHBOARD ---
uploaded_file = st.file_uploader("Carica il database compilato (.xlsx o .csv)", type=["xlsx", "csv"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df.columns = df.columns.str.strip().str.lower()
        
        # Estrazione dei 3 valori (Base Score, Profilo, Verdetto Termodinamico)
        results = df.apply(lambda r: get_base_score(r), axis=1)
        df['base_score'] = [res[0] for res in results]
        df['profilo'] = [res[1] for res in results]
        df['verdetto'] = [res[2] for res in results]
        
        df['score'] = df.apply(calculate_total_score, axis=1)
        df['tier'] = df['score'].apply(lambda s: "Tier 1 (Alta Priorità)" if s >= 7 else ("Tier 2 (Media/Alert)" if s > 0 else "Non Idoneo"))
        
        df_idonee = df[df['score'] > 0].sort_values(by='score', ascending=False)

        # KPI
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Aziende Analizzate", len(df))
        c2.metric("Semaforo Verde (Tier 1)", len(df[df['score'] >= 7]))
        c3.metric("Alert Elettrificazione (Tier 2)", len(df[(df['score'] > 0) & (df['score'] < 7)]))
        c4.metric("Spreco Termodinamico (Scartate)", len(df[df['score'] == 0]))

        st.markdown("### 🏢 Cruscotto Aziendale - Analisi Termodinamica")
        if not df_idonee.empty:
            cols_per_row = 2 # Ridotto a 2 colonne per far spazio ai testi più lunghi
            for i in range(0, len(df_idonee), cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < len(df_idonee):
                        row = df_idonee.iloc[i + j]
                        with cols[j]:
                            # Intestazione Visiva
                            if "Tier 1" in row['tier']: 
                                st.success(f"### 🏭 {row['nome azienda']}")
                            else: 
                                st.warning(f"### 🏭 {row['nome azienda']}")
                            
                            st.write(f"🏆 **Score Complessivo:** {row['score']} / 15")
                            st.write(f"📏 **Dimensione Aziendale:** {str(row.get('dimensione', 'N/D')).title()}")
                            
                            # Recupero Dizionario ATECO
                            codice_originale = str(row.get('codice ateco', 'N/D'))
                            codice_pulito = codice_originale.replace('.', '').strip()[:4]
                            descrizione_estesa = ATECO_DESCRIPTIONS.get(codice_pulito, "Descrizione non disponibile")
                            st.write(f"⚙️ **ATECO {codice_originale}:** *{descrizione_estesa}*")
                            
                            # --- IL NUOVO VERDETTO TERMODINAMICO ---
                            st.markdown(f"**💡 Verdetto Termodinamico:**")
                            # Usa un box colorato in base all'emoji del verdetto
                            verdetto_txt = row['verdetto']
                            if '🟢' in verdetto_txt: st.info(verdetto_txt)
                            elif '🟡' in verdetto_txt: st.warning(verdetto_txt)
                            elif '🟠' in verdetto_txt: st.error(verdetto_txt) # Uso rosso/error per l'alert forte
                            
                            note_txt = str(row.get('note', '')).strip()
                            if note_txt.lower() != 'nan' and note_txt:
                                st.caption(f"📝 Note: {note_txt}")
                            st.markdown("---")
        else:
            st.info("Nessuna azienda idonea. Tutti i processi analizzati risultano più adatti all'elettrificazione diretta.")

        with st.expander("📂 Esplora il Database Completo (Inclusi gli scartati)"):
            st.dataframe(df[['nome azienda', 'codice ateco', 'score', 'tier', 'profilo', 'verdetto']].sort_values(by='score', ascending=False), use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Errore: Assicurati che le colonne siano corrette. Dettaglio tecnico: {e}")
