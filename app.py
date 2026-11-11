"""Interface DigiCompta CGNC (Streamlit).

Lancer :  streamlit run app.py

Flux : 1) Import des factures  ->  2) Validation des écritures proposées  ->  3) États comptables
"""
from decimal import Decimal
from pathlib import Path

import pandas as pd
import streamlit as st

import bilan_cpc
import ocr
import parametres_atlas as P
from export_excel import construire_classeur
from etats_comptables import balance_generale, grand_livre, verifier_balance
from explications import detail_rubrique, impact, rubriques
from import_factures import charger
from pipeline import construire

DEFAULT = Path(__file__).parent / "data" / "factures_atlas.csv"

st.set_page_config(page_title="DigiCompta CGNC", page_icon="📒", layout="wide")


# ---------- utilitaires ----------
def mad(x):
    return f"{x:,.2f}".replace(",", " ").replace(".", ",") + " MAD"


def pour_affichage(df):
    """Decimal -> float, uniquement pour l'affichage (les exports restent exacts)."""
    d = df.copy()
    for c in d.columns:
        if len(d) and isinstance(d[c].iloc[0], Decimal):
            d[c] = d[c].astype(float)
    return d


def telecharger(df, nom, cle):
    st.download_button("⬇️ Télécharger en CSV", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=nom, mime="text/csv", key=cle)


# ---------- en-tête ----------
st.title("📒 DigiCompta CGNC")
st.caption("Prototype académique d'automatisation comptable (référentiel marocain CGNC/PCGE). "
           "Les états produits sont simplifiés et ne remplacent pas des états de synthèse légaux.")
with st.expander("Comment lire ces états ?"):
    st.markdown(
        "**Le chemin d'une facture.** Chaque facture validée devient une *écriture* : une ligne au débit et une au crédit, "
        "pour le même montant. Les écritures alimentent le **journal**, puis le **grand livre** (par compte), puis la "
        "**balance**, et enfin le **CPC** (ce que l'entreprise a gagné ou dépensé) et le **bilan** (ce qu'elle possède et "
        "ce qu'elle doit).\n\n"
        "**Retrouver une facture.** Dans l'onglet 2, « Impact de cette facture » explique en une phrase ce qu'elle change. "
        "Dans l'onglet 3, « Voir les factures derrière une ligne » liste les factures qui composent chaque chiffre.\n\n"
        "**Un résultat négatif** signifie une perte sur la période. **Une facture non validée ne compte nulle part.**")

# ---------- 1) import ----------
with st.sidebar:
    st.header("Import des factures")
    fichiers = st.file_uploader("Factures : PDF, scans/photos (png, jpg), CSV ou Excel",
                                type=["pdf", "png", "jpg", "jpeg", "csv", "xlsx"], accept_multiple_files=True)
    st.caption("Sans fichier, le jeu fictif d'Atlas Fournitures SARL (30 factures) est utilisé. "
               "Les scans et photos sont lus par OCR : les factures concernées sont toujours à vérifier.")
    photo = st.camera_input("Ou scannez une facture avec la caméra")
    st.caption("OCR (Tesseract) : " + ("✅ disponible" if ocr.disponible() else "❌ indisponible (voir README)"))


@st.cache_data(show_spinner="Lecture des factures...")
def charger_cache(entree):
    return charger(entree)


a_importer = bool(fichiers) or photo is not None
if a_importer:
    entree = [(f.name, f.getvalue()) for f in (fichiers or [])]
    if photo is not None:
        entree.append(("photo_camera.jpg", photo.getvalue()))
else:
    entree = [("factures_atlas.csv", DEFAULT.read_bytes())]
try:
    df, rapport_extraction, nom_source = charger_cache(entree)
except ValueError as e:
    st.error(str(e))
    st.stop()
if not a_importer:
    nom_source = "jeu fictif Atlas Fournitures (30 factures)"
signature = tuple((n, len(c)) for n, c in entree)

if df.empty:
    st.error("Aucune facture exploitable dans les fichiers importés.")
    if rapport_extraction is not None:
        st.dataframe(rapport_extraction, width="stretch", hide_index=True)
    st.stop()

if st.session_state.get("source") != signature:
    st.session_state.source = signature
    st.session_state.valides = set()
    st.session_state.version = 0
    st.session_state.kpi_last = None
    st.session_state.kpi_ref = None

hors = sorted(set(df.loc[(df["date_facture"] != "") & ((df["date_facture"] < P.DATE_OUVERTURE)
                                                         | (df["date_facture"] > P.DATE_ARRETE)), "facture_id"]))
if hors:
    st.warning(f"{len(hors)} facture(s) datée(s) hors de la période comptable ({P.DATE_OUVERTURE} au {P.DATE_ARRETE}) : "
               + ", ".join(hors[:6]) + ("..." if len(hors) > 6 else "")
               + ". Adaptez DATE_OUVERTURE et DATE_ARRETE dans parametres_atlas.py.")

base = construire(df, set())          # propositions, indépendantes de la validation
ids_ok = base["ids_ok"]

