"""Interface DigiCompta CGNC (Streamlit), avec import CSV/Excel/PDF/images."""
from decimal import Decimal
from pathlib import Path
import subprocess
import sys
import pandas as pd
import streamlit as st
import bilan_cpc
import ocr
import parametres_atlas as P
from export_excel import construire_classeur
from etats_comptables import balance_generale, grand_livre, verifier_balance
from import_factures import charger
from pipeline import construire

ROOT = Path(__file__).resolve().parent
DEFAULT = ROOT / "data" / "factures_atlas.csv"
st.set_page_config(page_title="DigiCompta CGNC", page_icon="📒", layout="wide")


def mad(x):
    return f"{x:,.2f}".replace(",", " ").replace(".", ",") + " MAD"


def affichage(df):
    d = df.copy()
    for c in d.columns:
        if len(d) and isinstance(d[c].iloc[0], Decimal):
            d[c] = d[c].astype(float)
    return d


def telecharger(df, nom, cle):
    st.download_button("⬇️ Télécharger en CSV", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=nom, mime="text/csv", key=cle)


def charger_demo():
    if not DEFAULT.exists():
        result = subprocess.run([sys.executable, str(ROOT / "generate_dataset.py")], cwd=ROOT,
                                capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError(result.stderr or result.stdout or "Échec de génération du jeu de démonstration")
    return DEFAULT.read_bytes()


st.title("📒 DigiCompta CGNC")
st.caption("Prototype académique : états simplifiés, non certifiés.")
st.warning("Utilisez uniquement des données fictives dans cette démo. Vérifiez manuellement les factures OCR.")
with st.sidebar:
    st.header("Import des factures")
    fichiers = st.file_uploader("PDF, scans/photos, CSV ou Excel", type=["pdf", "png", "jpg", "jpeg", "tif", "tiff", "csv", "xlsx"], accept_multiple_files=True)
    st.caption("Sans fichier, le jeu fictif est utilisé. Les scans nécessitent Tesseract installé sur le serveur.")
    photo = st.camera_input("Ou prendre une photo")
    st.caption("Tesseract : " + ("✅ disponible" if ocr.disponible() else "❌ indisponible"))

entree = [(f.name, f.getvalue()) for f in (fichiers or [])]
if photo is not None:
    entree.append(("photo_camera.jpg", photo.getvalue()))
a_importer = bool(entree)
if not a_importer:
    entree = [("factures_atlas.csv", charger_demo())]
try:
    df, rapport, nom_source = charger(entree)
except Exception as exc:
    st.error(f"Import impossible : {exc}")
    st.stop()
if df.empty:
    st.error("Aucune facture exploitable. Consultez le rapport d'extraction.")
    if rapport is not None:
        st.dataframe(rapport, width="stretch", hide_index=True)
    st.stop()
if not a_importer:
    nom_source = "Jeu fictif Atlas Fournitures"
signature = tuple((n, len(c)) for n, c in entree)
if st.session_state.get("signature") != signature:
    st.session_state.signature = signature
    st.session_state.valides = set()

hors = sorted(set(df.loc[(df.date_facture != "") & ((df.date_facture < P.DATE_OUVERTURE) | (df.date_facture > P.DATE_ARRETE)), "facture_id"]))
if hors:
    st.warning(f"Factures hors période ({P.DATE_OUVERTURE} au {P.DATE_ARRETE}) : {', '.join(hors[:6])}")
base = construire(df, set())
ids_ok = base["ids_ok"]
t_import, t_valid, t_etats = st.tabs(["1. Import et contrôles", "2. Validation", "3. États comptables"])
with t_import:
    st.subheader(f"Source : {nom_source}")
    a,b,c = st.columns(3)
    a.metric("Lignes importées", len(df)); b.metric("Factures", df.facture_id.nunique())
    c.metric("Factures rejetées", int((base["controles"].resultat == "REJETEE").sum()))
    if rapport is not None:
        st.markdown("**Rapport d'extraction**")
        st.dataframe(rapport, width="stretch", hide_index=True)
    st.markdown("**Contrôles comptables**")
    st.dataframe(base["controles"], width="stretch", hide_index=True)
    with st.expander("Détail des lignes importées"):
        st.dataframe(df, width="stretch", hide_index=True)

with t_valid:
    pieces = base["journal"][base["journal"].journal.isin(["AC", "VT"])]
    resume = (pieces.groupby(["facture_id", "piece", "date", "journal"], sort=False)
              .agg(total_ttc=("debit", "sum"), libelle=("libelle", "first")).reset_index())
    if resume.empty:
        st.info("Aucune écriture de facture exploitable.")
    else:
        resume["tiers"] = resume.libelle.str.split(" - ", n=1).str[-1]
        resume["type"] = resume.journal.map({"VT":"Vente", "AC":"Achat"})
        resume = resume.sort_values(["date", "piece"]).reset_index(drop=True)
        c1,c2,_ = st.columns([1,1,4])
        if c1.button("✅ Tout valider"):
            st.session_state.valides = set(ids_ok); st.rerun()
        if c2.button("↩️ Tout annuler"):
            st.session_state.valides = set(); st.rerun()
        table = pd.DataFrame({"Valider": resume.facture_id.isin(st.session_state.valides), "Pièce":resume.piece,
            "Facture":resume.facture_id,"Date":resume.date,"Type":resume.type,"Tiers":resume.tiers,
            "Total TTC":resume.total_ttc.astype(float)})
        edite = st.data_editor(table, hide_index=True, width="stretch",
            disabled=["Pièce","Facture","Date","Type","Tiers","Total TTC"],
            column_config={"Total TTC":st.column_config.NumberColumn(format="%.2f")}, key="validation_table")
        st.session_state.valides = set(table.loc[edite["Valider"].values,"Facture"])
        choix = st.selectbox("Détail de l'écriture", resume.facture_id.tolist())
        st.dataframe(affichage(pieces[pieces.facture_id == choix][["piece","date","compte","intitule_compte","debit","credit"]]), width="stretch", hide_index=True)
        note = base["controles"].set_index("facture_id").loc[choix,"detail"]
        if note: st.warning(note)

with t_etats:
    res = construire(df, st.session_state.valides)
    j = res["journal"]
    valide = j[j.statut == "VALIDEE"]
    bal = balance_generale(valide)
    cpc, resultat = bilan_cpc.calculer_cpc(bal)
    bilan, eq_bilan = bilan_cpc.calculer_bilan(bal, resultat)
    ok_m, ok_s = verifier_balance(bal)
    total_actif = bilan.loc[bilan.rubrique == "Total actif", "montant"].iloc[0]
    if not st.session_state.valides:
        st.info("Aucune facture validée : l'ouverture et les écritures de période restent visibles.")
    a,b,c,d = st.columns(4)
    a.metric("Factures validées", f"{len(st.session_state.valides)} / {len(res['ids_ok'])}")
    b.metric("Résultat simplifié", mad(resultat)); c.metric("Total actif", mad(total_actif))
    d.metric("Balance équilibrée", "✅ Oui" if ok_m and ok_s and eq_bilan else "❌ Non")
    classeur = construire_classeur(valide, grand_livre(valide), bal, res["inventaire"], res["alertes"],
        dict(periode=f"du {P.DATE_OUVERTURE} au {P.DATE_ARRETE}", valides=len(st.session_state.valides), total=len(res["ids_ok"])))
    st.download_button("📊 Export Excel", classeur, "etats_comptables_digicompta.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
    tabs = st.tabs(["Journal","Grand livre","Balance","CPC","Bilan","Inventaire","Alertes"])
    with tabs[0]:
        st.dataframe(affichage(valide), width="stretch", hide_index=True); telecharger(valide,"journal_complet.csv","j")
    with tabs[1]:
        gl = grand_livre(valide)
        if not gl.empty:
            comptes = gl[["compte","intitule_compte"]].drop_duplicates()
            compte = st.selectbox("Compte", comptes.apply(lambda r:f"{r.compte} - {r.intitule_compte}",axis=1).tolist())
            st.dataframe(affichage(gl[gl.compte.astype(str)==compte.split(" - ")[0]]),width="stretch",hide_index=True)
        telecharger(gl,"grand_livre.csv","gl")
    with tabs[2]:
        st.dataframe(affichage(bal),width="stretch",hide_index=True); telecharger(bal,"balance_generale.csv","bal")
    with tabs[3]:
        st.dataframe(affichage(cpc),width="stretch",hide_index=True); telecharger(cpc,"cpc_simplifie.csv","cpc")
    with tabs[4]:
        st.dataframe(affichage(bilan),width="stretch",hide_index=True); telecharger(bilan,"bilan_simplifie.csv","bil")
    with tabs[5]:
        st.dataframe(affichage(res["inventaire"]),width="stretch",hide_index=True); telecharger(res["inventaire"],"inventaire_stock.csv","inv")
    with tabs[6]:
        if res["alertes"]:
            for alerte in res["alertes"]: st.warning(alerte)
        else: st.success("Aucune alerte.")
