"""Archivio SQLite. Un file solo, facile da versionare nel branch 'data'."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS rdo (
  id_bando TEXT PRIMARY KEY,
  numero_rdo TEXT,
  titolo TEXT NOT NULL,
  ente TEXT,
  valore REAL,
  tipo TEXT,
  categorie TEXT,
  data_pubblicazione INTEGER,
  data_scadenza INTEGER,
  descrizione TEXT,
  cig TEXT,
  criterio TEXT,
  scopo TEXT,
  estratto TEXT,
  docs_stato TEXT DEFAULT 'da_fare',   -- da_fare | ok | parziale | nessuno | saltato | errore
  fonte TEXT DEFAULT 'RDO',            -- RDO | Avviso (avviso di indagine)
  first_seen INTEGER NOT NULL,
  last_seen INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS documento (
  id_documento TEXT PRIMARY KEY,
  id_bando TEXT NOT NULL REFERENCES rdo(id_bando),
  titolo TEXT,
  formato TEXT,
  stato TEXT                            -- ok | vuoto | non_supportato | errore | saltato
);
CREATE INDEX IF NOT EXISTS ix_rdo_scadenza ON rdo(data_scadenza);
CREATE INDEX IF NOT EXISTS ix_doc_bando ON documento(id_bando);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)  # crea la cartella se manca
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    _migra(con)
    return con


def _migra(con: sqlite3.Connection) -> None:
    """Aggiorna i database creati da versioni precedenti (idempotente)."""
    cols = {r[1] for r in con.execute("PRAGMA table_info(rdo)")}
    if "fonte" not in cols:
        con.execute("ALTER TABLE rdo ADD COLUMN fonte TEXT DEFAULT 'RDO'")
        con.execute("UPDATE rdo SET fonte='RDO' WHERE fonte IS NULL")
    versione = con.execute("PRAGMA user_version").fetchone()[0]
    if versione < 1:
        # Le RDO di tipo misto ("Lavori, Servizi", "Beni, Servizi") erano state saltate per errore: da rileggere
        con.execute("UPDATE rdo SET docs_stato='da_fare' WHERE docs_stato='saltato' AND tipo LIKE '%,%' "
                    "AND (tipo LIKE '%Beni%' OR tipo LIKE '%Lavori%')")
        con.execute("PRAGMA user_version = 1")
    con.commit()


def known_ids(con: sqlite3.Connection) -> set[str]:
    return {r[0] for r in con.execute("SELECT id_bando FROM rdo")}


def pending_ids(con: sqlite3.Connection, fonte: str = "RDO") -> list[str]:
    """Elementi da completare (dettaglio/documenti non ancora letti), solo se non scaduti."""
    now = int(time.time())
    rows = con.execute(
        "SELECT id_bando FROM rdo WHERE docs_stato IN ('da_fare','errore') AND COALESCE(fonte,'RDO') = ? "
        "AND (data_scadenza IS NULL OR data_scadenza > ?) ORDER BY (docs_stato = 'errore'), data_pubblicazione DESC",
        (fonte, now),
    )
    return [r[0] for r in rows]


def upsert_list_item(con: sqlite3.Connection, it: dict, now: int | None = None) -> bool:
    """Inserisce o aggiorna i dati di elenco. Ritorna True se la RDO e' nuova."""
    now = now or int(time.time())
    exists = con.execute("SELECT 1 FROM rdo WHERE id_bando=?", (it["id_bando"],)).fetchone()
    if exists:
        con.execute(
            "UPDATE rdo SET titolo=?, ente=?, valore=?, tipo=COALESCE(?, tipo), categorie=?, data_scadenza=?, last_seen=? "
            "WHERE id_bando=?",
            (it["titolo"], it["ente"], it["valore"], it["tipo"], it["categorie"], it["data_scadenza"], now, it["id_bando"]),
        )
        return False
    con.execute(
        "INSERT INTO rdo (id_bando, numero_rdo, titolo, ente, valore, tipo, categorie, data_pubblicazione, "
        "data_scadenza, first_seen, last_seen, fonte) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (it["id_bando"], it["numero_rdo"], it["titolo"], it["ente"], it["valore"], it["tipo"], it["categorie"],
         it["data_pubblicazione"], it["data_scadenza"], now, now, it.get("fonte", "RDO")),
    )
    return True


def save_detail(con: sqlite3.Connection, id_bando: str, *, descrizione, cig, criterio, scopo, estratto,
                docs_stato: str, documenti: list[dict], tipo: str | None = None) -> None:
    con.execute(
        "UPDATE rdo SET descrizione=?, cig=?, criterio=?, scopo=?, estratto=?, docs_stato=?, tipo=COALESCE(?, tipo) "
        "WHERE id_bando=?",
        (descrizione, cig, criterio, scopo, estratto, docs_stato, tipo, id_bando),
    )
    for d in documenti:
        con.execute(
            "INSERT INTO documento (id_documento, id_bando, titolo, formato, stato) VALUES (?,?,?,?,?) "
            "ON CONFLICT(id_documento) DO UPDATE SET stato=excluded.stato",
            (d["id_documento"], id_bando, d["titolo"], d["formato"], d.get("stato", "saltato")),
        )
    con.commit()
