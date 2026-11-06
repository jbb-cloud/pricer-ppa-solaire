"""Test d'un lambda par heure et par saison sur la chute de 2024 (`docs/stochastique.md`).

Usage : ``.venv/bin/python scripts/tester_lambda_plages.py``, après ``scripts/tester_chute_2024.py``.
Écrit ``reports/backtest/m2/lambda_plages.md`` et ``lambda_plages.csv``. Ne modifie ni la base ni les autres rapports.
Ce test donne au modèle les valeurs réelles de l'année : ce n'est pas une prévision et il n'a pas de verdict sur M2.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from tester_chute_2024 import ANNEES, ANNEES_REFERENCE, BASE, DOSSIER, charger, nb, pts, signe

from ppa_pricer.analyse.capture import taux_de_capture
from ppa_pricer.backtest.walk_forward import backtest
from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE
from ppa_pricer.modele.facteurs import (
    MOIS_ETE,
    VARIANTES,
    calibrer_facteurs,
    calibrer_plages,
    explique_la_chute,
    simuler_plages,
    simuler_valeurs_reelles,
    taux_capture_median,
)
from ppa_pricer.modele.m0 import GRAINE, N_TRAJECTOIRES, cases, prix_normalises

VARIANTE = VARIANTES["D"]
MIDI = (11, 16)
METHODES = {"A": "A, référence", "D": "D, λ unique", "P": "D, λ par heure × saison"}


def simuler(code: str, horaire: pd.DataFrame, annee: int):
    rng = np.random.default_rng([GRAINE, annee])
    if code == "P":
        p = calibrer_plages(horaire, annee, VARIANTE)
        return (*simuler_plages(p, horaire, VARIANTE, N_TRAJECTOIRES, rng), p)
    v = VARIANTES[code]
    p = calibrer_facteurs(horaire, annee, v)
    return (*simuler_valeurs_reelles(p, horaire, v, N_TRAJECTOIRES, rng), p)


def main() -> None:
    horaire = charger()
    previsions, _ = backtest(taux_de_capture(horaire, "M"), ANNEES)
    reel = previsions.dropna(subset=["taux_capture"]).set_index(["annee", "mois"])["taux_capture"]

    lignes_csv, modeles, ete_2024 = [], {}, {}
    for code in METHODES:
        for annee in ANNEES:
            y, q, ts, p = simuler(code, horaire, annee)
            realise = reel.xs(annee, level="annee")
            erreur = (taux_capture_median(y, q, ts).reindex(realise.index) - realise).dropna()
            lignes_csv.append(
                {
                    "methode": code,
                    "annee": annee,
                    "n_mois": len(erreur),
                    "mae": erreur.abs().mean(),
                    "biais": erreur.mean(),
                    "biais_ete": erreur.loc[MOIS_ETE[0] : MOIS_ETE[1]].mean(),
                    "biais_autres": erreur.drop(range(MOIS_ETE[0], MOIS_ETE[1] + 1), errors="ignore").mean(),
                }
            )
            if annee == 2024:
                c = cases(ts)
                ete, midi = c["mois"].between(*MOIS_ETE).to_numpy(), c["heure"].between(*MIDI).to_numpy()
                ete_2024[code] = (np.nanmean(y[ete & midi]), np.nanmean(y[ete & ~midi]))
            if code == "P":
                modeles[annee] = p
    bilan = pd.DataFrame(lignes_csv)
    DOSSIER.mkdir(parents=True, exist_ok=True)
    bilan.to_csv(DOSSIER / "lambda_plages.csv", index=False, float_format="%.5f")

    def valeur(code, annee, colonne):
        return bilan[(bilan["methode"] == code) & (bilan["annee"] == annee)][colonne].iloc[0]

    def mae_reference(code):
        g = bilan[(bilan["methode"] == code) & bilan["annee"].isin(ANNEES_REFERENCE)]
        return (g["mae"] * g["n_mois"]).sum() / g["n_mois"].sum()

    reference = mae_reference("A")
    lignes = [
        "# Test d'un λ par heure et par saison",
        "",
        f"Généré le {pd.Timestamp.now(tz=FUSEAU_AFFICHAGE):%d/%m/%Y}. Valeurs réelles de l'année données au modèle : ce n'est pas une prévision. "
        f"{N_TRAJECTOIRES} trajectoires par année, graine {GRAINE}. Définition, attentes et règle écrites avant le lancement : `docs/stochastique.md`.",
        "",
        "## Résultat de la règle",
        "",
        "Biais de 2024 sous 5 points en valeur absolue, sans dégrader l'erreur de 2018–2023 de plus de 0,5 point par rapport à A.",
        "",
        "| Méthode | Biais 2024 | Erreur 2024 | Erreur 2018–2023 | Règle | Biais 2025 | Erreur 2025 | Biais 2026 (à part) | Erreur 2026 (à part) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for code, nom in METHODES.items():
        verdict = explique_la_chute(valeur(code, 2024, "biais"), mae_reference(code), reference)
        lignes.append(
            f"| {nom} | {signe(valeur(code, 2024, 'biais'))} | {pts(valeur(code, 2024, 'mae'))} | {pts(mae_reference(code))} | {'**oui**' if verdict else 'non'} "
            f"| {signe(valeur(code, 2025, 'biais'))} | {pts(valeur(code, 2025, 'mae'))} | {signe(valeur(code, 2026, 'biais'))} | {pts(valeur(code, 2026, 'mae'))} |"
        )

    y_reel = prix_normalises(horaire, [2024])
    c = cases(y_reel.index)
    ete, midi = c["mois"].between(*MOIS_ETE).to_numpy(), c["heure"].between(*MIDI).to_numpy()
    reel_midi, reel_autres = y_reel[ete & midi].mean(), y_reel[ete & ~midi].mean()
    lignes += ["", "## Avril–août 2024, en part du baseload annuel", "", "| Cas | Midi (11–16 h) | Autres heures | Ratio | Biais du taux de capture, avril–août | Biais, autres mois |", "|---|---|---|---|---|---|",
               f"| Réel | {nb(reel_midi)} | {nb(reel_autres)} | {nb(reel_midi / reel_autres)} | — | — |"]
    for code, nom in METHODES.items():
        m, a = ete_2024[code]
        lignes.append(f"| {nom} | {nb(m)} | {nb(a)} | {nb(m / a)} | {signe(valeur(code, 2024, 'biais_ete'))} | {signe(valeur(code, 2024, 'biais_autres'))} |")

    lignes += ["", "## Biais par année", "", "| Année | " + " | ".join(METHODES.values()) + " |", "|---|" + "---|" * len(METHODES)]
    for annee in ANNEES:
        lignes.append(f"| {annee} | " + " | ".join(signe(valeur(code, annee, "biais")) for code in METHODES) + " |")

    lignes += ["", "## λ estimés", "", "Moyenne par plage, avril–août, sur la fenêtre de calibration de chaque année testée.", "",
               "| Année testée | Nuit 0–6 h | Matin 7–10 h | Midi 11–16 h | Soir 17–23 h | Autres mois, tout | Plus petit | Plus grand |", "|---|---|---|---|---|---|---|---|"]
    for annee in ANNEES:
        lam = modeles[annee].lambdas
        ete_l = lam.xs(True, level="ete")
        lignes.append(
            f"| {annee} | {nb(ete_l.loc[0:6].mean())} | {nb(ete_l.loc[7:10].mean())} | {nb(ete_l.loc[11:16].mean())} | {nb(ete_l.loc[17:23].mean())} "
            f"| {nb(lam.xs(False, level='ete').mean())} | {nb(lam.min())} | {nb(lam.max())} |"
        )
    lignes.append("")
    texte = "\n".join(lignes)
    (DOSSIER / "lambda_plages.md").write_text(texte)
    print(texte)


if __name__ == "__main__":
    main()
