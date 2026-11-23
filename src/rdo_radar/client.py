"""Client per i servizi pubblici di acquistinretepa.it.

ATTENZIONE: gli endpoint sono quelli usati dal sito web (osservati dal browser il
23/11/2026), non un'API documentata. Possono cambiare senza preavviso. Per questo:
  * una sola esecuzione al giorno, con pausa tra le richieste;
  * User-Agent che dichiara cosa siamo;
  * ogni risposta anomala fa fallire la singola RDO, non l'intera esecuzione.

DA VERIFICARE alla prima esecuzione su GitHub Actions (vedi docs/CONTEXT.md):
  * se serve davvero l'header X-XSRF-TOKEN (nel browser c'e', copiato dal cookie);
  * se il portale accetta richieste dagli IP dei runner GitHub.
"""
from __future__ import annotations

import base64
import logging
import time
from typing import Any, Iterator

import requests

BASE = "https://www.acquistinretepa.it"
LIST_PAGE = f"{BASE}/opencms/opencms/vetrina_bandi.html?filter=RDO"
SCHEDA_URL = BASE + "/opencms/opencms/scheda_altri_bandi.html?idBando={id}"
UA = "rdo-radar/0.1 (progetto personale non commerciale; una esecuzione al giorno)"

log = logging.getLogger(__name__)


class PortalError(RuntimeError):
    pass


class NotFound(PortalError):
    """Il servizio risponde exitCode 1008 'Elemento non trovato'."""


