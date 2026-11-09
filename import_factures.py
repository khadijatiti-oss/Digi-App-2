"""Import des factures PDF/image, CSV ou Excel vers le schéma DigiCompta."""
import io
import pandas as pd
from extracteur_pdf import EXT_IMAGES, extraire_dossier

COLONNES_REQUISES = {"facture_id", "type", "date_facture", "tiers_nom", "tiers_ice", "ligne", "designation",
                     "categorie", "quantite", "prix_unitaire_ht", "taux_tva", "mode_paiement",
                     "date_echeance", "total_ttc_facture"}


def lire_tableau(contenu, nom):
    if nom.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(contenu), dtype=str).fillna("")
    return pd.read_csv(io.BytesIO(contenu), dtype=str, keep_default_na=False, encoding="utf-8-sig")


def charger(fichiers):
    """fichiers: liste (nom, bytes); retourne DataFrame, rapport éventuel, libellé."""
    docs = (".pdf",) + EXT_IMAGES
    documents = [(n, c) for n, c in fichiers if n.lower().endswith(docs)]
    tableaux = [(n, c) for n, c in fichiers if not n.lower().endswith(docs)]
    if documents and tableaux:
        raise ValueError("Importez soit des PDF/images, soit un seul tableau CSV/Excel.")
    if len(tableaux) > 1:
        raise ValueError("Un seul fichier CSV ou Excel à la fois.")
    if documents:
        df, rapport = extraire_dossier(documents)
        return df, rapport, f"{len(documents)} document(s) PDF/image"
    if not tableaux:
        raise ValueError("Aucun fichier fourni.")
    nom, contenu = tableaux[0]
    try:
        df = lire_tableau(contenu, nom)
    except Exception as exc:
        raise ValueError(f"Impossible de lire le fichier : {exc}") from exc
    manquantes = COLONNES_REQUISES - set(df.columns)
    if manquantes:
        raise ValueError("Colonnes manquantes : " + ", ".join(sorted(manquantes)))
    return df, None, nom
