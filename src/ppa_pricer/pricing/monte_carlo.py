"""Monte-Carlo de pricing : distribution du revenu d'un site et risques par contrat, sur une livraison d'un an.

Chaque trajectoire tire les prix et le solaire national de M2, une année de volumes PVGIS, un baseload annuel et une
erreur de modèle. Le prix horaire vaut $p_t = B\\,y_t$, avec $y_t$ de moyenne annuelle 1 : le niveau et le profil sont séparés.

Chaque contrat répartit le revenu au spot $R = \\sum_t q_t p_t$ entre le vendeur et l'acheteur : vendeur + acheteur = $R$, et le
prix est fixé pour que l'espérance du flux de l'acheteur soit nulle. C'est une valeur de l'énergie au spot, pas un prix de
contrat : garanties d'origine, équilibrage, crédit et marge sont exclus. Choix et limites dans `docs/pricing.md`.
"""

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
from scipy import stats

from ppa_pricer.analyse.capture import SEUIL_MANQUANT, heures_calendaires, periodes_paris
from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE
from ppa_pricer.modele.m0 import grille_annee
from ppa_pricer.modele.m2 import SERIES_METEO, ParametresM2, calibrer_m2, simuler_m2
from ppa_pricer.modele.v1 import derniers_douze_mois

SIGMA_BASELOAD = 0.25
CORRELATION_BASELOAD = 0.65
PLANCHERS = (0.0, 10.0, 20.0)
NIVEAU_VAR = 0.95
CONTRAT_SPOT = "Spot, sans contrat"
CONTRAT_PAP = "Pay-as-produced"
CONTRAT_RUBAN = "Ruban"


def nom_plancher(k: float) -> str:
    return f"Plancher à {k:.0f} €/MWh"


def calibrer_livraison(horaire: pd.DataFrame, mensuel: pd.DataFrame, annee: int) -> ParametresM2:
    """M2 pour livrer ``annee``, quand l'année précédente n'est pas forcément terminée.

    La fenêtre reste les 2 dernières années civiles complètes. Les niveaux viennent des 12 derniers mois valides, et chaque
    croissance passée est portée sur l'horizon entre le milieu de ces 12 mois et le milieu de ``annee``.
    Refuse une année déjà couverte par ces 12 mois, qui utiliserait des données futures.
    """
    base, _ = derniers_douze_mois(mensuel)
    debut, fin = base["periode"].iloc[0], base["periode"].iloc[-1]
    if fin.year >= annee:
        raise ValueError(f"Les données vont jusqu'à {fin} : {annee} n'est pas une année future")
    derniere_complete = fin.year if fin.month == 12 else fin.year - 1
    p = calibrer_m2(horaire, derniere_complete + 1)
    h = horaire.set_index("ts_utc").sort_index()
    periodes = periodes_paris(h.index.to_series(), "M")
    niveaux = h.loc[((periodes >= debut) & (periodes <= fin)).to_numpy(), SERIES_METEO].mean()
    horizon = ((annee * 12 + 6) - (debut.year * 12 + debut.month - 1 + 6)) / 12
    return replace(p, annee_prevue=annee, niveaux=niveaux, croissances=(1 + p.croissances) ** horizon - 1)


def volumes_par_annee(profil: pd.DataFrame, seuil_manquant: float = SEUIL_MANQUANT) -> pd.DataFrame:
    """Volume en MWh de chaque mois (colonnes 1 à 12) de chaque année civile de Paris dont les 12 mois sont complets."""
    mois = periodes_paris(profil["ts_utc"], "M")
    energie = (profil["solaire_mw"] * profil["duree_min"] / 60).groupby(mois).sum(min_count=1)
    heures = profil.groupby(mois).size()
    energie = energie[heures >= heures_calendaires(heures.index) * (1 - seuil_manquant)]
    table = pd.DataFrame({"annee": energie.index.year, "mois": energie.index.month, "mwh": energie.to_numpy()}).pivot(index="annee", columns="mois", values="mwh")
    return table.dropna().reindex(columns=range(1, 13))


