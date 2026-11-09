"""Extraction de factures PDF texte, PDF scannés et images vers le schéma DigiCompta.

Les extractions OCR sont toujours signalées comme à vérifier; les écritures restent à valider.
"""
import difflib
import io
import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import pandas as pd
import pdfplumber
import ocr
import parametres_atlas as P

COLONNES = ["facture_id", "type", "date_facture", "numero_fournisseur", "tiers_nom", "tiers_ice", "tiers_if",
            "tiers_ville", "ligne", "designation", "categorie", "quantite", "prix_unitaire_ht", "taux_tva",
            "mode_paiement", "date_echeance", "total_ttc_facture"]
EXT_IMAGES = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")
MODES = ["virement", "chèque", "effet", "espèces"]
MOTS_CLES = [("loyer", r"loyer|location"), ("telecom", r"internet|téléphon|telephon|télécom|telecom|abonnement"),
             ("transport", r"livraison|transport"), ("entretien", r"entretien|réparation|reparation|maintenance")]
DATE = r"([\dOoIl]{2}/[\dOoIl]{2}/[\dOoIl]{4})"
RE_NUM = re.compile(r"^\s*FACTURE\s+N\W{0,2}\s*(\S+)", re.M | re.I)
RE_DATE = re.compile(r"^\s*Date\s*:?\s*" + DATE, re.M | re.I)
RE_ECH = re.compile(r"^\s*[ÉEe]ch[éeè]ance\s*:?\s*" + DATE, re.M | re.I)
RE_MODE = re.compile(r"Mode\s+de\s+r[èeé]g?l?ement\s*:?\s*([A-Za-zéèêàç]+)", re.I)
RE_ICE = re.compile(r"ICE\s*:?\s*(\d+)")
RE_IF = re.compile(r"\bIF\s*:?\s*(\d+)")
MONTANT = r"((?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+),\d{2})"
RE_LIGNE = re.compile(r"^(\S{1,2})\s+(.*?\S)\s+(\d+(?:,\d+)?|[^\s\d]{1,3})\s+" + MONTANT + r"\s+(\d{1,2})\s+" + MONTANT + r"$")
RE_TOTAL_HT = re.compile(r"\bTotal\s*HT\D{0,8}" + MONTANT, re.I)
RE_NUM_B = re.compile(r"N\W{0,2}\s*Facture\s*:?\s*(\S+)", re.I)
RE_DATE_B = re.compile(r"\bDate\s*:?\s*" + DATE, re.I)
RE_ECH_B = re.compile(r"[ÉEe]ch[éeè]ance\s*:?\s*" + DATE, re.I)
RE_MODE_B = re.compile(r"Mode\s+de\s+(?:r[èeé]g?l?ement|paiement)\s*:?\s*([A-Za-zéèêàç]+)", re.I)
RE_TVA_TAUX = re.compile(r"TVA\s*\(?\s*(\d{1,2})\s*%")
RE_TVA_MONT = re.compile(r"TVA\s*\(?\s*\d{1,2}\s*%\s*\)?\s*" + MONTANT, re.I)
RE_LIGNE_REF = re.compile(r"^(\S+)\s+(.*?\S)\s+(\d+(?:,\d+)?|[^\s\d]{1,3})\s+" + MONTANT + r"\s+" + MONTANT + r"$")
MOTS_MARCHANDISES = r"papier|ramette|stylo|crayon|chemise|colle|bloc|cahier|classeur|cartouche|agrafe|marqueur|usb|calculatrice|enveloppe|trombone|ciseaux|toner|surligneur"
RE_TTC = re.compile(r"Total\s*TTC\D{0,8}" + MONTANT, re.I)
CENT = Decimal("0.01")


def _nombre(s):
    s = re.sub(r"[\s\u00a0\u202f]", "", str(s)).replace(",", ".")
    if not re.fullmatch(r"-?\d+(\.\d+)?", s):
        raise ValueError(f"nombre illisible : '{s}'")
    return s


