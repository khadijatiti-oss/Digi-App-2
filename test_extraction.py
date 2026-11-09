"""Tests de l'import PDF : les PDF générés puis relus doivent redonner EXACTEMENT les mêmes
données et les mêmes écritures que le CSV d'origine.

Lancer :  python test_extraction.py      (ou : pytest test_extraction.py)
"""
import tempfile
from decimal import Decimal
from pathlib import Path

import pandas as pd

import generer_factures_pdf
from etats_comptables import balance_generale
from extracteur_pdf import extraire_dossier
from moteur_ecritures import charger_factures
from pipeline import construire

CSV = Path(__file__).parent / "data" / "factures_atlas.csv"
COLS = ["type", "date_facture", "tiers_nom", "tiers_ice", "tiers_if", "tiers_ville", "ligne", "designation",
        "categorie", "quantite", "prix_unitaire_ht", "taux_tva", "mode_paiement", "date_echeance",
        "total_ttc_facture"]
NUMERIQUES = ["ligne", "quantite", "prix_unitaire_ht", "taux_tva", "total_ttc_facture"]


def _cle(df):
    df = df.copy()
    df["cle"] = df.apply(lambda r: r["facture_id"] if r["type"] == "VENTE" else r["numero_fournisseur"], axis=1)
    return df.sort_values(["cle", "ligne"], key=lambda s: s.astype(str)).reset_index(drop=True)


def _pdfs(dossier):
    generer_factures_pdf.main(CSV, dossier)
    return [(p.name, str(p)) for p in sorted(Path(dossier).glob("*.pdf"))]


def test_champs_identiques():
    with tempfile.TemporaryDirectory() as d:
        ext, rap = extraire_dossier(_pdfs(d))
    assert (rap["statut"] == "OK").all(), rap[rap["statut"] != "OK"]
    a, b = _cle(charger_factures(CSV)), _cle(ext)
    assert len(a) == len(b) == 71
    assert (a["cle"] == b["cle"]).all()
    for col in COLS:
        if col in NUMERIQUES:
            assert all(Decimal(x) == Decimal(y) for x, y in zip(a[col], b[col])), col
        else:
            assert (a[col] == b[col]).all(), f"colonne {col} différente"


def test_ecritures_identiques():
    with tempfile.TemporaryDirectory() as d:
        ext, _ = extraire_dossier(_pdfs(d))
    bal_csv = balance_generale(construire(charger_factures(CSV))["journal"])
    bal_pdf = balance_generale(construire(ext)["journal"])
    assert bal_csv.drop(columns="intitule_compte").equals(bal_pdf.drop(columns="intitule_compte"))


def test_pdf_illisible_signale():
    _, rap = extraire_dossier([("vide.pdf", b"ceci n'est pas un pdf")])
    assert rap.loc[0, "statut"] == "ERREUR"


def test_doublon_ignore():
    with tempfile.TemporaryDirectory() as d:
        pdfs = _pdfs(d)
        _, rap = extraire_dossier(pdfs + [("copie.pdf", pdfs[0][1])])
    assert (rap["statut"] == "DOUBLON").sum() == 1


def test_designation_inconnue_a_classer():
    with tempfile.TemporaryDirectory() as d:
        df = charger_factures(CSV)
        f = df[df["facture_id"] == "FA-2026-002"].copy()  # loyer
        f["designation"] = "Prestation non identifiée"
        generer_factures_pdf.construire_pdf(f, Path(d) / "x.pdf")
        ext, rap = extraire_dossier([("x.pdf", str(Path(d) / "x.pdf"))])
    assert rap.loc[0, "statut"] == "A_VERIFIER"
    _, controles = __import__("moteur_ecritures").generer_journal(ext)
    assert controles.loc[0, "resultat"] == "REJETEE"


def test_charger_pdf_et_melange():
    from import_factures import charger
    with tempfile.TemporaryDirectory() as d:
        pdfs = [(n, Path(p).read_bytes()) for n, p in _pdfs(d)]
    df, rap, libelle = charger(pdfs)
    assert df["facture_id"].nunique() == 30 and rap is not None and "PDF" in libelle
    try:
        charger(pdfs[:1] + [("x.csv", b"a,b\n1,2")])
        raise AssertionError("le mélange aurait dû être refusé")
    except ValueError:
        pass


if __name__ == "__main__":
    for nom, fn in list(globals().items()):
        if nom.startswith("test_"):
            fn()
            print("OK  ", nom)
    print("Tous les tests réussissent.")