def simuler_livraison(p: ParametresM2, volumes: pd.DataFrame, n: int, rng: np.random.Generator) -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray]:
    """Heures, prix normalisés de moyenne annuelle 1 et production du site (lignes : heures, colonnes : trajectoires).

    Le volume de chaque mois vient de l'année PVGIS tirée ; dans le mois, la forme est celle du solaire national (H2).
    """
    ts = grille_annee(p.annee_prevue)
    y, q_national = simuler_m2(p, ts, n, rng)
    moyenne = y.mean(axis=0)
    if (moyenne <= 0).any():
        raise ValueError("Une trajectoire a un prix moyen annuel négatif ou nul : normalisation impossible")
    tirage = volumes.to_numpy()[rng.integers(len(volumes), size=n)]
    mois = ts.tz_convert(FUSEAU_AFFICHAGE).month
    q_site = np.empty_like(q_national)
    for m in range(1, 13):
        k = mois == m
        total = q_national[k].sum(axis=0)
        if (total <= 0).any():
            raise ValueError(f"Aucune production nationale simulée en mois {m}")
        q_site[k] = q_national[k] / total * tirage[:, m - 1]
    return ts, y / moyenne, q_site


def taux_capture_annuel(y: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Taux de capture annuel de chaque trajectoire."""
    return (q * y).sum(axis=0) / q.sum(axis=0) / y.mean(axis=0)


def tirer_baseload(tc: np.ndarray, aleas: np.ndarray, moyenne: float, sigma: float = SIGMA_BASELOAD, correlation: float = CORRELATION_BASELOAD) -> np.ndarray:
    """Baseload lognormal de moyenne ``moyenne``, lié au rang du taux de capture par une copule gaussienne.

    ``aleas`` est un tirage normal fourni par l'appelant : les sensibilités gardent ainsi les mêmes hasards.
    """
    rangs = stats.norm.ppf((stats.rankdata(tc) - 0.5) / len(tc))
    g = correlation * rangs + np.sqrt(1 - correlation**2) * aleas
    return moyenne * np.exp(sigma * g - sigma**2 / 2)


def revenu_avec_erreur(revenu: np.ndarray, volume: np.ndarray, baseload: np.ndarray, erreurs: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Revenu après une erreur annuelle de taux de capture (prévision − réalisé), centrée pour ne pas changer le prix juste."""
    tc = revenu / (volume * baseload)
    e = rng.choice(erreurs - erreurs.mean(), len(revenu))
    return revenu * (tc - e) / tc


def caler_trimestres(y: np.ndarray, ts: pd.DatetimeIndex, cibles: dict[int, float]) -> np.ndarray:
    """Multiplie le prix normalisé de chaque trimestre par une constante, pour que sa moyenne sur les trajectoires égale ``cibles``.

    La constante est commune à toutes les trajectoires : on change la forme attendue, pas la dispersion entre trajectoires.
    """
    trimestre = ts.tz_convert(FUSEAU_AFFICHAGE).quarter
    resultat = y.copy()
    for q, cible in cibles.items():
        k = trimestre == q
        resultat[k] = y[k] * cible / y[k].mean()
    return resultat


@dataclass(frozen=True)
class Flux:
    prix: dict[str, float]
    vendeur: dict[str, np.ndarray]
    acheteur: dict[str, np.ndarray]
    revenu: np.ndarray
    volume: np.ndarray


def flux_contrats(
    y: np.ndarray, q: np.ndarray, baseload: np.ndarray, planchers: tuple[float, ...] = PLANCHERS, revenu_realise: np.ndarray | None = None
) -> Flux:
    """Flux annuels en € du vendeur et de l'acheteur de chaque contrat.

    Les prix justes viennent toujours du revenu du modèle. ``revenu_realise`` remplace le revenu au spot dans les flux, pour
    mesurer le risque avec une erreur de modèle ; la valeur du put du plancher n'en dépend pas (approximation).
    """
    prix_horaire = y * baseload
    revenu = (q * prix_horaire).sum(axis=0)
    volume = q.sum(axis=0)
    realise = revenu if revenu_realise is None else revenu_realise
    k_pap = revenu.mean() / volume.mean()
    prix = {CONTRAT_PAP: k_pap}
    vendeur = {CONTRAT_SPOT: realise, CONTRAT_PAP: k_pap * volume}
    acheteur = {CONTRAT_PAP: realise - k_pap * volume}
    for k in planchers:
        put = (q * np.maximum(k - prix_horaire, 0)).sum(axis=0)
        prime = put.mean() / volume.mean()
        nom = nom_plancher(k)
        prix[nom] = prime
        vendeur[nom] = realise + put - prime * volume
        acheteur[nom] = prime * volume - put
    k_ruban = prix_horaire.mean()
    puissance = volume.mean() / y.shape[0]
    prix[CONTRAT_RUBAN] = k_ruban
    acheteur[CONTRAT_RUBAN] = puissance * (prix_horaire - k_ruban).sum(axis=0)
    vendeur[CONTRAT_RUBAN] = realise - acheteur[CONTRAT_RUBAN]
    return Flux(prix, vendeur, acheteur, revenu, volume)


def mesures_risque(x: np.ndarray, niveau: float = NIVEAU_VAR) -> dict[str, float]:
    """Moyenne, écart-type, VaR et CVaR d'un flux, la perte étant mesurée par rapport au flux moyen."""
    perte = x.mean() - x
    var = float(np.quantile(perte, niveau))
    return {"moyenne": float(x.mean()), "ecart_type": float(x.std()), "var": var, "cvar": float(perte[perte >= var].mean())}


def parts_variance(revenu: np.ndarray, volume: np.ndarray, baseload: np.ndarray) -> dict[str, float]:
    """Parts de la variance de $\\ln R = \\ln Q + \\ln B + \\ln TC$, le reste étant dû aux covariances."""
    tc = revenu / (volume * baseload)
    if (tc <= 0).any():
        raise ValueError("Un taux de capture annuel négatif ou nul empêche la décomposition en logarithmes")
    total = np.log(revenu).var()
    parts = {"volume": np.log(volume).var() / total, "baseload": np.log(baseload).var() / total, "taux_capture": np.log(tc).var() / total}
    return {**{k: float(v) for k, v in parts.items()}, "covariances": float(1 - sum(parts.values()))}


def var_en_figeant(revenu: np.ndarray, volume: np.ndarray, baseload: np.ndarray, niveau: float = NIVEAU_VAR) -> dict[str, float]:
    """VaR du revenu au spot quand on fige tour à tour le volume, le baseload et le taux de capture."""
    tc = revenu / (volume * baseload)
    return {
        "volume": mesures_risque(revenu * volume.mean() / volume, niveau)["var"],
        "baseload": mesures_risque(revenu * baseload.mean() / baseload, niveau)["var"],
        "taux_capture": mesures_risque(revenu * np.median(tc) / tc, niveau)["var"],
    }


def parts_covariance(revenu: np.ndarray, volume: np.ndarray, baseload: np.ndarray) -> dict[str, float]:
    """Parts de la variance de $\\ln R$ attribuées par covariance : $\\text{Cov}(X, \\ln R) / \\text{Var}(\\ln R)$. Leur somme vaut 1, sans terme résiduel."""
    tc = revenu / (volume * baseload)
    if (tc <= 0).any():
        raise ValueError("Un taux de capture annuel négatif ou nul empêche la décomposition en logarithmes")
    ln_r = np.log(revenu)
    return {nom: float(np.cov(np.log(x), ln_r)[0, 1] / ln_r.var(ddof=1)) for nom, x in (("volume", volume), ("baseload", baseload), ("taux_capture", tc))}


def flux_avec_erreurs(f: Flux, baseload: np.ndarray, erreurs: np.ndarray) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Flux de chaque contrat, en combinant chaque trajectoire à chaque erreur centrée, sans tirage : le résultat ne dépend d'aucune graine.

    Seuls les flux qui contiennent le revenu au spot changent. Le put du plancher n'en dépend pas (approximation).
    """
    tc = f.revenu / (f.volume * baseload)
    ecart = np.concatenate([f.revenu * (tc - e) / tc - f.revenu for e in erreurs - erreurs.mean()])
    n = len(erreurs)
    vendeur = {c: np.tile(x, n) + (0 if c == CONTRAT_PAP else ecart) for c, x in f.vendeur.items()}
    acheteur = {c: np.tile(x, n) + (ecart if c == CONTRAT_PAP else 0) for c, x in f.acheteur.items()}
    return vendeur, acheteur
