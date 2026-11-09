"""Plan comptable simplifié CGNC/PCGE utilisé par DigiCompta.

Les comptes et intitulés doivent être vérifiés avec le référentiel en vigueur.
"""
COMPTES = {
    "3421": "Clients", "4411": "Fournisseurs", "4455": "État - TVA facturée",
    "34552": "État - TVA récupérable sur les charges", "7111": "Ventes de marchandises au Maroc",
    "6111": "Achats revendus de marchandises", "6131": "Locations et charges locatives",
    "6133": "Entretien et réparations", "6142": "Transports",
    "6145": "Frais postaux et frais de télécommunication", "1111": "Capital social",
    "2355": "Matériel informatique",
    "2835": "Amortissements du mobilier, matériel de bureau et aménagements divers",
    "3111": "Marchandises (stock)", "5141": "Banques", "5161": "Caisses",
    "6114": "Variation des stocks de marchandises",
    "6193": "Dotations d'exploitation aux amortissements des immobilisations corporelles",
}
CATEGORIE_VENTE = {"marchandises": "7111"}
CATEGORIE_ACHAT = {"marchandises": "6111", "loyer": "6131", "entretien": "6133",
                   "transport": "6142", "telecom": "6145"}
COMPTE_CLIENT = "3421"
COMPTE_FOURNISSEUR = "4411"
COMPTE_TVA_FACTUREE = "4455"
COMPTE_TVA_RECUPERABLE = "34552"
JOURNAL_VENTES = "VT"
JOURNAL_ACHATS = "AC"
TAUX_TVA_VALIDES = {0, 7, 10, 14, 20}
