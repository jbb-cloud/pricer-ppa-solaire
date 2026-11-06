"""Modèle M2 : M1 conditionné à la charge résiduelle, avec météo tirée et croissance du parc.

La charge résiduelle $R_t$ = consommation − solaire − éolien, réduite dans sa case en $x_t$, agit sur le rang
du prix dans sa case :

$$z_t = \\lambda\\,x_t + \\sqrt{1-\\lambda^2}\\,\\varepsilon_t, \\qquad y_t = F^{-1}_{\\text{case}}(\\Phi(z_t)),$$

où $\\varepsilon_t$ suit les deux Ornstein-Uhlenbeck de M1. Avec $\\lambda = 0$, on retrouve M1.

Pourquoi cette forme (voir `docs/stochastique.md`) : plus de solaire baisse $R_t$, donc le rang, et le prix reste
dans les valeurs observées de la case. Une courbe additive du prix en $R_t$ n'a aucun plancher et donne des taux de
capture absurdes. La sensibilité au parc n'est pas imposée : elle vient de la forme des lois de chaque case.

Pour simuler une année, chaque trajectoire tire la météo par semaines dans la fenêtre et une croissance du parc
parmi celles déjà observées. Limites : aucune réaction du marché à la hausse du parc, voisins et nucléaire non
modélisés, aucun prix hors des valeurs observées, ratio instable quand le prix moyen d'un mois approche 0.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE
from ppa_pricer.modele.m0 import (
    CLES_CASE,
    FENETRE_ANNEES,
    GRAINE,
    N_TRAJECTOIRES,
    QUANTILES_INTERVALLE,
    cases,
    grille_annee,
    prix_normalises,
)
from ppa_pricer.modele.m1 import (
    RETARDS_AJUSTEMENT,
    ajuster_deux_vitesses,
    autocorrelations,
    prix_depuis_scores,
    scores_normaux,
    simuler_latente,
)

SERIES_METEO = ["solaire_mw", "eolien_mw", "conso_mw"]
HEURES_SEMAINE = 168
HEURES_DECALAGE_ANNUEL = 364 * 24
REGLES_CROISSANCE = ("tirage", "h4")


@dataclass(frozen=True)
class ParametresM2:
    lois: dict[tuple[int, int, bool], np.ndarray]
    charge_moyenne: pd.Series
    charge_ecart: pd.Series
    poids_charge: float
    poids_rapide: float
    phi_rapide: float
    phi_lent: float
    erreur_ajustement: float
    formes: dict[int, pd.DataFrame]
    niveaux: pd.Series
    croissances: np.ndarray
    annee_prevue: int

    @property
    def demi_vie_rapide_h(self) -> float:
        return float(np.log(2) / -np.log(self.phi_rapide))

    @property
    def demi_vie_lente_h(self) -> float:
        return float(np.log(2) / -np.log(self.phi_lent))


def croissances_passees(horaire: pd.DataFrame, annee: int) -> np.ndarray:
    """Croissances annuelles de la production solaire moyenne, pour les années civiles avant ``annee``."""
    solaire = horaire.dropna(subset=["solaire_mw"]).set_index("ts_utc").sort_index()["solaire_mw"]
    moyennes = solaire.groupby(solaire.index.tz_convert(FUSEAU_AFFICHAGE).year).mean()
    croissances = moyennes[moyennes.index < annee].pct_change().dropna().to_numpy()
    if len(croissances) == 0:
        raise ValueError(f"Aucune croissance connue avant {annee}")
    return croissances


def formes_meteo(horaire: pd.DataFrame, annees: list[int]) -> dict[int, pd.DataFrame]:
    """Solaire, éolien et consommation de chaque année, divisés par leur moyenne annuelle. Un trou reste NaN."""
    h = horaire.set_index("ts_utc").sort_index()[SERIES_METEO]
    formes = {}
    for annee in annees:
        serie = h.reindex(grille_annee(annee))
        formes[annee] = serie / serie.mean()
    return formes


def calibrer_m2(horaire: pd.DataFrame, annee: int, fenetre: int = FENETRE_ANNEES, regle_croissance: str = "tirage") -> ParametresM2:
    """Estime M2 sur les ``fenetre`` années civiles précédant ``annee`` (aucune donnée de ``annee`` ni après).

    Seules les croissances du parc regardent plus loin que la fenêtre, jamais au-delà de ``annee - 1``.
    ``regle_croissance`` vaut ``"tirage"`` (toutes les croissances passées) ou ``"h4"`` (la dernière seule).
    """
    if regle_croissance not in REGLES_CROISSANCE:
        raise ValueError(f"Règle de croissance inconnue : {regle_croissance}")
    annees = list(range(annee - fenetre, annee))
    y = prix_normalises(horaire, annees)
    h = horaire.set_index("ts_utc").sort_index()
    charge = (h["conso_mw"] - h["solaire_mw"] - h["eolien_mw"]).reindex(y.index)
    c = cases(y.index)
    cles = [c[k] for k in CLES_CASE]
    groupes = charge.groupby(cles)
    x = (charge - groupes.transform("mean")) / groupes.transform("std")
    z = scores_normaux(y)
    connus = x.notna()
    lam = float(np.corrcoef(x[connus], z[connus])[0, 1])
    if not -1 < lam < 1:
        raise ValueError(f"Lien entre charge résiduelle et prix non estimable : lambda = {lam}")
    bruit = ((z - lam * x) / np.sqrt(1 - lam**2))[connus]
    w, phi_r, phi_l, erreur = ajuster_deux_vitesses(autocorrelations(bruit, RETARDS_AJUSTEMENT), RETARDS_AJUSTEMENT)
    croissances = croissances_passees(horaire, annee)
    return ParametresM2(
        lois={cle: np.sort(g.to_numpy()) for cle, g in y.groupby(cles)},
        charge_moyenne=groupes.mean(),
        charge_ecart=groupes.std(),
        poids_charge=lam,
        poids_rapide=w,
        phi_rapide=phi_r,
        phi_lent=phi_l,
        erreur_ajustement=erreur,
        formes=formes_meteo(horaire, annees),
        niveaux=h[SERIES_METEO].reindex(grille_annee(annee - 1)).mean(),
        croissances=croissances[-1:] if regle_croissance == "h4" else croissances,
        annee_prevue=annee,
    )


def positions_source(ts: pd.DatetimeIndex, annee: int, annee_source: int, forme: pd.DataFrame) -> np.ndarray:
    """Position dans ``forme`` de l'heure source de chaque heure de ``ts``, par blocs d'une semaine.

    Le décalage est un multiple de 7 jours : le jour de la semaine et l'heure UTC sont conservés, et l'heure de Paris
    aussi, sauf quelques jours autour des changements d'heure. Une semaine incomplète est remplacée par la semaine
    complète la plus proche de la même année : on ne fabrique aucune valeur.
    """
    complet = forme.notna().all(axis=1).to_numpy()
    n = len(forme)
    decalage = HEURES_DECALAGE_ANNUEL * (annee - annee_source)
    positions = np.empty(len(ts), dtype=int)
    for depart in range(0, len(ts), HEURES_SEMAINE):
        longueur = min(HEURES_SEMAINE, len(ts) - depart)
        origine = int((ts[depart] - forme.index[0]) / pd.Timedelta("1h")) - decalage
        while origine + longueur > n:
            origine -= HEURES_SEMAINE
        while origine < 0:
            origine += HEURES_SEMAINE
        for ecart in range(n // HEURES_SEMAINE + 1):
            candidats = [origine + signe * ecart * HEURES_SEMAINE for signe in ((1,) if ecart == 0 else (-1, 1))]
            valides = [k for k in candidats if k >= 0 and k + longueur <= n and complet[k : k + longueur].all()]
            if valides:
                positions[depart : depart + longueur] = valides[0] + np.arange(longueur)
                break
        else:
            raise ValueError(f"Aucune semaine complète en {annee_source} pour simuler {annee}")
    return positions


def tirer_meteo(p: ParametresM2, ts: pd.DatetimeIndex, n: int, rng: np.random.Generator) -> dict[str, np.ndarray]:
    """Solaire, éolien et consommation en MW (lignes : heures, colonnes : trajectoires).

    Pour chaque semaine, les trois séries viennent de la même année, ce qui garde leur lien physique.
    Le solaire est ensuite ramené au niveau de l'année précédente, multiplié par une croissance tirée par trajectoire.
    """
    annees = sorted(p.formes)
    positions = {a: positions_source(ts, p.annee_prevue, a, p.formes[a]) for a in annees}
    semaine = np.arange(len(ts)) // HEURES_SEMAINE
    choix = rng.integers(len(annees), size=(semaine[-1] + 1, n))[semaine]
    meteo = {}
    for cle in SERIES_METEO:
        par_annee = np.column_stack([p.formes[a][cle].to_numpy()[positions[a]] for a in annees])
        meteo[cle] = np.take_along_axis(par_annee, choix, axis=1) * p.niveaux[cle]
    meteo["solaire_mw"] = meteo["solaire_mw"] * (1 + rng.choice(p.croissances, n))
    return meteo


def simuler_m2(p: ParametresM2, ts: pd.DatetimeIndex, n: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Trajectoires du prix normalisé et de la production solaire (lignes : heures, colonnes : trajectoires)."""
    meteo = tirer_meteo(p, ts, n, rng)
    charge = meteo["conso_mw"] - meteo["solaire_mw"] - meteo["eolien_mw"]
    cle = pd.MultiIndex.from_frame(cases(ts))
    moyenne, ecart = p.charge_moyenne.reindex(cle).to_numpy()[:, None], p.charge_ecart.reindex(cle).to_numpy()[:, None]
    if np.isnan(moyenne).any() or np.isnan(ecart).any() or (ecart == 0).any():
        raise ValueError("Une case de la période simulée n'a pas de charge résiduelle exploitable")
    z = p.poids_charge * (charge - moyenne) / ecart + np.sqrt(1 - p.poids_charge**2) * simuler_latente(p, len(ts), n, rng)
    return prix_depuis_scores(p.lois, z, ts), meteo["solaire_mw"]


