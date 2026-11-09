"""OCR (Tesseract) pour les factures scannées ou photographiées.

Prérequis système : installer Tesseract et idéalement les données de langue française.
Variables optionnelles : TESSERACT_CMD et TESSDATA_PREFIX.
"""
import os
import numpy as np
from PIL import Image, ImageOps

MESSAGE_ABSENT = ("Tesseract n'est pas installé ou introuvable : l'OCR est indisponible. "
                  "Installez-le ou renseignez TESSERACT_CMD.")


def _pytesseract():
    import pytesseract
    cmd = os.environ.get("TESSERACT_CMD")
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    return pytesseract


def disponible():
    try:
        _pytesseract().get_tesseract_version()
        return True
    except Exception:
        return False


def _langue(pt):
    try:
        langues = set(pt.get_languages(config=""))
    except Exception:
        langues = set()
    if "fra" in langues:
        return "fra+eng" if "eng" in langues else "fra"
    return "eng"


def _redresser(img):
    petit = img.resize((600, max(1, int(img.height * 600 / img.width))))
    sombre = Image.fromarray(((np.asarray(petit) < 160) * 255).astype(np.uint8))
    meilleur, angle = -1.0, 0.0
    for a in np.arange(-3.0, 3.01, 0.1):
        score = (np.asarray(sombre.rotate(a, resample=Image.BILINEAR)) > 0).sum(axis=1).astype(float).var()
        if score > meilleur:
            meilleur, angle = score, a
    return img.rotate(angle, resample=Image.BICUBIC, fillcolor=255)


def _masque_traits(sombre, k, axe):
    if axe == 0:
        return _masque_traits(sombre.T, k, 1).T
    h, w = sombre.shape
    if k <= 0 or k >= w:
        return np.zeros_like(sombre, dtype=bool)
    cs = np.concatenate([np.zeros((h, 1), dtype=np.int32), np.cumsum(sombre.astype(np.int32), axis=1)], axis=1)
    pleins = (cs[:, k:] - cs[:, :-k]) == k
    diff = np.zeros((h, w + 1), dtype=np.int32)
    diff[:, :w - k + 1] += pleins
    diff[:, k:w + 1] -= pleins
    return np.cumsum(diff, axis=1)[:, :w] > 0


def _effacer_tableau(img):
    a = np.array(img)
    sombre = a < 170
    h, w = sombre.shape
    horiz = _masque_traits(sombre, max(1, int(0.25 * w)), 1)
    vert = _masque_traits(sombre, max(1, int(0.025 * h)), 0)
    horiz |= np.roll(horiz, 1, axis=0) | np.roll(horiz, -1, axis=0)
    vert |= np.roll(vert, 1, axis=1) | np.roll(vert, -1, axis=1)
    a[horiz | vert] = 255
    return Image.fromarray(a)


def pretraiter(img):
    img = ImageOps.autocontrast(img.convert("L"))
    if img.width < 1800:
        facteur = 1800 / img.width
        img = img.resize((int(img.width * facteur), int(img.height * facteur)), Image.LANCZOS)
    return _effacer_tableau(_redresser(img))


def lire_images(images):
    if not disponible():
        raise RuntimeError(MESSAGE_ABSENT)
    pt = _pytesseract()
    textes, confs = [], []
    for img in images:
        d = pt.image_to_data(pretraiter(img), lang=_langue(pt), config="--psm 6", output_type=pt.Output.DICT)
        lignes = {}
        for i, mot in enumerate(d["text"]):
            if not str(mot).strip():
                continue
            lignes.setdefault((d["block_num"][i], d["par_num"][i], d["line_num"][i]), []).append(str(mot))
            try:
                c = float(d["conf"][i])
                if c >= 0:
                    confs.append(c)
            except (TypeError, ValueError):
                pass
        textes.append("\n".join(" ".join(mots) for _, mots in sorted(lignes.items())))
    return "\n".join(textes), (sum(confs) / len(confs) if confs else 0.0)
