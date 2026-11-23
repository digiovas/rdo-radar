"""Esecuzione giornaliera: python -m rdo_radar.run --db dati/rdo.sqlite --out dati/rdo.json"""
from __future__ import annotations

import argparse
import logging
import sys
import time

from . import db, documents, extract
from .client import Portal, parse_detail, parse_list_item
from .export import export_json

log = logging.getLogger("rdo_radar")

# Si leggono i documenti solo per questi tipi: i Servizi sono fuori dal vostro settore.
TIPI_CON_DOCUMENTI = {"Beni", "Lavori"}
MAX_BYTES = 8 * 1024 * 1024


def process_detail(portal: Portal, con, id_bando: str, tipo: str | None) -> str:
    """Legge dettaglio e documenti di una RDO e li salva. Ritorna lo stato documenti."""
    det = parse_detail(portal.detail(id_bando))
    row = con.execute("SELECT titolo FROM rdo WHERE id_bando=?", (id_bando,)).fetchone()
    titolo = row["titolo"]
    texts: list[str] = []
    saved_docs: list[dict] = []
    stato = "saltato"

    if tipo in TIPI_CON_DOCUMENTI:
        chosen = documents.rank_documents(det["documenti"])
        chosen_ids = {d["id_documento"] for d in chosen}
        for d in det["documenti"]:
            d["stato"] = "saltato"
        if not det["documenti"]:
            stato = "nessuno"
        ok = fail = 0
        for d in det["documenti"]:
            if d["id_documento"] not in chosen_ids:
                continue
            try:
                name, raw = portal.get_documento(d["id_documento"])
                if len(raw) > MAX_BYTES:
                    d["stato"] = "saltato"
                    continue
                text, st = documents.extract_text(d["titolo"] or name, raw)
            except Exception as exc:  # un documento rotto non ferma la RDO
                log.warning("documento %s: %s", d["id_documento"], exc)
                text, st = "", "errore"
            d["stato"] = st
            if st == "ok":
                texts.append(text)
                ok += 1
            else:
                fail += 1
        if det["documenti"]:
            stato = "ok" if ok and not fail else ("parziale" if ok else "errore" if fail else "saltato")
    saved_docs = det["documenti"]

    scopo = extract.find_scopo(titolo, det["descrizione"], texts)
    estratto = extract.build_excerpt(texts)
    db.save_detail(con, id_bando, descrizione=det["descrizione"], cig=det["cig"], criterio=det["criterio"],
                   scopo=scopo, estratto=estratto, docs_stato=stato, documenti=saved_docs)
    return stato


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-pages", type=int, default=40)
    ap.add_argument("--max-new", type=int, default=150, help="tetto di RDO nuove lette per esecuzione")
    ap.add_argument("--max-minutes", type=float, default=0,
                    help="tempo massimo di lettura dettagli; poi si salva e si riprende al prossimo avvio (0 = nessun limite)")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    for noisy in ("urllib3", "pypdf", "fontTools"):  # meno rumore: i PDF mal formati sono frequenti
        logging.getLogger(noisy).setLevel(logging.ERROR if noisy != "urllib3" else logging.WARNING)
    con = db.connect(args.db)
    portal = Portal(delay=args.delay)

    known = db.known_ids(con)
    nuove = 0
    for raw in portal.iter_list(known, max_pages=args.max_pages):
        if db.upsert_list_item(con, parse_list_item(raw)):
            nuove += 1
    con.commit()
    log.info("elenco letto: %d RDO nuove", nuove)

    todo = db.pending_ids(con)[: args.max_new]
    fatte = errori = 0
    deadline = time.monotonic() + args.max_minutes * 60 if args.max_minutes else None
    for id_bando in todo:
        if deadline and time.monotonic() > deadline:
            log.info("tempo massimo raggiunto: si salva e si riprende al prossimo avvio (%d RDO ancora da leggere)",
                     len(todo) - fatte - errori)
            break
        tipo = con.execute("SELECT tipo FROM rdo WHERE id_bando=?", (id_bando,)).fetchone()["tipo"]
        try:
            process_detail(portal, con, id_bando, tipo)
            fatte += 1
        except Exception as exc:
            errori += 1
            con.execute("UPDATE rdo SET docs_stato='errore' WHERE id_bando=?", (id_bando,))
            con.commit()
            log.warning("RDO %s non letta: %s", id_bando, exc)
    log.info("dettagli letti: %d, errori: %d", fatte, errori)

    n = export_json(con, args.out)
    log.info("esportate %d RDO in %s", n, args.out)
    # Se quasi tutto fallisce il portale e' cambiato o ci blocca: l'azione deve diventare rossa
    if todo and fatte == 0 and errori > 0:
        log.error("tutte le letture sono fallite")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
