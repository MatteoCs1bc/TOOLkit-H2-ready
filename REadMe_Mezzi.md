# 🎯 DSS Mobilità: Guida, Logiche e Assunzioni

Questo strumento è un **Simulatore Strategico di Flotta** progettato per superare il semplice "calcolo contabile". Il tool unisce la solida base dati (consumi fisici ed emissioni base) presente nel file Excel del Comune con un **motore di proiezione dinamica**, permettendo di valutare la fattibilità fisica e la competitività economica delle tecnologie BEV (Elettrico) e FCEV (Idrogeno) da oggi fino al 2035.

---

### ⚙️ 1. Motore di Estrazione (Integrazione con Excel)
Il simulatore non "inventa" i consumi. All'avvio, il sistema va a leggere in tempo reale il file `Comparison H2 elc FF.xlsx` caricato nel repository, estraendo per la categoria selezionata (Auto, Bus o Camion):
* **Consumo Base [kWh/km]** (Colonna E)
* **Autonomia Base [km]** (Colonna D)
* **Costo Veicolo Base [€]** (Colonna Z)
* **Costo Manutenzione [€/km]** (Colonna W)
* **Emissioni Costruzione e WtW** (Colonne R e Q)

Tutti i calcoli successivi applicano le proiezioni temporali partendo da questa "fotografia" esatta dei dati comunali.

---

### 🚦 2. I Colli di Bottiglia Fisici (Semaforo BEV)
Prima di valutare l'economia, il tool verifica se il mezzo a batterie è fisicamente in grado di operare il servizio richiesto (Payload e Tempi). L'Idrogeno viene consigliato (Semaforo Blu) se l'Elettrico fallisce in uno di questi due campi:

* **Payload Penalty (Peso Massimo):** Il tool calcola i kWh necessari per la missione e li divide per la densità della batteria. Al peso risultante viene sottratta la **Deroga Normativa UE** per i mezzi a zero emissioni (da 2.000 kg nel 2024 fino a 4.000 kg nel 2030). Se il peso extra netto supera i limiti di tolleranza (es. > 3.000 kg per un Bus Urbano), il mezzo perderebbe troppi passeggeri o merci. (Semaforo Rosso).
* **Collo di Bottiglia Ricarica:** Calcola il tempo di ricarica necessario per ripristinare i kWh consumati. Se supera le ore di fermo al deposito inserite dall'utente, il servizio salta. (Semaforo Rosso).
* **Stress Ambientali:** Il modello applica moltiplicatori ai consumi base per orografia (Pianura 1.0, Collina 1.25, Montagna 1.45) e clima rigido (<0°C: 1.25), con picchi di consumo fino al +81%. Per i veicoli elettrici (BEV), questo obbliga a installare max-batterie che innescano un "effetto domino": sfondamento dei limiti di peso (Payload Penalty), tempi di ricarica insostenibili e conseguente fallimento operativo, rendendo l'idrogeno la scelta obbligata.

---

### 📈 3. Proiezioni Tecnologiche e Curve di Costo (2024 ➔ 2035)
Muovendo lo slider "Anno di Acquisto", il simulatore applica delle curve di apprendimento (*Learning Curves*) ai dati base dell'Excel, simulando l'evoluzione tecnologica:

**A. Evoluzione Fisica (Autonomia e Densità):**
* **Batterie (BEV):** La densità gravimetrica passa da 0.16 kWh/kg (2024) a 0.256 kWh/kg (2030+). Questo genera un incremento dell'**Autonomia Massima fino al +40%** a parità di peso.
* **Idrogeno (FCEV):** L'efficienza delle Fuel Cell migliora, garantendo un incremento dell'**Autonomia Massima fino al +15%** a parità di serbatoi.
* **Ricarica Megawatt:** Fino al 2027, la ricarica per i mezzi pesanti è limitata a 150 kW. Dal 2028, il tool sblocca l'accesso al *Megawatt Charging System* (1.000 kW), abbattendo drasticamente i tempi di ricarica (non applicato alle automobili).

**B. Evoluzione CAPEX (Sconto sull'acquisto):**
I costi dei mezzi (Colonna Z dell'Excel) vengono scontati anno per anno in base al crollo dei costi delle due tecnologie propulsive:
* **Pacco Batterie:** Il costo scala linearmente da 210 €/kWh (2024) a 100 €/kWh (2030+).
* **Fuel Cell:** Il costo della cella a combustibile scala da 330 €/kW (2024) a 210 €/kW (2030+).

**C. Evoluzione OPEX Carburante (Prezzi Dinamici):**
Il costo operativo Fuel viene calcolato convertendo i kWh consumati in Litri o Kg (usando i poteri calorifici: 9.91 per Diesel, 33.33 per H2, ecc.) e moltiplicandoli per i cursori di prezzo della barra laterale, a cui vengono applicate le seguenti variazioni previsionali:
* **Fossili (Diesel/Benzina):** Subiscono un rincaro del **+10%** al 2030 a causa dell'incremento delle carbon tax.
* **Elettricità (Rete/FV):** Subisce uno sconto del **-10%** al 2030 per la maggiore penetrazione delle rinnovabili.
* **Idrogeno (Grigio):** Mantenuto artificialmente stabile nel breve periodo, subisce uno sconto del **-20%** nel lungo.
* **Idrogeno (Rete):** Grazie alla maturità degli elettrolizzatori e alla supply chain, il costo di mercato subisce un abbattimento fino al **-40%**.
* **Idrogeno (Autoprodotto):** Sconta i costi di ammortamento dei macchinari (CAPEX Elettrolizzatore) riducendo il prezzo finale fino al **-30%**.

---

### 🌍 4. Valutazione LCA (Emissioni Totali)
L'approccio LCA (Life Cycle Assessment) calcola le tonnellate di CO2 prodotte dal mezzo in tutto il suo ciclo di vita:
1. **Costruzione Mezzo (CAPEX Emissivo):** Valori estratti dalla **Cella R** del file Excel. Rimangono un "debito carbonico" iniziale che il mezzo deve compensare viaggiando.
2. **Uso e Carburante (WtW):** Il tool estrae le emissioni annue operative basate sui percorsi standard (Cella Q), le scompone al chilometro e le moltiplica per il vero chilometraggio del ciclo di vita impostato dall'utente (`Km annui * Anni di vita utile`), tenendo conto della gravosità orografica (montagna vs pianura).

---

### 💰 5. Strategia Incentivi (Gap Analysis)
Il tool espone il **Gap di Finanziamento**, ovvero il "delta" tra il TCO del mezzo fossile e il TCO delle alternative zero emissioni. 
* Un valore positivo in questa sezione indica all'Amministrazione quanti **fondi o incentivi (in €)** andranno reperiti o stanziati per ogni singolo veicolo nel corso della sua vita utile affinché l'operazione raggiunga la parità economica (*Break-even*). 
* È esposto anche il **Gap al chilometro (€/km)**, fondamentale per dimensionare eventuali contributi in conto esercizio sul servizio di trasporto locale.
