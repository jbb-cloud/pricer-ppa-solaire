"""Robustesse des conclusions d'un backtest : année retirée et bootstrap par années entières.

Le test de Diebold-Mariano suppose une série assez longue. Avec 8 années, on regarde aussi directement si une conclusion dépend
d'une seule année. Le bootstrap tire des années entières, parce que les mois d'une même année partagent le même régime de prix :
tirer des mois séparés donnerait un intervalle trop étroit. Avec 8 blocs, il reste approximatif : c'est un ordre de grandeur.
"""

import numpy as np
import pandas as pd


def _pertes_par_annee(table: pd.DataFrame, methode: str, reference: str) -> pd.DataFrame:
    e = table.dropna(subset=["taux_capture", methode, reference])
    return pd.DataFrame(
        {
            "methode": (e[methode] - e["taux_capture"]).abs().groupby(e["annee"]).sum(),
            "reference": (e[reference] - e["taux_capture"]).abs().groupby(e["annee"]).sum(),
        }
    )


def skill_global(table: pd.DataFrame, methode: str, reference: str) -> float:
    """Skill sur tous les mois de ``table`` : 1 − MAE de la méthode / MAE de la référence."""
    p = _pertes_par_annee(table, methode, reference).sum()
    return float(1 - p["methode"] / p["reference"])


def skill_sans_chaque_annee(table: pd.DataFrame, methode: str, reference: str) -> pd.Series:
    """Skill en retirant tour à tour chaque année, indexé par l'année retirée."""
    p = _pertes_par_annee(table, methode, reference)
    total = p.sum()
    return 1 - (total["methode"] - p["methode"]) / (total["reference"] - p["reference"])


def bootstrap_skill(table: pd.DataFrame, methode: str, reference: str, n: int, rng: np.random.Generator) -> np.ndarray:
    """Skills obtenus en tirant des années entières avec remise, autant que d'années observées."""
    p = _pertes_par_annee(table, methode, reference).to_numpy()
    tirage = rng.integers(len(p), size=(n, len(p)))
    return 1 - p[tirage, 0].sum(axis=1) / p[tirage, 1].sum(axis=1)
