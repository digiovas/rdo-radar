import json
import sqlite3

from rdo_radar import db, documents, extract
from rdo_radar.client import parse_detail, parse_list_item
from rdo_radar.export import export_json

# Elemento reale dell'elenco (23/11/2026), accorciato
LIST_ITEM = {
    "idBando": "98578d595ccf4b57",
    "titoloBando": "ACQUISTO DI SONDA ECOGRAFICA, PER LE ESIGENZE DELLA UOSD CARDIOLOGIA PEDIATRICA DEL PO SANTOBONO",
    "strumentoSigla": "RDO",
    "valore": "3687",
    "enteCommittente": "AZIENDA OSPEDALIERA SANTOBONO PAUSILIPON NAPOLI",
    "dataPubblicazione": 1795388400000,
    "dataScadenzaBando": 1796115600000,
    "categoria": [],
    "numeroRdo": "6942120",
    "riassuntoBando": "Beni",
}

LIST_ITEM_DECIMAL = {**LIST_ITEM, "idBando": "02e9ec9b080c0557", "valore": "2553,6", "categoria": ["Sanità, Ricerca e Welfare"]}

DETAIL = {
    "bando": {"altriBandi": {"titoloRDO": "X", "descrizioneRDO": "SONDA ECOGRAFICA (vedi fabbisogno e caratteristiche)"}},
    "lotti": {"dettaglioLottiAltriBandi": [{"cig": "BDE7794F78", "criterioAggiudcazione": "Minor prezzo"}]},
    "documenti": {"listaDocumentiIniziativa": [
        {"idDocumento": "a1", "titolo": "03 - CAPITOLATO - ALLEGATO A.pdf", "descrizione": "CAPITOLATO", "formato": "pdf", "flDocumento": True},
        {"idDocumento": "a2", "titolo": "08 - PATTO INTEGRITA - ALLEGATO F.docx", "descrizione": "PATTO", "formato": "docx", "flDocumento": True},
        {"idDocumento": "a3", "titolo": "08 - PATTO INTEGRITA - ALLEGATO F.docx", "descrizione": "PATTO", "formato": "docx", "flDocumento": True},
        {"idDocumento": "a4", "titolo": "Request.xml", "descrizione": "", "formato": "xml", "flDocumento": True},
        {"idDocumento": "a5", "titolo": "Relazione tecnica.pdf", "descrizione": "", "formato": "pdf", "flDocumento": True},
    ]},
}


def test_parse_list_item():
    it = parse_list_item(LIST_ITEM)
    assert it["numero_rdo"] == "6942120" and it["tipo"] == "Beni"
    assert it["valore"] == 3687.0
    assert it["data_scadenza"] == 1796115600
    assert parse_list_item(LIST_ITEM_DECIMAL)["valore"] == 2553.6
    assert parse_list_item(LIST_ITEM_DECIMAL)["categorie"].startswith("Sanità")


def test_parse_detail_e_scelta_documenti():
    det = parse_detail(DETAIL)
    assert det["cig"] == "BDE7794F78" and det["criterio"] == "Minor prezzo"
    assert det["descrizione"].startswith("SONDA")
    scelti = documents.rank_documents(det["documenti"])
    titoli = [d["titolo"] for d in scelti]
    assert titoli[0].startswith("03 - CAPITOLATO")          # priorita' al capitolato
    assert not any("PATTO" in t or t.endswith(".xml") for t in titoli)  # burocratici scartati
    assert len(titoli) == len(set(titoli))                    # niente duplicati


def test_estrazione_scopo_da_intestazione():
    testo = (
        "Premessa generale del documento.\n\n"
        "Art. 1 - OGGETTO DELLA FORNITURA\n"
        "Fornitura e posa in opera di recinzione in acciaio zincato per il parco comunale, "
        "altezza 2 m, completa di cancello carrabile.\n\nArt. 2 - Durata"
    )
    scopo = extract.find_scopo("Titolo", None, [testo])
    assert "recinzione in acciaio zincato" in scopo
    assert "Durata" not in scopo or len(scopo) <= 601


def test_scopo_fallback_titolo_e_descrizione_generica():
    assert extract.find_scopo("FORNITURA PANCHINE", "vedi allegato", []) == "FORNITURA PANCHINE"
    assert extract.find_scopo("T", "Panchine in acciaio per il parco", []).startswith("Panchine")


