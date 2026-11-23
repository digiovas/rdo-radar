# RDO Radar

Portale personale per trovare, ogni giorno, le **RDO aperte** di acquistinretepa.it adatte a un'officina
metalmeccanica. Legge i documenti allegati (capitolati, fabbisogni), ricava lo scopo della fornitura e
permette di cercare con parole chiave positive e negative.

- `src/rdo_radar/` script Python (client del portale, lettura documenti, estrazione scopo, SQLite, export)
- `dashboard/` dashboard statica (ricerca nel browser, ricerche salvate, parole negative)
- `.github/workflows/daily.yml` aggiornamento giornaliero su GitHub Actions + pubblicazione su Pages
- `docs/CONTEXT.md` cosa abbiamo scoperto sul portale (endpoint, limiti, dati Consip)
- `docs/ARCHITETTURA.md` scelte, alternative e rischi
- `docs/AVVIO.md` come metterlo online passo passo

Stato: scheletro funzionante e testato in locale; **mai eseguito contro il portale reale**. Il primo
giro su GitHub Actions decide se serve un ritocco (vedi `docs/AVVIO.md`).

```bash
pip install -e ".[dev]" && pytest
python scripts/make_sample_data.py && python -m http.server -d dashboard 8000
```
