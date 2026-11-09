"""Génère des factures PDF fictives pour tester l'import et l'OCR."""
import sys
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from xml.sax.saxutils import escape
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import parametres_atlas as P

CENT = Decimal("0.01")
STYLES = getSampleStyleSheet()
NORMAL = ParagraphStyle("n", parent=STYLES["Normal"], fontName="Helvetica", fontSize=9.5, leading=13)
GRAS = ParagraphStyle("g", parent=NORMAL, fontName="Helvetica-Bold")
TITRE = ParagraphStyle("t", parent=STYLES["Title"], fontName="Helvetica-Bold", fontSize=18, alignment=0)
PETIT = ParagraphStyle("p", parent=NORMAL, fontSize=8, textColor=colors.grey)
CELL = ParagraphStyle("c", parent=NORMAL, fontSize=9, leading=11)


def arrondi(x):
    return Decimal(x).quantize(CENT, rounding=ROUND_HALF_UP)


def nombre(x):
    return f"{Decimal(x):,.2f}".replace(",", " ").replace(".", ",")


def date_fr(iso):
    a, m, j = iso.split("-")
    return f"{j}/{m}/{a}"


def bloc_partie(titre, nom, ville, ice, if_):
    return [Paragraph(titre, GRAS), Paragraph(escape(nom), NORMAL), Paragraph(escape(ville), NORMAL),
            Paragraph(f"ICE : {ice} &nbsp;&nbsp; IF : {if_}", NORMAL), Spacer(1, 5 * mm)]


def construire_pdf(lignes, chemin):
    f = lignes.iloc[0]
    vente = f["type"] == "VENTE"
    numero = f["facture_id"] if vente else f["numero_fournisseur"]
    tiers = (f["tiers_nom"], f["tiers_ville"], f["tiers_ice"], f["tiers_if"])
    atlas = (P.NOM_SOCIETE, P.VILLE_SOCIETE, P.ICE_SOCIETE, P.IF_SOCIETE)
    emetteur, destinataire = (atlas, tiers) if vente else (tiers, atlas)
    doc = SimpleDocTemplate(str(chemin), pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=16*mm, bottomMargin=16*mm, title=f"Facture {numero}", author=emetteur[0])
    story = [Paragraph(f"FACTURE N° {numero}", TITRE), Paragraph(f"Date : {date_fr(f['date_facture'])}", NORMAL),
             Paragraph(f"Échéance : {date_fr(f['date_echeance'])}", NORMAL),
             Paragraph(f"Mode de règlement : {f['mode_paiement']}", NORMAL), Spacer(1, 6*mm)]
    story += bloc_partie("ÉMETTEUR", *emetteur) + bloc_partie("DESTINATAIRE", *destinataire)
    data, ht_taux = [["N°", "Désignation", "Qté", "P.U. HT (MAD)", "TVA %", "Total HT (MAD)"]], defaultdict(Decimal)
    for _, l in lignes.iterrows():
        q, pu, taux = Decimal(l["quantite"]), Decimal(l["prix_unitaire_ht"]), int(l["taux_tva"])
        ht = arrondi(q*pu); ht_taux[taux] += ht
        data.append([l["ligne"], Paragraph(escape(l["designation"]), CELL), l["quantite"], nombre(pu), str(taux), nombre(ht)])
    table = Table(data, colWidths=[9*mm,80*mm,12*mm,28*mm,12*mm,33*mm], repeatRows=1)
    table.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.5,colors.black),
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E8ECEF")),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),9),("ALIGN",(2,1),(-1,-1),"RIGHT"),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story += [table, Spacer(1, 6*mm)]
    total_ht = sum(ht_taux.values(), Decimal("0"))
    tva = {t: arrondi(ht*t/100) for t, ht in ht_taux.items()}
    tot = [["Total HT", nombre(total_ht)]] + [[f"TVA {t} %", nombre(v)] for t,v in sorted(tva.items())]
    tot.append(["Total TTC", nombre(total_ht+sum(tva.values(), Decimal("0")))])
    table_total = Table(tot, colWidths=[40*mm,38*mm], hAlign="RIGHT")
    table_total.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.5,colors.black),("FONTSIZE",(0,0),(-1,-1),9.5),
        ("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),("ALIGN",(1,0),(1,-1),"RIGHT")]))
    story += [table_total, Spacer(1, 8*mm), Paragraph("Facture fictive générée à des fins pédagogiques - projet DigiCompta CGNC. Montants en MAD.", PETIT)]
    doc.build(story)


def main(csv_path="data/factures_atlas.csv", dossier="data/factures_pdf"):
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    out = Path(dossier); out.mkdir(parents=True, exist_ok=True)
    for fid, lignes in df.groupby("facture_id", sort=False):
        construire_pdf(lignes, out / f"{fid}.pdf")
    return df["facture_id"].nunique()


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv)>1 else "data/factures_atlas.csv"
    dst = sys.argv[2] if len(sys.argv)>2 else "data/factures_pdf"
    print(f"{main(src,dst)} factures PDF générées dans {dst}/")
