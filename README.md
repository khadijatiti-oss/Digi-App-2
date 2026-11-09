# DigiCompta CGNC

Prototype académique de traitement comptable de factures marocaines (CGNC/PCGE), avec données fictives. Le projet comprend un moteur Python de génération d'écritures proposées et une interface locale Streamlit pour les examiner, les valider et consulter des états simplifiés.

> **Avertissement :** DigiCompta est un prototype pédagogique, pas un logiciel comptable ou fiscal certifié. Les comptes et règles doivent être vérifiés par une personne qualifiée. N'importez pas de factures réelles ou de données personnelles dans cette démo.

## Lancer l'interface web locale

Python 3.10+ recommandé.

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell : .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

L'application s'ouvre dans le navigateur. Elle démarre avec un jeu de démonstration fictif généré automatiquement. Vous pouvez également importer un CSV respectant le schéma `factures_atlas.csv`.

## Fonctionnalités actuelles

- Génération des écritures proposées à partir des factures CSV, avec contrôles et statut de validation manuelle.
- Interface pour approuver ou annuler les factures traitées.
- Consultation et téléchargement CSV du journal validé, du grand livre et de la balance.
- Affichage et téléchargement d'un CPC et d'un bilan simplifiés.

Les rapports sont calculés à partir des factures validées seulement. Les écritures d'ouverture, règlements et inventaire ne sont pas encore intégrés à l'interface; le bilan peut donc ne pas être équilibré. Les validations de l'interface sont conservées dans la session Streamlit, pas dans une base de données.

## Structure

- `app.py` — interface web locale Streamlit.
- `generate_dataset.py` — génère un jeu fictif de 30 factures sous `data/factures_atlas.csv`.
- `plan_comptable.py` — comptes et correspondance catégories/comptes.
- `moteur_ecritures.py` — contrôles et génération des écritures proposées.
- `etats_comptables.py` — grand livre et balance générale.
- `bilan_cpc.py` — CPC et bilan simplifiés.
- `requirements.txt` — dépendances Python.

## Exécution en ligne de commande

```bash
python generate_dataset.py
python moteur_ecritures.py data/factures_atlas.csv output/
python etats_comptables.py output/journal.csv output/
python bilan_cpc.py output/balance_generale.csv output/
```

Les sorties locales sont enregistrées dans `output/`, ignoré par Git.

## Limites et prochaines étapes

Le projet ne gère pas encore la persistance des validations, les écritures d'ouverture/règlements/inventaire, les tests automatisés, l'authentification ni le stockage sécurisé des documents. Les états sont incomplets et ne sont pas destinés à un usage légal ou fiscal. Toute donnée de démonstration doit rester fictive.
