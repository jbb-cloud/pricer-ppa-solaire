"""Calcul commun du pricing V2, appelé par ``scripts/pricer_v2.py`` et par l'appli (voir `docs/interface.md`).

Trois étages, pour que l'appli ne recalcule que ce qui change :

1. ``preparer_marche`` cale tout ce qui ne dépend ni du site ni des réglages (environ 1 s, mis en cache par l'appli) ;
2. ``prix_v2`` donne le prix du pay-as-produced et son détail mensuel (instantané) ;
3. ``simuler_risques`` tire le Monte-Carlo (environ 1 s pour 1 000 trajectoires).

Le niveau ``niveau`` est le baseload calendaire. Quand il diffère de la cotation, les trimestres sont mis à l'échelle en
gardant leurs rapports, comme dans la sensibilité du rapport V2. Choix et limites : `docs/pricing.md`.
"""

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from ppa_pricer.analyse.capture import taux_de_capture
from ppa_pricer.modele.m2 import ParametresM2
from ppa_pricer.modele.v1 import MOIS, ParametresV1
from ppa_pricer.modele.v2 import ParametresV2, calibrer_v2, prevoir_v2
from ppa_pricer.pricing.courbe import PARC_BASE_GW, TRIMESTRES, baseload_courbe, heures_mensuelles, niveau_par_mois, niveaux_courbe, part_selon_parc
from ppa_pricer.pricing.monte_carlo import (
    CORRELATION_BASELOAD,
    PLANCHERS,
    SIGMA_BASELOAD,
    Flux,
    caler_trimestres,
    calibrer_livraison,
    flux_avec_erreurs,
    flux_contrats,
    simuler_livraison,
    taux_capture_annuel,
    tirer_baseload,
)
from ppa_pricer.pricing.v1 import ANNEES_FORME, entrees_pricing, forme_baseload, prix_juste


@dataclass(frozen=True)
class Marche:
    """Tout ce que le pricing d'une année de livraison tire des données de marché, indépendamment du site."""

    annee: int
    niveaux: pd.Series  # base de chaque trimestre sur la courbe
    calendaire: float  # contrat calendaire de la courbe
    forme: pd.Series  # répartition du baseload entre les mois d'un trimestre
    entrees: pd.DataFrame  # part du solaire de base, persistance, par mois
    p_v1: ParametresV1
    p_v2: ParametresV2
    livraison: ParametresM2  # M2 calé pour livrer ``annee``
    erreurs: np.ndarray  # erreurs annuelles de taux de capture du backtest (prévision − réalisé)


def preparer_marche(horaire: pd.DataFrame, courbe: pd.DataFrame, annee: int, erreurs: np.ndarray) -> Marche:
    """Cale V1, V2 et M2 sur ``horaire`` (prix, solaire, consommation, éolien) et lit la courbe pour ``annee``."""
    mensuel = taux_de_capture(horaire, "M")
    entrees, p_v1 = entrees_pricing(mensuel, annee)
    return Marche(
        annee=annee,
        niveaux=niveaux_courbe(courbe, annee),
        calendaire=float(courbe.loc[f"CAL_{annee}", "base_eur_mwh"]),
        forme=forme_baseload(mensuel, ANNEES_FORME),
        entrees=entrees,
        p_v1=p_v1,
        p_v2=calibrer_v2(mensuel, annee),
        livraison=calibrer_livraison(horaire, mensuel, annee),
        erreurs=np.asarray(erreurs, dtype=float),
    )


def niveaux_a(marche: Marche, niveau: float | None = None) -> pd.Series:
    """Niveaux trimestriels pour un calendaire ``niveau`` : ceux de la courbe, multipliés par ``niveau`` / calendaire."""
    return marche.niveaux if niveau is None else marche.niveaux * niveau / marche.calendaire


@dataclass(frozen=True)
class PrixV2:
    prix: float  # €/MWh, pay-as-produced
    detail: pd.DataFrame  # par mois : volume_mwh, baseload, part_solaire, taux_capture, revenu


def prix_v2(marche: Marche, volumes: pd.Series, parc_gw: float, niveau: float | None = None) -> PrixV2:
    """Prix V2 du pay-as-produced : taux de capture de chaque mois selon la part du solaire et le niveau du trimestre."""
    k = niveaux_a(marche, niveau)
    baseload = baseload_courbe(k, marche.forme, marche.annee)
    part = part_selon_parc(marche.entrees["part_solaire_base"], parc_gw)
    mois = pd.Series(list(MOIS), index=list(MOIS), name="mois")
    tc = prevoir_v2(marche.p_v2, mois, part, niveau_par_mois(k))
    detail = pd.DataFrame({"volume_mwh": volumes, "baseload": baseload, "part_solaire": part, "taux_capture": tc})
    detail["revenu"] = detail["volume_mwh"] * detail["baseload"] * detail["taux_capture"]
    return PrixV2(prix_juste(tc, baseload, volumes), detail)


@dataclass(frozen=True)
class Risques:
    """Un tirage du Monte-Carlo. ``y`` et ``q`` (heures × trajectoires) servent aux sensibilités du rapport."""

    y: np.ndarray  # prix normalisé, de moyenne annuelle 1
    q: np.ndarray  # production du site, MWh
    taux_capture: np.ndarray  # taux de capture annuel de chaque trajectoire, avant baseload
    aleas: np.ndarray  # tirage normal du baseload, gardé pour refaire le baseload avec d'autres σ et corrélations
    baseload: np.ndarray
    flux: Flux  # sans erreur de modèle
    vendeur: dict[str, np.ndarray]  # avec erreur de modèle
    acheteur: dict[str, np.ndarray]


def simuler_risques(
    marche: Marche,
    volumes_annuels: pd.DataFrame,
    parcs_gw: tuple[float, ...],
    niveau: float | None = None,
    sigma: float = SIGMA_BASELOAD,
    correlation: float = CORRELATION_BASELOAD,
    n: int = 1000,
    graine: int = 0,
    planchers: tuple[float, ...] = PLANCHERS,
) -> Risques:
    """Prix et solaire de M2, volumes PVGIS tirés, baseload lognormal lié au taux de capture, erreur de modèle du backtest.

    Chaque trajectoire tire l'un des ``parcs_gw`` : un seul parc pour l'appli, les 3 scénarios pour le rapport. Les prix sont
    calés en espérance sur les trimestres de la courbe, dont seuls les rapports comptent ici : le niveau vient de ``niveau``.
    """
    k = niveaux_a(marche, niveau)
    calendaire = marche.calendaire if niveau is None else niveau
    p = replace(marche.livraison, croissances=np.array([g / PARC_BASE_GW - 1 for g in parcs_gw]))
    h = heures_mensuelles(marche.annee)
    poids = pd.Series({t: h[m].sum() for t, m in TRIMESTRES.items()})
    cibles = {t: float(k[t] / ((k * poids).sum() / poids.sum())) for t in TRIMESTRES}
    rng = np.random.default_rng([graine, marche.annee])
    ts, y, q = simuler_livraison(p, volumes_annuels, n, rng)
    y = caler_trimestres(y, ts, cibles)
    tc = taux_capture_annuel(y, q)
    aleas = rng.standard_normal(n)
    b = tirer_baseload(tc, aleas, calendaire, sigma, correlation)
    f = flux_contrats(y, q, b, planchers)
    vendeur, acheteur = flux_avec_erreurs(f, b, marche.erreurs)
    return Risques(y, q, tc, aleas, b, f, vendeur, acheteur)
