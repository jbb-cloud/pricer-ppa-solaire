"""Backtest walk-forward du modèle V2, face à la V1, à M2 et aux références (`docs/pricing.md`).

Usage : ``.venv/bin/python scripts/backtest_v2.py``, après ``scripts/backtest_m2.py``.
Écrit dans ``reports/backtest/v2/`` : ``rapport.md``, ``previsions.csv``, ``parametres_geles.csv``. Ne modifie ni la base ni les rapports précédents.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ppa_pricer.analyse.capture import charger_horaire, taux_de_capture
from ppa_pricer.backtest.metriques import biais, diebold_mariano, mae, skill_score
from ppa_pricer.backtest.robustesse import bootstrap_skill, skill_global, skill_sans_chaque_annee
from ppa_pricer.donnees.base import connexion
from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE
from ppa_pricer.modele.m0 import GRAINE
from ppa_pricer.modele.v1 import MOIS, prevoir_part_solaire
from ppa_pricer.modele.v2 import calibrer_v2, niveau_du_trimestre, niveaux_trimestriels, prevoir_v2

RACINE = Path(__file__).resolve().parents[1]
BASE = RACINE / "data" / "ppa.sqlite"
PREVISIONS_M2 = RACINE / "reports" / "backtest" / "m2" / "previsions.csv"
DOSSIER = RACINE / "reports" / "backtest" / "v2"
ANNEES = list(range(2018, 2026))
ANNEE_A_PART = 2026
ANNEE_GEL = 2027
N_BOOTSTRAP = 10_000
NOMS = {"v2_realise": "V2, niveau réalisé", "v2_persistant": "V2, niveau persistant", "modele_realiste": "V1", "tc_m2": "M2", "r1_persistance": "R1", "r2_climatologie": "R2"}


def pt(x: float) -> str:
    return "n.d." if pd.isna(x) else f"{x * 100:.1f}".replace(".", ",").replace("-", "−")


def sg(x: float, d: int = 2) -> str:
    return "n.d." if pd.isna(x) else f"{x:+.{d}f}".replace(".", ",").replace("-", "−")


def main() -> None:
    mensuel = taux_de_capture(charger_horaire(connexion(BASE)), "M")
    niveaux = niveaux_trimestriels(mensuel)
    mois = pd.Series(list(MOIS), index=list(MOIS), name="mois")
    morceaux, parametres = [], []
    for annee in [*ANNEES, ANNEE_A_PART]:
        p = calibrer_v2(mensuel, annee)
        part = prevoir_part_solaire(mensuel, annee)
        morceaux.append(
            pd.DataFrame(
                {
                    "annee": annee,
                    "mois": list(MOIS),
                    "v2_realise": prevoir_v2(p, mois, part, niveau_du_trimestre(niveaux, annee, mois)).to_numpy(),
                    "v2_persistant": prevoir_v2(p, mois, part, niveau_du_trimestre(niveaux, annee - 1, mois)).to_numpy(),
                }
            )
        )
        parametres.append({"annee_prevue": annee, "beta": p.beta, "gamma": p.gamma, "delta": p.delta, "n_mois": p.n_mois})
    p_m2 = pd.read_csv(PREVISIONS_M2)
    previsions = p_m2.merge(pd.concat(morceaux, ignore_index=True), on=["annee", "mois"], validate="one_to_one")
    colonnes = ["taux_capture", *NOMS]
    officiel = previsions[previsions["annee"].isin(ANNEES)].dropna(subset=colonnes).sort_values(["annee", "mois"], ignore_index=True)
    a_part = previsions[previsions["annee"] == ANNEE_A_PART].dropna(subset=colonnes)

    DOSSIER.mkdir(parents=True, exist_ok=True)
    previsions[["annee", "mois", "periode", "taux_capture", *NOMS]].to_csv(DOSSIER / "previsions.csv", index=False, float_format="%.5f")
    gel = calibrer_v2(mensuel, ANNEE_GEL)
    pd.DataFrame([{"parametre": f"alpha_{m:02d}", "valeur": v} for m, v in gel.alpha.items()] + [{"parametre": k, "valeur": getattr(gel, k)} for k in ("beta", "gamma", "delta")] + [{"parametre": "n_mois", "valeur": gel.n_mois}]).to_csv(DOSSIER / "parametres_geles.csv", index=False, float_format="%.6f")

    def erreurs(t, c):
        return t[c] - t["taux_capture"]

    maes = {c: mae(erreurs(officiel, c)) for c in NOMS}
    skill_r1, skill_v1 = skill_score(maes["v2_realise"], maes["r1_persistance"]), skill_score(maes["v2_realise"], maes["modele_realiste"])
    atteint = skill_r1 > 0 and skill_v1 > 0
    lignes = [
        "# Backtest du modèle V2",
        "",
        f"Généré le {pd.Timestamp.now(tz=FUSEAU_AFFICHAGE):%d/%m/%Y}. Définition, limites et attentes : `docs/pricing.md`. Erreurs en points de taux de capture (prévision − réalisé). Part du solaire prévue par H4.",
        "",
        "**La forme de V2 a été choisie après avoir vu ces années** : ce backtest ne la valide pas. Le niveau réalisé équivaut à une cotation parfaite et lui est donc favorable. Le niveau persistant est celui du même trimestre de l'année précédente. Seuls les mois publiés après le 29/10/2026 forment un test propre.",
        "",
        f"## Critère (2018–2025, {len(officiel)} mois, niveau réalisé)",
        "",
        f"Skill > 0 contre R1 et contre la V1. Skill vs R1 = {sg(skill_r1)}, skill vs V1 = {sg(skill_v1)} → **critère {'ATTEINT' if atteint else 'NON ATTEINT'}, sans valeur de preuve**.",
        "",
        "## Précision",
        "",
        "| Méthode | MAE | Biais | Skill vs R1 | Skill vs V1 | Skill vs R2 |",
        "|---|---|---|---|---|---|",
    ]
    for c, nom in NOMS.items():
        lignes.append(f"| {nom} | {pt(maes[c])} | {pt(biais(erreurs(officiel, c)))} | {sg(skill_score(maes[c], maes['r1_persistance']))} | {sg(skill_score(maes[c], maes['modele_realiste']))} | {sg(skill_score(maes[c], maes['r2_climatologie']))} |")
    lignes += ["", "## Par année", "", "| Année | " + " | ".join(NOMS.values()) + " | Biais V2, niveau réalisé |", "|---|" + "---|" * (len(NOMS) + 1)]
    for annee, g in pd.concat([officiel, a_part]).groupby("annee"):
        libelle = f"{annee} ({len(g)} mois, à part)" if annee == ANNEE_A_PART else str(annee)
        lignes.append(f"| {libelle} | " + " | ".join(pt(mae(erreurs(g, c))) for c in NOMS) + f" | {pt(biais(erreurs(g, 'v2_realise')))} |")
    lignes += ["", "## Diebold-Mariano (perte absolue, Newey-West 11 retards, Student n−1)", "", "| Comparaison | Statistique | p-value |", "|---|---|---|"]
    couples = [("v2_realise", "modele_realiste"), ("v2_realise", "r1_persistance"), ("v2_realise", "tc_m2"), ("v2_persistant", "modele_realiste"), ("v2_persistant", "r1_persistance")]
    for a, b in couples:
        dm = diebold_mariano(erreurs(officiel, a), erreurs(officiel, b))
        lignes.append(f"| {NOMS[a]} contre {NOMS[b]} | {sg(dm.statistique)} | {dm.p_valeur:.3f} |".replace(".", ","))
    rng = np.random.default_rng([GRAINE, 4])
    lignes += ["", "## Robustesse", "", f"Skill en retirant chaque année, puis bootstrap par années entières ({N_BOOTSTRAP} tirages, à lire comme un ordre de grandeur).", "",
               "| Comparaison | Tout | " + " | ".join(str(a) for a in ANNEES) + " | Retraits > 0 | IC à 90 % | Tirages > 0 |", "|---|---|" + "---|" * (len(ANNEES) + 3)]
    for a, b in couples:
        s = skill_sans_chaque_annee(officiel, a, b)
        boot = bootstrap_skill(officiel, a, b, N_BOOTSTRAP, rng)
        lignes.append(f"| {NOMS[a]} contre {NOMS[b]} | {sg(skill_global(officiel, a, b))} | " + " | ".join(sg(s[x]) for x in ANNEES) + f" | {int((s > 0).sum())} sur {len(s)} | {sg(np.quantile(boot, 0.05))} à {sg(np.quantile(boot, 0.95))} | {(boot > 0).mean() * 100:.0f} % |")
    lignes += ["", "## Paramètres", "", "`parametres_geles.csv` fige les paramètres estimés sur tous les mois valides, pour le test sur les mois nouveaux.", "", "| Calibration pour | β | γ | δ | Mois |", "|---|---|---|---|---|"]
    for r in parametres + [{"annee_prevue": ANNEE_GEL, "beta": gel.beta, "gamma": gel.gamma, "delta": gel.delta, "n_mois": gel.n_mois}]:
        lignes.append(f"| {r['annee_prevue']} | {sg(r['beta'])} | {sg(r['gamma'], 3)} | {sg(r['delta'])} | {r['n_mois']} |")
    lignes.append("")
    texte = "\n".join(lignes)
    (DOSSIER / "rapport.md").write_text(texte)
    print(texte)


if __name__ == "__main__":
    main()
