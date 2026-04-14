### 🔄 La Logica del Reverse Engineering
L'algoritmo non risponde alla domanda *"Quanto idrogeno produce il mio impianto?"*, ma al quesito opposto: **"Data una domanda fissa di idrogeno (Target), quanta infrastruttura devo costruire?"**
Il sistema calcola a ritroso basandosi su 8760 ore di dati climatici reali:
1. **La Massa:** Sizing dei serbatoi in base ai giorni di autonomia (buffer) richiesti.
2. **La Potenza:** Sizing di Elettrolizzatore e Compressori in base al fabbisogno orario.
3. **L'Energia:** Sizing dei Megawatt di Fotovoltaico ed Eolico necessari per alimentare Elettrolisi e Compressione, supportati dalle batterie (BESS) per coprire i buchi di produzione.

---

### 💶 Il Modello Economico PPA e il CfD (Contract for Difference)
Per garantire la bancabilità, il simulatore adotta un modello finanziario "ibrido", tipico delle grandi *Hydrogen Valleys*:

* **Nessun CAPEX Rinnovabile:** Il progetto **NON** paga la costruzione fisica dei campi fotovoltaici o eolici. L'investimento iniziale (CAPEX) è focalizzato al 100% sull'impianto idrogeno (Elettrolizzatore, BESS, Stoccaggio, Compressori e Allaccio alla Rete).
* **Il ruolo del CfD (Contract for Difference):** L'energia rinnovabile viene acquistata da parchi terzi tramite un **PPA (Power Purchase Agreement)** a prezzo fisso. I cursori "CfD €/MWh" rappresentano questo *Strike Price*. 
* **Perché si usa il CfD?** Perché protegge il progetto dalla volatilità del mercato elettrico (PUN). Se il prezzo di borsa sale a 150 €/MWh, tu continui a pagare il tuo CfD (es. 60 €/MWh). L'OPEX energetico diventa così un costo piatto e prevedibile per tutti i 20 anni di vita dell'impianto.

---

### 🔌 Costi di Allacciamento alla Rete (e-distribuzione)
I costi di connessione sono estratti dalla **Guida e-distribuzione (Ed. Ottobre 2025)** e vengono calcolati dinamicamente in base alla potenza installata:
* **MT (< 6MW):** Cavo interrato Al 185mm² (155 k€/km) + Cabina Consegna (8 k€).
* **AT (> 6MW):** Linea Aerea 150kV (300 k€/km) + Stallo AIS in Cabina Primaria (730 k€).
Se si seleziona la modalità OFF-GRID (Isola), i costi si azzerano ma aumenta esponenzialmente il rischio di sprecare energia (Curtailment).