def test_norm_accenti():
    assert extract.norm("Sanità  Ricerca") == "sanita ricerca"


def test_extract_text_docx_e_stati():
    import io
    import docx

    d = docx.Document()
    d.add_paragraph("OGGETTO: fornitura di armadi metallici a due ante per archivio comunale.")
    buf = io.BytesIO()
    d.save(buf)
    text, st = documents.extract_text("x.docx", buf.getvalue())
    assert st == "ok" and "armadi metallici" in text
    assert documents.extract_text("x.p7m", b"zz")[1] == "non_supportato"
    assert documents.extract_text("x.pdf", b"non e' un pdf")[1] == "errore"


def test_db_ed_export(tmp_path):
    con = db.connect(tmp_path / "t.sqlite")
    assert db.upsert_list_item(con, parse_list_item(LIST_ITEM), now=1795400000) is True
    assert db.upsert_list_item(con, parse_list_item(LIST_ITEM), now=1795500000) is False  # gia' nota
    con.commit()
    assert db.known_ids(con) == {"98578d595ccf4b57"}
    db.save_detail(con, "98578d595ccf4b57", descrizione="d", cig="C", criterio="Minor prezzo", scopo="s",
                   estratto="testo", docs_stato="ok",
                   documenti=[{"id_documento": "a1", "titolo": "cap.pdf", "formato": "pdf", "stato": "ok"}])
    out = tmp_path / "rdo.json"
    n = export_json(con, out, now=1795600000)
    assert n == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    r = data["rdo"][0]
    assert r["numero"] == "6942120" and r["documenti"][0]["stato"] == "ok" and r["url"].endswith("idBando=98578d595ccf4b57")
    # una RDO scaduta da molto tempo non viene esportata
    assert export_json(con, out, now=1796115600 + 40 * 86400) == 0
    assert db.pending_ids(con) == []


def test_pending_ids_esclude_scadute(tmp_path):
    con = db.connect(tmp_path / "t.sqlite")
    it = parse_list_item(LIST_ITEM)
    it["data_scadenza"] = 1  # scaduta
    db.upsert_list_item(con, it)
    con.commit()
    assert db.pending_ids(con) == []


def test_connect_crea_la_cartella(tmp_path):
    con = db.connect(tmp_path / "nuova" / "cartella" / "rdo.sqlite")
    assert (tmp_path / "nuova" / "cartella" / "rdo.sqlite").exists()
    con.close()


class _Resp:
    def __init__(self, body, status=200):
        self._b, self.status_code = body, status
    def raise_for_status(self): pass
    def json(self):
        if self._b is None:
            raise ValueError("no json")
        return self._b


class _FakeSession:
    """Prima risposta: pagina HTML di passaggio (non JSON); poi JSON corretto."""
    def __init__(self, responses):
        self.responses, self.calls = list(responses), 0
        self.headers, self.cookies = {}, {}
    def post(self, *a, **k):
        self.calls += 1
        return self.responses.pop(0)


def test_ritenta_se_la_risposta_non_e_json():
    from rdo_radar.client import Portal, PortalError
    ok = {"result": {"exitCode": "200"}, "payload": {"nomeDocumento": "a.pdf", "file": "QUJD"}}
    p = Portal(delay=0, session=_FakeSession([_Resp(None), _Resp(ok)]))
    name, raw = p.get_documento("x")
    assert (name, raw) == ("a.pdf", b"ABC") and p.s.calls == 2
    p2 = Portal(delay=0, session=_FakeSession([_Resp(None), _Resp(None)]))
    import pytest
    with pytest.raises(PortalError):
        p2.get_documento("x")


def test_scopo_ignora_intestazioni_modulo_e_oggetto_della_fornitura():
    from rdo_radar.extract import find_scopo
    form = ["PARTE RISERVATA ALL'AMMINISTRAZIONE NON MODIFICABILE DAL CONCORRENTE | PARTE RISERVATA AL CONCORRENTE"]
    assert "RISERVATA" not in find_scopo("Fornitura armadi metallici spogliatoio", None, form).upper()
    doc = ["Art. 1 Oggetto della fornitura\nLa presente procedura ha per oggetto la fornitura di armadi metallici a due ante."]
    r = find_scopo("titolo", None, doc)
    assert r.startswith("La presente procedura") and "armadi" in r


