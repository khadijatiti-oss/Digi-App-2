"""Export Excel des états comptables DigiCompta (openpyxl).

Le classeur contient des FORMULES (et non des valeurs figées) : la balance, le CPC, le bilan et
les contrôles se recalculent si le journal est modifié.

  Synthèse | Journal | Grand livre | Balance | CPC | Bilan | Inventaire | Alertes | Hypothèses

Dépendances de formules : Journal -> Balance -> CPC -> Bilan -> Synthèse.
"""
import io
from datetime import date, datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import bilan_cpc as B
import parametres_atlas as P

POLICE = "Arial"
FMT_MONTANT = '#,##0.00;-#,##0.00;"-"'
FMT_DATE = "dd/mm/yyyy"
BLEU = "1F3A5F"
F_ENTETE = PatternFill("solid", fgColor=BLEU)
F_TOTAL = PatternFill("solid", fgColor="E8ECEF")
F_SECTION = PatternFill("solid", fgColor="D6E4F0")
FINE = Side(style="thin", color="9AA5B1")
BORD = Border(top=FINE, bottom=FINE, left=FINE, right=FINE)


def _f(bold=False, color="000000", size=10, italic=False):
    return Font(name=POLICE, bold=bold, color=color, size=size, italic=italic)


def _entete(ws, colonnes, ligne=1):
    for j, nom in enumerate(colonnes, 1):
        c = ws.cell(row=ligne, column=j, value=nom)
        c.font, c.fill, c.border = _f(True, "FFFFFF"), F_ENTETE, BORD
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[ligne].height = 24


def _largeurs(ws, largeurs):
    for j, w in enumerate(largeurs, 1):
        ws.column_dimensions[get_column_letter(j)].width = w


def _cellule(ws, ref, valeur, fmt=None, gras=False, fond=None, couleur="000000", wrap=False):
    c = ws[ref]
    c.value = valeur
    c.font = _f(gras, couleur)
    c.border = BORD
    if fmt:
        c.number_format = fmt
    if fond:
        c.fill = fond
    if wrap:
        c.alignment = Alignment(wrap_text=True, vertical="top")
    return c


def _iso(d):
    return date.fromisoformat(d) if isinstance(d, str) else d


def _prefixe(plage_compte, plage_valeur, prefixes):
    """Formule : somme de plage_valeur pour les comptes commençant par un des préfixes."""
    return "+".join(
        f'SUMPRODUCT((LEFT({plage_compte},{len(p)})="{p}")*({plage_valeur}))' for p in prefixes)


# ----------------------------------------------------------------- feuilles de données
def _feuille_journal(wb, journal):
    ws = wb.create_sheet("Journal")
    _entete(ws, ["Pièce", "Date", "Journal", "Facture", "Compte", "Intitulé du compte", "Libellé",
                 "Débit (MAD)", "Crédit (MAD)", "Statut"])
    for i, r in enumerate(journal.itertuples(index=False), 2):
        vals = [r.piece, _iso(r.date), r.journal, r.facture_id, int(r.compte), r.intitule_compte,
                r.libelle, float(r.debit), float(r.credit), r.statut]
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=i, column=j, value=v)
            c.font, c.border = _f(), BORD
            if j == 2:
                c.number_format = FMT_DATE
            if j in (8, 9):
                c.number_format = FMT_MONTANT
    n = len(journal)
    t = n + 2
    ws.cell(row=t, column=1, value="TOTAL")
    ws[f"H{t}"] = f"=SUM(H2:H{n + 1})"
    ws[f"I{t}"] = f"=SUM(I2:I{n + 1})"
    ws[f"J{t}"] = f'=IF(ROUND(H{t}-I{t},2)=0,"Équilibré","ÉCART")'
    for col in "ABCDEFGHIJ":
        c = ws[f"{col}{t}"]
        c.font, c.fill, c.border = _f(True), F_TOTAL, BORD
        if col in "HI":
            c.number_format = FMT_MONTANT
    _largeurs(ws, [10, 12, 9, 14, 9, 46, 48, 15, 15, 12])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:J{n + 1}"
    return n, t