tab_import, tab_valid, tab_etats = st.tabs(["1. Import et contrôles", "2. Validation des écritures", "3. États comptables"])

with tab_import:
    st.subheader(f"Source : {nom_source}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Lignes importées", len(df))
    c2.metric("Factures", df["facture_id"].nunique())
    c3.metric("Factures rejetées", int((base["controles"]["resultat"] == "REJETEE").sum()))
    if rapport_extraction is not None:
        st.markdown("**Rapport d'extraction (PDF, scans, photos)**")
        rap = rapport_extraction.copy()
        rap["statut"] = rap["statut"].map({"OK": "✅ OK", "A_VERIFIER": "⚠️ À vérifier",
                                           "DOUBLON": "🔁 Doublon ignoré", "ERREUR": "❌ Erreur"})
        st.dataframe(rap, width="stretch", hide_index=True)
    st.markdown("**Contrôles automatiques** (ICE, catégories, TVA, total TTC)")
    ctrl = base["controles"].copy()
    ctrl["resultat"] = ctrl["resultat"].map({"OK": "✅ OK", "AVERTISSEMENT": "⚠️ Avertissement", "REJETEE": "❌ Rejetée"})
    st.dataframe(ctrl, width="stretch", hide_index=True)
    with st.expander("Voir les lignes de factures importées"):
        st.dataframe(df, width="stretch", hide_index=True)

# ---------- 2) validation ----------
with tab_valid:
    st.subheader("Écritures proposées")
    st.write("Cochez les factures dont vous approuvez l'écriture comptable. "
             "Seules les factures validées alimentent le grand livre, la balance, le bilan et le CPC.")

    pieces = base["journal"][base["journal"]["journal"].isin(["AC", "VT"])]
    resume = (pieces.groupby(["facture_id", "piece", "date", "journal"], sort=False)
              .agg(total_ttc=("debit", "sum"), lignes=("compte", "count"),
                   libelle=("libelle", "first")).reset_index())
    resume["tiers"] = resume["libelle"].str.split(" - ").str[1]
    resume["type"] = resume["journal"].map({"VT": "Vente", "AC": "Achat"})
    resume = resume.sort_values(["date", "piece"]).reset_index(drop=True)

    b1, b2, b3 = st.columns([1, 1, 4])
    if b1.button("✅ Tout valider"):
        st.session_state.valides = set(ids_ok)
        st.session_state.version += 1
        st.rerun()
    if b2.button("↩️ Tout annuler"):
        st.session_state.valides = set()
        st.session_state.version += 1
        st.rerun()

    table = pd.DataFrame({
        "Valider": resume["facture_id"].isin(st.session_state.valides),
        "Pièce": resume["piece"], "Facture": resume["facture_id"], "Date": resume["date"],
        "Type": resume["type"], "Tiers": resume["tiers"], "Total TTC": resume["total_ttc"].astype(float),
    })
    edite = st.data_editor(
        table, hide_index=True, width="stretch",
        disabled=["Pièce", "Facture", "Date", "Type", "Tiers", "Total TTC"],
        column_config={"Total TTC": st.column_config.NumberColumn(format="%.2f")},
        key=f"editeur_{st.session_state.version}")
    st.session_state.valides = set(table.loc[edite["Valider"].values, "Facture"])
    st.progress(len(st.session_state.valides) / max(len(ids_ok), 1),
                text=f"{len(st.session_state.valides)} facture(s) validée(s) sur {len(ids_ok)}")

    choix = st.selectbox("Voir le détail d'une écriture", resume["facture_id"].tolist())
    detail = pieces[pieces["facture_id"] == choix][["piece", "date", "compte", "intitule_compte", "debit", "credit"]]
    st.dataframe(pour_affichage(detail), width="stretch", hide_index=True)
    avert = base["controles"].set_index("facture_id").loc[choix, "detail"]
    if avert:
        st.warning(avert)

    st.markdown("#### Impact de cette facture")
    type_choix = resume.loc[resume["facture_id"] == choix, "type"].iloc[0]
    phrase, lignes_impact = impact(detail, type_choix)
    if choix not in st.session_state.valides:
        phrase += " Cette facture n'est pas encore validée : cochez-la pour qu'elle compte dans les états."
    st.info(phrase)
    st.dataframe(pd.DataFrame(lignes_impact, columns=["Ce qui change", "Où le voir", "Montant (MAD)"]),
                 width="stretch", hide_index=True,
                 column_config={"Montant (MAD)": st.column_config.NumberColumn(format="%+.2f")})

