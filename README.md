# DigiCompta CGNC - Digi-App-2

Prototype académique marocain de traitement comptable (CGNC/PCGE), avec données fictives. Il propose des écritures, permet leur validation manuelle, et produit des états simplifiés. **Ce n'est pas un logiciel comptable ou fiscal certifié.**

## Lancer l'application

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell : .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

L'interface accepte CSV/Excel, PDF texte, PDF scannés et images. Les scans exigent Tesseract installé en plus des paquets Python (sur Streamlit Community Cloud, `packages.txt` demande Tesseract et les données de langue française). Le jeu fictif est généré automatiquement si `data/factures_atlas.csv` n'existe pas.

Pour générer les factures PDF de test :

```bash
python generer_factures_pdf.py
python simuler_scans.py
```

Tests disponibles : `python test_extraction.py` et `python test_ocr.py`. Le second nécessite Tesseract. Vérifiez systématiquement les champs extraits et les écritures, surtout pour les scans.

## Modules

`app.py` (Streamlit), `import_factures.py` (routage des imports), `extracteur_pdf.py` (PDF/images vers lignes), `ocr.py` (Tesseract), `pipeline.py` (journal complet et statuts), `ecritures_complementaires.py` (ouverture, règlements et inventaire), `export_excel.py` (exports), ainsi que le moteur et le plan comptable.

Les validations ne sont pas persistées dans une base de données. Les états sont simplifiés, et les paramètres comptables/fiscaux doivent être validés par un professionnel. N'utilisez que des données fictives dans cette démo.
