import streamlit as st
import pandas as pd
import numpy as np
import os # Necessario per controllare se il file esiste

# ... (Il resto delle tue funzioni: get_ateco_score, calculate_score, assign_tier rimangono IDENTICHE a prima) ...

# --- INTERFACCIA STREAMLIT ---
st.title("🔍 H2READY: Tool di Scouting Industriale (A.1)")
st.markdown("**Parola d'ordine: IDROGENO SOLO DOVE ALTRIMENTI NON ELETTRIFICABILE!**")

# --- SEZIONE ESPANDIBILE CON LETTURA DA FILE ESTERNO ---
with st.expander("📚 Guida all'Utilizzo: Scopri come funziona l'algoritmo e come preparare i dati", expanded=False):
    # Prova a leggere il file Markdown esterno
    file_guida = "guida.md"
    if os.path.exists(file_guida):
        with open(file_guida, 'r', encoding='utf-8') as f:
            testo_guida = f.read()
        st.markdown(testo_guida)
    else:
        st.warning("Il file della guida ('guida.md') non è stato trovato nella directory.")

    # Aggiungo la tabella riassuntiva sotto il testo letto dal file
    st.table({
        "Nome Colonna (Esatto)": ["Nome Azienda", "Codice ATECO", "Dimensione", "Fatturato (€)", "# Dipendenti", "Ubicazione/Consorzio", "Vicinanza South H2 Corridor"],
        "Tipo di Dato": ["Testo", "Testo / Numero", "Testo (Grande/Media/Piccola)", "Numero", "Numero", "Testo (SÌ/NO)", "Testo (SÌ/NO)"],
        "Obbligatorio": ["SÌ", "SÌ", "SÌ", "NO", "NO", "NO", "NO"],
        "Esempio Compilazione": ["Acciaierie Friulane S.p.A.", "24.10 oppure 24", "Grande", "50000000", "250", "SÌ", "NO"]
    })
    st.caption("*Suggerimento: Scarica l'elenco delle aziende dal registro camerale (o dal Consorzio locale) e rinomina le colonne affinché corrispondano esattamente alla tabella qui sopra prima di caricare il file.*")

# --- SEZIONE DI CARICAMENTO FILE ---
st.info("Carica il database aziendale. Colonne minime richieste: Nome Azienda, Codice ATECO, Dimensione.")

# ... (Il resto del codice per il caricamento file rimane identico a prima) ...
