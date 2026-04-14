# 📘 Metodologia e Assunzioni del Modello H2READY

Questo simulatore utilizza un approccio di **Ingegneria Inversa (Reverse Engineering)** per trasformare un obiettivo di decarbonizzazione in un progetto infrastrutturale dimensionato.

### 1. Logica di Produzione Energetica (8760h)
L'energia non viene calcolata su medie mensili, ma su una simulazione oraria per un intero anno solare.
* **Profili Climatici:** Utilizziamo database storici (PVGIS/Renewables.ninja) pesati geograficamente per riflettere la resa reale del Nord o del Sud Italia.
* **Mix Tecnologico:** Il sistema permette di bilanciare Fotovoltaico (picco diurno) ed Eolico (spesso più costante o notturno). L'integrazione delle due fonti serve a massimizzare il **Capacity Factor** dell'elettrolizzatore, riducendo i tempi di fermo macchina.
* **Priorità di Carico:** L'energia prodotta alimenta prima l'elettrolizzatore; l'eccedenza carica le batterie (BESS); se la batteria è carica e l'elettrolizzatore è al massimo, l'energia viene persa (*Curtailment*).

### 2. Struttura Finanziaria: Il Modello PPA/CfD
Il tool assume che l'idrogeno sia prodotto tramite un accordo **On-Site PPA** (Power Purchase Agreement):
* **Senza CAPEX FER:** Non stiamo acquistando i pannelli o le turbine. Assumiamo che un investitore terzo costruisca l'impianto FER e ci venda l'energia.
* **Prezzo CfD (Strike Price):** Il cursore €/MWh rappresenta il prezzo fisso negoziato. Questo protegge il progetto dalle fluttuazioni del mercato elettrico (PUN), garantendo un costo dell'idrogeno (LCOH) stabile per 20 anni.

### 3. Compressione e Stoccaggio: La distinzione tra Massa e Potenza
Il modello separa rigorosamente queste due componenti critiche:
* **Lo Stoccaggio (Massa):** Si dimensiona in base ai **kg** che vogliamo tenere di scorta (buffer). Il CAPEX dipende dai materiali dei serbatoi (Tipo I-IV) necessari per resistere alla pressione.
* **La Compressione (Potenza):** Si dimensiona in base alla spinta necessaria. Questo comporta un **OPEX energetico** (kWh consumati per ogni kg compresso) che viene aggiunto al consumo dell'elettrolizzatore, costringendo il sistema a sovradimensionare le fonti rinnovabili.

### 4. Assunzioni Economiche di Base
* **Vita Utile:** 20 anni.
* **WACC (Costo del Capitale):** 5% (parametro standard per progetti infrastrutturali).
* **O&M (Manutenzione):** Calcolata come il 3% annuo del CAPEX totale (include sostituzione membrane elettrolizzatore, manutenzione compressori e revamping BESS).
* **Efficienza Elettrolisi:** 55 kWh per kg di H2 prodotto (tecnologia PEM/Alcalina standard).

### 5. Allacciamento Rete (e-distribuzione 2025)
Il costo di connessione segue la normativa italiana vigente:
* **Sotto i 6 MW:** Connessione in Media Tensione (MT).
* **Sopra i 6 MW:** Obbligo di connessione in Alta Tensione (AT) con stallo dedicato in Cabina Primaria, con un salto di costo significativo dovuto alla complessità delle apparecchiature AT.
