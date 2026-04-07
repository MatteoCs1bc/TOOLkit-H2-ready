import streamlit as st
import pandas as pd

# Mappatura Pesi ATECO basata su H2READY (Calore > 400°C)
ateco_weights = {
    '24': 10,  # Metallurgia (HTA Certo)
    '23': 10,  # Vetro, Cemento, Ceramica (HTA Certo)
    '20': 6,   # Chimica (HTA Probabile)
    '17': 6,   # Carta (HTA Probabile)
    '10': 3,   # Alimentare (HTA Possibile - Processi termici)
    '16': 2    # Legno (Bassa probabilità, ma possibile sinergia)
}

def calculate_h2_readiness(row):
    score = 0
    # 1. Peso Settore (ATECO)
    ateco_prefix = str(row['Codice ATECO'])[:2]
    score += ateco_weights.get(ateco_prefix, 0)
    
    # 2. Peso Dimensione
    dim_multipliers = {'Grande': 1.5, 'Media': 1.2, 'Piccola': 1.0}
    score *= dim_multipliers.get(row['Dimensione'], 1.0)
    
    # 3. Bonus Consorzio
    if row['Ubicazione/Consorzio'].upper() == 'SÌ':
        score += 5
        
    # 4. Bonus South H2 Corridor (Peso Strategico)
    if row['Vicinanza South H2 Corridor'].upper() == 'SÌ':
        score += 3
        
    return score

st.title("H2READY: Scouting Industriale Strategico")
uploaded_file = st.file_uploader("Carica l'Excel delle aziende locali", type="xlsx")

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df['Scoring Strategico'] = df.apply(calculate_h2_readiness, axis=1)
    
    # Classificazione Tier
    df['Priorità Contatto'] = df['Scoring Strategico'].apply(
        lambda x: 'Tier 1 (Alto)' if x >= 15 else ('Tier 2 (Medio)' if x >= 8 else 'Tier 3 (Monitoraggio)')
    )
    
    st.write("### Risultati dello Scouting")
    st.dataframe(df.sort_values(by='Scoring Strategico', ascending=False))