def _feuille_grand_livre(wb, gl):
    ws = wb.create_sheet("Grand livre")
    _entete(ws, ["Compte", "Intitulé du compte", "Date", "Pièce", "Libellé", "Débit (MAD)", "Crédit (MAD)",
                 "Solde progressif (D - C)"])
    for i, r in enumerate(gl.itertuples(index=False), 2):
        vals = [int(r.compte), r.intitule_compte, _iso(r.date), r.piece, r.libelle, float(r.debit), float(r.credit)]
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=i, column=j, value=v)
            c.font, c.border = _f(), BORD
            if j == 3:
                c.number_format = FMT_DATE
            if j in (6, 7):
                c.number_format = FMT_MONTANT
        h = ws.cell(row=i, column=8, value=f"=F{i}-G{i}" if i == 2 else f"=IF(A{i}=A{i - 1},H{i - 1},0)+F{i}-G{i}")
        h.font, h.border, h.number_format = _f(), BORD, FMT_MONTANT
    n = len(gl)
    ws.cell(row=n + 3, column=1,
            value="Solde progressif = débit - crédit : un nombre négatif est un solde créditeur.").font = _f(italic=True)
    _largeurs(ws, [9, 46, 12, 10, 48, 15, 15, 20])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:H{n + 1}"


def _feuille_balance(wb, bal, n_j):
    ws = wb.create_sheet("Balance")
    _entete(ws, ["Compte", "Intitulé du compte", "Total débit (MAD)", "Total crédit (MAD)",
                 "Solde débiteur (MAD)", "Solde créditeur (MAD)"])
    jc, jd, jk = (f"Journal!$E$2:$E${n_j + 1}", f"Journal!$H$2:$H${n_j + 1}", f"Journal!$I$2:$I${n_j + 1}")
    for i, r in enumerate(bal.itertuples(index=False), 2):
        ws.cell(row=i, column=1, value=int(r.compte))
        ws.cell(row=i, column=2, value=r.intitule_compte)
        ws.cell(row=i, column=3, value=f"=SUMIFS({jd},{jc},A{i})")
        ws.cell(row=i, column=4, value=f"=SUMIFS({jk},{jc},A{i})")
        ws.cell(row=i, column=5, value=f"=MAX(C{i}-D{i},0)")
        ws.cell(row=i, column=6, value=f"=MAX(D{i}-C{i},0)")
        for j in range(1, 7):
            c = ws.cell(row=i, column=j)
            c.font, c.border = _f(), BORD
            if j >= 3:
                c.number_format = FMT_MONTANT
    n = len(bal)
    t = n + 2
    ws.cell(row=t, column=1, value="TOTAL")
    for col in "CDEF":
        ws[f"{col}{t}"] = f"=SUM({col}2:{col}{n + 1})"
    ws[f"G{t}"] = f'=IF(AND(ROUND(C{t}-D{t},2)=0,ROUND(E{t}-F{t},2)=0),"Équilibrée","ÉCART")'
    for col in "ABCDEFG":
        c = ws[f"{col}{t}"]
        c.font, c.fill, c.border = _f(True), F_TOTAL, BORD
        if col in "CDEF":
            c.number_format = FMT_MONTANT
    _largeurs(ws, [9, 46, 18, 18, 18, 18, 14])
    ws.freeze_panes = "A2"
    return n, t


