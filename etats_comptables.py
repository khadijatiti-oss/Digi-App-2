"""Grand livre et balance générale calculés à partir du journal comptable."""
import sys
from decimal import Decimal
from pathlib import Path
import pandas as pd

ZERO = Decimal("0.00")


def charger_journal(chemin):
    journal = pd.read_csv(chemin, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    journal["debit"] = journal["debit"].map(Decimal)
    journal["credit"] = journal["credit"].map(Decimal)
    return journal


def grand_livre(journal, seulement_validees=False):
    j = journal[journal["statut"] == "VALIDEE"] if seulement_validees else journal
    j = j.sort_values(["compte", "date", "piece"], kind="stable")
    lignes = []
    for compte, groupe in j.groupby("compte", sort=True):
        solde = ZERO
        for _, r in groupe.iterrows():
            solde += r["debit"] - r["credit"]
            lignes.append(dict(compte=compte, intitule_compte=r["intitule_compte"], date=r["date"],
                piece=r["piece"], libelle=r["libelle"], debit=r["debit"], credit=r["credit"],
                solde_progressif=solde))
    return pd.DataFrame(lignes)


def balance_generale(journal, seulement_validees=False):
    j = journal[journal["statut"] == "VALIDEE"] if seulement_validees else journal
    lignes = []
    for compte, groupe in j.groupby("compte", sort=True):
        debit, credit = sum(groupe["debit"], ZERO), sum(groupe["credit"], ZERO)
        lignes.append(dict(compte=compte, intitule_compte=groupe["intitule_compte"].iloc[0],
            total_debit=debit, total_credit=credit,
            solde_debiteur=debit-credit if debit > credit else ZERO,
            solde_crediteur=credit-debit if credit > debit else ZERO))
    return pd.DataFrame(lignes)


def verifier_balance(b):
    return (b["total_debit"].sum() == b["total_credit"].sum(),
            b["solde_debiteur"].sum() == b["solde_crediteur"].sum())


def main(chemin_journal, dossier_sortie):
    out = Path(dossier_sortie)
    out.mkdir(parents=True, exist_ok=True)
    journal = charger_journal(chemin_journal)
    gl, balance = grand_livre(journal), balance_generale(journal)
    gl.to_csv(out / "grand_livre.csv", index=False, encoding="utf-8-sig")
    balance.to_csv(out / "balance_generale.csv", index=False, encoding="utf-8-sig")
    return gl, balance


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "output/journal.csv"
    dst = sys.argv[2] if len(sys.argv) > 2 else "output"
    _, balance = main(src, dst)
    print(balance.to_string(index=False))
    print(f"Total débit : {balance['total_debit'].sum()} | crédit : {balance['total_credit'].sum()}")
    print("Balance équilibrée :", "OUI" if all(verifier_balance(balance)) else "NON - ERREUR")
