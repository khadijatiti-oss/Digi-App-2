"""Génère un jeu fictif de 30 factures (15 ventes et 15 achats).

Usage : python generate_dataset.py
Toutes les entités, identifiants et données générés sont fictifs.
"""
import csv
import random
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

random.seed(2026)
CENT = Decimal("0.01")


def arrondi(x):
    return Decimal(x).quantize(CENT, rounding=ROUND_HALF_UP)


def identifiant(longueur):
    return "".join(random.choice("0123456789") for _ in range(longueur))


PRODUITS = [
    ("Ramette papier A4 80g (carton de 5)", 112.00, 78.00),
    ("Stylo bille bleu (boîte de 50)", 45.00, 31.00),
    ("Classeur à levier A4", 14.00, 9.50),
    ("Cartouche d'encre noire compatible", 245.00, 170.00),
    ("Agrafeuse professionnelle", 55.00, 38.00),
    ("Cahier 96 pages grands carreaux (lot de 10)", 65.00, 44.00),
    ("Chemises cartonnées (lot de 100)", 70.00, 48.00),
    ("Marqueurs tableau blanc (boîte de 12)", 96.00, 66.00),
    ("Clé USB 32 Go", 59.00, 40.00),
    ("Calculatrice scientifique", 120.00, 85.00),
]
CLIENTS = [("Librairie Al Majd SARL", "Rabat"), ("Papeterie Ennahda", "Salé"),
           ("Cabinet Benjelloun & Associés", "Rabat"), ("École Les Lauriers SARL", "Témara"),
           ("Clinique Al Amal SA", "Rabat"), ("Agence Immobilière Souissi SARL", "Rabat"),
           ("Cafétéria Bab Rabat SARL", "Rabat"), ("Association Nour pour l'Éducation", "Salé")]
FOURNISSEURS = [("Maghreb Papier SA", "Casablanca"),
               ("Distribution Bureautique du Nord SARL", "Tanger"),
               ("Tech Import Maroc SARL", "Casablanca"),
               ("Imprimerie Fès Cartonnage SARL", "Fès")]
SERVICES = [
    ("Immobilière Hassan SARL", "Rabat", "Loyer local commercial - janvier 2026", "loyer", 7500, 20, date(2026, 1, 5)),
    ("Immobilière Hassan SARL", "Rabat", "Loyer local commercial - février 2026", "loyer", 7500, 20, date(2026, 2, 5)),
    ("Télécom Maghreb Pro SA", "Rabat", "Abonnement internet et téléphonie - T1 2026", "telecom", 1850, 20, date(2026, 2, 12)),
    ("Transports Rapides du Bouregreg", "Salé", "Livraison marchandises Rabat-Casablanca", "transport", 900, 14, date(2026, 2, 20)),
    ("Clim Services Rabat SARL", "Rabat", "Entretien climatisation du magasin", "entretien", 1400, 20, date(2026, 3, 3)),
]
MODES = ["virement", "chèque", "effet", "espèces"]
TIERS = {}


def infos_tiers(nom, ville):
    if nom not in TIERS:
        TIERS[nom] = (identifiant(15), identifiant(8), ville)
    return TIERS[nom]


def date_aleatoire(debut=date(2026, 1, 5), fin=date(2026, 3, 28)):
    return debut + timedelta(days=random.randint(0, (fin - debut).days))


factures = []
for i, d in enumerate(sorted(date_aleatoire() for _ in range(15)), 1):
    nom, ville = random.choice(CLIENTS)
    lignes = [(des, "marchandises", random.randint(2, 40), pv, 20)
              for des, pv, _ in random.sample(PRODUITS, random.randint(1, 4))]
    factures.append(dict(id=f"FV-2026-{i:03d}", type="VENTE", date=d,
                         tiers=(nom, ville), ref="", lignes=lignes))
for d in sorted(date_aleatoire(date(2026, 1, 3), date(2026, 3, 20)) for _ in range(10)):
    nom, ville = random.choice(FOURNISSEURS)
    lignes = [(des, "marchandises", random.randint(20, 120), pa, 20)
              for des, _, pa in random.sample(PRODUITS, random.randint(1, 3))]
    factures.append(dict(type="ACHAT", date=d, tiers=(nom, ville),
                         ref=f"F{random.randint(1000, 9999)}", lignes=lignes))
for nom, ville, des, cat, ht, taux, d in SERVICES:
    factures.append(dict(type="ACHAT", date=d, tiers=(nom, ville), ref=f"F{random.randint(1000, 9999)}",
                         lignes=[(des, cat, 1, ht, taux)]))

achats = sorted((f for f in factures if f["type"] == "ACHAT"), key=lambda f: f["date"])
for i, f in enumerate(achats, 1):
    f["id"] = f"FA-2026-{i:03d}"

colonnes = ["facture_id", "type", "date_facture", "numero_fournisseur", "tiers_nom", "tiers_ice", "tiers_if",
            "tiers_ville", "ligne", "designation", "categorie", "quantite", "prix_unitaire_ht", "taux_tva",
            "mode_paiement", "date_echeance", "total_ttc_facture"]
out = Path(__file__).parent / "data"
out.mkdir(exist_ok=True)
with (out / "factures_atlas.csv").open("w", newline="", encoding="utf-8-sig") as fh:
    writer = csv.DictWriter(fh, fieldnames=colonnes)
    writer.writeheader()
    for f in sorted(factures, key=lambda x: (x["type"] != "VENTE", x["id"])):
        ice, ifiscal, ville = infos_tiers(*f["tiers"])
        ht_par_taux = defaultdict(Decimal)
        for _, _, q, pu, taux in f["lignes"]:
            ht_par_taux[taux] += arrondi(Decimal(q) * Decimal(str(pu)))
        ttc = sum(ht + arrondi(ht * taux / 100) for taux, ht in ht_par_taux.items())
        echeance = f["date"] + timedelta(days=random.choice([0, 30, 60]))
        mode = random.choice(MODES)
        for n, (des, cat, q, pu, taux) in enumerate(f["lignes"], 1):
            writer.writerow(dict(facture_id=f["id"], type=f["type"], date_facture=f["date"].isoformat(),
                numero_fournisseur=f["ref"], tiers_nom=f["tiers"][0], tiers_ice=ice, tiers_if=ifiscal,
                tiers_ville=ville, ligne=n, designation=des, categorie=cat, quantite=q,
                prix_unitaire_ht=f"{pu:.2f}", taux_tva=taux, mode_paiement=mode,
                date_echeance=echeance.isoformat(), total_ttc_facture=f"{ttc:.2f}"))
print(f"{len(factures)} factures générées -> {out / 'factures_atlas.csv'}")
