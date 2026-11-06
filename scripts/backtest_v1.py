"""Backtest walk-forward du modèle V1 (protocole de `docs/perimetre.md`).

Usage : ``.venv/bin/python scripts/backtest_v1.py``
Écrit dans ``reports/backtest/v1/`` : ``rapport.md``, ``previsions.csv``, ``parametres.csv``.
"""

from pathlib import Path

import pandas as pd

from ppa_pricer.analyse.capture import charger_horaire, taux_de_capture
from ppa_pricer.backtest.metriques import biais, diebold_mariano, mae, mae_ponderee, skill_score
from ppa_pricer.backtest.walk_forward import METHODES, backtest, echantillon_commun, taux_annuels
from ppa_pricer.donnees.base import connexion
from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE

RACINE = Path(__file__).resolve().parents[1]
BASE = RACINE / "data" / "ppa.sqlite"
DOSSIER = RACINE / "reports" / "backtest" / "v1"
ANNEES_OFFICIELLES = list(range(2018, 2026))
ANNEE_A_PART = 2026

NOMS = {
    "modele_realiste": "Modèle V1, réaliste",
    "modele_conditionnel": "Modèle V1, conditionnel (part solaire réalisée)",
    "r1_persistance": "R1 persistance",
    "r2_climatologie": "R2 climatologie",
}


def pts(x: float) -> str:
    """Valeur en points de taux de capture (0,05 → « 5,0 »)."""
    return f"{x * 100:.1f}".replace(".", ",")


def signe(x: float) -> str:
    """Nombre signé à deux décimales, virgule française (0,1 → « +0,10 »)."""
    return f"{x:+.2f}".replace(".", ",")


def tableau_metriques(e: pd.DataFrame) -> list[str]:
    erreurs = {m: e[m] - e["taux_capture"] for m in METHODES}
    maes = {m: mae(erreurs[m]) for m in METHODES}
    lignes = [
        "| Méthode | MAE | MAE pondérée | Biais | Skill vs R1 | Skill vs R2 |",
        "|---|---|---|---|---|---|",
    ]
    for m in METHODES:
        lignes.append(
            f"| {NOMS[m]} | {pts(maes[m])} | {pts(mae_ponderee(erreurs[m], e['energie_solaire_mwh']))} "
            f"| {pts(biais(erreurs[m]))} | {signe(skill_score(maes[m], maes['r1_persistance']))} "
            f"| {signe(skill_score(maes[m], maes['r2_climatologie']))} |"
        )
    return lignes


