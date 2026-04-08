import streamlit as st
import pandas as pd
import plotly.express as px

# Configurazione Pagina
st.set_page_config(page_title="H2READY - Dashboard Scouting", layout="wide")

# --- LOGICA DI SCORING (Invariata ma robusta) ---
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
    mult = 1.5 if str(row.get('dimensione', '')).title() == 'Grande' else (1.2 if str(row.get('dimensione', '')).title() == 'Media' else 1.0)
    score = base * mult
    if str(row.get('aia (si/no)', '')).lower() in ['sì', 'si']: score += 2
    if "z.i." in str(row.get('ubicazione/consorzio', '')).lower() or str(row.get('ubicazione/consorzio', '')).lower() in ['sì', 'si']: score += 3
    if str(row.get('vicinanza south h2 corridor', '')).lower() in ['sì', 'si']: score += 3
    return round(score, 1)

# --- INTERFACCIA DASHBOARD ---
st.title("🚀 H2READY Strategic Dashboard")
st.subheader("Identificazione dei Campioni della Transizione Energetica")

uploaded_file = st.file_uploader("Carica il database aziendale", type=["xlsx", "csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    df.columns = df.columns.str.strip().str.lower()
    
    # Elaborazione
    df['score'] = df.apply(calculate_total_score, axis=1)
    df['tipo'] = df.apply(lambda r: get_base_score(r)[1], axis=1)
    df['tier'] = df['score'].apply(lambda s: "Tier 1" if s >= 9 else ("Tier 2" if s >= 5 else "Non Idoneo"))
    df_winners = df[df['tier'] == "Tier 1"].sort_values(by='score', ascending=False)

    # --- 1. KPI SECTION ---
    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Aziende Analizzate", len(df))
    c2.metric("Campioni (Tier 1)", len(df_winners))
    c3.metric("Potenziale Medio", f"{df[df['score']>0]['score'].mean():.1f} pts")
    c4.metric("Settori HTA", len(df[df['score'] > 0]))

    # --- 2. THE WINNERS PODIUM (Cards) ---
    st.markdown("### 🏆 Il Podio delle Aziende Vincitrici")
    if not df_winners.empty:
        # Mostriamo le top 3 o 4 aziende come card grafiche
        cols = st.columns(len(df_winners[:4]))
        for i, (idx, row) in enumerate(df_winners[:4].iterrows()):
            with cols[i]:
                st.info(f"**{row['nome azienda']}**")
                st.write(f"⭐ Score: **{row['score']}**")
                st.caption(f"📍 {row.get('ubicazione/consorzio', 'N/D')}")
                st.write(f"🏭 {row['tipo']}")
    else:
        st.warning("Nessuna azienda ha raggiunto il Tier 1 con i dati attuali.")

    # --- 3. VISUAL ANALYTICS ---
    st.markdown("---")
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("#### Distribuzione delle Fasce (Tier)")
        fig_pie = px.pie(df, names='tier', color='tier', 
                         color_discrete_map={'Tier 1':'#2E7D32', 'Tier 2':'#FBC02D', 'Non Idoneo':'#D32F2F'})
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_b:
        st.markdown("#### Top 10 per Punteggio Strategico")
        fig_bar = px.bar(df.sort_values('score').tail(10), x='score', y='nome azienda', orientation='h',
                         color='score', color_continuous_scale='Greens')
        st.plotly_chart(fig_bar, use_container_width=True)

    # --- 4. DETAILED TABLE (At the bottom) ---
    st.markdown("---")
    with st.expander("📂 Sfoglia il Database Completo e Analisi Tecnica"):
        st.write("Usa i filtri sopra le colonne per ordinare i dati.")
        
        # Colorazione per la tabella
        def color_tier(val):
            color = '#d4edda' if val == 'Tier 1' else ('#fff3cd' if val == 'Tier 2' else '#f8d7da')
            return f'background-color: {color}'

        st.dataframe(df.sort_values(by='score', ascending=False), use_container_width=True, hide_index=True)

    # Download Button
    st.download_button("📥 Esporta Report Finale", df.to_csv(index=False), "h2ready_report.csv", "text/csv")

else:
    st.warning("In attesa del caricamento del file per generare la dashboard...")
