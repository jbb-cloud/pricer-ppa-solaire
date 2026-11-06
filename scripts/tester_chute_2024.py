"""Test de la chute de 2024 : quelle variable explique l'erreur de M2 (`docs/stochastique.md`) ?

Usage : ``.venv/bin/python scripts/tester_chute_2024.py``, après ``scripts/telecharger_voisins.py``.
Écrit ``reports/backtest/m2/chute_2024.md`` et ``chute_2024.csv``. Ne modifie ni la base ni les autres rapports.
Ce test donne au modèle les valeurs réelles de l'année : ce n'est pas une prévision et il n'a pas de verdict sur M2.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ppa_pricer.analyse.capture import charger_horaire, taux_de_capture
from ppa_pricer.backtest.walk_forward import backtest
from ppa_pricer.donnees.base import connexion
from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE
from ppa_pricer.donnees.energy_charts import agreger_horaire, charger_eolien, charger_filiere, lire_prix_brut
from ppa_pricer.modele.facteurs import HYDRO, VARIANTES, calibrer_facteurs, explique_la_chute, simuler_valeurs_reelles, taux_capture_median
from ppa_pricer.modele.m0 import GRAINE, N_TRAJECTOIRES, cases

RACINE = Path(__file__).resolve().parents[1]
BASE = RACINE / "data" / "ppa.sqlite"
BRUTS = RACINE / "data" / "raw" / "energy_charts"
DOSSIER = RACINE / "reports" / "backtest" / "m2"
ANNEES = list(range(2018, 2027))
ANNEES_REFERENCE = list(range(2018, 2024))
ANNEES_LECTURE = [2019, 2021, 2022, 2023, 2024, 2025]


def pts(x: float) -> str:
    return "n.d." if pd.isna(x) else f"{x * 100:.1f}".replace(".", ",")


def signe(x: float) -> str:
    return "n.d." if pd.isna(x) else f"{x * 100:+.1f}".replace(".", ",").replace("-", "−")


def nb(x: float) -> str:
    return "n.d." if pd.isna(x) else f"{x:.2f}".replace(".", ",").replace("-", "−")


def charger() -> pd.DataFrame:
    horaire = charger_horaire(connexion(BASE)).merge(charger_eolien(BRUTS), on="ts_utc", how="left")
    ajouts = [
        charger_filiere(BRUTS, "Nuclear", "nucleaire_mw"),
        charger_filiere(BRUTS, "Hydro Run-of-River", HYDRO),
        charger_filiere(BRUTS, "Residual load", "charge_de_mw", pays="de"),
        charger_filiere(BRUTS, "Residual load", "charge_es_mw", pays="es"),
    ]
    for ajout in ajouts:
        horaire = horaire.merge(ajout, on="ts_utc", how="left")
    return horaire


def prix_zone(*zones: str) -> pd.Series:
    """Prix horaires d'un pays, en réunissant ses zones successives."""
    morceaux = []
    for zone in zones:
        for chemin in sorted(BRUTS.glob(f"prix_{zone}_*.json")):
            morceaux.append(lire_prix_brut(chemin).dropna(subset=["prix_eur_mwh"]))
    serie = pd.concat(morceaux, ignore_index=True).drop_duplicates("ts_utc").sort_values("ts_utc")
    return agreger_horaire(serie).set_index("ts_utc")["prix_eur_mwh"]


def lecture_convergence(horaire: pd.DataFrame) -> list[str]:
    """Médianes et convergence des prix à midi, d'avril à août : description, sans lien de cause à effet."""
    fr = horaire.dropna(subset=["prix_eur_mwh"]).set_index("ts_utc")["prix_eur_mwh"]
    prix = pd.DataFrame({"fr": fr, "de": prix_zone("DE-AT-LU", "DE-LU"), "es": prix_zone("ES")}).reindex(fr.index)
    c = cases(prix.index)
    prix = prix[c["heure"].between(11, 16) & c["mois"].between(4, 8)]
    annee = prix.index.tz_convert(FUSEAU_AFFICHAGE).year
    lignes = ["| Année | Prix FR (€/MWh) | Prix DE | Prix ES | Écart FR–DE sous 1 € | Écart FR–ES sous 1 € |", "|---|---|---|---|---|---|"]
    for a in ANNEES_LECTURE:
        g = prix[annee == a]
        lignes.append(
            f"| {a} | {nb(g['fr'].median())} | {nb(g['de'].median())} | {nb(g['es'].median())} "
            f"| {pts(((g['fr'] - g['de']).abs() < 1).mean())} % | {pts(((g['fr'] - g['es']).abs() < 1).mean())} % |"
        )
    return lignes


