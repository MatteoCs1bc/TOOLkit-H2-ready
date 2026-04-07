Benvenuto nel **Tool di Scouting Industriale H2READY**. Questo strumento è progettato per supportare le Amministrazioni Comunali nell'identificazione delle aziende del proprio territorio che presentano il maggior potenziale strategico per la transizione verso l'idrogeno verde.

Il sistema si basa sul principio della **neutralità tecnologica**:   
l'idrogeno viene considerato una priorità esclusivamente per i settori "Hard-to-Abate" (HTA), ovvero dove le temperature di processo superano i 400°C o dove l'idrogeno è impiegato come materia prima. Per tutti i settori con processi a bassa/media temperatura, l'elettrificazione (es. pompe di calore) rimane la soluzione più efficiente ed economica.

### 1. Come funziona l'algoritmo di Scoring (I Pesi)
Il tool calcola automaticamente uno "Score Strategico" per ogni azienda caricata, assegnandola a una fascia di priorità (Tier) basandosi su tre parametri fondamentali:

**A. Il Peso del Settore (Codice ATECO) - *Fattore Obbligatorio***
Il motore di calcolo analizza le prime due cifre del Codice ATECO dell'azienda per determinarne l'idoneità termica o chimica all'uso dell'idrogeno:
* **Priorità Assoluta (Score Base: 5 Punti):**
    * **ATECO 24.x (Siderurgia e Metallurgia):** Processi di fusione e forgiatura con temperature che superano gli 800°C (fino a 1.500°C). L'idrogeno funge anche da agente chimico riducente (processo DRI).
    * **ATECO 19.x e 20.x (Chimica e Raffinazione):** Settori soggetti agli obblighi europei RED III. L'idrogeno è utilizzato come materia prima (feedstock) o per alimentare processi termici estremi (700°C - 1.100°C).
* **Priorità Alta (Score Base: 4 Punti):**
    * **ATECO 23.x (Minerali Non Metalliferi):** Produzione di Cemento (clinker >1.450°C), Vetro (fusione ~1.600°C) e Ceramica (cottura >400°C).
* **ESCLUSIONE (Score: 0 Punti):**
    * **ATECO 10.x, 11.x (Alimentare/Bevande), 16.x (Legno/Arredo), 13.x, 14.x, 17.x (Carta):** Processi a bassa/media temperatura (es. essiccazione, produzione vapore) dove l'elettrificazione diretta è prioritaria. Il tool scarta automaticamente queste aziende.

**B. Il Moltiplicatore Dimensionale - *Fattore Obbligatorio***
Le aziende di maggiori dimensioni hanno tipicamente una maggiore capacità di sostenere investimenti infrastrutturali (CAPEX) e sono maggiormente soggette alle pressioni normative europee (es. ETS, CBAM).
* **Grande Impresa:** Moltiplicatore x1.5
* **Media Impresa:** Moltiplicatore x1.2
* **Piccola Impresa:** Moltiplicatore x1.0 (o valore di default se mancante)

**C. I Bonus Strategici e Territoriali - *Fattori Opzionali***
Se il file Excel contiene i dati, il sistema premia le sinergie:
* **Aggregazione Consortile (+3 Punti):** L'appartenenza a Consorzi di Sviluppo Economico (es. ZIPR, COSEF) facilita la condivisione delle infrastrutture per l'idrogeno, riducendo i costi logistici.
* **South H2 Corridor (+3 Punti):** La vicinanza al futuro gasdotto transnazionale (PCI) garantisce un'opzione di approvvigionamento strategico a lungo termine.

### 2. Classificazione dei Risultati (Tier)
Sulla base del punteggio totale, le aziende vengono classificate in tre fasce:
* 🟢 **Tier 1 - Priorità Alta (Score ≥ 10.0):** Aziende ideali per essere invitate ai tavoli tecnici strategici H2READY e per accedere a studi di pre-fattibilità.
* 🟡 **Tier 2 - Media (Score 7.0 - 9.9):** Aziende con buon potenziale, da coinvolgere in logiche di distretto o per applicazioni specifiche (es. cogenerazione).
* 🔴 **Non Idoneo / Tier 3:** Settori elettrificabili o con punteggi insufficienti per giustificare l'investimento nell'idrogeno.

### 3. Come strutturare il file di Input
Affinché il tool funzioni correttamente, il file caricato **DEVE** rispettare un'intestazione precisa. È sufficiente che siano presenti le colonne obbligatorie.
