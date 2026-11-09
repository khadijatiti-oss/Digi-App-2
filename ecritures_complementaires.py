cmup = s["val"] / s["qte"] if s["qte"] > 0 else ZERO
        lignes.append(dict(designation=des, qte_ouverture=s["qte_ouverture"], qte_achetee=s["achetee"],
                           qte_vendue=s["vendue"], qte_finale=s["qte"], cmup=arrondi(cmup),
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
