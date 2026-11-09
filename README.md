# DigiCompta CGNC

Prototype académique de traitement comptable de factures marocaines (CGNC/PCGE), avec données fictives. Il calcule des écritures proposées, un grand livre, une balance générale, ainsi que des états simplifiés. **Ce projet n'est pas un logiciel comptable ou fiscal certifié.** Faites vérifier les comptes et règles fiscales par une personne qualifiée avant tout usage réel.

## État actuel

Le dépôt contient les modules Python de base pour générer un jeu de données fictif, proposer les écritures de factures, puis calculer le grand livre, la balance et les états simplifiés. Il ne contient pas encore l'interface web décrite dans le projet initial (`app.py` / Streamlit), le pipeline complet avec validations, ni les modules d'écritures complémentaires (ouverture, règlements et inventaire). Les rapports CSV sont générés localement et ne sont pas suivis dans Git.

## Prérequis et lancement

Python 3.10+ recommandé.

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell : .venv\Scripts\Activate.ps1
pip install -r requirements.txt

python generate_dataset.py
python moteur_ecritures.py data/factures_atlas.csv output/
python etats_comptables.py output/journal.csv output/
python bilan_cpc.py output/balance_generale.csv output/
```

Les sorties seront créées dans `output/`. Le moteur produit des écritures au statut `PROPOSEE`; ce dépôt ne fournit pas encore d'écran permettant de les valider. `bilan_cpc.py` calcule un bilan et un CPC simplifiés à partir de la balance.

## Fichiers principaux

- `generate_dataset.py` — génère 30 factures fictives dans `data/factures_atlas.csv`.
- `plan_comptable.py` — comptes et correspondance catégories/comptes.
- `moteur_ecritures.py` — contrôles et génération des écritures proposées.
- `etats_comptables.py` — grand livre et balance générale.
- `bilan_cpc.py` — CPC et bilan simplifiés.
- `requirements.txt` — dépendances Python.

## Données et limites

Les données générées sont fictives. Les états sont pédagogiques et incomplets : notamment, ils ne constituent pas des états de synthèse légaux et n'incluent pas tous les traitements fiscaux/comptables. Les comptes, taux de TVA et règles applicables doivent être vérifiés au regard des textes marocains en vigueur. N'utilisez pas de factures réelles ou de données personnelles dans cette version de démonstration.

## Suite prévue

1. Ajouter les modules d'écritures complémentaires et le pipeline de validation.
2. Créer l'interface web, ses tests automatisés et les instructions de déploiement.
3. Ajouter séparément la démo HTML du navigateur et documenter ses dépendances et limites.

Toutes les sociétés et informations du jeu de démonstration sont fictives.
