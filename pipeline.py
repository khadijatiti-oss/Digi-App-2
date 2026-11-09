"""Pipeline réutilisable : factures -> journal complet (avec statuts de validation).

Règle de validation (utilisée par l'interface) :
  - les pièces de factures (AC / VT) restent PROPOSEE tant que l'utilisateur ne les a pas validées ;
  - l'ouverture, les règlements et l'inventaire sont générés uniquement à partir des
    factures VALIDÉES et sont marqués VALIDEE (ils en dérivent automatiquement).
"""
from collections import defaultdict

import pandas as pd

import ecritures_complementaires as ec
from moteur_ecritures import ZERO, generer_journal

ORDRE_JOURNAUX = {"AN": 0, "AC": 1, "VT": 2, "BQ": 3, "CA": 4, "OD": 5}


def alertes_tresorerie(journal):
    alertes = []
    for compte, nom in [("5141", "Banque"), ("5161", "Caisse")]:
        par_jour = defaultdict(lambda: ZERO)
        for _, r in journal[journal["compte"] == compte].iterrows():
            par_jour[r["date"]] += r["debit"] - r["credit"]
        solde = ZERO
        for jour in sorted(par_jour):
            solde += par_jour[jour]
            if solde < 0:
                alertes.append(f"{nom} négative : {solde} MAD au {jour}")
                break
    return alertes


def construire(df, ids_valides=None):
    """Retourne un dict : journal, controles, inventaire, alertes, ids_ok.

    ids_valides=None -> toutes les factures non rejetées sont considérées validées.
    """
    j_fact, controles = generer_journal(df)
    ids_ok = set(controles.loc[controles["resultat"] != "REJETEE", "facture_id"])
    ids_val = ids_ok if ids_valides is None else ids_ok & set(ids_valides)

    if len(j_fact):
        j_fact["statut"] = j_fact["facture_id"].map(lambda f: "VALIDEE" if f in ids_val else "PROPOSEE")

    ouverture = ec.ecritures_ouverture()
    reglements, alertes_reg = ec.ecritures_reglements(df, ids_val)
    inv_rows, inventaire, alertes_stock = ec.ecritures_inventaire(df, ids_val)
    comp = pd.DataFrame(ouverture + reglements + inv_rows)
    comp["statut"] = "VALIDEE"

    journal = pd.concat([j_fact, comp], ignore_index=True)
    journal["_j"] = journal["journal"].map(ORDRE_JOURNAUX)
    journal = journal.sort_values(["date", "_j", "piece"], kind="stable").drop(columns="_j")

    valide = journal[journal["statut"] == "VALIDEE"]
    alertes = alertes_reg + alertes_stock + alertes_tresorerie(valide)
    return dict(journal=journal, controles=controles, inventaire=inventaire,
                alertes=alertes, ids_ok=ids_ok)
