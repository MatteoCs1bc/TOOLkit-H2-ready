# Tool 3.1 | Motore di Sizing e Sostenibilità Economica 🏭

Questo tool rappresenta il "motore ingegneristico" e finanziario del toolkit *H2READY*. A differenza di fogli di calcolo statici, utilizza un algoritmo Python (ottimizzato con Numba) per simulare ora per ora (8760 ore/anno) il funzionamento di un impianto a idrogeno verde basato su profili eolici e fotovoltaici reali italiani.

<details>
<summary><b>🛠️ Clicca qui per espandere il Menù Metodologico e le Istruzioni</b></summary>

## Come funziona il Reverse Engineering?
L'obiettivo non è dire "quanto idrogeno produce il mio impianto rinnovabile", ma il contrario: l'utente inserisce la **domanda** (Target Idrogeno in ton/anno) e il codice esegue un calcolo a ritroso per determinare:
1. I Megawatt esatti di Fotovoltaico ed Eolico necessari.
2. La taglia dell'Elettrolizzatore.
3. La capacità del sistema di accumulo a batterie (BESS) per stabilizzare la produzione.

## La Logica Economica (Opzione A - CfD PPA)
I calcoli finanziari mostrati nella sezione di "Sostenibilità Economica" si basano sul modello del **Power Purchase Agreement (PPA)** tramite *Contratti per Differenza (CfD)*.
* **CAPEX (Spesa in Conto Capitale):** Il Comune o l'azienda investe unicamente nell'infrastruttura di trasformazione (Elettrolizzatore) e stoccaggio (Batterie). Non si sobbarca il costo di costruzione dei parchi rinnovabili.
* **OPEX (Spesa Operativa):** L'energia rinnovabile (Fotovoltaico ed Eolico) viene acquistata da impianti terzi dedicati o tramite la rete a un prezzo fisso pre-negoziato (i cursori CfD €/MWh).
* **Payback:** Il tempo di rientro è calcolato sottraendo ai ricavi di vendita dell'H2 l'intero OPEX energetico e i costi di manutenzione (stimati al 3% del CAPEX totale).

## Variabili Modificabili (Sidebar)
* **Limite max Batteria:** Evita che l'algoritmo dimensioni batterie gigantesche e insostenibili. Limita la capacità MWh a un multiplo prestabilito (es. 3x) rispetto alla taglia in MW del Fotovoltaico.
* **CfD PV / Eolico:** Il prezzo dell'energia elettrica a cui chiudi il contratto di fornitura.
* **CAPEX Batterie:** Costo degli accumuli. Settato di default a 150 €/kWh per simulare prezzi di mercato attuali per sistemi stazionari LFP.
* **Prezzo Vendita H2:** Il valore economico per kg dell'idrogeno. Se autoproduci, rappresenta il costo evitato del combustibile fossile o dell'energia elettrica sostituita.

## Requisiti Tecnici
Assicurati che nella stessa cartella del file `app.py` siano presenti i due file CSV dei profili climatici:
* `dataset_fotovoltaico_produzione.csv`
* `dataset_eolico_produzione.csv`
</details>

---
*Progetto H2READY - Percorso B1/C1 Valutazione Tecnico-Economica*
