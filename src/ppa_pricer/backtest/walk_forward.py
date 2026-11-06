"""Backtest walk-forward du modèle V1 contre les références naïves.

Pour chaque année de test $T$ : calibration sur les mois strictement antérieurs au 1er janvier
$T$, puis prévision des 12 mois de $T$ par quatre méthodes :
- ``modele_realiste`` : modèle V1 avec la part du solaire prévue (H4) ;
- ``modele_conditionnel`` : modèle V1 avec la part du solaire réalisée (variante « oracle » sur
  cette seule entrée, pour tester la relation part du solaire → taux de capture) ;
- ``r1_persistance`` et ``r2_climatologie`` : références naïves.
"""

import pandas as pd

from ppa_pricer.backtest.references import climatologie, persistance
from ppa_pricer.modele.v1 import calibrer, prevoir, prevoir_part_solaire

METHODES = ["modele_realiste", "modele_conditionnel", "r1_persistance", "r2_climatologie"]


def prevoir_annee(mensuel: pd.DataFrame, annee: int) -> tuple[pd.DataFrame, dict]:
    """Prévisions des 12 mois de ``annee`` et paramètres estimés, sans donnée de ``annee`` ni après.

    Les colonnes réalisées (taux de capture, part du solaire, baseload, énergie) sont jointes
    après les prévisions, uniquement pour l'évaluation.
    """
    parametres = calibrer(mensuel, annee)
    mois = pd.Series(range(1, 13), index=range(1, 13), name="mois")
    part_prevue = prevoir_part_solaire(mensuel, annee)
    prevision = pd.DataFrame(
        {
            "mois": mois,
            "part_solaire_prevue": part_prevue,
            "modele_realiste": prevoir(parametres, mois, part_prevue),
            "r1_persistance": persistance(mensuel, annee),
            "r2_climatologie": climatologie(mensuel, annee),
        }
    )

    realise = mensuel[mensuel["periode"].dt.year == annee]
    realise = realise.set_index(realise["periode"].dt.month).reindex(mois.index)
    prevision["periode"] = pd.period_range(f"{annee}-01", periods=12, freq="M")
    prevision["annee"] = annee
    for colonne in ["valide", "taux_capture", "part_solaire", "baseload_eur_mwh", "energie_solaire_mwh",
                    "heures_utilisees"]:
        prevision[colonne] = realise[colonne].to_numpy()
    prevision["modele_conditionnel"] = prevoir(parametres, mois, prevision["part_solaire"])

    infos = {"annee": annee, "beta": parametres.beta, "n_mois_calibration": parametres.n_mois,
             **{f"alpha_{m:02d}": a for m, a in parametres.alpha.items()}}
    return prevision.reset_index(drop=True), infos


def backtest(mensuel: pd.DataFrame, annees: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Prévisions de toutes les années de test (une ligne par mois) et paramètres par année."""
    resultats = [prevoir_annee(mensuel, annee) for annee in annees]
    previsions = pd.concat([r[0] for r in resultats], ignore_index=True)
    parametres = pd.DataFrame([r[1] for r in resultats])
    return previsions, parametres


def echantillon_commun(previsions: pd.DataFrame) -> pd.DataFrame:
    """Mois où le réalisé et toutes les méthodes sont disponibles : toutes jugées sur les mêmes mois."""
    return previsions.dropna(subset=["taux_capture", *METHODES]).sort_values("periode", ignore_index=True)


def taux_annuels(previsions: pd.DataFrame) -> pd.DataFrame:
    """Taux de capture annuel réalisé et prévu par chaque méthode.

    $\\widehat{TC}_T = \\sum_m \\widehat{TC}_m B_m Q_m / (B_T \\sum_m Q_m)$ avec le baseload $B_m$,
    l'énergie solaire $Q_m$ et le baseload annuel $B_T = \\sum_m B_m H_m / \\sum_m H_m$ réalisés
    ($H_m$ : heures utilisées). Avec les taux mensuels réalisés, on retrouve exactement le taux
    annuel réalisé. Une année dont un mois manque donne NaN.
    """
    lignes = []
    for annee, p in previsions.groupby("annee"):
        b, q, h = p["baseload_eur_mwh"], p["energie_solaire_mwh"], p["heures_utilisees"]
        baseload_annuel = (b * h).sum() / h.sum()
        ligne = {"annee": annee}
        for colonne in ["taux_capture", *METHODES]:
            complet = len(p) == 12 and p[[colonne, "baseload_eur_mwh", "energie_solaire_mwh"]].notna().all().all()
            ligne[colonne] = (p[colonne] * b * q).sum() / (baseload_annuel * q.sum()) if complet else float("nan")
        lignes.append(ligne)
    return pd.DataFrame(lignes)
