"""Chaîne complète DigiCompta :
factures -> journal (factures) + ouverture + règlements + inventaire
         -> journal complet -> grand livre -> balance -> bilan et CPC simplifiés

Usage :  python run_all.py
"""
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pandas as pd

import bilan_cpc
import export_excel
import ecritures_complementaires as ec
from etats_comptables import balance_generale, grand_livre, verifier_balance
from moteur_ecritures import ZERO, charger_factures, generer_journal

SRC = "data/factures_atlas.csv"
OUT = Path("output")
OUT.mkdir(exist_ok=True)
ORDRE_JOURNAUX = {"AN": 0, "AC": 1, "VT": 2, "BQ": 3, "CA": 4, "OD": 5}

df = charger_factures(SRC)
j_fact, controles = generer_journal(df)
ids_ok = set(controles.loc[controles["resultat"] != "REJETEE", "facture_id"])

lignes_ouv = ec.ecritures_ouverture()
lignes_reg, alertes_reg = ec.ecritures_reglements(df, ids_ok)
lignes_inv, inventaire, alertes_stock = ec.ecritures_inventaire(df, ids_ok)

journal = pd.concat([j_fact, pd.DataFrame(lignes_ouv + lignes_reg + lignes_inv)], ignore_index=True)
journal["_j"] = journal["journal"].map(ORDRE_JOURNAUX)
journal = journal.sort_values(["date", "_j", "piece"], kind="stable").drop(columns="_j")

# --- contrôles ---
alertes = alertes_reg + alertes_stock
for piece, g in journal.groupby("piece"):
    assert g["debit"].sum() == g["credit"].sum(), f"Pièce {piece} déséquilibrée"
for compte, nom in [("5141", "Banque"), ("5161", "Caisse")]:
    par_jour = defaultdict(lambda: ZERO)
    for _, r in journal[journal["compte"] == compte].iterrows():
        par_jour[r["date"]] += r["debit"] - r["credit"]
    solde, mini = ZERO, None
    for jour in sorted(par_jour):
        solde += par_jour[jour]
        if mini is None or solde < mini[1]:
            mini = (jour, solde)
    if mini and mini[1] < 0:
        alertes.append(f"{nom} négative : {mini[1]} MAD au {mini[0]}")
    print(f"{nom} : solde minimum {mini[1]} MAD ({mini[0]}) | solde final {solde} MAD")

# --- sorties ---
journal.to_csv(OUT / "journal_complet.csv", index=False, encoding="utf-8-sig")
inventaire.to_csv(OUT / "inventaire_stock.csv", index=False, encoding="utf-8-sig")
pd.DataFrame({"alerte": alertes}).to_csv(OUT / "alertes.csv", index=False, encoding="utf-8-sig")
grand_livre(journal).to_csv(OUT / "grand_livre.csv", index=False, encoding="utf-8-sig")
bal = balance_generale(journal)
bal.to_csv(OUT / "balance_generale.csv", index=False, encoding="utf-8-sig")
cpc, bilan, equilibre = bilan_cpc.main(OUT / "balance_generale.csv", OUT)
export_excel.exporter(OUT / "etats_comptables.xlsx", journal, grand_livre(journal), bal, inventaire, alertes,
                      dict(periode="1er janvier au 31 mars 2026", valides=len(ids_ok), total=len(ids_ok)))

ok_m, ok_s = verifier_balance(bal)
pd.set_option("display.width", 200)
print(f"\n{journal['piece'].nunique()} pièces | {len(journal)} lignes | balance équilibrée : {ok_m and ok_s}")
print("\n", cpc.to_string(index=False))
print("\n", bilan.to_string(index=False))
print("\nActif = Passif :", equilibre)
print(f"\n{len(alertes)} alerte(s) :")
for a in alertes:
    print(" -", a)