def _feuille_cpc(wb, nb):
    ws = wb.create_sheet("CPC")
    ws["A1"] = "COMPTE DE PRODUITS ET CHARGES (CPC) SIMPLIFIÉ"
    ws["A1"].font = _f(True, BLEU, 13)
    ws["A2"] = "Démonstration : situation intermédiaire, sans impôt ni personnel."
    ws["A2"].font = _f(italic=True)
    _entete(ws, ["Rubrique", "Montant (MAD)", "Comptes"], ligne=4)
    ca, cd, cc = f"Balance!$A$2:$A${nb + 1}", f"Balance!$E$2:$E${nb + 1}", f"Balance!$F$2:$F${nb + 1}"
    r = 5
    lignes_prod, lignes_ch = [], []

    def section(titre):
        nonlocal r
        for col in "ABC":
            ws[f"{col}{r}"].fill, ws[f"{col}{r}"].border = F_SECTION, BORD
        ws[f"A{r}"] = titre
        ws[f"A{r}"].font = _f(True)
        r += 1

    section("PRODUITS D'EXPLOITATION")
    for nom, pref in B.CPC_PRODUITS:
        _cellule(ws, f"A{r}", nom)
        _cellule(ws, f"B{r}", "=" + _prefixe(ca, f"{cc}-{cd}", pref), FMT_MONTANT)
        _cellule(ws, f"C{r}", ", ".join(pref))
        lignes_prod.append(r)
        r += 1
    t_prod = r
    _cellule(ws, f"A{r}", "Total des produits", gras=True, fond=F_TOTAL)
    _cellule(ws, f"B{r}", f"=SUM(B{lignes_prod[0]}:B{lignes_prod[-1]})", FMT_MONTANT, True, F_TOTAL)
    _cellule(ws, f"C{r}", "", fond=F_TOTAL)
    r += 1
    section("CHARGES D'EXPLOITATION")
    for nom, pref in B.CPC_CHARGES:
        _cellule(ws, f"A{r}", nom)
        _cellule(ws, f"B{r}", "=" + _prefixe(ca, f"{cd}-{cc}", pref), FMT_MONTANT)
        _cellule(ws, f"C{r}", ", ".join(pref))
        lignes_ch.append(r)
        r += 1
    t_ch = r
    _cellule(ws, f"A{r}", "Total des charges", gras=True, fond=F_TOTAL)
    _cellule(ws, f"B{r}", f"=SUM(B{lignes_ch[0]}:B{lignes_ch[-1]})", FMT_MONTANT, True, F_TOTAL)
    _cellule(ws, f"C{r}", "", fond=F_TOTAL)
    r += 1
    res = r
    _cellule(ws, f"A{r}", "RÉSULTAT (bénéfice + / perte -)", gras=True, fond=F_SECTION)
    _cellule(ws, f"B{r}", f"=B{t_prod}-B{t_ch}", FMT_MONTANT, True, F_SECTION)
    _cellule(ws, f"C{r}", "", fond=F_SECTION)
    _largeurs(ws, [48, 20, 22])
    return res


def _feuille_bilan(wb, nb, res_cpc):
    ws = wb.create_sheet("Bilan")
    ws["A1"] = "BILAN SIMPLIFIÉ"
    ws["A1"].font = _f(True, BLEU, 13)
    ws["A2"] = f"Situation au {date.fromisoformat(P.DATE_ARRETE).strftime('%d/%m/%Y')} - démonstration uniquement."
    ws["A2"].font = _f(italic=True)
    _entete(ws, ["ACTIF", "Montant (MAD)"], ligne=4)
    for j, nom in enumerate(["PASSIF", "Montant (MAD)"], 4):
        c = ws.cell(row=4, column=j, value=nom)
        c.font, c.fill, c.border = _f(True, "FFFFFF"), F_ENTETE, BORD
        c.alignment = Alignment(horizontal="center")
    ca, cd, cc = f"Balance!$A$2:$A${nb + 1}", f"Balance!$E$2:$E${nb + 1}", f"Balance!$F$2:$F${nb + 1}"
    r = 5
    for nom, pref in B.BILAN_ACTIF:
        _cellule(ws, f"A{r}", nom)
        _cellule(ws, f"B{r}", "=" + _prefixe(ca, f"{cd}-{cc}", pref), FMT_MONTANT)
        r += 1
    fin_a = r - 1
    r = 5
    for nom, pref in B.BILAN_PASSIF:
        _cellule(ws, f"D{r}", nom)
        _cellule(ws, f"E{r}", "=" + _prefixe(ca, f"{cc}-{cd}", pref), FMT_MONTANT)
        r += 1
    _cellule(ws, f"D{r}", "Résultat de l'exercice (bénéfice + / perte -)")
    _cellule(ws, f"E{r}", f"=CPC!B{res_cpc}", FMT_MONTANT, couleur="008000")
    fin_p = r
    t = max(fin_a, fin_p) + 2
    _cellule(ws, f"A{t}", "Total actif", gras=True, fond=F_TOTAL)
    _cellule(ws, f"B{t}", f"=SUM(B5:B{fin_a})", FMT_MONTANT, True, F_TOTAL)
    _cellule(ws, f"D{t}", "Total passif", gras=True, fond=F_TOTAL)
    _cellule(ws, f"E{t}", f"=SUM(E5:E{fin_p})", FMT_MONTANT, True, F_TOTAL)
    _largeurs(ws, [38, 18, 8, 38, 18])
    return t


