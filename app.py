"""Interface Streamlit locale pour le prototype DigiCompta.

Lancer avec : streamlit run app.py
Démo pédagogique uniquement : ne pas charger de factures réelles ou sensibles.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from bilan_cpc import calculer_bilan, calculer_cpc
from etats_comptables import balance_generale, grand_livre, verifier_balance
from moteur_ecritures import generer_journal

ROOT = Path(__file__).resolve().parent
SAMPLE_CSV = ROOT / "data" / "factures_atlas.csv"

st.set_page_config(page_title="DigiCompta CGNC", page_icon="📒", layout="wide")
st.title("📒 DigiCompta CGNC")
st.caption("Prototype pédagogique — données fictives, états simplifiés, non certifié.")
st.warning(
    "N’importez pas de factures réelles ni de données personnelles dans cette démo. "
    "Les écritures et états doivent être vérifiés par une personne qualifiée."
)


def make_csv_download(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8-sig")


def load_sample() -> pd.DataFrame:
    if not SAMPLE_CSV.exists():
        result = subprocess.run(
            [sys.executable, str(ROOT / "generate_dataset.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout or "Échec de génération du jeu de démonstration.")
    return pd.read_csv(SAMPLE_CSV, dtype=str, keep_default_na=False, encoding="utf-8-sig")


with st.sidebar:
    st.header("Données")
    source = st.radio("Source des factures", ["Jeu fictif de démonstration", "Importer un CSV"])
    uploaded = None
    if source == "Importer un CSV":
        uploaded = st.file_uploader("Choisir un fichier CSV", type=["csv"])
        st.caption("Format attendu : les colonnes du fichier factures_atlas.csv.")

try:
    if source == "Importer un CSV":
        if uploaded is None:
            st.info("Importez un CSV pour commencer. Vous pouvez aussi sélectionner le jeu fictif dans le menu latéral.")
            st.stop()
        invoices = pd.read_csv(uploaded, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    else:
        invoices = load_sample()
except Exception as exc:
    st.error(f"Impossible de charger les factures : {exc}")
    st.stop()

required_columns = {
    "facture_id", "type", "date_facture", "tiers_nom", "tiers_ice", "categorie",
    "quantite", "prix_unitaire_ht", "taux_tva", "total_ttc_facture",
}
missing = sorted(required_columns - set(invoices.columns))
if missing:
    st.error("Colonnes manquantes dans le CSV : " + ", ".join(missing))
    st.stop()

try:
    journal_propose, controles = generer_journal(invoices)
except Exception as exc:
    st.error(f"Le fichier n’a pas pu être traité. Vérifiez les dates et les montants. Détail : {exc}")
    st.stop()

invoice_ids = list(invoices["facture_id"].drop_duplicates())
if "digicompta_validated_ids" not in st.session_state:
    st.session_state.digicompta_validated_ids = set()
# Remove stale selections after changing the uploaded dataset.
st.session_state.digicompta_validated_ids.intersection_update(invoice_ids)

valid_ids = st.session_state.digicompta_validated_ids
journal = journal_propose.copy()
if not journal.empty:
    journal["statut"] = journal["facture_id"].map(lambda fid: "VALIDEE" if fid in valid_ids else "PROPOSEE")

valid_controls = controles[controles["facture_id"].isin(valid_ids)] if not controles.empty else controles
accepted_count = len(valid_ids.intersection(set(controles.loc[controles["resultat"] != "REJETEE", "facture_id"]))) if not controles.empty else 0
st.subheader("Aperçu")
c1, c2, c3 = st.columns(3)
c1.metric("Factures détectées", f"{len(invoice_ids)}")
c2.metric("Factures validées", f"{accepted_count} / {len(invoice_ids)}")
c3.metric("Écritures proposées", f"{len(journal_propose)} lignes")

if not controles.empty:
    with st.expander("Contrôles des factures"):
        st.dataframe(controles, use_container_width=True, hide_index=True)

invoice_tab, journal_tab, balance_tab, reports_tab = st.tabs(
    ["Validation", "Journal", "Grand livre & balance", "CPC & bilan"]
)

with invoice_tab:
    st.write("Examinez les contrôles, puis sélectionnez les factures dont vous approuvez les écritures.")
    rejected = set(controles.loc[controles["resultat"] == "REJETEE", "facture_id"]) if not controles.empty else set()
    selectable = [fid for fid in invoice_ids if fid not in rejected]
    selected = st.multiselect(
        "Factures approuvées",
        options=selectable,
        default=[fid for fid in selectable if fid in valid_ids],
        help="Seules les factures sélectionnées alimentent les rapports.",
    )
    left, right = st.columns(2)
    if left.button("Valider la sélection", type="primary"):
        st.session_state.digicompta_validated_ids = set(selected)
        st.rerun()
    if right.button("Tout annuler"):
        st.session_state.digicompta_validated_ids = set()
        st.rerun()
    if not journal_propose.empty:
        details = journal_propose[journal_propose["facture_id"].isin(selected)]
        st.dataframe(details, use_container_width=True, hide_index=True)
    else:
        st.info("Aucune écriture n’a été générée. Vérifiez les contrôles ci-dessus.")

approved_journal = journal[journal["statut"] == "VALIDEE"].copy() if not journal.empty else journal
with journal_tab:
    st.subheader("Journal des factures validées")
    if approved_journal.empty:
        st.info("Validez une ou plusieurs factures pour afficher le journal.")
    else:
        st.dataframe(approved_journal, use_container_width=True, hide_index=True)
        st.download_button("Télécharger le journal CSV", make_csv_download(approved_journal),
                           "journal_valide.csv", "text/csv")

with balance_tab:
    st.subheader("Grand livre et balance des factures validées")
    if approved_journal.empty:
        st.info("Validez une ou plusieurs factures pour calculer les états.")
    else:
        gl = grand_livre(approved_journal)
        balance = balance_generale(approved_journal)
        ok_mouvements, ok_soldes = verifier_balance(balance)
        st.success("Balance équilibrée" if ok_mouvements and ok_soldes else "Attention : balance non équilibrée")
        gl_tab, trial_tab = st.tabs(["Grand livre", "Balance générale"])
        with gl_tab:
            st.dataframe(gl, use_container_width=True, hide_index=True)
            st.download_button("Télécharger le grand livre CSV", make_csv_download(gl),
                               "grand_livre.csv", "text/csv")
        with trial_tab:
            st.dataframe(balance, use_container_width=True, hide_index=True)
            st.download_button("Télécharger la balance CSV", make_csv_download(balance),
                               "balance_generale.csv", "text/csv")

with reports_tab:
    st.subheader("CPC et bilan simplifiés")
    st.caption("Ces états sont calculés uniquement à partir des factures validées. Ils n’intègrent pas d’à-nouveaux, d’inventaire ni d’écritures complémentaires.")
    if approved_journal.empty:
        st.info("Validez une ou plusieurs factures pour afficher les états.")
    else:
        balance = balance_generale(approved_journal)
        cpc, resultat = calculer_cpc(balance)
        bilan, equilibre = calculer_bilan(balance, resultat)
        st.metric("Résultat simplifié (MAD)", f"{resultat:,.2f}")
        left, right = st.columns(2)
        with left:
            st.markdown("**CPC simplifié**")
            st.dataframe(cpc, use_container_width=True, hide_index=True)
            st.download_button("Télécharger le CPC CSV", make_csv_download(cpc), "cpc_simplifie.csv", "text/csv")
        with right:
            st.markdown("**Bilan simplifié**")
            st.dataframe(bilan, use_container_width=True, hide_index=True)
            st.info("Équilibré" if equilibre else "Non équilibré : les écritures d’ouverture et de clôture ne sont pas incluses dans cette démo.")
            st.download_button("Télécharger le bilan CSV", make_csv_download(bilan), "bilan_simplifie.csv", "text/csv")
