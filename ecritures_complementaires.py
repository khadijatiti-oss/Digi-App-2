"""Écritures complémentaires : ouverture, règlements, inventaire et amortissement.

  AN : écriture d'ouverture (bilan de départ)
  BQ / CA : règlements clients et fournisseurs (banque / caisse), à la date d'échéance
  OD : inventaire de fin de période (variation de stock) et dotation aux amortissements

Les factures dont l'échéance dépasse la date d'arrêté restent impayées (clients / fournisseurs).
"""
from decimal import Decimal

import pandas as pd

import parametres_atlas as P
from moteur_ecritures import ZERO, arrondi, calculer_facture
from plan_comptable import COMPTES, COMPTE_CLIENT, COMPTE_FOURNISSEUR

BANQUE, CAISSE = "5141", "5161"


def _l(piece, date, journal, ref, compte, libelle, debit=ZERO, credit=ZERO):
    return dict(piece=piece, date=date, journal=journal, facture_id=ref, compte=compte,
                intitule_compte=COMPTES[compte], libelle=libelle, debit=debit, credit=credit,
                statut="PROPOSEE")


def stock_ouverture():
    return sum((arrondi(Decimal(P.STOCK_OUVERTURE_QTE) * c)
                for c in P.COUT_UNITAIRE_OUVERTURE.values()), ZERO)


def ecritures_ouverture():
    stock = stock_ouverture()
    banque = (P.CAPITAL_SOCIAL + P.AMORTISSEMENT_CUMULE_OUVERTURE
              - P.IMMOBILISATION_BRUT - stock - P.CAISSE_OUVERTURE)
    if banque < 0:
        raise ValueError("Solde bancaire d'ouverture négatif : revoir parametres_atlas.py")
    d, p, lib = P.DATE_OUVERTURE, "AN-0001", "Écriture d'ouverture"
    return [
        _l(p, d, "AN", "OUVERTURE", "2355", lib, debit=P.IMMOBILISATION_BRUT),
        _l(p, d, "AN", "OUVERTURE", "3111", lib, debit=stock),
        _l(p, d, "AN", "OUVERTURE", BANQUE, lib, debit=banque),
        _l(p, d, "AN", "OUVERTURE", CAISSE, lib, debit=P.CAISSE_OUVERTURE),
        _l(p, d, "AN", "OUVERTURE", "1111", lib, credit=P.CAPITAL_SOCIAL),
        _l(p, d, "AN", "OUVERTURE", "2835", lib, credit=P.AMORTISSEMENT_CUMULE_OUVERTURE),
    ]


def ecritures_reglements(df, ids_ok):
    """Règlement de chaque facture à sa date d'échéance (si <= arrêté)."""
    regs, alertes = [], []
    for fid, g in df[df["facture_id"].isin(ids_ok)].groupby("facture_id", sort=False):
        f = g.iloc[0]
        ech = f["date_echeance"]
        if not ech or ech > P.DATE_ARRETE:
            continue
        ttc = calculer_facture(g)["total_ttc"]
        mode = f["mode_paiement"]
        if f["type"] == "ACHAT" and mode == "espèces" and ttc > P.PLAFOND_ESPECES_JOUR:
            alertes.append(f"{fid} : espèces de {ttc} MAD > plafond {P.PLAFOND_ESPECES_JOUR} "
                           f"-> règlement basculé en banque (plafond à vérifier)")
            mode = "virement"
        regs.append((max(ech, f["date_facture"]), fid, f["type"], mode, ttc, f["tiers_nom"]))
    regs.sort(key=lambda r: (r[0], r[1]))

    rows, cpt = [], {"BQ": 0, "CA": 0}
    for date, fid, typ, mode, ttc, tiers in regs:
        journal = "CA" if mode == "espèces" else "BQ"
        cpt[journal] += 1
        piece = f"{journal}-{cpt[journal]:04d}"
        tresor = CAISSE if journal == "CA" else BANQUE
        lib = f"Règlement {fid} - {tiers} ({mode})"
        if typ == "VENTE":
            rows += [_l(piece, date, journal, fid, tresor, lib, debit=ttc),
                     _l(piece, date, journal, fid, COMPTE_CLIENT, lib, credit=ttc)]
        else:
            rows += [_l(piece, date, journal, fid, COMPTE_FOURNISSEUR, lib, debit=ttc),
                     _l(piece, date, journal, fid, tresor, lib, credit=ttc)]
    return rows, alertes


def calculer_stock(df, ids_ok):
    """Stock final en quantités et en valeur (coût moyen unitaire pondéré, perpétuel)."""
    st = {}
    for des, cout in P.COUT_UNITAIRE_OUVERTURE.items():
        q0 = Decimal(P.STOCK_OUVERTURE_QTE)
        st[des] = dict(qte_ouverture=q0, achetee=ZERO, vendue=ZERO, qte=q0, val=q0 * cout)
    d = df[df["facture_id"].isin(ids_ok) & (df["categorie"] == "marchandises")].copy()
    d["ordre"] = d["type"].map({"ACHAT": 0, "VENTE": 1})
    d = d.sort_values(["date_facture", "ordre", "facture_id", "ligne"], kind="stable")
    alertes = []
    for _, r in d.iterrows():
        s = st.setdefault(r["designation"], dict(qte_ouverture=ZERO, achetee=ZERO, vendue=ZERO, qte=ZERO, val=ZERO))
        q, pu = Decimal(r["quantite"]), Decimal(r["prix_unitaire_ht"])
        if r["type"] == "ACHAT":
            s["qte"] += q
            s["val"] += q * pu
            s["achetee"] += q
        else:
            if s["qte"] < q:
                alertes.append(f"{r['facture_id']} : vente de {q} × {r['designation']} supérieure au stock ({s['qte']})")
            cmup = s["val"] / s["qte"] if s["qte"] > 0 else ZERO
            s["val"] -= q * cmup
            s["qte"] -= q
            s["vendue"] += q
    lignes = []
    for des, s in st.items():
        cmup = s["val"] / s["qte"] if s["qte"] > 0 else ZERO
        lignes.append(dict(designation=des, qte_ouverture=s["qte_ouverture"], qte_achetee=s["achetee"],
                           qte_vendue=s["vendue"], qte_finale=s["qte"], cmup=arrondi(cmu p),
                           valeur_finale=arrondi(s["val"])))
    inv = pd.DataFrame(lignes)
    return inv, sum(inv["valeur_finale"], ZERO), alertes


def ecritures_inventaire(df, ids_ok):
    inv, stock_final, alertes = calculer_stock(df, ids_ok)
    d = P.DATE_ARRETE
    stock_init = stock_ouverture()
    dotation = arrondi(P.IMMOBILISATION_BRUT * P.TAUX_AMORTISSEMENT_ANNUEL * P.MOIS_PERIODE / 12)
    rows = [
        _l("OD-0001", d, "OD", "INVENTAIRE", "6114", "Annulation du stock initial", debit=stock_init),
        _l("OD-0001", d, "OD", "INVENTAIRE", "3111", "Annulation du stock initial", credit=stock_init),
        _l("OD-0002", d, "OD", "INVENTAIRE", "3111", "Constatation du stock final", debit=stock_final),
        _l("OD-0002", d, "OD", "INVENTAIRE", "6114", "Constatation du stock final", credit=stock_final),
        _l("OD-0003", d, "OD", "AMORTISSEMENT", "6193", "Dotation aux amortissements (T1 2026)", debit=dotation),
        _l("OD-0003", d, "OD", "AMORTISSEMENT", "2835", "Dotation aux amortissements (T1 2026)", credit=dotation),
    ]
    return rows, inv, alertes