def main() -> None:
    horaire = charger()
    previsions, _ = backtest(taux_de_capture(horaire, "M"), ANNEES)
    reel = previsions.dropna(subset=["taux_capture"]).set_index(["annee", "mois"])["taux_capture"]

    lignes_csv, coefficients = [], {}
    for code, variante in VARIANTES.items():
        for annee in ANNEES:
            p = calibrer_facteurs(horaire, annee, variante)
            y, q, ts = simuler_valeurs_reelles(p, horaire, variante, N_TRAJECTOIRES, np.random.default_rng([GRAINE, annee]))
            modele = taux_capture_median(y, q, ts)
            realise = reel.xs(annee, level="annee")
            erreur = (modele.reindex(realise.index) - realise).dropna()
            lignes_csv.append({"variante": code, "annee": annee, "n_mois": len(erreur), "mae": erreur.abs().mean(), "biais": erreur.mean(), "variance_expliquee": p.variance_expliquee})
            coefficients[(code, annee)] = p.coefficients
    bilan = pd.DataFrame(lignes_csv)
    DOSSIER.mkdir(parents=True, exist_ok=True)
    bilan.to_csv(DOSSIER / "chute_2024.csv", index=False, float_format="%.5f")

    def valeur(code, annee, colonne):
        return bilan[(bilan["variante"] == code) & (bilan["annee"] == annee)][colonne].iloc[0]

    def mae_reference(code):
        g = bilan[(bilan["variante"] == code) & bilan["annee"].isin(ANNEES_REFERENCE)]
        return (g["mae"] * g["n_mois"]).sum() / g["n_mois"].sum()

    lignes = [
        "# Test de la chute de 2024",
        "",
        f"Généré le {pd.Timestamp.now(tz=FUSEAU_AFFICHAGE):%d/%m/%Y}. Valeurs réelles de l'année données au modèle : ce n'est pas une prévision. "
        f"{N_TRAJECTOIRES} trajectoires par année, graine {GRAINE}. Règle écrite avant le lancement : `docs/stochastique.md`.",
        "",
        "## Résultat de la règle",
        "",
        "Une variante explique 2024 si son biais de 2024 est sous 5 points en valeur absolue, sans dégrader l'erreur de 2018–2023 de plus de 0,5 point par rapport à A.",
        "",
        "| Variante | Biais 2024 | Erreur 2024 | Erreur 2018–2023 | Règle | Biais 2025 | Erreur 2025 | Biais 2026 (à part) | Erreur 2026 (à part) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    reference = mae_reference("A")
    for code, variante in VARIANTES.items():
        verdict = explique_la_chute(valeur(code, 2024, "biais"), mae_reference(code), reference)
        lignes.append(
            f"| {code}, {variante.nom} | {signe(valeur(code, 2024, 'biais'))} | {pts(valeur(code, 2024, 'mae'))} | {pts(mae_reference(code))} "
            f"| {'**oui**' if verdict else 'non'} | {signe(valeur(code, 2025, 'biais'))} | {pts(valeur(code, 2025, 'mae'))} "
            f"| {signe(valeur(code, 2026, 'biais'))} | {pts(valeur(code, 2026, 'mae'))} |"
        )

    lignes += ["", "## Biais par année", "", "| Année | " + " | ".join(VARIANTES) + " |", "|---|" + "---|" * len(VARIANTES)]
    for annee in ANNEES:
        lignes.append(f"| {annee} | " + " | ".join(signe(valeur(code, annee, "biais")) for code in VARIANTES) + " |")

    lignes += ["", "## Coefficients de la variante F, et part expliquée", "", "| Année testée | France | Allemagne | Espagne | Part expliquée de $z$ |", "|---|---|---|---|---|"]
    for annee in ANNEES:
        c = coefficients[("F", annee)]
        lignes.append(f"| {annee} | {nb(c['france'])} | {nb(c['charge_de_mw'])} | {nb(c['charge_es_mw'])} | {nb(valeur('F', annee, 'variance_expliquee'))} |")

    lignes += ["", "## Lecture descriptive : prix à midi, avril–août", "", "Médianes et part des heures avec un écart de prix sous 1 €/MWh. Un écart faible montre un couplage, pas sa cause.", "", *lecture_convergence(horaire), ""]
    texte = "\n".join(lignes)
    (DOSSIER / "chute_2024.md").write_text(texte)
    print(texte)


if __name__ == "__main__":
    main()