def test_scopo_da_tabella_excel_e_titolo_spezzato():
    from rdo_radar.extract import find_scopo
    tab = ["PARTE RISERVATA AL CONCORRENTE\n| POS. | ARTICOLO RICHIESTO | UNITA' | NOME OFFERTO\n1 | Sedia ergonomica | NR\n2 | Armadio metallico 2 ante | NR"]
    r = find_scopo("t", None, tab)
    assert "Sedia ergonomica" in r and "Armadio metallico" in r and "POS." not in r
    doc = ["Art. 2 Oggetto della fornitura, quantitativi e requisiti di legge\nI prodotti oggetto della presente fornitura dovranno essere nuovi."]
    assert find_scopo("t", None, doc).startswith("I prodotti")


def test_pending_mette_in_fondo_le_rdo_in_errore(tmp_path):
    import time
    from rdo_radar import db
    con = db.connect(str(tmp_path / "x.sqlite"))
    fut = int(time.time()) + 86400
    for i, (st, pub) in enumerate([("errore", 300), ("da_fare", 100), ("da_fare", 200)]):
        con.execute("INSERT INTO rdo (id_bando, titolo, docs_stato, data_pubblicazione, data_scadenza, first_seen, last_seen) "
                    "VALUES (?,?,?,?,?,0,0)", (f"id{i}", "t", st, pub, fut))
    con.commit()
    assert db.pending_ids(con) == ["id2", "id1", "id0"]


def test_ripete_dopo_connessione_chiusa(monkeypatch):
    import requests
    from rdo_radar.client import Portal
    monkeypatch.setattr("time.sleep", lambda *_: None)
    ok = {"result": {"exitCode": "200"}, "payload": {"x": 1}}

    class S(_FakeSession):
        def post(self, *a, **k):
            self.calls += 1
            r = self.responses.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

    p = Portal(delay=0, session=S([requests.ConnectionError("chiusa"), requests.ConnectionError("chiusa"), _Resp(ok)]))
    assert p._post("/x", {}) == {"x": 1} and p.s.calls == 3


# ---- avvisi di indagine (osservati sul portale il 24/11/2026) ----
AVVISO_ITEM = {
    "idBando": "770892cd9590a9d9",
    "titoloBando": "AVVISO PUBBLICO DI INDAGINE DI MERCATO ... Museo Archeologico Nazionale di Vibo Valentia",
    "strumentoSigla": "ADI", "valore": "951500.01",
    "enteCommittente": "MINISTERO DELLA CULTURA",
    "dataPubblicazione": 1795600800000, "dataScadenzaBando": 1796835600000,
    "categoria": ["Lavori di manutenzione e opere pubbliche"], "numeroAvviso": "6947000",
}
AVVISO_DETAIL = {
    "tyTipologiaAppalto": "APPALTO_LAVORI", "criterioAggiudcazione": "MP",
    "dettaglioLottiAltriBandi": [{"idLotto": 1, "cig": "BDEF6D962C", "valore": "951500,01"}],
}


def test_parse_avviso():
    from rdo_radar.client import parse_avviso_detail, parse_avviso_item
    it = parse_avviso_item(AVVISO_ITEM)
    assert it["fonte"] == "Avviso" and it["numero_rdo"] == "6947000" and it["valore"] == 951500.01
    assert it["tipo"] is None and it["data_scadenza"] == 1796835600
    d = parse_avviso_detail(AVVISO_DETAIL)
    assert d == {"tipo": "Lavori", "cig": "BDEF6D962C", "criterio": "Minor prezzo"}
    assert parse_avviso_detail({"tyTipologiaAppalto": "APPALTO_MISTO"})["tipo"] == "Misto"


