"""Modèle M1 : loi empirique des prix par case et deux Ornstein-Uhlenbeck latents.

Dans chaque case (mois × heure × week-end), le prix normalisé $y_t$ est remplacé par son score normal
$z_t = \\Phi^{-1}((r_t - 0{,}5)/n)$, avec $r_t$ son rang et $n$ la taille de la case. Ce score suit

$$z_t = \\sqrt{w}\\,a_t + \\sqrt{1-w}\\,b_t,$$

où $a$ et $b$ sont deux AR(1) indépendants de variance 1, l'un rapide, l'autre lent. Pour simuler, on
revient aux prix par la loi empirique de la case : $y_t = F^{-1}_{\\text{case}}(\\Phi(z_t))$. On parle de
copule gaussienne : la dépendance dans le temps est gaussienne, pas la loi des prix.

Pourquoi cette forme (voir `docs/stochastique.md`) : garder la loi réelle de chaque case reproduit les
queues épaisses et les prix bloqués près de 0, sans état de surplus explicite. Les rangs rendent aussi la
dynamique insensible à la taille des pics. Il reste 3 paramètres de dynamique. Limites : aucun prix simulé
ne dépasse ceux observés dans la case, et la prévision centrale reste liée au profil passé.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import optimize, stats

from ppa_pricer.modele.m0 import (
    CLES_CASE,
    FENETRE_ANNEES,
    GRAINE,
    N_TRAJECTOIRES,
    QUANTILES_INTERVALLE,
    cases,
    grille_annee,
    prix_normalises,
    profil_solaire,
    taux_capture_simules,
)

RETARDS_AJUSTEMENT = np.arange(1, 73)


@dataclass(frozen=True)
class ParametresM1:
    lois: dict[tuple[int, int, bool], np.ndarray]
    profil_solaire: pd.Series
    poids_rapide: float
    phi_rapide: float
    phi_lent: float
    erreur_ajustement: float
    annee_prevue: int

    @property
    def demi_vie_rapide_h(self) -> float:
        return float(np.log(2) / -np.log(self.phi_rapide))

    @property
    def demi_vie_lente_h(self) -> float:
        return float(np.log(2) / -np.log(self.phi_lent))


def scores_normaux(y: pd.Series) -> pd.Series:
    """Score normal de chaque prix dans sa case. Les ex æquo, fréquents à 0, reçoivent le même score."""
    c = cases(y.index)
    groupes = y.groupby([c[k] for k in CLES_CASE])
    rangs = (groupes.rank(method="average") - 0.5) / groupes.transform("size")
    return pd.Series(stats.norm.ppf(rangs), index=y.index)


def autocorrelations(z: pd.Series, retards: np.ndarray) -> np.ndarray:
    """Autocorrélation aux ``retards`` (en heures), sur une grille horaire : un trou reste un trou."""
    grille = pd.date_range(z.index.min(), z.index.max(), freq="h")
    v = z.reindex(grille).to_numpy()
    resultat = []
    for k in retards:
        a, b = v[k:], v[:-k]
        connus = ~np.isnan(a) & ~np.isnan(b)
        resultat.append(np.corrcoef(a[connus], b[connus])[0, 1])
    return np.array(resultat)


def ajuster_deux_vitesses(acf: np.ndarray, retards: np.ndarray) -> tuple[float, float, float, float]:
    """Ajuste $w\\varphi_r^k + (1-w)\\varphi_l^k$ aux moindres carrés.

    Renvoie le poids rapide, $\\varphi_r$, $\\varphi_l$ et l'erreur quadratique moyenne ; $\\varphi_r \\leq \\varphi_l$.
    """

    def ecarts(t):
        return t[0] * t[1] ** retards + (1 - t[0]) * t[2] ** retards - acf

    solution = optimize.least_squares(ecarts, [0.4, 0.85, 0.99], bounds=([0, 0.01, 0.01], [1, 0.9999, 0.9999]))
    w, phi_a, phi_b = solution.x
    if phi_a > phi_b:
        w, phi_a, phi_b = 1 - w, phi_b, phi_a
    return float(w), float(phi_a), float(phi_b), float(np.sqrt(np.mean(solution.fun**2)))


def calibrer_m1(horaire: pd.DataFrame, annee: int, fenetre: int = FENETRE_ANNEES) -> ParametresM1:
    """Estime M1 sur les ``fenetre`` années civiles précédant ``annee`` (aucune donnée de ``annee`` ni après)."""
    annees = list(range(annee - fenetre, annee))
    y = prix_normalises(horaire, annees)
    c = cases(y.index)
    lois = {cle: np.sort(g.to_numpy()) for cle, g in y.groupby([c[k] for k in CLES_CASE])}
    acf = autocorrelations(scores_normaux(y), RETARDS_AJUSTEMENT)
    w, phi_r, phi_l, erreur = ajuster_deux_vitesses(acf, RETARDS_AJUSTEMENT)
    return ParametresM1(lois, profil_solaire(horaire, annees), w, phi_r, phi_l, erreur, annee)


def simuler_latente(p: ParametresM1, n_heures: int, n: int, rng: np.random.Generator) -> np.ndarray:
    """Trajectoires de $z_t$ (lignes : heures, colonnes : trajectoires), de variance 1, en régime stationnaire."""
    a, b = rng.standard_normal(n), rng.standard_normal(n)
    k_r, k_l = np.sqrt(1 - p.phi_rapide**2), np.sqrt(1 - p.phi_lent**2)
    poids_r, poids_l = np.sqrt(p.poids_rapide), np.sqrt(1 - p.poids_rapide)
    z = np.empty((n_heures, n))
    z[0] = poids_r * a + poids_l * b
    for t in range(1, n_heures):
        a = p.phi_rapide * a + k_r * rng.standard_normal(n)
        b = p.phi_lent * b + k_l * rng.standard_normal(n)
        z[t] = poids_r * a + poids_l * b
    return z


def prix_depuis_scores(lois: dict[tuple[int, int, bool], np.ndarray], z: np.ndarray, ts: pd.DatetimeIndex) -> np.ndarray:
    """Revient de $z_t$ à $y_t$ par la loi empirique de chaque case, sans dépasser ses valeurs observées."""
    u = stats.norm.cdf(z)
    c = cases(ts)
    y = np.empty_like(u)
    for cle, positions in c.groupby(CLES_CASE).indices.items():
        loi = lois.get(cle)
        if loi is None:
            raise ValueError(f"La case {cle} de la période simulée n'a aucune observation")
        y[positions] = np.interp(u[positions], (np.arange(len(loi)) + 0.5) / len(loi), loi)
    return y


def simuler_prix_normalises(p: ParametresM1, ts: pd.DatetimeIndex, n: int, rng: np.random.Generator) -> np.ndarray:
    """Trajectoires de $y_t$ : la loi empirique de chaque case, sans dépasser ses valeurs observées."""
    return prix_depuis_scores(p.lois, simuler_latente(p, len(ts), n, rng), ts)


def prevoir_m1(
    horaire: pd.DataFrame, annee: int, n: int = N_TRAJECTOIRES, graine: int = GRAINE, fenetre: int = FENETRE_ANNEES
) -> tuple[pd.DataFrame, ParametresM1]:
    """Médiane et intervalle à 90 % du taux de capture des 12 mois de ``annee``."""
    p = calibrer_m1(horaire, annee, fenetre)
    ts = grille_annee(annee)
    y = simuler_prix_normalises(p, ts, n, np.random.default_rng([graine, annee]))
    tc = taux_capture_simules(y, ts, p.profil_solaire)
    bas, haut = QUANTILES_INTERVALLE
    prevision = pd.DataFrame({"tc": tc.median(axis=1), "tc_bas": tc.quantile(bas, axis=1), "tc_haut": tc.quantile(haut, axis=1)})
    return prevision.rename_axis("mois").reset_index(), p
