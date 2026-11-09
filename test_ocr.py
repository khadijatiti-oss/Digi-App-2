"""Tests de l'OCR : factures scannées (simulées) relues puis comparées au CSV d'origine.

Nécessite Tesseract (avec la langue française pour les accents) ; sinon les tests sont ignorés.
Lancer :  python test_ocr.py      (ou : pytest test_ocr.py)
"""
import random
import tempfile
from pathlib import Path

import pdfplumber

import generer_factures_pdf
import ocr
import simuler_scans
from extracteur_pdf import extraire_dossier
from moteur_ecritures import charger_factures

CSV = Path(__file__).parent / "data" / "factures_atlas.csv"
# factures choisies pour leurs difficultés : quantité illisible, milliers, ligne unique, 3 lignes...
FACTURES = ["FV-2026-001", "FV-2026-003", "FA-2026-002", "FA-2026-012", "FA-2026-014"]
COLS = ["type", "date_facture", "tiers_nom", "tiers_ice", "tiers_if", "designation", "categorie",
        "quantite", "prix_unitaire_ht", "taux_tva", "mode_paiement", "date_echeance", "total_ttc_facture"]


def _cle(df):
    d = df.copy()
    d["cle"] = d.apply(lambda r: r["facture_id"] if r["type"] == "VENTE" else r["numero_fournisseur"], axis=1)
    return d


def test_scans_corrects():
    if not ocr.disponible():
        print("SKIP test_scans_corrects : Tesseract absent")
        return
    orig = charger_factures(CSV)
    with tempfile.TemporaryDirectory() as d:
        pdfs, scans = Path(d) / "pdf", Path(d) / "scans"
        pdfs.mkdir()
        for fid in FACTURES:
            generer_factures_pdf.construire_pdf(orig[orig["facture_id"] == fid], pdfs / f"{fid}.pdf")
        simuler_scans.main(str(pdfs), str(scans))
        ext, rap = extraire_dossier([(f.name, str(f)) for f in sorted(scans.iterdir())])
    assert (rap["statut"] == "A_VERIFIER").all(), rap       # OCR : toujours à vérifier
    assert (~rap["detail"].str.contains("TTC lu")).all(), rap
    o, e = _cle(orig[orig["facture_id"].isin(FACTURES)]), _cle(ext)
    assert set(o["cle"]) == set(e["cle"])
    for k, g in o.groupby("cle"):
        h = e[e["cle"] == k]
        assert len(g) == len(h), k
        for c in COLS:
            assert list(g.sort_values("ligne")[c]) == list(h.sort_values("ligne")[c]), (k, c)


def test_facture_reelle_almansour():
    """Facture réelle d'un fournisseur (photo) : Atlas est le client -> ACHAT."""
    if not ocr.disponible():
        print("SKIP test_facture_reelle_almansour : Tesseract absent")
        return
    chemin = Path(__file__).parent / "data" / "exemples" / "facture_almansour_F2025-1107.png"
    ext, rap = extraire_dossier([(chemin.name, str(chemin))])
    assert rap.loc[0, "statut"] == "A_VERIFIER", rap
    assert len(ext) == 5 and set(ext["type"]) == {"ACHAT"}
    f = ext.iloc[0]
    assert f["numero_fournisseur"] == "F2025/1107" and f["tiers_nom"].startswith("Al-Mansour")
    assert f["date_facture"] == "2025-11-07" and f["date_echeance"] == "2025-11-22"
    assert f["mode_paiement"] == "virement" and f["tiers_if"] == "12457890"
    assert f["total_ttc_facture"] == "1512.00" and set(ext["categorie"]) == {"marchandises"}
    assert [r for r in zip(ext["quantite"], ext["prix_unitaire_ht"])] == [
        ("10", "65.00"), ("5", "8.00"), ("20", "12.00"), ("10", "15.00"), ("10", "18.00")]


def test_tesseract_absent_message():
    import os
    ancien = os.environ.get("TESSERACT_CMD")
    os.environ["TESSERACT_CMD"] = "/chemin/inexistant/tesseract"
    try:
        from PIL import Image
        try:
            ocr.lire_images([Image.new("L", (100, 100), 255)])
            raise AssertionError("une erreur était attendue")
        except RuntimeError as e:
            assert "Tesseract" in str(e)
    finally:
        if ancien is None:
            del os.environ["TESSERACT_CMD"]
        else:
            os.environ["TESSERACT_CMD"] = ancien


if __name__ == "__main__":
    for nom, fn in list(globals().items()):
        if nom.startswith("test_"):
            fn()
            print("OK  ", nom)
    print("Tests OCR terminés.")
