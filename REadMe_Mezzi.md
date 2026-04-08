### 🎯 Obiettivo del Simulatore
Questo strumento non è un semplice "calcolatore di costi", ma un **Simulatore di Fattibilità Operativa e Strategica** per il Trasporto Pubblico e la Logistica Pesante. 

La transizione ecologica non si fa solo con i bilanci, ma con la fisica. L'obiettivo del tool è aiutare le Amministrazioni a capire quando l'Elettrico a Batteria (BEV) è la soluzione ottimale e quando, invece, i suoi limiti fisici rendono l'Idrogeno (FCEV) una necessità irrinunciabile per garantire il servizio pubblico.

### ⚙️ Come funziona la logica di valutazione?
Il tool processa i dati inseriti nella barra laterale seguendo tre fasi sequenziali:

**1. Il test di "Sopravvivenza Fisica" (I Colli di Bottiglia del BEV)**
Prima di guardare il portafoglio, il sistema calcola se un mezzo elettrico è fisicamente in grado di completare il turno. Se si imposta un percorso lungo, montano e freddo, il fabbisogno energetico (kWh) esplode. Il tool calcola quindi:
* **Il Limite di Carico (Payload):** Se la batteria necessaria supera una certa tonnellata (oltre la deroga UE), toglie troppo spazio ai passeggeri o alle merci. (Semaforo Rosso).
* **Il Limite di Tempo:** Se il tempo per ricaricare gli immensi pacchi batteria supera le ore di fermo del mezzo nel deposito, il servizio salta. (Semaforo Rosso).

**2. L'Analisi Economica Dinamica (TCO e Evoluzione Tecnologica)**
La tecnologia non è ferma. Spostando lo slider dell'**Anno di Acquisto**, il tool proietta il crollo del costo delle batterie, l'aumento della loro densità e l'abbassamento dei costi delle Fuel Cell al 2030. Inoltre, il costo dell'Idrogeno Autoprodotto è calcolato matematicamente sul costo della tua elettricità (Assunzione: *55 kWh per produrre 1 kg di H2*). Se l'energia costa troppo, produrre idrogeno localmente sarà sempre in perdita.

**3. Valutazione LCA ed Efficienza Globale (Dati da Database)**
Nella sezione inferiore, il tool pesca i dati fisici (Efficienza WtW, Consumi) direttamente dal database Excel e genera i grafici di scostamento rispetto al mezzo **Diesel** (Baseline). Le emissioni di CO2 vengono calcolate su tutto il ciclo di vita (LCA), unendo la fase di costruzione del mezzo (CAPEX) a quella dell'uso e della manutenzione (OPEX).

### 🚦 Guida alla Lettura del Verdetto
In base all'approccio della *neutralità tecnologica*:
* **Eccezione Urbana (Verde Diretto):** Per percorsi urbani brevi (< 200 km), la tecnologia a batteria ha già vinto la sfida commerciale e tecnica. L'idrogeno qui è uno spreco di risorse pubbliche.
* **Vittoria Idrogeno (Blu):** Appare solo nei casi "Hard-to-Abate" (lunghe percorrenze, montagne, turni H24). Se l'elettrico fallisce per eccesso di peso o tempi di ricarica lenti, l'idrogeno diventa la scelta strategica obbligata, nonostante la sua fisiologica inefficienza termodinamica.

**Istruzioni Rapide:** Modifica i parametri della missione nella barra laterale a sinistra e osserva come cambiano in tempo reale i semafori di fattibilità, il grafico a cascata dei costi e le proiezioni sulle emissioni.
