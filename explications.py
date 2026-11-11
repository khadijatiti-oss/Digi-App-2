"""Explications en langage simple : impact d'une facture et détail d'une ligne du CPC ou du bilan.

Aide à répondre à deux questions : « qu'est-ce que cette facture a changé ? » et
« quelles factures composent ce chiffre ? ». Fonctions pures, sans Streamlit.
"""
from decimal import Decimal

import pandas as pd

import bilan_cpc as B

ZERO = Decimal("0.00")

# compte -> (où le voir, libellé simple, sens qui augmente le poste)
RUBRIQUES_COMPTE = {
    "3421": ("Bilan · actif", "Clients (ils vous doivent)", "debit"),
    "34552": ("Bilan · actif", "TVA à récupérer", "debit"),
    "4411": ("Bilan · passif", "Dette envers le fournisseur", "credit"),
    "4455": ("Bilan · passif", "TVA à reverser à l'État", "credit"),
    "7111": ("CPC · produits", "Ventes de marchandises", "credit"),
    "6111": ("CPC · charges", "Achats de marchandises", "debit"),
    "6131": ("CPC · charges", "Loyers", "debit"),
    "6133": ("CPC · charges", "Entretien et réparations", "debit"),
    "6142": ("CPC · charges", "Transports", "debit"),
    "6145": ("CPC · charges", "Téléphone et internet", "debit"),
    "5141": ("Bilan · actif", "Banque", "debit"),
    "5161": ("Bilan · actif", "Caisse", "debit"),
}

ORIGINES = {"OUVERTURE": "Écriture d'ouverture", "INVENTAIRE": "Inventaire de fin de période",
            "AMORTISSEMENT": "Amortissement de la période"}


def mad(x):
    return f"{Decimal(x):,.2f}".replace(",", " ").replace(".", ",") + " MAD"


def impact(detail, type_facture):
    """detail : lignes d'écriture d'une facture (compte, debit, credit). Retourne (phrase, lignes)
    où lignes = [(ce qui change, où le voir, montant signé)]."""
    par = {}
    for r in detail.itertuples():
        par[r.compte] = par.get(r.compte, ZERO) + r.debit - r.credit
    lignes = []
    for compte, net in par.items():
        ou, lib, sens = RUBRIQUES_COMPTE.get(compte, ("Autre", f"Compte {compte}", "debit"))
        lignes.append((lib, ou, float(net if sens == "debit" else -net)))
    lignes.sort(key=lambda l: (not l[1].startswith("CPC"), l[1]))

    ttc = abs(par.get("3421", par.get("4411", ZERO)))
    tva = abs(par.get("4455", par.get("34552", ZERO)))
    ht = ttc - tva
    if type_facture == "Vente":
        if tva > 0:
            phrase = (f"Facture de vente de {mad(ttc)}. Votre chiffre d'affaires augmente de {mad(ht)} hors taxes, "
                      f"la TVA de {mad(tva)} est à reverser à l'État, et le client vous doit {mad(ttc)}.")
        else:
            phrase = (f"Facture de vente de {mad(ttc)}, sans TVA. Votre chiffre d'affaires augmente de {mad(ht)} "
                      f"et le client vous doit {mad(ttc)}.")
    else:
        marchandises = par.get("6111", ZERO)
        services = sum((v for c, v in par.items() if c.startswith("6") and c != "6111"), ZERO)
        if tva > 0:
            phrase = (f"Facture d'achat de {mad(ttc)}. La TVA de {mad(tva)} est à récupérer "
                      f"et vous devez {mad(ttc)} au fournisseur.")
        else:
            phrase = f"Facture d'achat de {mad(ttc)}, sans TVA. Vous devez {mad(ttc)} au fournisseur."
        if marchandises > 0:
            phrase += (f" Les marchandises ({mad(marchandises)} hors taxes) ne pèsent sur le résultat qu'à mesure "
                       "qu'elles sont vendues : le coût des marchandises vendues est calculé en fin de période à partir du stock.")
        if services > 0:
            phrase += f" La charge de services de {mad(services)} hors taxes diminue votre résultat."
    return phrase, lignes


def rubriques():
    """Nom affiché -> (préfixes de comptes, sens). Reprend exactement les lignes du CPC et du bilan."""
    out = {}
    for nom, pref in B.CPC_PRODUITS:
        out[f"CPC · {nom}"] = (pref, "credit")
    for nom, pref in B.CPC_CHARGES:
        out[f"CPC · {nom}"] = (pref, "debit")
    for nom, pref in B.BILAN_ACTIF:
        out[f"Bilan · {nom}"] = (pref, "debit")
    for nom, pref in B.BILAN_PASSIF:
        out[f"Bilan · {nom}"] = (pref, "credit")
    return out


def detail_rubrique(j_val, prefixes, sens):
    """Les factures (et écritures de fin de période) qui composent une ligne du CPC ou du bilan.
    Les règlements sont regroupés avec leur facture : pour clients et fournisseurs, on voit le reste à payer."""
    masque = j_val["compte"].apply(lambda c: any(c.startswith(p) for p in prefixes))
    lignes = []
    for ref, g in j_val[masque].groupby("facture_id", sort=False):
        d, c = sum(g["debit"], ZERO), sum(g["credit"], ZERO)
        montant = d - c if sens == "debit" else c - d
        if montant == 0:
            continue
        lignes.append(dict(Origine=ORIGINES.get(ref, ref), Date=g["date"].min(),
                           Libellé=g["libelle"].iloc[0], Montant=montant))
    df = pd.DataFrame(lignes, columns=["Origine", "Date", "Libellé", "Montant"])
    df = df.sort_values(["Date", "Origine"]).reset_index(drop=True) if len(df) else df
    total = sum(df["Montant"], ZERO) if len(df) else ZERO
    df.loc[len(df)] = ["Total", "", "", total]
    return df, total
