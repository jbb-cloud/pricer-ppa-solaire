"""Métriques du backtest (voir `docs/perimetre.md`, protocole et journal des modifications).

Toutes les erreurs sont en points de taux de capture : erreur = prévision − réalisé.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

RETARDS_NEWEY_WEST = 11


def mae(erreurs: pd.Series) -> float:
    """Erreur absolue moyenne."""
    return float(erreurs.abs().mean())


def biais(erreurs: pd.Series) -> float:
    """Erreur moyenne signée : positive si la méthode surestime le taux de capture."""
    return float(erreurs.mean())


def mae_ponderee(erreurs: pd.Series, poids: pd.Series) -> float:
    """MAE où chaque mois pèse selon ``poids`` (l'énergie solaire réalisée du mois)."""
    return float((erreurs.abs() * poids).sum() / poids.sum())


def skill_score(mae_methode: float, mae_reference: float) -> float:
    """1 − MAE méthode / MAE référence : > 0 si la méthode fait mieux que la référence."""
    return 1 - mae_methode / mae_reference


def couverture(realise: pd.Series, bas: pd.Series, haut: pd.Series) -> float:
    """Part des réalisés comprise dans l'intervalle ; un intervalle à 90 % fiable donne environ 0,90."""
    return float(((realise >= bas) & (realise <= haut)).mean())


def variance_long_terme(d: np.ndarray, retards: int) -> float:
    """Variance de long terme de Newey-West (noyau de Bartlett) d'une série ordonnée dans le temps.

    $\\hat V = \\hat\\gamma_0 + 2\\sum_{k=1}^{L}(1 - k/(L+1))\\,\\hat\\gamma_k$ ; les poids de Bartlett
    garantissent $\\hat V \\geq 0$.
    """
    centre = d - d.mean()
    n = len(d)
    v = centre @ centre / n
    for k in range(1, min(retards, n - 1) + 1):
        v += 2 * (1 - k / (retards + 1)) * (centre[k:] @ centre[:-k]) / n
    return float(v)


@dataclass(frozen=True)
class ResultatDM:
    statistique: float
    p_valeur: float
    n: int
    ecart_moyen: float


def diebold_mariano(erreurs_a: pd.Series, erreurs_b: pd.Series, retards: int = RETARDS_NEWEY_WEST) -> ResultatDM:
    """Test de Diebold-Mariano à perte absolue : H0, les deux méthodes ont la même précision.

    $d_t = |e^A_t| - |e^B_t|$ ; statistique $\\bar d / \\sqrt{\\hat V / n}$ avec $\\hat V$ de
    Newey-West ; p-value bilatérale d'une loi de Student à $n - 1$ degrés de liberté (plus
    prudente que la loi normale en petit échantillon). Statistique négative : A meilleure.
    Les erreurs doivent être alignées et triées dans le temps.
    """
    d = (erreurs_a.abs() - erreurs_b.abs()).to_numpy(dtype=float)
    n = len(d)
    statistique = d.mean() / np.sqrt(variance_long_terme(d, retards) / n)
    p_valeur = 2 * stats.t.sf(abs(statistique), df=n - 1)
    return ResultatDM(float(statistique), float(p_valeur), n, float(d.mean()))
