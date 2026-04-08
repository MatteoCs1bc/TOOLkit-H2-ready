import streamlit as st
import pandas as pd
import plotly.express as px

# Configurazione Pagina
st.set_page_config(page_title="H2READY - Dashboard Scouting", layout="wide")

# --- LOGICA DI SCORING ---
def get_base_score(row):
    ateco = str(row.get('codice ateco', '')).replace('.', '').strip()
    prefix = ateco[:2]
    
    if prefix in ['24', '19', '20']: return 5, "HTA Priorità Assoluta"
    elif prefix == '23': return 4, "HTA Calore Estremo"
    
    testo_tecnico = (str(row.get('processo', '')) + " " + str(row.get('note', ''))).lower()
    parole_chiave = ['metano', 'mw', 'forno', 'fusione', 'calore', 'termico', 'ossidazione', 'verniciatura']
    if any(k in testo_tecnico for k in parole_chiave) and prefix in ['25', '26', '27', '28', '33']:
        return 3, "Recupero: Processo termico"
    
    if prefix in ['10', '11', '16', '17', '13', '14']: return 0, "Escluso (Bassa Temp)"
    return 0, "Non Idoneo"

def calculate_total_score(row):
    base, _ = get_base_score(row)
    if base == 0: return 0
    
    dim = str(row.get('dimensione', '')).strip().title()
    mult = 1.5 if dim == 'Grande' else (1.2 if dim == 'Media' else 1.0)
    score = base * mult
    
    if str(row.get('aia (si/no)', '')).lower() in ['sì', 'si']: score += 2
    if "z.i." in str(row.get('ubicazione/consorzio', '')).lower() or str(row.get('ubicazione/consorzio', '')).lower() in ['sì', 'si']: score += 3
    if str(row.get('vicinanza south h2 corridor', '')).lower() in ['sì', 'si']: score += 3
    return round(score, 1)

# --- INTERFACCIA DASHBOARD ---
st.title("🚀 H2READY Strategic Dashboard")
st.subheader("Mappatura delle Aziende Potenzialmente Idonee all'Idrogeno")

with st.expander("📚 Istruzioni per l'Excel", expanded=False):
    st.write("Il file deve contenere queste colonne (non importa se maiuscole o minuscole):")
    st.code("nome azienda, codice ateco, dimensione, ubicazione/consorzio, vicinanza south h2 corridor, aia (si/no), processo, note")

uploaded_file = st.file_uploader("Carica il database aziendale", type=["xlsx", "csv"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        df.columns = df.columns.str.strip().str.lower()
        
        # Elaborazione
        df['score'] = df.apply(calculate_total_score, axis=1)
        df['tipo'] = df.apply(lambda r: get_base_score(r)[1], axis=1)
        df['tier'] = df['score'].apply(lambda s: "Tier 1 (Priorità Alta)" if s >= 9 else ("Tier 2 (Media)" if s >= 5 else "Non Idoneo"))
        
        # Filtriamo solo le aziende idonee per la galleria
        df_idonee = df[df['score'] > 0].sort_values(by='score', ascending=False)

        # --- 1. KPI SECTION ---
        st.markdown("---")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Aziende Analizzate", len(df))
        c2.metric("Aziende Selezionate", len(df_idonee))
        c3.metric("Campioni Tier 1", len(df[df['score'] >= 9]))
        c4.metric("Escluse (Elettrificabili)", len(df[df['score'] == 0]))

        # --- 2. GALLERIA DELLE AZIENDE SELEZIONATE (CARDS) ---
        st.markdown("---")
        st.markdown("### 🏢 Dettaglio Aziende Potenzialmente Selezionate")
        st.write("Elenco completo delle aziende con profili termici o chimici compatibili, ordinate per punteggio strategico.")
        
        if not df_idonee.empty:
            # Creiamo un layout a griglia (3 colonne per riga)
            cols_per_row = 3
            for i in range(0, len(df_idonee), cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < len(df_idonee):
                        row = df_idonee.iloc[i + j]
                        with cols[j]:
                            # Scegliamo il colore del box in base al Tier
                            if "Tier 1" in row['tier']:
                                st.success(f"### {row['nome azienda']}")
                            else:
                                st.warning(f"### {row['nome azienda']}")
                            
                            st.write(f"🏆 **Score:** {row['score']} - {row['tier']}")
                            st.write(f"🏭 **Processo:** {row['tipo']}")
                            st.write(f"⚙️ **ATECO:** {row.get('codice ateco', 'N/D')} | **Dim:** {str(row.get('dimensione', 'N/D')).title()}")
                            
                            # Note tecniche (mostrate solo se presenti)
                            note_tecniche = str(row.get('note', '')).strip()
                            if note_tecniche and note_tecniche.lower() != 'nan':
                                st.caption(f"📝 **Note:** {note_tecniche}")
                            
                            st.markdown("---") # Separatore interno alla card
        else:
            st.info("Nessuna azienda idonea trovata con i parametri attuali.")

        # --- 3. VISUAL ANALYTICS ---
        st.markdown("---")
        st.markdown("### 📊 Analisi Grafica del Territorio")
        col_a, col_b = st.columns(2)
        
        with col_a:
            fig_pie = px.pie(df, names='tier', color='tier', 
                             color_discrete_map={'Tier 1 (Priorità Alta)':'#2E7D32', 'Tier 2 (Media)':'#FBC02D', 'Non Idoneo':'#D32F2F'})
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_b:
            if not df_idonee.empty:
                # Grafico a barre solo per le idonee
                fig_bar = px.bar(df_idonee.head(15).sort_values('score'), x='score', y='nome azienda', orientation='h',
                                 color='score', color_continuous_scale='Greens', title="Top 15 Aziende")
                st.plotly_chart(fig_bar, use_container_width=True)

        # --- 4. TABELLA COMPLETA ---
        st.markdown("---")
        with st.expander("📂 Sfoglia il Database Completo in formato Tabella"):
            st.dataframe(df.sort_values(by='score', ascending=False), use_container_width=True, hide_index=True)

        # Download Button
        st.download_button("📥 Esporta Report Finale CSV", df.sort_values(by='score', ascending=False).to_csv(index=False), "h2ready_report.csv", "text/csv")

    except Exception as e:
        st.error(f"Errore durante l'elaborazione del file. Dettagli: {e}")

else:
    st.info("In attesa del caricamento del file Excel o CSV per generare la dashboard...")
