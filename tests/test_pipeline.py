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