def taux_capture_trajectoires(y: np.ndarray, q: np.ndarray, ts: pd.DatetimeIndex) -> pd.DataFrame:
    """Taux de capture de chaque mois (lignes) et trajectoire (colonnes), avec la production de la trajectoire."""
    mois = ts.tz_convert(FUSEAU_AFFICHAGE).month
    return pd.DataFrame({int(m): (q[mois == m] * y[mois == m]).sum(axis=0) / q[mois == m].sum(axis=0) / y[mois == m].mean(axis=0) for m in np.unique(mois)}).T


def prevoir_m2(
    horaire: pd.DataFrame, annee: int, n: int = N_TRAJECTOIRES, graine: int = GRAINE, fenetre: int = FENETRE_ANNEES, regle_croissance: str = "tirage"
) -> tuple[pd.DataFrame, ParametresM2]:
    """Médiane et intervalle à 90 % du taux de capture des 12 mois de ``annee``."""
    p = calibrer_m2(horaire, annee, fenetre, regle_croissance)
    ts = grille_annee(annee)
    y, q = simuler_m2(p, ts, n, np.random.default_rng([graine, annee]))
    tc = taux_capture_trajectoires(y, q, ts)
    bas, haut = QUANTILES_INTERVALLE
    prevision = pd.DataFrame({"tc": tc.median(axis=1), "tc_bas": tc.quantile(bas, axis=1), "tc_haut": tc.quantile(haut, axis=1)})
    return prevision.rename_axis("mois").reset_index(), p
