# Architettura

```
GitHub Actions (ogni giorno)            Branch "data"                 GitHub Pages
┌─────────────────────────┐            ┌────────────────┐            ┌───────────────────────┐
│ python -m rdo_radar.run │──scrive──▶ │ rdo.sqlite     │──copia──▶  │ index.html (dashboard)│
│ 1. elenco RDO nuove     │            │ rdo.json       │            │ data/rdo.json         │
│ 2. dettaglio + allegati │            └────────────────┘            └───────────────────────┘
│ 3. testo → scopo        │                                            │
└─────────────────────────┘                                            ▼
                                                                  Il tuo browser:
                                                                  parole chiave, negative,
                                                                  ricerche salvate (localStorage)
```

## Scelte e alternative

**Archivio: SQLite nel branch `data`** (scelta attuale)
- Pro: gratuito, un file, storico completo, nessun account esterno.
- Contro: ogni commit di un file binario ingrandisce il repository. Mitigazione: si salvano solo scopo e un
  estratto di ~3.000 caratteri, non i PDF; ci si aspetta qualche MB all'anno. Se crescesse, si puo'
  ricreare il branch `data` con un solo commit ogni tanto.
- Alternative: JSON per mese (diff leggibili), Cloudflare D1 o Turso (SQL gratuito ospitato, ma un account in piu'),
  Supabase (piano gratuito si mette in pausa se inattivo).

**Dashboard statica** (scelta attuale)
- Il JSON contiene solo le RDO aperte o scadute da meno di 14 giorni (qualche centinaio): si carica subito.
- Le parole chiave positive/negative sono applicate **nel browser**: nessun server, nessuna ricerca inviata a terzi.
- Contro: le ricerche salvate stanno nel browser (per questo c'e' Esporta/Importa); i dati sono pubblici
  perche' GitHub Pages per repository privati e' a pagamento. Le RDO sono comunque pubbliche.
- Alternativa: dashboard privata con Cloudflare Pages + Access, oppure aprire `index.html` in locale.

**Estrazione dello scopo**: euristica (titolo OGGETTO/DESCRIZIONE, poi inizio del documento), senza modelli
linguistici. Un riassunto con un modello (API a pagamento) si puo' aggiungere dopo solo per le RDO che
superano il filtro.

**Documenti**: si leggono solo i Beni e i Lavori (i Servizi sono fuori settore), al massimo 6 per RDO, con
priorita' a capitolato/fabbisogno/specifiche e scarto di DGUE, DUVRI, patti e dichiarazioni.
Non c'e' OCR: i PDF scansionati risultano "testo non leggibile" e la RDO si valuta dal titolo.

**Parole chiave per radice**: la ricerca e' per sottostringa senza accenti, quindi `armad` trova armadio,
armadi, armadietti. Evitare radici troppo corte (`cancell` troverebbe anche "cancelleria").

## Rischi
- Gli endpoint sono quelli del sito, non un'API: possono cambiare. L'azione diventa rossa se tutte le letture
  falliscono (e GitHub manda un'email), ma non se cambia un solo campo: controllare ogni tanto.
- Possibile blocco degli IP dei runner: sarebbe visibile al primo avvio manuale (vedi AVVIO.md).
- Educazione: una richiesta al secondo, un'esecuzione al giorno, User-Agent che dichiara il progetto.
