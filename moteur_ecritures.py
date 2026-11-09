"""Moteur de génération des écritures comptables à partir des factures CSV.

Usage : python moteur_ecritures.py data/factures_atlas.csv output/
Les écritures générées sont proposées et doivent être validées par une personne.
"""
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import pandas as pd
from plan_comptable import (CATEGORIE_ACHAT, CATEGORIE_VENTE, COMPTE_CLIENT, COMPTE_FOURNISSEUR,
    COMPTE_TVA_FACTUREE, COMPTE_TVA_RECUPERABLE, COMPTES, JOURNAL_ACHATS, JOURNAL_VENTES,
    TAUX_TVA_VALIDES)

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def arrondi(x):
    return Decimal(x).quantize(CENT, rounding=ROUND_HALF_UP)


def charger_factures(chemin):
    return pd.read_csv(chemin, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def calculer_facture(lignes):
    ht_cat, ht_taux = defaultdict(Decimal), defaultdict(Decimal)
    for _, ligne in lignes.iterrows():
        ht = arrondi(Decimal(ligne["quantite"]) * Decimal(ligne["prix_unitaire_ht"]))
        ht_cat[ligne["categorie"]] += ht
        ht_taux[int(ligne["taux_tva"])] += ht
    tva_taux = {t: arrondi(ht * t / 100) for t, ht in ht_taux.items()}
    total_ht = sum(ht_cat.values(), ZERO)
    total_tva = sum(tva_taux.values(), ZERO)
    return dict(ht_cat=dict(ht_cat), tva_taux=tva_taux, total_ht=total_ht,
                total_tva=total_tva, total_ttc=total_ht + total_tva)


def controler_facture(lignes, calc):
    f = lignes.iloc[0]
    erreurs, avertissements = [], []
    if lignes["type"].nunique() > 1:
        erreurs.append("type de facture incohérent entre les lignes")
    table = CATEGORIE_VENTE if f["type"] == "VENTE" else CATEGORIE_ACHAT
    for categorie in calc["ht_cat"]:
        if categorie not in table:
            erreurs.append(f"catégorie inconnue : '{categorie}'")
    for taux in calc["tva_taux"]:
        if taux not in TAUX_TVA_VALIDES:
            erreurs.append(f"taux de TVA invalide : {taux}%")
    try:
        date.fromisoformat(f["date_facture"])
    except ValueError:
        erreurs.append(f"date invalide : '{f['date_facture']}'")
    if f["type"] not in ("VENTE", "ACHAT"):
        erreurs.append(f"type inconnu : '{f['type']}'")
    if not (f["tiers_ice"].isdigit() and len(f["tiers_ice"]) == 15):
        avertissements.append("ICE du tiers absent ou différent de 15 chiffres")
    if f["total_ttc_facture"] and arrondi(Decimal(f["total_ttc_facture"])) != calc["total_ttc"]:
        avertissements.append(f"TTC indiqué ({f['total_ttc_facture']}) différent du TTC recalculé ({calc['total_ttc']})")
    return erreurs, avertissements


def ecritures_facture(f, calc):
    libelle = f"{f['facture_id']} - {f['tiers_nom']}"
    lignes = []
    if f["type"] == "VENTE":
        lignes.append((COMPTE_CLIENT, libelle, calc["total_ttc"], ZERO))
        for categorie, ht in calc["ht_cat"].items():
            lignes.append((CATEGORIE_VENTE[categorie], libelle, ZERO, ht))
        if calc["total_tva"]:
            lignes.append((COMPTE_TVA_FACTUREE, libelle, ZERO, calc["total_tva"]))
    else:
        for categorie, ht in calc["ht_cat"].items():
            lignes.append((CATEGORIE_ACHAT[categorie], libelle, ht, ZERO))
        if calc["total_tva"]:
            lignes.append((COMPTE_TVA_RECUPERABLE, libelle, calc["total_tva"], ZERO))
        lignes.append((COMPTE_FOURNISSEUR, libelle, ZERO, calc["total_ttc"]))
    return lignes


def generer_journal(df):
    ecritures, controles = [], []
    ordre = df.groupby("facture_id", sort=False)["date_facture"].first().sort_values(kind="stable").index
    compteurs = {JOURNAL_VENTES: 0, JOURNAL_ACHATS: 0}
    for fid in ordre:
        lignes = df[df["facture_id"] == fid]
        f = lignes.iloc[0]
        calc = calculer_facture(lignes)
        erreurs, avertissements = controler_facture(lignes, calc)
        if erreurs:
            controles.append((fid, "REJETEE", " ; ".join(erreurs + avertissements)))
            continue
        journal = JOURNAL_VENTES if f["type"] == "VENTE" else JOURNAL_ACHATS
        compteurs[journal] += 1
        piece = f"{journal}-{compteurs[journal]:04d}"
        lignes_ec = ecritures_facture(f, calc)
        total_d = sum((d for _, _, d, _ in lignes_ec), ZERO)
        total_c = sum((c for _, _, _, c in lignes_ec), ZERO)
        if total_d != total_c:
            raise AssertionError(f"Pièce {piece} ({fid}) déséquilibrée : {total_d} ≠ {total_c}")
        for compte, libelle, debit, credit in lignes_ec:
            ecritures.append(dict(piece=piece, date=f["date_facture"], journal=journal, facture_id=fid,
                compte=compte, intitule_compte=COMPTES[compte], libelle=libelle,
                debit=debit, credit=credit, statut="PROPOSEE"))
        controles.append((fid, "AVERTISSEMENT" if avertissements else "OK", " ; ".join(avertissements)))
    return (pd.DataFrame(ecritures),
            pd.DataFrame(controles, columns=["facture_id", "resultat", "detail"]))


def main(chemin_csv, dossier_sortie):
    out = Path(dossier_sortie)
    out.mkdir(parents=True, exist_ok=True)
    journal, controles = generer_journal(charger_factures(chemin_csv))
    journal.to_csv(out / "journal.csv", index=False, encoding="utf-8-sig")
    controles.to_csv(out / "controles.csv", index=False, encoding="utf-8-sig")
    return journal, controles


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "data/factures_atlas.csv"
    dst = sys.argv[2] if len(sys.argv) > 2 else "output"
    journal, controles = main(src, dst)
    print(controles["resultat"].value_counts().to_string())
    print(f"{journal['piece'].nunique()} pièces, {len(journal)} lignes d'écriture")
    print(f"Total débit : {journal['debit'].sum()}")
    print(f"Total crédit : {journal['credit'].sum()}")
