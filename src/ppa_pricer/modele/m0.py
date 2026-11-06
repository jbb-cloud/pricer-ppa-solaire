"""Modèle M0 : saisonnalité + Ornstein-Uhlenbeck gaussien, au pas horaire.

$$y_t = p_t / B_{\\text{année}(t)} = s(\\text{mois}, \\text{heure}, \\text{week-end}) + x_t,
\\qquad x_{t+1} = \\varphi\\, x_t + \\eta_t,\\quad \\eta_t \\sim \\mathcal N(0, \\sigma_\\eta^2)$$

Un processus d'Ornstein-Uhlenbeck $dx = -\\kappa x\\,dt + \\sigma\\,dW$ observé toutes les heures est
exactement un AR(1) avec $\\varphi = e^{-\\kappa}$ : on estime donc $\\varphi$ par moindres carrés.

M0 est une référence volontairement simple. Son bruit est indépendant de la production, et la
production est un profil moyen sans météo : sa prévision du taux de capture revient presque à
reprendre le profil passé. Sa question est : que manque-t-il à un OU gaussien ? Protocole et attentes
écrits avant le premier résultat dans `docs/stochastique.md`.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE

FENETRE_ANNEES = 2
N_TRAJECTOIRES = 1000
GRAINE = 20261030
QUANTILES_INTERVALLE = (0.05, 0.95)
CLES_CASE = ["mois", "heure", "week_end"]
RETARDS_DIAGNOSTIC = (1, 24, 48, 168)


@dataclass(frozen=True)
class ParametresM0:
    saisonnalite: pd.Series
    profil_solaire: pd.Series
    phi: float
    sigma_innovation: float
    annee_prevue: int

    @property
    def kappa_par_heure(self) -> float:
        return -float(np.log(self.phi))

    @property
    def demi_vie_h(self) -> float:
        return float(np.log(2)) / self.kappa_par_heure

    @property
    def sigma_stationnaire(self) -> float:
        """Écart-type de long terme de $x_t$, en part du baseload annuel."""
        return self.sigma_innovation / float(np.sqrt(1 - self.phi**2))

    @property
    def sigma_ou(self) -> float:
        """Volatilité $\\sigma$ de l'équation continue, par racine d'heure."""
        return self.sigma_stationnaire * float(np.sqrt(2 * self.kappa_par_heure))


def cases(ts: pd.DatetimeIndex) -> pd.DataFrame:
    """Case saisonnière de chaque horodatage UTC, en heure de Paris."""
    local = ts.tz_convert(FUSEAU_AFFICHAGE)
    return pd.DataFrame({"mois": local.month, "heure": local.hour, "week_end": local.day_of_week >= 5}, index=ts)


def prix_normalises(horaire: pd.DataFrame, annees: list[int]) -> pd.Series:
    """Prix de chaque année civile de Paris rapporté au baseload de cette année, indexé par ``ts_utc``.

    Le baseload d'une année n'est connu qu'à sa fin : on n'utilise que des années passées et complètes.
    """
    prix = horaire.dropna(subset=["prix_eur_mwh"]).set_index("ts_utc").sort_index()["prix_eur_mwh"]
    annee = prix.index.tz_convert(FUSEAU_AFFICHAGE).year
    prix = prix[annee.isin(annees)]
    annee = prix.index.tz_convert(FUSEAU_AFFICHAGE).year
    absentes = set(annees) - set(annee)
    if absentes:
        raise ValueError(f"Aucun prix pour les années {sorted(absentes)}")
    return prix / prix.groupby(annee).transform("mean")


def estimer_ar1(x: pd.Series) -> tuple[float, float]:
    """$\\varphi$ et $\\sigma_\\eta$ d'un AR(1) de moyenne nulle, sur les seuls couples d'heures consécutives."""
    consecutif = (x.index[1:] - x.index[:-1]) == pd.Timedelta("1h")
    avant, apres = x.to_numpy()[:-1][consecutif], x.to_numpy()[1:][consecutif]
    denominateur = avant @ avant
    phi = float(avant @ apres / denominateur) if denominateur > 0 else float("nan")
    if not 0 < phi < 1:
        raise ValueError(f"Retour à la moyenne non estimable : phi = {phi}")
    innovations = apres - phi * avant
    return phi, float(np.sqrt(np.mean(innovations**2)))


def calibrer_m0(horaire: pd.DataFrame, annee: int, fenetre: int = FENETRE_ANNEES) -> ParametresM0:
    """Estime M0 sur les ``fenetre`` années civiles précédant ``annee`` (aucune donnée de ``annee`` ni après)."""
    annees = list(range(annee - fenetre, annee))
    y = prix_normalises(horaire, annees)
    c = cases(y.index)
    groupes = y.groupby([c[k] for k in CLES_CASE])
    phi, sigma_innovation = estimer_ar1(y - groupes.transform("mean"))
    return ParametresM0(groupes.mean(), profil_solaire(horaire, annees), phi, sigma_innovation, annee)


def profil_solaire(horaire: pd.DataFrame, annees: list[int]) -> pd.Series:
    """Production moyenne par mois et heure de Paris sur ``annees`` : un profil sans météo."""
    solaire = horaire.dropna(subset=["solaire_mw"]).set_index("ts_utc").sort_index()["solaire_mw"]
    solaire = solaire[solaire.index.tz_convert(FUSEAU_AFFICHAGE).year.isin(annees)]
    local = solaire.index.tz_convert(FUSEAU_AFFICHAGE)
    return solaire.groupby([local.month.rename("mois"), local.hour.rename("heure")]).mean()


def grille_annee(annee: int) -> pd.DatetimeIndex:
    """Heures UTC d'une année civile de Paris."""
    debut = pd.Timestamp(f"{annee}-01-01", tz=FUSEAU_AFFICHAGE).tz_convert("UTC")
    fin = pd.Timestamp(f"{annee + 1}-01-01", tz=FUSEAU_AFFICHAGE).tz_convert("UTC")
    return pd.date_range(debut, fin, freq="h", inclusive="left")