def main() -> None:
    horaire = charger_horaire(connexion(BASE))
    mensuel = taux_de_capture(horaire, frequence="M")
    derniere_donnee = horaire.dropna()["ts_utc"].max().tz_convert(FUSEAU_AFFICHAGE)

    previsions, parametres = backtest(mensuel, [*ANNEES_OFFICIELLES, ANNEE_A_PART])
    DOSSIER.mkdir(parents=True, exist_ok=True)
    previsions.to_csv(DOSSIER / "previsions.csv", index=False, float_format="%.5f")
    parametres.to_csv(DOSSIER / "parametres.csv", index=False, float_format="%.5f")

    officiel = echantillon_commun(previsions[previsions["annee"].isin(ANNEES_OFFICIELLES)])
    erreurs = {m: officiel[m] - officiel["taux_capture"] for m in METHODES}
    maes = {m: mae(erreurs[m]) for m in METHODES}
    skill_r1 = skill_score(maes["modele_realiste"], maes["r1_persistance"])
    skill_r2 = skill_score(maes["modele_realiste"], maes["r2_climatologie"])
    atteint = skill_r1 > 0 and skill_r2 > 0

    lignes = [
        "# Backtest du modèle V1",
        "",
        f"Généré le {pd.Timestamp.now(tz=FUSEAU_AFFICHAGE):%d/%m/%Y} ; données jusqu'au "
        f"{derniere_donnee:%d/%m/%Y %H:%M}. Protocole : `docs/perimetre.md`. Erreurs en points de "
        "taux de capture (prévision − réalisé).",
        "",
        "## Verdict officiel (2018–2025, variante réaliste)",
        "",
        f"Critère : skill score > 0 contre R1 **et** contre R2. Skill vs R1 = {signe(skill_r1)}, "
        f"skill vs R2 = {signe(skill_r2)} → **critère {'ATTEINT' if atteint else 'NON ATTEINT'}**.",
        "",
        f"## Métriques 2018–2025 ({len(officiel)} mois)",
        "",
        *tableau_metriques(officiel),
        "",
        "## Diebold-Mariano (perte absolue, Newey-West 11 retards, Student n−1)",
        "",
        "Statistique négative : le modèle se trompe moins que la référence.",
        "",
        "| Comparaison | Écart moyen de perte | Statistique | p-value |",
        "|---|---|---|---|",
    ]
    for modele in ["modele_realiste", "modele_conditionnel"]:
        for ref in ["r1_persistance", "r2_climatologie"]:
            dm = diebold_mariano(erreurs[modele], erreurs[ref])
            lignes.append(f"| {NOMS[modele]} vs {NOMS[ref]} | {pts(dm.ecart_moyen)} | "
                          f"{signe(dm.statistique)} | {dm.p_valeur:.3f}".replace(".", ",") + " |")

    sans_2022 = officiel[officiel["annee"] != 2022]
    lignes += ["", f"## Sensibilité : 2018–2025 sans 2022 ({len(sans_2022)} mois)", "",
               *tableau_metriques(sans_2022)]

    lignes += ["", "## MAE par année", "",
               "| Année | " + " | ".join(NOMS[m] for m in METHODES) + " |",
               "|---|" + "---|" * len(METHODES)]
    for annee, groupe in officiel.groupby("annee"):
        lignes.append(f"| {annee} | " + " | ".join(pts(mae(groupe[m] - groupe["taux_capture"])) for m in METHODES) + " |")

    annuels = taux_annuels(previsions[previsions["annee"].isin(ANNEES_OFFICIELLES)])
    lignes += ["", "## Taux de capture annuel (avec baseload et volumes réalisés)", "",
               "Réalisé en %, puis erreur de chaque méthode en points.", "",
               "| Année | Réalisé | " + " | ".join(NOMS[m] for m in METHODES) + " |",
               "|---|---|" + "---|" * len(METHODES)]
    for _, a in annuels.iterrows():
        lignes.append(f"| {int(a['annee'])} | {pts(a['taux_capture'])} | "
                      + " | ".join(pts(a[m] - a["taux_capture"]) for m in METHODES) + " |")
    lignes.append("| **MAE** | | " + " | ".join(
        f"**{pts((annuels[m] - annuels['taux_capture']).abs().mean())}**" for m in METHODES) + " |")

    a_part = echantillon_commun(previsions[previsions["annee"] == ANNEE_A_PART])
    lignes += ["", f"## {ANNEE_A_PART}, rapporté à part ({len(a_part)} mois valides, hors verdict)", "",
               *tableau_metriques(a_part), "",
               "| Mois | Réalisé | Part solaire réalisée / prévue | " + " | ".join(NOMS[m] for m in METHODES) + " |",
               "|---|---|---|" + "---|" * len(METHODES)]
    for _, r in a_part.iterrows():
        lignes.append(f"| {r['periode']} | {pts(r['taux_capture'])} | {pts(r['part_solaire'])} / "
                      f"{pts(r['part_solaire_prevue'])} % | " + " | ".join(pts(r[m]) for m in METHODES) + " |")

    lignes += ["", "## Paramètres estimés à chaque calibration", "",
               "| Année prévue | Mois de calibration | β |", "|---|---|---|"]
    for _, p in parametres.iterrows():
        lignes.append(f"| {int(p['annee'])} | {int(p['n_mois_calibration'])} | {p['beta']:.2f} |".replace(".", ","))

    texte = "\n".join(lignes) + "\n"
    (DOSSIER / "rapport.md").write_text(texte)
    print(texte)


if __name__ == "__main__":
    main()
