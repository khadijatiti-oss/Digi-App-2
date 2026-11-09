"""Hypothèses FICTIVES de départ d'Atlas Fournitures SARL (à adapter librement).

Tout ce qui n'est pas dans les 30 factures est défini ici : bilan d'ouverture,
stock de départ, amortissement. Le solde bancaire d'ouverture est calculé
automatiquement pour que l'écriture d'ouverture soit équilibrée.
"""
from decimal import Decimal

DATE_OUVERTURE = "2026-01-01"
DATE_ARRETE = "2026-03-31"          # arrêté de la situation intermédiaire (T1 2026)

CAPITAL_SOCIAL = Decimal("200000.00")
IMMOBILISATION_BRUT = Decimal("60000.00")             # 2355 Matériel informatique
AMORTISSEMENT_CUMULE_OUVERTURE = Decimal("12000.00")  # 2835
TAUX_AMORTISSEMENT_ANNUEL = Decimal("0.20")           # linéaire sur 5 ans
MOIS_PERIODE = 3
CAISSE_OUVERTURE = Decimal("5000.00")

# Stock de départ : même quantité pour chaque produit, valorisé à ce coût unitaire HT
STOCK_OUVERTURE_QTE = 60
COUT_UNITAIRE_OUVERTURE = {
    "Ramette papier A4 80g (carton de 5)": Decimal("78.00"),
    "Stylo bille bleu (boîte de 50)": Decimal("31.00"),
    "Classeur à levier A4": Decimal("9.50"),
    "Cartouche d'encre noire compatible": Decimal("170.00"),
    "Agrafeuse professionnelle": Decimal("38.00"),
    "Cahier 96 pages grands carreaux (lot de 10)": Decimal("44.00"),
    "Chemises cartonnées (lot de 100)": Decimal("48.00"),
    "Marqueurs tableau blanc (boîte de 12)": Decimal("66.00"),
    "Clé USB 32 Go": Decimal("40.00"),
    "Calculatrice scientifique": Decimal("85.00"),
}

# Règle à vérifier : plafond de paiement en espèces par jour et par fournisseur
PLAFOND_ESPECES_JOUR = Decimal("5000.00")

# Identité fictive d'Atlas Fournitures (utilisée sur les factures PDF et pour reconnaître
# si une facture est une vente (Atlas émet) ou un achat (Atlas reçoit))
NOM_SOCIETE = "Atlas Fournitures SARL"
ICE_SOCIETE = "001234567000089"
IF_SOCIETE = "12345678"
VILLE_SOCIETE = "Rabat"
