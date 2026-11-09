"""Simule des factures SCANNÉES ou PHOTOGRAPHIÉES à partir des PDF : légère rotation, bruit,
flou et compression JPEG. Sert à tester l'OCR.

  - factures de vente  -> photo .jpg
  - factures d'achat   -> PDF scanné (image seule, sans texte)

Usage :  python simuler_scans.py [data/factures_pdf] [data/factures_scans] [nombre_max]
"""
import random
import sys
from pathlib import Path

import numpy as np
import pdfplumber
from PIL import Image, ImageFilter


def degrader(img, rng, rotation=1.0, bruit=9.0, flou=0.6):
    img = img.convert("L")
    img = img.rotate(rng.uniform(-rotation, rotation), expand=True, fillcolor=255, resample=Image.BICUBIC)
    img = img.filter(ImageFilter.GaussianBlur(flou))
    arr = np.asarray(img, dtype=np.float32)
    arr = arr + np.random.default_rng(rng.randint(0, 10**6)).normal(0, bruit, arr.shape)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def main(src, dst, maximum=None, graine=7, **kw):
    rng = random.Random(graine)
    out = Path(dst)
    out.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(Path(src).glob("*.pdf"))
    if maximum:
        pdfs = pdfs[::max(1, len(pdfs) // maximum)][:maximum]   # échantillon réparti
    for p in pdfs:
        with pdfplumber.open(p) as pdf:
            img = pdf.pages[0].to_image(resolution=200).original
        img = degrader(img, rng, **kw)
        if p.stem.startswith("FV"):
            img.save(out / f"scan_{p.stem}.jpg", quality=70)
        else:
            img.save(out / f"scan_{p.stem}.pdf", "PDF", resolution=200, quality=70)
    return len(pdfs)


if __name__ == "__main__":
    s = sys.argv[1] if len(sys.argv) > 1 else "data/factures_pdf"
    d = sys.argv[2] if len(sys.argv) > 2 else "data/factures_scans"
    m = int(sys.argv[3]) if len(sys.argv) > 3 else None
    print(f"{main(s, d, m)} scans simulés dans {d}/")
