"""Scelta dei documenti da leggere ed estrazione del testo (PDF, Word, Excel).

Non fa OCR: un PDF scansionato risulta 'vuoto' e viene segnalato, non perso.
I file firmati .p7m non sono letti (stato 'non_supportato').
"""
from __future__ import annotations

import io
import re
import zipfile

# Documenti che quasi mai descrivono l'oggetto della fornitura
SKIP = re.compile(
    r"dgue|espd|patto.?d?i?.?integrit|duvri|tracciabilit|schema.?d?i?.?offerta|dichiarazion|"
    r"autocertificazion|presa.?visione|request\.xml|informativa|privacy|modulo|istanza|"
    r"come.?compilare|facsimile|fac-simile|garanzia|polizza|pagamento|bollo|avcpass|anticorruzione",
    re.I,
)
# Documenti che descrivono l'oggetto
PRIORITY = re.compile(
    r"capitolat|fabbisogn|caratteristic|specifich|disciplinar|relazione|descrizion|progetto|"
    r"computo|elenco.?prezzi|lettera.?(di)?.?invito|condizioni|requisiti.?tecnici|scheda.?tecnica|allegato.?a\b",
    re.I,
)
SUPPORTED = {"pdf", "docx", "xlsx", "txt"}


def rank_documents(docs: list[dict], max_docs: int = 6) -> list[dict]:
    """Ordina i documenti per utilita' e scarta quelli burocratici/duplicati."""
    seen: set[str] = set()
    scored = []
    for d in docs:
        title = f"{d.get('titolo', '')} {d.get('descrizione', '')}"
        key = (d.get("titolo") or "").strip().lower()
        if key in seen:
            continue
        seen.add(key)
        if SKIP.search(title):
            continue
        fmt = d.get("formato") or key.rsplit(".", 1)[-1]
        score = (2 if PRIORITY.search(title) else 0) + (1 if fmt == "pdf" else 0)
        scored.append((-score, len(scored), d))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [d for _, _, d in scored[:max_docs]]


def extract_text(name: str, data: bytes, max_pages: int = 40, max_chars: int = 60_000) -> tuple[str, str]:
    """Ritorna (testo, stato). Stati: ok | vuoto | non_supportato | errore."""
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    try:
        if ext == "pdf":
            text = _pdf(data, max_pages)
        elif ext == "docx":
            text = _docx(data)
        elif ext == "xlsx":
            text = _xlsx(data)
        elif ext == "txt":
            text = data.decode("utf-8", errors="replace")
        else:
            return "", "non_supportato"
    except Exception:  # file corrotto o protetto: non deve fermare l'esecuzione
        return "", "errore"
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) < 30:
        return "", "vuoto"
    return text[:max_chars], "ok"


def _pdf(data: bytes, max_pages: int) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts = []
    for page in reader.pages[:max_pages]:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _docx(data: bytes) -> str:
    import docx

    d = docx.Document(io.BytesIO(data))
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            parts.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n".join(parts)


def _xlsx(data: bytes) -> str:
    import openpyxl

    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise ValueError("xlsx non valido")
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    parts = []
    for ws in wb.worksheets[:3]:
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i > 300:
                break
            cells = [str(c) for c in row if c not in (None, "")]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)
