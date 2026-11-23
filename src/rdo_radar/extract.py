"""Ricava lo 'scopo della fornitura' dal testo dei documenti.

Euristica semplice e volutamente prevedibile (nessun modello linguistico):
  1. un paragrafo introdotto da titoli tipo OGGETTO / DESCRIZIONE / FORNITURA DI;
  2. altrimenti l'inizio del primo documento utile;
  3. altrimenti la descrizione RDO o il titolo.
Lo scopo e' un aiuto per la lettura, non una sintesi: la ricerca per parole chiave
lavora anche sull'estratto di testo.
"""
from __future__ import annotations

import re
import unicodedata

_PRE = r"(?im)^[ \t]*(?:art(?:icolo)?\.?[ \t]*\d+[ \t]*[-–.:)]?[ \t]*)?"
# 1) titoli espliciti (OGGETTO..., DESCRIZIONE...), 2) frasi che iniziano con "Fornitura di"/"Acquisto di"
HEADING_MAIN = re.compile(
    _PRE
    + r"(oggetto(?:[ \t]+(?:dell['’]?[ \t]*|della[ \t]+|del[ \t]+)?(?:appalto|affidamento|fornitura|gara|procedura|contratto))?"
    r"|descrizione(?:[ \t]+(?:della|del|dell['’]?)[ \t]*(?:fornitura|servizio|appalto|bene|prodotto))?"
    r"|oggetto[ \t]+e[ \t]+importo)"
    r"[ \t]*[:\-–.]?[ \t]*"
)
HEADING_VERB = re.compile(_PRE + r"(fornitura[ \t]+di|acquisto[ \t]+di)[ \t]*")


def norm(s: str) -> str:
    """Minuscolo, senza accenti, spazi compattati (per confronti e ricerche)."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s.lower()).strip()


def _clean(s: str, limit: int) -> str:
    s = re.sub(r"[-_=.]{4,}", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0]
    return cut + "…"


# Intestazioni di moduli/modelli che non descrivono la fornitura (colonne dei fogli Excel, ecc.)
BOILER = re.compile(
    r"(?i)parte[ \t]+riservata[ \t]+(?:all['’]?[ \t]*amministrazione|al[ \t]+concorrente)"
    r"(?:[ \t]+non[ \t]+modificabile[ \t]+dal[ \t]+concorrente)?"
    r"|compilabile[ \t]+dal[ \t]+concorrente|da[ \t]+compilare[ \t]+a[ \t]+cura[ \t]+del[ \t]+concorrente"
)


def _strip_boiler(text: str) -> str:
    t = BOILER.sub(" ", text)
    return re.sub(r"(?:\s*\|\s*){2,}", " | ", t)


def _starts_mid_sentence(snippet: str) -> bool:
    return bool(re.match(r"[a-zàèéìòù]{1,4}\b", snippet)) and norm(snippet).split(" ")[0] in {
        "della", "del", "dell", "di", "e", "dei", "delle", "degli", "per", "il", "la", "le", "lo"}


def _table_items(text: str, max_items: int = 8) -> str:
    """Fogli Excel di offerta: righe 'N | articolo | ...' sotto un'intestazione 'ARTICOLO RICHIESTO'."""
    items, in_table = [], False
    for line in text.splitlines():
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if not cells:
            continue
        if not in_table:
            if "ARTICOLO RICHIESTO" in line.upper() or ("POS" in cells[0].upper() and "DESCRIZIONE" in line.upper()):
                in_table = True
            continue
        if len(cells) >= 2 and re.fullmatch(r"\d{1,3}(?:[.,]0+)?", cells[0]) and len(cells[1]) > 3:
            items.append(cells[1])
            if len(items) >= max_items:
                break
    return "Articoli richiesti: " + "; ".join(items) if items else ""


def find_scopo(titolo: str, descrizione: str | None, texts: list[str], limit: int = 600) -> str:
    texts = [_strip_boiler(t) for t in texts]
    for text in texts:
        items = _table_items(text)
        if items:
            return _clean(items, limit)
    for heading in (HEADING_MAIN, HEADING_VERB):
        for text in texts:
            for m in heading.finditer(text):
                tail = text[m.end(): m.end() + limit * 2]
                if heading is HEADING_MAIN:
                    first, _, rest = tail.partition("\n")
                    # resto del titolo ("..., quantitativi e requisiti"): non e' ancora il contenuto
                    if re.match(r"[ \t]*[,;a-zàèéìòù]", first) and len(first) < 150 and rest.strip():
                        tail = rest
                head = m.group(1)
                snippet = (head + " " + tail) if heading is HEADING_VERB else tail
                snippet = _clean(snippet, limit)
                if len(snippet) >= 40 and not _starts_mid_sentence(snippet):
                    return snippet
    for text in texts:
        t = _clean(text, limit)
        if len(t) >= 80:
            return t
    if descrizione and len(descrizione) > 15 and "vedi" not in norm(descrizione)[:6]:
        return _clean(descrizione, limit)
    return _clean(titolo, limit)


def build_excerpt(texts: list[str], limit: int = 3000) -> str:
    """Estratto per la ricerca: l'inizio dei documenti utili, in ordine di priorita'."""
    out, used = [], 0
    for t in (_strip_boiler(x) for x in texts):
        if used >= limit:
            break
        chunk = re.sub(r"\s+", " ", t).strip()[: limit - used]
        out.append(chunk)
        used += len(chunk) + 1
    return "\n".join(out)
