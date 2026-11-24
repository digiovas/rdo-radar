# Contesto del progetto (da caricare come conoscenza nel Project di Claude)

Ultimo aggiornamento: 23/11/2026. Fonte: conversazione di esplorazione del portale.

## Obiettivo
Un portale personale che ogni giorno raccoglie le **RDO aperte** di acquistinretepa.it, ne legge i
documenti allegati, ricava lo **scopo della fornitura** e permette di cercare per parole chiave
positive e **negative** (le RDO con parole negative non vengono messe in evidenza).
Serve a individuare forniture realizzabili da un'officina metalmeccanica / carpenteria metallica
(recinzioni, strutture metalliche, armadi, tubi, arredo da esterni, ecc.).

## Vincoli decisi
- Aggiornamento tramite script Python su servizio gratuito (GitHub Actions).
- Archivio SQLite versionato su GitHub (branch `data`).
- Dashboard statica (GitHub Pages) con ricerca per parole chiave e negative.
- Nessun costo, nessun server da gestire.

## Come funziona il portale (verificato il 23/11/2026)
Strumenti nell'elenco "Vendi > Bandi": AQ, Convenzioni, MePA, SDA, Altri bandi, **RDO aperte**,
Avvisi di indagine. Le RDO sono una modalita' di acquisto *dentro* il MePA; le SDA sono un sistema
separato, piu' formale e di importi maggiori.

- Elenco pubblico RDO aperte (senza accesso): `https://www.acquistinretepa.it/opencms/opencms/vetrina_bandi.html?filter=RDO`
  (circa 477 RDO il 23/11/2026, 20 per pagina).
- Le RDO **a invito** e le **trattative dirette** NON sono visibili da fuori: nei dati Consip 2025, sui CPV
  vicini alla carpenteria metallica, circa l'85% delle negoziazioni sono trattative dirette.
- Per **presentare offerta** servono accesso e abilitazione alla categoria; per **leggere** RDO e
  documenti no.
- I titoli spesso non bastano (esempio: "SONDA ECOGRAFICA (vedi fabbisogno e caratteristiche)"):
  lo scopo vero e' nel PDF allegato.

## Servizi JSON usati dal sito (osservati dal browser, NON documentati)
Tutti `POST`, JSON, senza login. Nel browser le richieste dell'elenco portano anche gli header
`X-XSRF-TOKEN` (dal cookie omonimo) e `KEY_REQUEST` (timestamp in ms).

| Scopo | Endpoint | Body |
|---|---|---|
| Elenco RDO aperte | `/publicservices/vetrineservices/getAltriBandiRdoAperte` | `{"isArchive":false,"strumento":[{"label":"RDO APERTE","totale":1,"id":1}],"categoria":[],"tempo":{"dataDa":null,"dataA":null},"paginazione":{"pagina":1,"itemPagina":20},"orderBy":{"campo":"dataPubblicazione","verso":"desc"},"idt":""}` |
| Dettaglio RDO | `/publicservices/iniziativaservices/getDettaglioBandoRDO` | `{"idIniziativa":"<idBando>"}` |
| Lotti (CIG, valore, criterio) | `/publicservices/iniziativaservices/getDettaglioLottiRDO` | idem |
| Date e fasi | `/publicservices/iniziativaservices/getDettaglioInformazioniRDO` | idem |
| Richieste ai partecipanti | `/publicservices/iniziativaservices/getRichiestePartecipantiRDO` | idem |
| Elenco documenti | `/publicservices/iniziativaservices/getDocIniziativa` | idem |
| Scarico documento | `/eproc2/documentaleservices/getDocumento` | `{"idDocumento":"<id>"}` → JSON con `nomeDocumento`, `dimensione`, `file` (base64) |

Risposta tipo: `{"result":{"exitCode":"200",...},"payload":{...}}`; `exitCode` 1008 = elemento non trovato.
Elenco: `payload.elencoBandi[]` con `idBando`, `titoloBando`, `numeroRdo`, `valore`, `enteCommittente`,
`dataPubblicazione` e `dataScadenzaBando` (ms epoch), `riassuntoBando` (Beni/Servizi/Lavori), `categoria[]`.
Pagina scheda: `/opencms/opencms/scheda_altri_bandi.html?idBando=<idBando>`.

Documenti incontrati: PDF (testo vero), Word (.docx), `Request.xml` (richiesta ESPD, ~290 KB, da ignorare).
Provato su un PDF reale: il testo si estrae senza OCR.

## Da verificare (primo giro su GitHub Actions)
1. Il portale risponde agli IP dei runner GitHub? (potrebbe bloccarli)
2. Serve davvero l'header `X-XSRF-TOKEN`? Il client lo copia dal cookie, come fa il browser.
3. Nome esatto del campo "Descrizione RDO" in `getDettaglioBandoRDO` (il client cerca varianti).
4. Termini d'uso del portale per l'accesso automatico: leggerli prima di usare lo script in continuo.

## Dati Consip (dati.consip.it) — risultati utili
Aggregati, non per singola RDO; aggiornamento mensile. Sul 2025, per ~35 CPV legati alla carpenteria:
circa 5.500 negoziazioni (800 RDO, 4.730 TD). Lazio prima regione (766), poi Veneto, Sicilia, Piemonte;
nel Lazio la provincia di Roma pesa 611. Categorie di abilitazione piu' rilevanti: Arredi da esterno,
Archivi compattabili/scaffalature, Prodotti per la raccolta rifiuti, Ferramenta (Beni); OS 18-A
Componenti strutturali in acciaio e OS 6 Finiture (Lavori).
Il campo "% RdO con invito selettivo" e' vuoto nel 2025: non permette di separare aperte e a invito.

## Altre piste
- MePA Light (dal 29/10/2026): affidamenti diretti sotto 5.000 € anche a imprese non abilitate.
- Abilitazione al MePA: necessaria per rispondere; da fare prima di trovare la RDO giusta (tempi brevi,
  in media circa 11 giorni per presentare l'offerta).
- Avvisi di indagine: indagini di mercato della PA, non ancora esplorati.

## Stato dello scheletro
Funzionano e sono testati: archivio SQLite, estrazione testo (PDF/Word/Excel), scelta dei documenti,
estrazione dello scopo, export JSON, dashboard (ricerca, negativi, ricerche salvate nel browser),
workflow GitHub Actions (non ancora eseguito). Non testato contro il portale reale.

## Avvisi di indagine (aggiunti il 24/11/2026)
- Elenco: `POST /adi/api/v1/vetrina/ricerca` (body come la vetrina, strumento id `AVVISO_DI_INDAGINE`, itemPagina fino a 100)
  -> `payload.elencoAvvisi` (idBando, titoloBando, valore, enteCommittente, date, categoria, numeroAvviso).
- Dettaglio: `POST /adi/api/v1/vetrina/dettaglio` con `{"idIniziativa": idBando}` -> `payload.altriBandi`
  (tyTipologiaAppalto: APPALTO_FORNITURE/LAVORI/SERVIZI/MISTO, lotti con CIG, criterio).
- Verificato su 61 avvisi: nessun documento pubblico (getDocIniziativa vuoto). Lo "scopo" e' il titolo.
- Nel database stanno nella stessa tabella `rdo` con `fonte = 'Avviso'`; `tipo`: Beni/Lavori/Servizi/Misto.
- Un guasto sugli avvisi non ferma la lettura delle RDO (vedi `leggi_avvisi` in run.py).
- Le RDO di tipo misto ("Lavori, Servizi") ora vengono lette come Beni/Lavori (prima erano saltate).