# ---------- 3) états ----------
with tab_etats:
    res = construire(df, st.session_state.valides)
    j_val = res["journal"][res["journal"]["statut"] == "VALIDEE"]
    bal = balance_generale(j_val)
    cpc, resultat = bilan_cpc.calculer_cpc(bal)
    bilan, equilibre = bilan_cpc.calculer_bilan(bal, resultat)
    ok_m, ok_s = verifier_balance(bal)
    total_actif = bilan.loc[bilan["rubrique"] == "Total actif", "montant"].iloc[0]

    if not st.session_state.valides:
        st.info("Aucune facture validée : seuls l'écriture d'ouverture et l'amortissement apparaissent. "
                "Validez des factures dans l'onglet 2.")

    cur = (resultat, total_actif)
    if st.session_state.get("kpi_last") != cur:
        st.session_state.kpi_ref = st.session_state.get("kpi_last")
        st.session_state.kpi_last = cur
    ref = st.session_state.get("kpi_ref")

    def variation(i):
        if ref is None or cur[i] == ref[i]:
            return None
        return ("+" if cur[i] > ref[i] else "-") + mad(abs(cur[i] - ref[i]))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Factures validées", f"{len(st.session_state.valides)} / {len(res['ids_ok'])}")
    m2.metric("Résultat (période)", mad(resultat), delta=variation(0))
    m3.metric("Total actif", mad(total_actif), delta=variation(1))
    m4.metric("Balance équilibrée", "✅ Oui" if ok_m and ok_s and equilibre else "❌ Non")

    classeur = construire_classeur(
        j_val, grand_livre(j_val), bal, res["inventaire"], res["alertes"],
        dict(periode=f"du {P.DATE_OUVERTURE} au {P.DATE_ARRETE}", valides=len(st.session_state.valides),
             total=len(res["ids_ok"])))
    st.download_button("📊 Exporter tous les états en Excel", classeur, "etats_comptables_digicompta.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")

    t_j, t_gl, t_b, t_cpc, t_bil, t_inv, t_al = st.tabs(
        ["Journal", "Grand livre", "Balance générale", "CPC", "Bilan", "Inventaire", "Alertes"])

    with t_j:
        q = st.text_input("Rechercher (n° de facture, tiers, compte, libellé)", key="rech_j")
        vue = j_val
        if q.strip():
            cols = j_val[["piece", "facture_id", "compte", "intitule_compte", "libelle"]].astype(str)
            vue = j_val[cols.apply(lambda c: c.str.contains(q.strip(), case=False, regex=False)).any(axis=1)]
            st.caption(f"{len(vue)} écriture(s) trouvée(s)")
        st.dataframe(pour_affichage(vue), width="stretch", hide_index=True)
        telecharger(j_val, "journal_complet.csv", "dl_j")

    with t_gl:
        gl = grand_livre(j_val)
        comptes = (gl[["compte", "intitule_compte"]].drop_duplicates()
                   .apply(lambda r: f"{r['compte']} - {r['intitule_compte']}", axis=1).tolist())
        compte = st.selectbox("Compte", comptes)
        st.caption("Solde progressif = débit - crédit : un nombre négatif signifie un solde créditeur.")
        st.dataframe(pour_affichage(gl[gl["compte"] == compte.split(" - ")[0]]),
                     width="stretch", hide_index=True)
        telecharger(gl, "grand_livre.csv", "dl_gl")

    with t_b:
        st.dataframe(pour_affichage(bal), width="stretch", hide_index=True)
        st.write(f"Total débit {mad(bal['total_debit'].sum())} | total crédit {mad(bal['total_credit'].sum())}")
        telecharger(bal, "balance_generale.csv", "dl_b")

    def detail_ligne(section, cle):
        rub = rubriques()
        options = [k for k in rub if k.startswith(section)]
        choix_l = st.selectbox("Voir les factures derrière une ligne", options, key=cle,
                               format_func=lambda k: k.split(" · ", 1)[1])
        prefixes, sens = rub[choix_l]
        d_l, _ = detail_rubrique(j_val, prefixes, sens)
        st.dataframe(pour_affichage(d_l), width="stretch", hide_index=True)
        if section == "Bilan" and any(p.startswith(("342", "441")) for p in prefixes):
            st.caption("Pour les clients et les fournisseurs, le montant est le reste à payer : les règlements sont déduits.")

    with t_cpc:
        st.dataframe(pour_affichage(cpc), width="stretch", hide_index=True)
        detail_ligne("CPC", "det_cpc")
        telecharger(cpc, "cpc_simplifie.csv", "dl_cpc")

    with t_bil:
        ca, cp = st.columns(2)
        ca.markdown("**Actif**")
        ca.dataframe(pour_affichage(bilan[(bilan["cote"] == "ACTIF") | (bilan["rubrique"] == "Total actif")]
                                    .drop(columns="cote")), width="stretch", hide_index=True)
        cp.markdown("**Passif**")
        cp.dataframe(pour_affichage(bilan[(bilan["cote"] == "PASSIF") | (bilan["rubrique"] == "Total passif")]
                                    .drop(columns="cote")), width="stretch", hide_index=True)
        detail_ligne("Bilan", "det_bil")
        telecharger(bilan, "bilan_simplifie.csv", "dl_bil")

    with t_inv:
        st.dataframe(pour_affichage(res["inventaire"]), width="stretch", hide_index=True)
        telecharger(res["inventaire"], "inventaire_stock.csv", "dl_inv")

    with t_al:
        if res["alertes"]:
            for a in res["alertes"]:
                st.warning(a)
        else:
            st.success("Aucune alerte.")