class Portal:
    def __init__(self, delay: float = 1.0, timeout: int = 30, session: requests.Session | None = None):
        self.delay = delay
        self.timeout = timeout
        self.s = session or requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept": "application/json, text/plain, */*"})
        self._last = 0.0
        if session is None:
            self._bootstrap()

    # -- basso livello -------------------------------------------------
    def _bootstrap(self) -> None:
        """Apre la pagina elenco per ottenere i cookie di sessione (incluso XSRF-TOKEN)."""
        r = self.s.get(LIST_PAGE, timeout=self.timeout)
        r.raise_for_status()
        token = self.s.cookies.get("XSRF-TOKEN")
        if token:
            self.s.headers["X-XSRF-TOKEN"] = token
        else:
            # Verificato il 23/11/2026: il portale risponde anche senza questo header
            log.info("Cookie XSRF-TOKEN assente: non serve per leggere elenco e dettagli")
        # Come il browser, tocca due servizi /eproc2 per ottenere i cookie di sessione usati
        # dal download dei documenti (la prima chiamata puo' passare da un login automatico).
        for path in ("/eproc2/dizionariservices/getSessionTimeInfo", "/eproc2/autorizzazioneservices/getUserInfo"):
            try:
                self.s.get(BASE + path, timeout=self.timeout)
            except requests.RequestException:
                pass

    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        data = None
        for attempt in (1, 2):
            self.s.headers["KEY_REQUEST"] = str(int(time.time() * 1000))
            r = self.s.post(BASE + path, json=payload, timeout=self.timeout)
            self._last = time.monotonic()
            r.raise_for_status()
            try:
                data = r.json()
                break
            except ValueError:
                # Capita alla prima chiamata a /eproc2: il portale risponde con una pagina di
                # passaggio del login e imposta i cookie. Si riprova una volta con i cookie nuovi.
                if attempt == 2:
                    raise PortalError(f"{path}: risposta non JSON (HTTP {r.status_code})")
                log.info("%s: risposta non JSON, riprovo una volta", path)
                time.sleep(self.delay)
        res = data.get("result") or {}
        code = str(res.get("exitCode"))
        if code == "1008":
            raise NotFound(path)
        if code != "200":
            raise PortalError(f"{path}: exitCode={code} {res.get('text')}")
        return data.get("payload")

    # -- elenco --------------------------------------------------------
    def list_page(self, page: int = 1, per_page: int = 20) -> list[dict]:
        """Una pagina dell'elenco RDO aperte, dalla piu' recente."""
        payload = {
            "isArchive": False,
            "strumento": [{"label": "RDO APERTE", "totale": 1, "id": 1}],
            "categoria": [],
            "tempo": {"dataDa": None, "dataA": None},
            "paginazione": {"pagina": page, "itemPagina": per_page},
            "orderBy": {"campo": "dataPubblicazione", "verso": "desc"},
            "idt": "",
        }
        out = self._post("/publicservices/vetrineservices/getAltriBandiRdoAperte", payload)
        return list((out or {}).get("elencoBandi") or [])

    def iter_list(self, known_ids: set[str], max_pages: int = 40, per_page: int = 20) -> Iterator[dict]:
        """Scorre l'elenco dalla piu' recente e si ferma dopo una pagina interamente nota."""
        for page in range(1, max_pages + 1):
            items = self.list_page(page, per_page)
            if not items:
                return
            new = [i for i in items if i.get("idBando") not in known_ids]
            yield from items
            if not new:
                return

    # -- dettaglio -----------------------------------------------------
    def detail(self, id_bando: str) -> dict:
        p = {"idIniziativa": id_bando}
        base = self._post("/publicservices/iniziativaservices/getDettaglioBandoRDO", p) or {}
        try:
            lotti = self._post("/publicservices/iniziativaservices/getDettaglioLottiRDO", p) or {}
        except NotFound:
            lotti = {}
        try:
            docs = self._post("/publicservices/iniziativaservices/getDocIniziativa", p) or {}
        except NotFound:
            docs = {}
        return {"bando": base, "lotti": lotti, "documenti": docs}

    def get_documento(self, id_documento: str) -> tuple[str, bytes]:
        out = self._post("/eproc2/documentaleservices/getDocumento", {"idDocumento": id_documento}) or {}
        raw = base64.b64decode(out.get("file") or "")
        return out.get("nomeDocumento") or id_documento, raw


# -- parsing (funzioni pure, testabili) -----------------------------------
def parse_list_item(it: dict) -> dict:
    """Normalizza un elemento dell'elenco."""
    def ms(v):
        return int(v) // 1000 if v else None

    try:
        valore = float(str(it.get("valore")).replace(",", ".")) if it.get("valore") not in (None, "") else None
    except ValueError:
        valore = None
    return {
        "id_bando": it["idBando"],
        "numero_rdo": it.get("numeroRdo"),
        "titolo": (it.get("titoloBando") or "").strip(),
        "ente": it.get("enteCommittente") or it.get("descrizioneEnte"),
        "valore": valore,
        "tipo": it.get("riassuntoBando"),  # Beni / Servizi / Lavori
        "categorie": ", ".join(it.get("categoria") or []),
        "data_pubblicazione": ms(it.get("dataPubblicazione")),
        "data_scadenza": ms(it.get("dataScadenzaBando")),
    }


def _find_first(d: Any, keys: tuple[str, ...]) -> str | None:
    """Cerca ricorsivamente il primo valore stringa non vuoto per una delle chiavi."""
    if isinstance(d, dict):
        for k in keys:
            v = d.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for v in d.values():
            r = _find_first(v, keys)
            if r:
                return r
    elif isinstance(d, list):
        for v in d:
            r = _find_first(v, keys)
            if r:
                return r
    return None


def parse_detail(det: dict) -> dict:
    """Estrae descrizione, CIG, criterio e l'elenco documenti dal dettaglio.

    I nomi dei campi della descrizione non sono confermati: si cercano varianti.
    Verificare con un esempio reale e restringere (vedi docs/CONTEXT.md).
    """
    bando = det.get("bando") or {}
    lotti = (det.get("lotti") or {}).get("dettaglioLottiAltriBandi") or []
    docs = (det.get("documenti") or {}).get("listaDocumentiIniziativa") or []
    return {
        "descrizione": _find_first(bando, ("descrizioneRDO", "descrizioneBando", "descrizione")),
        "cig": ", ".join(sorted({l.get("cig") for l in lotti if l.get("cig")})) or None,
        "criterio": _find_first(lotti, ("criterioAggiudcazione", "criterioAggiudicazione")),
        "documenti": [
            {
                "id_documento": d["idDocumento"],
                "titolo": d.get("titolo") or d.get("descrizione") or "",
                "descrizione": d.get("descrizione") or "",
                "formato": (d.get("formato") or "").lower(),
                "tipologia": d.get("tipologia") or "",
            }
            for d in docs
            if d.get("idDocumento") and d.get("flDocumento", True)
        ],
    }
