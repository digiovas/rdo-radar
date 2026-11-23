# Avvio passo passo

## 1. Prova in locale (5 minuti, senza toccare il portale)
```bash
pip install -e ".[dev]"
pytest                                   # 8 test devono passare
python scripts/make_sample_data.py       # crea dati FITTIZI di esempio
python -m http.server -d dashboard 8000  # poi apri http://localhost:8000
```

## 2. Crea il repository su GitHub
1. Nuovo repository **pubblico** (GitHub Pages gratuito richiede un repository pubblico), per esempio `rdo-radar`.
2. Carica il contenuto di questa cartella nel branch `main`.
3. *Settings → Pages → Build and deployment → Source: GitHub Actions*.
4. *Settings → Actions → General → Workflow permissions*: "Read and write permissions".

## 3. Primo giro (il passaggio che decide tutto)
1. Tab *Actions* → "Aggiornamento giornaliero RDO" → *Run workflow*.
2. Apri il log del passo "Aggiorna le RDO":
   - **funziona** se vedi "elenco letto: N RDO nuove" e poi "dettagli letti";
   - **403/429 o pagine HTML** al posto del JSON: il portale blocca i runner GitHub → vedi "Piano B";
   - **errore su un campo**: incollami il log, e' un ritocco al client.
3. Terminato il lavoro, la dashboard e' all'indirizzo mostrato dal passo *deploy*.

Il primo giro legge tutto l'elenco (circa 25 pagine) e fino a 150 RDO con i documenti: puo' durare 20-40 minuti.
Le RDO rimaste si completano nei giorni successivi.

## 4. Uso quotidiano
Apri la dashboard, scegli o crea una ricerca, scrivi le parole chiave (una per riga) e le negative. "Salva ricerca"
la conserva nel browser; "Esporta" ne fa una copia.

## Piano B se il portale blocca GitHub
- Eseguire lo stesso script da un computer o Raspberry di casa con `cron` / Utilita' di pianificazione, poi
  fare `git push` del branch `data`; la dashboard resta su GitHub Pages.
- In alternativa un'esecuzione locale e `index.html` aperto da `localhost`.

## Manutenzione
- Se l'azione diventa rossa per piu' giorni: il portale e' cambiato; incolla il log in una chat con Claude.
- Parole chiave troppo generiche (poche righe utili): aggiungi negative; troppo restrittive: usa le radici.
