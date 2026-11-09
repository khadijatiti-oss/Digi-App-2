"""Bilan et CPC simplifiés (démonstration uniquement), calculés depuis la balance.

Usage : python bilan_cpc.py output/balance_generale.csv output/
Ces états ne sont pas des états de synthèse légaux.
"""
import sys
from decimal import Decimal
from pathlib import Path
import pandas as pd

ZERO = Decimal("0.00")
CPC_PRODUITS = [("Ventes de marchandises", ["711"])]
CPC_CHARGES = [("Achats de marchandises", ["6111"]),
    ("Variation des stocks de marchandises", ["6114"]),
    ("Autres charges externes", ["612", "613", "614"]),
    ("Dotations d'exploitation (amortissements)", ["619"])]
BILAN_ACTIF = [("Immobilisations corporelles (brut)", ["235"]), ("Amortissements cumulés", ["283"]),
    ("Stock de marchandises", ["311"]), ("Clients et comptes rattachés", ["342"]),
    ("État - TVA récupérable", ["3455"]), ("Banques", ["514"]), ("Caisse", ["516"])]
BILAN_PASSIF = [("Capital social", ["111"]), ("Fournisseurs et comptes rattachés", ["441"]),
    ("État - TVA facturée (à reverser)", ["4455"])]


def charger_balance(chemin):
    b = pd.read_csv(chemin, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    for col in ["total_debit", "total_credit", "solde_debiteur", "solde_crediteur"]:
        b[col] = b[col].map(Decimal)
    return b


def _somme(b, prefixes, colonne):
    masque = b["compte"].apply(lambda c: any(c.startswith(p) for p in prefixes))
    return sum(b.loc[masque, colonne], ZERO)


def calculer_cpc(b):
    lignes, produits, charges = [], ZERO, ZERO
    for nom, prefixes in CPC_PRODUITS:
        montant = _somme(b, prefixes, "solde_crediteur") - _somme(b, prefixes, "solde_debiteur")
        lignes.append(("PRODUIT", nom, montant)); produits += montant
    for nom, prefixes in CPC_CHARGES:
        montant = _somme(b, prefixes, "solde_debiteur") - _somme(b, prefixes, "solde_crediteur")
        lignes.append(("CHARGE", nom, montant)); charges += montant
    resultat = produits - charges
    lignes.extend([("TOTAL", "Total des produits", produits), ("TOTAL", "Total des charges", charges),
                   ("RESULTAT", "Résultat (bénéfice + / perte -)", resultat)])
    return pd.DataFrame(lignes, columns=["type", "rubrique", "montant"]), resultat


def calculer_bilan(b, resultat):
    lignes, actif, passif = [], ZERO, ZERO
    for nom, prefixes in BILAN_ACTIF:
        montant = _somme(b, prefixes, "solde_debiteur") - _somme(b, prefixes, "solde_crediteur")
        lignes.append(("ACTIF", nom, montant)); actif += montant
    for nom, prefixes in BILAN_PASSIF:
        montant = _somme(b, prefixes, "solde_crediteur") - _somme(b, prefixes, "solde_debiteur")
        lignes.append(("PASSIF", nom, montant)); passif += montant
    lignes.append(("PASSIF", "Résultat de l'exercice (bénéfice + / perte -)", resultat)); passif += resultat
    lignes.extend([("TOTAL", "Total actif", actif), ("TOTAL", "Total passif", passif)])
    return pd.DataFrame(lignes, columns=["cote", "rubrique", "montant"]), actif == passif


def main(chemin_balance, dossier_sortie):
    out = Path(dossier_sortie); out.mkdir(parents=True, exist_ok=True)
    balance = charger_balance(chemin_balance)
    cpc, resultat = calculer_cpc(balance)
    bilan, equilibre = calculer_bilan(balance, resultat)
    cpc.to_csv(out / "cpc_simplifie.csv", index=False, encoding="utf-8-sig")
    bilan.to_csv(out / "bilan_simplifie.csv", index=False, encoding="utf-8-sig")
    return cpc, bilan, equilibre


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "output/balance_generale.csv"
    dst = sys.argv[2] if len(sys.argv) > 2 else "output"
    cpc, bilan, ok = main(src, dst)
    print("CPC SIMPLIFIÉ\n", cpc.to_string(index=False))
    print("\nBILAN SIMPLIFIÉ\n", bilan.to_string(index=False))
    print("Actif = Passif :", "OUI" if ok else "NON - ERREUR")
