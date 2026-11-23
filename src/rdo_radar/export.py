"""Esporta in JSON le RDO utili alla dashboard (aperte o scadute da poco)."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from .client import SCHEDA_URL


def export_json(con: sqlite3.Connection, out: str | Path, grace_days: int = 14, now: int | None = None) -> int:
    now = now or int(time.time())
    limite = now - grace_days * 86400
    rows = con.execute(
        "SELECT * FROM rdo WHERE data_scadenza IS NULL OR data_scadenza >= ? "
        "ORDER BY data_pubblicazione DESC",
        (limite,),
    ).fetchall()
    docs: dict[str, list[dict]] = {}
    for d in con.execute("SELECT id_bando, titolo, formato, stato FROM documento"):
        docs.setdefault(d["id_bando"], []).append(
            {"titolo": d["titolo"], "formato": d["formato"], "stato": d["stato"]}
        )
    items = []
    for r in rows:
        items.append({
            "id": r["id_bando"],
            "numero": r["numero_rdo"],
            "titolo": r["titolo"],
            "ente": r["ente"],
            "valore": r["valore"],
            "tipo": r["tipo"],
            "categorie": r["categorie"],
            "pubblicata": r["data_pubblicazione"],
            "scadenza": r["data_scadenza"],
            "descrizione": r["descrizione"],
            "cig": r["cig"],
            "criterio": r["criterio"],
            "scopo": r["scopo"],
            "estratto": r["estratto"],
            "docs_stato": r["docs_stato"],
            "documenti": docs.get(r["id_bando"], []),
            "visto_il": r["first_seen"],
            "url": SCHEDA_URL.format(id=r["id_bando"]),
        })
    payload = {"generato": now, "totale": len(items), "rdo": items}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(items)