def test_avvisi_nel_db_e_nell_export(tmp_path):
    import json
    from rdo_radar import db
    from rdo_radar.client import parse_avviso_detail, parse_avviso_item
    from rdo_radar.run import process_avviso

    con = db.connect(str(tmp_path / "x.sqlite"))
    assert db.upsert_list_item(con, parse_avviso_item(AVVISO_ITEM), now=1795700000) is True
    assert db.pending_ids(con, "Avviso") == ["770892cd9590a9d9"] and db.pending_ids(con, "RDO") == []

    class P:
        def detail_avviso(self, _):
            return AVVISO_DETAIL
    process_avviso(P(), con, "770892cd9590a9d9")
    r = con.execute("SELECT * FROM rdo").fetchone()
    assert (r["tipo"], r["fonte"], r["docs_stato"], r["cig"]) == ("Lavori", "Avviso", "nessuno", "BDEF6D962C")
    assert r["scopo"].startswith("AVVISO PUBBLICO")
    # al giro dopo l'elenco non deve cancellare il tipo letto dal dettaglio
    db.upsert_list_item(con, parse_avviso_item(AVVISO_ITEM), now=1795800000)
    assert con.execute("SELECT tipo FROM rdo").fetchone()[0] == "Lavori"
    out = tmp_path / "o.json"
    export_json(con, out, now=1795700000)
    item = json.loads(out.read_text())["rdo"][0]
    assert item["fonte"] == "Avviso" and item["numero"] == "6947000"


def test_migrazione_db_vecchio_e_rdo_miste(tmp_path):
    import sqlite3
    from rdo_radar import db
    path = tmp_path / "vecchio.sqlite"
    c = sqlite3.connect(path)  # schema precedente: senza colonna "fonte"
    c.executescript(db.SCHEMA.replace("  fonte TEXT DEFAULT 'RDO',            -- RDO | Avviso (avviso di indagine)\n", ""))
    now = 4102444800  # 2100: non scadute
    for i, (tipo, st) in enumerate([("Lavori, Servizi", "saltato"), ("Servizi", "saltato"), ("Beni", "ok")]):
        c.execute("INSERT INTO rdo (id_bando, titolo, tipo, docs_stato, data_scadenza, first_seen, last_seen) "
                  "VALUES (?,?,?,?,?,0,0)", (f"id{i}", "t", tipo, st, now))
    c.commit(); c.close()
    con = db.connect(str(path))
    assert {r["fonte"] for r in con.execute("SELECT fonte FROM rdo")} == {"RDO"}
    assert db.pending_ids(con, "RDO") == ["id0"]            # solo la mista torna in coda
    db.connect(str(path))                                     # seconda apertura: nessun nuovo accodamento
    con.execute("UPDATE rdo SET docs_stato='saltato' WHERE id_bando='id0'"); con.commit()
    assert db.pending_ids(db.connect(str(path)), "RDO") == []


def test_documenti_per_tipi_misti():
    from rdo_radar.run import vuole_documenti
    assert vuole_documenti("Beni") and vuole_documenti("Lavori, Servizi") and vuole_documenti("Beni, Servizi")
    assert vuole_documenti(None) and not vuole_documenti("Servizi")


class _PortaleFinto:
    def __init__(self, avvisi_rotti=False, **k):
        self.rotti = avvisi_rotti
    def iter_list(self, known, max_pages=40):
        yield LIST_ITEM
    def iter_avvisi(self, known, **k):
        if self.rotti:
            raise RuntimeError("servizio avvisi cambiato")
        yield AVVISO_ITEM
    def detail_avviso(self, _):
        return AVVISO_DETAIL
    def detail(self, _):
        return DETAIL
    def get_documento(self, _):
        raise RuntimeError("niente documenti nel test")


def test_esecuzione_completa_con_avvisi(tmp_path, monkeypatch):
    import json
    from rdo_radar import run
    monkeypatch.setattr(run, "Portal", lambda **k: _PortaleFinto(**k))
    db_, out = tmp_path / "d.sqlite", tmp_path / "o.json"
    assert run.main(["--db", str(db_), "--out", str(out)]) == 0
    fonti = sorted((x["fonte"], x["numero"]) for x in json.loads(out.read_text())["rdo"])
    assert fonti == [("Avviso", "6947000"), ("RDO", "6942120")]


def test_guasto_avvisi_non_ferma_le_rdo(tmp_path, monkeypatch):
    import json
    from rdo_radar import run
    monkeypatch.setattr(run, "Portal", lambda **k: _PortaleFinto(avvisi_rotti=True))
    out = tmp_path / "o.json"
    assert run.main(["--db", str(tmp_path / "d.sqlite"), "--out", str(out)]) == 0
    assert [x["fonte"] for x in json.loads(out.read_text())["rdo"]] == ["RDO"]