def simuler_prix_normalises(p: ParametresM0, ts: pd.DatetimeIndex, n: int, rng: np.random.Generator) -> np.ndarray:
    """Trajectoires de $y_t$ (lignes : heures, colonnes : trajectoires), parties de la loi stationnaire."""
    saison = p.saisonnalite.reindex(pd.MultiIndex.from_frame(cases(ts))).to_numpy()
    if np.isnan(saison).any():
        raise ValueError("Une case saisonnière de la période simulée n'a aucune observation")
    x = np.empty((len(ts), n))
    x[0] = rng.normal(0, p.sigma_stationnaire, n)
    chocs = rng.normal(0, p.sigma_innovation, (len(ts) - 1, n))
    for t in range(1, len(ts)):
        x[t] = p.phi * x[t - 1] + chocs[t - 1]
    return saison[:, None] + x


def taux_capture_simules(y: np.ndarray, ts: pd.DatetimeIndex, profil: pd.Series) -> pd.DataFrame:
    """Taux de capture de chaque mois (lignes) et trajectoire (colonnes), avec le profil de production."""
    local = ts.tz_convert(FUSEAU_AFFICHAGE)
    q = profil.reindex(pd.MultiIndex.from_arrays([local.month, local.hour])).to_numpy()
    if np.isnan(q).any():
        raise ValueError("Le profil de production ne couvre pas la période simulée")
    resultats = {}
    for mois in np.unique(local.month):
        masque = local.month == mois
        capte = q[masque] @ y[masque] / q[masque].sum()
        resultats[int(mois)] = capte / y[masque].mean(axis=0)
    return pd.DataFrame(resultats).T


def prevoir_m0(horaire: pd.DataFrame, annee: int, n: int = N_TRAJECTOIRES, graine: int = GRAINE) -> tuple[pd.DataFrame, ParametresM0]:
    """Médiane et intervalle à 90 % du taux de capture des 12 mois de ``annee``."""
    p = calibrer_m0(horaire, annee)
    ts = grille_annee(annee)
    y = simuler_prix_normalises(p, ts, n, np.random.default_rng([graine, annee]))
    tc = taux_capture_simules(y, ts, p.profil_solaire)
    bas, haut = QUANTILES_INTERVALLE
    prevision = pd.DataFrame({"tc_m0": tc.median(axis=1), "tc_m0_bas": tc.quantile(bas, axis=1), "tc_m0_haut": tc.quantile(haut, axis=1)})
    return prevision.rename_axis("mois").reset_index(), p


def faits_stylises(y: pd.Series) -> dict:
    """Propriétés d'une série horaire régulière de prix normalisés, réelle ou simulée.

    La mémoire et les queues se lisent sur le résidu après retrait de la moyenne par case de cette série.
    """
    c = cases(y.index)
    residu = (y - y.groupby([c[k] for k in CLES_CASE]).transform("mean")).to_numpy()
    z = (residu - residu.mean()) / residu.std()
    midi = c["heure"].between(11, 16) & c["mois"].between(4, 8)
    return {
        **{f"autocorr_{k}h": float(np.corrcoef(residu[k:], residu[:-k])[0, 1]) for k in RETARDS_DIAGNOSTIC},
        "kurtosis": float((z**4).mean()),
        "part_negative": float((y < 0).mean()),
        "mediane_midi": float(y[midi].median()),
        "q05": float(y.quantile(0.05)),
        "q95": float(y.quantile(0.95)),
    }