def _iso(d):
    d = d.translate(str.maketrans("OoIl", "0011"))
    j, m, a = d.split("/")
    return f"{a}-{m}-{j}"


def _sans_accent(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _etiquette(l):
    return re.sub(r"[^A-Z]", "", _sans_accent(l).upper())


def _partie(lignes, label):
    i = next((k for k, l in enumerate(lignes) if _etiquette(l) == label), None)
    if i is None or i + 3 >= len(lignes):
        raise ValueError(f"bloc '{label}' introuvable")
    suite = " ".join(lignes[i + 3:i + 5])
    ice, if_ = RE_ICE.search(suite), RE_IF.search(suite)
    return dict(nom=lignes[i + 1].strip(), ville=lignes[i + 2].strip(),
                ice=ice.group(1) if ice else "", if_=if_.group(1) if if_ else "")


def _est_societe(nom):
    return P.NOM_SOCIETE.split()[0].lower() in nom.lower()


def classer(designation, type_facture):
    if designation in P.COUT_UNITAIRE_OUVERTURE:
        return "marchandises"
    if type_facture == "ACHAT":
        for cat, motif in MOTS_CLES:
            if re.search(motif, designation, re.I):
                return cat
    return "marchandises" if re.search(MOTS_MARCHANDISES, designation, re.I) else "a_classer"


def _mode(brut):
    brut = _sans_accent(brut.lower())
    sans = [_sans_accent(m) for m in MODES]
    cand = difflib.get_close_matches(brut, sans, n=1, cutoff=0.6)
    return MODES[sans.index(cand[0])] if cand else brut


def _charger(source, nom):
    est_octets = isinstance(source, (bytes, bytearray))
    if nom.lower().endswith(EXT_IMAGES):
        from PIL import Image
        img = Image.open(io.BytesIO(source) if est_octets else source)
        texte, conf = ocr.lire_images([img])
        return texte, [], True, conf
    with pdfplumber.open(io.BytesIO(source) if est_octets else source) as pdf:
        texte = "\n".join(p.extract_text() or "" for p in pdf.pages)
        if texte.strip():
            return texte, [t for p in pdf.pages for t in p.extract_tables()], False, None
        images = [p.to_image(resolution=300).original for p in pdf.pages]
    texte, conf = ocr.lire_images(images)
    return texte, [], True, conf


def _lignes_depuis_tableaux(tableaux):
    tl = next((t for t in tableaux if t and t[0] and any("Désignation" in str(c) for c in t[0])), None)
    tt = next((t for t in tableaux if t and t[0] and str(t[0][0]).startswith("Total HT")), None)
    if tl is None:
        raise ValueError("tableau des lignes introuvable")
    ttc = ""
    for row in (tt or []):
        if row and str(row[0]).startswith("Total TTC"):
            ttc = _nombre(row[1])
    lignes = []
    for row in tl[1:]:
        cells = [(c or "").replace("\n", " ").strip() for c in row]
        if cells and cells[0].isdigit() and len(cells) >= 5:
            n, des, q, pu, taux = cells[:5]
            lignes.append((n, des, _nombre(q), f"{Decimal(_nombre(pu)):.2f}", re.sub(r"\D", "", taux)))
    return lignes, ttc, None, []


def _normaliser_designation(des):
    base = {_sans_accent(k).lower(): k for k in P.COUT_UNITAIRE_OUVERTURE}
    cand = difflib.get_close_matches(_sans_accent(des).lower(), list(base), n=1, cutoff=0.85)
    return base[cand[0]] if cand else des


def _lignes_depuis_texte(texte, taux_defaut=None):
    lignes, ttc, total_ht, anomalies = [], "", None, []
    for brut in texte.splitlines():
        l = re.sub(r"[|\u00a0\u202f_]", " ", brut)
        l = re.sub(r"\s+", " ", l).strip()
        l = re.sub(r"(?<= )(\d{1,2})[.,;:]+(?= )", r"\1", l)
        m = RE_TTC.search(l)
        if m:
            ttc = _nombre(m.group(1)); continue
        m = RE_TOTAL_HT.search(l)
        if m:
            total_ht = Decimal(_nombre(m.group(1))); continue
        m = RE_LIGNE.match(l)
        if m:
            _, des, qtxt, putxt, taux, tottxt = m.groups()
        elif taux_defaut:
            m = RE_LIGNE_REF.match(l)
            if not m:
                continue
            _, des, qtxt, putxt, tottxt = m.groups(); taux = taux_defaut
        else:
            continue
        n = str(len(lignes) + 1)
        des = _normaliser_designation(des.strip())
        pu, tot = Decimal(_nombre(putxt)), Decimal(_nombre(tottxt))
        q = Decimal(_nombre(qtxt)) if re.fullmatch(r"\d+(,\d+)?", qtxt) else None
        if q is None or (q * pu).quantize(CENT) != tot:
            q_dep = tot / pu if pu else None
            pu_dep = tot / q if q else None
            q_ok = q_dep is not None and q_dep >= 1 and q_dep == q_dep.to_integral_value()
            pu_ok = pu_dep is not None and pu_dep == pu_dep.quantize(CENT)
            if q is None and q_ok:
                q = q_dep; anomalies.append(f"ligne {n} : quantité illisible, déduite = {q}")
            elif q is not None and q_ok and not pu_ok:
                anomalies.append(f"ligne {n} : quantité corrigée en {q_dep}"); q = q_dep
            elif q is not None and pu_ok and not q_ok:
                anomalies.append(f"ligne {n} : prix corrigé en {pu_dep}"); pu = pu_dep
            else:
                anomalies.append(f"ligne {n} : quantité x prix ≠ total de ligne, à vérifier")
                if q is None:
                    continue
        lignes.append((n, des, str(int(q)) if q == q.to_integral_value() else str(q), f"{pu:.2f}", taux))
    if lignes and total_ht is not None:
        somme = sum((Decimal(q) * Decimal(pu)).quantize(CENT) for _, _, q, pu, _ in lignes)
        if somme != total_ht:
            anomalies.append(f"somme des lignes ({somme}) ≠ Total HT imprimé ({total_ht})")
    return lignes, ttc, total_ht, anomalies


def _a_blocs(texte):
    return any(_etiquette(l) == "EMETTEUR" for l in texte.splitlines())


def _mots_capitalises(texte):
    mots = []
    for w in texte.split():
        if re.fullmatch(r"[A-ZÉ][\w\-éèêëïôûçÉ’']+", w):
            mots.append(w)
        else:
            break
    return " ".join(mots)


def _ville(adresse):
    m = re.search(r",\s*([A-ZÉ][A-Za-zÀ-ÿ\-]+)\s*$", adresse.strip())
    return m.group(1) if m else ""


def _extraire_classique(texte):
    anomalies = []
    txt = [l.strip() for l in texte.splitlines() if l.strip()]
    plein = "\n".join(txt)
    def trouver(regex, label):
        m = regex.search(plein)
        if not m:
            raise ValueError(f"champ introuvable : {label}")
        return m.group(1).strip()
    numero = trouver(RE_NUM_B, "numéro de facture")
    date_f, date_e = _iso(trouver(RE_DATE_B, "date")), _iso(trouver(RE_ECH_B, "échéance"))
    i = next((k for k, l in enumerate(txt) if re.search(r"\bClient\b\s*:", l, re.I)), None)
    if i is None:
        raise ValueError("bloc client introuvable")
    m = re.search(r"Client\s*:\s*(.*?)(?:\s+N\W{0,2}\s*Facture.*)?$", txt[i], re.I)
    client = m.group(1).strip() if m else ""
    if re.match(r"N\W{0,2}\s*Facture", client, re.I):
        client = ""
    if not client and i + 1 < len(txt):
        client = re.split(r"\s+Date\b", txt[i + 1])[0].strip()
    avant, apres = txt[:i], "\n".join(txt[i:])
    m_if = RE_IF.search("\n".join(avant))
    m_pour = re.search(r"Pour\s+(.+)", plein)
    nom_four = _mots_capitalises(m_pour.group(1)) if m_pour else ""
    if not nom_four:
        nom_four = "Fournisseur à identifier"; anomalies.append("nom du fournisseur non lu")
    ville_four = next((_ville(l) for l in avant if re.search(r"\b(Av|Rue|Bd|Avenue)\b", l) and _ville(l)), "")
    m_adr = re.search(r"Adresse\s*:\s*(.*?)(?:\s+Date\b.*)?$", apres, re.M | re.I)
    m_if_c = RE_IF.search(apres)
    four = dict(nom=nom_four, ville=ville_four, ice="", if_=m_if.group(1) if m_if else "")
    cli = dict(nom=client, ville=_ville(m_adr.group(1)) if m_adr else "", ice="", if_=m_if_c.group(1) if m_if_c else "")
    if _est_societe(client):
        type_f, tiers = "ACHAT", four
    elif _est_societe(nom_four):
        type_f, tiers = "VENTE", cli
    else:
        raise ValueError(f"ni le client ({client or '?'}) ni l'émetteur ({nom_four}) n'est {P.NOM_SOCIETE}")
    m_mode = RE_MODE_B.search(plein)
    if m_mode:
        mode = _mode(m_mode.group(1))
    else:
        candidats = [w for w in ("virement", "chèque", "cheque", "espèces", "especes", "effet") if w in plein.lower()]
        mode = _mode(candidats[0]) if candidats else "virement"
        anomalies.append("mode de paiement supposé ou ambigu")
    m_taux = RE_TVA_TAUX.search(plein)
    if not m_taux:
        raise ValueError("taux de TVA introuvable")
    brutes, ttc, total_ht, anom = _lignes_depuis_texte(plein, taux_defaut=m_taux.group(1))
    anomalies += anom
    if not ttc and total_ht is not None:
        m_tva = RE_TVA_MONT.search(plein)
        if m_tva:
            ttc = str(total_ht + Decimal(_nombre(m_tva.group(1))))
            anomalies.append("TTC déduit du Total HT et de la TVA imprimés")
    return numero, date_f, date_e, mode, type_f, tiers, brutes, ttc, anomalies


def extraire_facture(source, nom=""):
    texte, tableaux, par_ocr, confiance = _charger(source, nom)
    if not texte.strip():
        raise ValueError("aucun texte reconnu dans le document")
    if tableaux or _a_blocs(texte):
        def champ(regex, label):
            m = regex.search(texte)
            if not m:
                raise ValueError(f"champ introuvable : {label}")
            return m.group(1).strip()
        numero = champ(RE_NUM, "numéro de facture")
        date_f, date_e = _iso(champ(RE_DATE, "date")), _iso(champ(RE_ECH, "échéance"))
        mode = _mode(champ(RE_MODE, "mode de règlement"))
        txt = [l.strip() for l in texte.splitlines() if l.strip()]
        emet, dest = _partie(txt, "EMETTEUR"), _partie(txt, "DESTINATAIRE")
        if _est_societe(emet["nom"]):
            type_f, tiers = "VENTE", dest
        elif _est_societe(dest["nom"]):
            type_f, tiers = "ACHAT", emet
        else:
            raise ValueError(f"ni l'émetteur ni le destinataire n'est {P.NOM_SOCIETE}")
        brutes, ttc, _, anomalies = _lignes_depuis_tableaux(tableaux) if tableaux else _lignes_depuis_texte(texte)
    else:
        numero, date_f, date_e, mode, type_f, tiers, brutes, ttc, anomalies = _extraire_classique(texte)
    if not ttc:
        raise ValueError("total TTC introuvable")
    if not brutes:
        raise ValueError("aucune ligne de facture lue")
    lignes = [dict(facture_id=numero if type_f == "VENTE" else "", type=type_f, date_facture=date_f,
        numero_fournisseur=numero if type_f == "ACHAT" else "", tiers_nom=tiers["nom"], tiers_ice=tiers["ice"],
        tiers_if=tiers["if_"], tiers_ville=tiers["ville"], ligne=n, designation=des,
        categorie=classer(des, type_f), quantite=q, prix_unitaire_ht=pu, taux_tva=taux,
        mode_paiement=mode, date_echeance=date_e, total_ttc_facture=ttc)
        for n, des, q, pu, taux in brutes]
    ht = {}
    for l in lignes:
        valeur = (Decimal(l["quantite"]) * Decimal(l["prix_unitaire_ht"])).quantize(CENT, ROUND_HALF_UP)
        taux = int(l["taux_tva"])
        ht[taux] = ht.get(taux, Decimal(0)) + valeur
    recalcule = sum(h + (h * taux / 100).quantize(CENT, ROUND_HALF_UP) for taux, h in ht.items())
    return lignes, dict(ocr=par_ocr, confiance=confiance, ttc_coherent=recalcule == Decimal(ttc), anomalies=anomalies)


def extraire_dossier(sources):
    factures, rapport, vus = [], [], set()
    for nom, src in sources:
        try:
            lignes, meta = extraire_facture(src, nom)
        except Exception as exc:
            rapport.append((nom, "ERREUR", "", 0, str(exc)))
            continue
        f = lignes[0]
        cle = (f["type"], f["facture_id"] or (f["tiers_ice"], f["numero_fournisseur"]))
        ref = f["facture_id"] or f["numero_fournisseur"]
        if cle in vus:
            rapport.append((nom, "DOUBLON", ref, len(lignes), "facture déjà importée, ignorée")); continue
        vus.add(cle)
        notes = []
        if meta["ocr"]:
            notes.append(f"lue par OCR (confiance {meta['confiance']:.0f} %) : vérifier les montants")
        notes += meta["anomalies"]
        if not meta["ttc_coherent"]:
            notes.append("TTC lu différent du TTC recalculé")
        inconnues = sum(l["categorie"] == "a_classer" for l in lignes)
        if inconnues:
            notes.append(f"{inconnues} ligne(s) à classer manuellement")
        rapport.append((nom, "A_VERIFIER" if notes else "OK", ref, len(lignes), " ; ".join(notes)))
        factures.append(lignes)
    achats = sorted((ls for ls in factures if ls[0]["type"] == "ACHAT"),
                    key=lambda ls: (ls[0]["date_facture"], ls[0]["numero_fournisseur"]))
    compteur = {}
    for lignes in achats:
        an = lignes[0]["date_facture"][:4]
        compteur[an] = compteur.get(an, 0) + 1
        for l in lignes:
            l["facture_id"] = f"FA-{an}-{compteur[an]:03d}"
    plat = [l for ls in factures for l in ls]
    df = pd.DataFrame(plat, columns=COLONNES) if plat else pd.DataFrame(columns=COLONNES)
    rap = pd.DataFrame(rapport, columns=["fichier", "statut", "facture", "lignes", "detail"])
    return df, rap


def main(dossier, dossier_sortie):
    p = Path(dossier)
    fichiers = sorted(f for f in p.iterdir() if f.suffix.lower() == ".pdf" or f.suffix.lower() in EXT_IMAGES)
    df, rap = extraire_dossier([(f.name, str(f)) for f in fichiers])
    out = Path(dossier_sortie); out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "factures_extraites.csv", index=False, encoding="utf-8-sig")
    rap.to_csv(out / "rapport_extraction.csv", index=False, encoding="utf-8-sig")
    return df, rap


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else "data/factures_pdf"
    dst = sys.argv[2] if len(sys.argv) > 2 else "output"
    df, rap = main(src, dst)
    print(rap["statut"].value_counts().to_string())
    print(f"{df['facture_id'].nunique()} factures, {len(df)} lignes -> {dst}/factures_extraites.csv")
