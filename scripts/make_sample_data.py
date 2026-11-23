"""Genera dashboard/data/rdo.json con RDO FITTIZIE per provare la dashboard in locale.

Uso:  python scripts/make_sample_data.py && python -m http.server -d dashboard 8000
I dati sono inventati e marcati [ESEMPIO]; non provengono dal portale.
"""
import json
import time
from pathlib import Path

now = int(time.time())
D = 86400


def rdo(i, titolo, ente, valore, tipo, scopo, estratto, scad_giorni, visto_giorni, descrizione=""):
    return {
        "id": f"esempio{i:03d}", "numero": str(9000000 + i), "titolo": f"[ESEMPIO] {titolo}", "ente": ente,
        "valore": valore, "tipo": tipo, "categorie": "", "pubblicata": now - visto_giorni * D,
        "scadenza": now + scad_giorni * D, "descrizione": descrizione, "cig": f"ESEMPIO{i:03d}",
        "criterio": "Minor prezzo", "scopo": scopo, "estratto": estratto, "docs_stato": "ok",
        "documenti": [{"titolo": "Capitolato.pdf", "formato": "pdf", "stato": "ok"}],
        "visto_il": now - visto_giorni * D, "url": "https://www.acquistinretepa.it/",
    }


items = [
    rdo(1, "Fornitura di arredi per parco", "COMUNE DI ESEMPIO", 18500, "Beni",
        "Fornitura di n. 12 panchine in acciaio zincato e n. 8 cestini portarifiuti per il parco comunale.",
        "Art. 1 Oggetto: panchine in acciaio zincato verniciato, cestini in lamiera forata, ancoraggio con tasselli. Consegna entro 45 giorni.", 9, 1),
    rdo(2, "Lavori di sostituzione recinzione scuola", "ISTITUTO COMPRENSIVO ESEMPIO", 42000, "Lavori",
        "Rimozione della recinzione esistente e posa di nuova recinzione in acciaio con cancello pedonale e carrabile.",
        "Capitolato: recinzione modulare altezza 2,00 m, pali in acciaio zincato a caldo, cancello scorrevole.", 5, 0),
    rdo(3, "Fornitura sonde ecografiche", "AZIENDA OSPEDALIERA ESEMPIO", 3687, "Beni",
        "Fornitura di n. 1 sonda ecografica compatibile con ecotomografo, con codice UDI.",
        "Dispositivo medico CND Z110402, codice UDI-DI, compatibile con ecotomografo.", 7, 0),
    rdo(4, "Armadi per archivio", "MINISTERO DI ESEMPIO", 9800, "Beni",
        "Fornitura di armadi metallici a due ante per l'archivio dell'ufficio.",
        "Armadi in lamiera d'acciaio verniciata, ripiani regolabili, serratura a chiave.", 12, 2),
    rdo(5, "Servizio di pulizia uffici", "COMUNE DI ESEMPIO", 61000, "Servizi",
        "Servizio di pulizia degli uffici comunali per 12 mesi.", "", 14, 3),
    rdo(6, "Carta per fotocopie", "MINISTERO DI ESEMPIO", 1150, "Beni",
        "Fornitura di carta per fotocopie A4 80 g.", "Risme da 500 fogli A4.", 3, 6),
    rdo(7, "Fornitura di scaffalature per ospedale", "ASL ESEMPIO", 14000, "Beni",
        "Fornitura di scaffalature metalliche per magazzino farmaci dell'ospedale.",
        "Scaffalature in acciaio per magazzino farmaceutico, portata 200 kg per ripiano.", 6, 1),
]
out = Path(__file__).resolve().parent.parent / "dashboard" / "data" / "rdo.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"generato": now, "totale": len(items), "rdo": items}, ensure_ascii=False), encoding="utf-8")
print("scritto", out)