def exporter(dossier, journal, gl, bal, inventaire, alertes, meta):
    wb = Workbook()
    ws = wb.active
    ws.title = "Synthèse"
    ws["A1"] = "DigiCompta CGNC - synthèse"
    ws["A1"].font = _f(True, BLEU, 14)
    ws["A2"] = f"Période : {meta['periode']}"
    ws["A3"] = f"Factures validées : {meta['valides']} / {meta['total']}"
    ws["A5"] = "Balance équilibrée"
    ws["A6"] = "Alertes"
    ws["A5"].font = _f(True)
    ws["A6"].font = _f(True)
    ws["B5"] = "=IF(AND(ROUND(Balance!C{len(bal)+2}-Balance!D{len(bal)+2},2)=0,ROUND(Balance!E{len(bal)+2}-Balance!F{len(bal)+2},2)=0),\"OUI\",\"NON\")"
    ws["B6"] = len(alertes)
    _feuille_journal(wb, journal)
    _feuille_grand_livre(wb, gl)
    _feuille_balance(wb, bal, len(journal))
    res_cpc = _feuille_cpc(wb, len(bal))
    _feuille_bilan(wb, len(bal), res_cpc)
    ws_inv = wb.create_sheet("Inventaire")
    _entete(ws_inv, ["Désignation", "Qte ouverture", "Qté achetée", "Qté vendue", "Qté finale",
                     "CMUP", "Valeur finale"])
    for i, r in enumerate(inventaire.itertuples(index=False), 2):
        vals = [r.designation, r.qte_ouverture, r.qte_achetee, r.qte_vendue, r.qte_finale,
                float(r.cmup), float(r.valeur_finale)]
        for j, v in enumerate(vals, 1):
            c = ws_inv.cell(row=i, column=j, value=v)
            c.font, c.border = _f(), BORD
            if j in (6, 7):
                c.number_format = FMT_MONTANT
    ws_alert = wb.create_sheet("Alertes")
    ws_alert["A1"] = "Alerte"
    ws_alert["A1"].font = _f(True)
    for i, a in enumerate(alertes, 2):
        ws_alert[f"A{i}"] = a
    _largeurs(ws_inv, [36, 12, 12, 12, 12, 14, 18])
    _largeurs(ws_alert, [90])
    wb.save(dossier)
    return dossier


def construire_classeur(journal, gl, bal, inventaire, alertes, meta):
    bio = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Synthèse"
    ws["A1"] = "DigiCompta CGNC - synthèse"
    ws["A1"].font = _f(True, BLEU, 14)
    ws["A2"] = f"Période : {meta['periode']}"
    ws["A3"] = f"Factures validées : {meta['valides']} / {meta['total']}"
    ws["A5"] = "Balance équilibrée"
    ws["A6"] = "Alertes"
    ws["A5"].font = _f(True)
    ws["A6"].font = _f(True)
    ws["B5"] = "=IF(AND(ROUND(Balance!C{len(bal)+2}-Balance!D{len(bal)+2},2)=0,ROUND(Balance!E{len(bal)+2}-Balance!F{len(bal)+2},2)=0),\"OUI\",\"NON\")"
    ws["B6"] = len(alertes)
    _feuille_journal(wb, journal)
    _feuille_grand_livre(wb, gl)
    _feuille_balance(wb, bal, len(journal))
    res_cpc = _feuille_cpc(wb, len(bal))
    _feuille_bilan(wb, len(bal), res_cpc)
    ws_inv = wb.create_sheet("Inventaire")
    _entete(ws_inv, ["Désignation", "Qte ouverture", "Qté achetée", "Qté vendue", "Qté finale",
                     "CMUP", "Valeur finale"])
    for i, r in enumerate(inventaire.itertuples(index=False), 2):
        vals = [r.designation, r.qte_ouverture, r.qte_achetee, r.qte_vendue, r.qte_finale,
                float(r.cmup), float(r.valeur_finale)]
        for j, v in enumerate(vals, 1):
            c = ws_inv.cell(row=i, column=j, value=v)
            c.font, c.border = _f(), BORD
            if j in (6, 7):
                c.number_format = FMT_MONTANT
    ws_alert = wb.create_sheet("Alertes")
    ws_alert["A1"] = "Alerte"
    ws_alert["A1"].font = _f(True)
    for i, a in enumerate(alertes, 2):
        ws_alert[f"A{i}"] = a
    _largeurs(ws_inv, [36, 12, 12, 12, 12, 14, 18])
    _largeurs(ws_alert, [90])
    wb.save(bio)
    return bio.getvalue()
