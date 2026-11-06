"""Test de la chute de 2024 : M2 avec d'autres variables, nourri des valeurs réelles de l'année.

On garde les lois par case et la dynamique de M2, mais le rang du prix dépend de plusieurs variables :

$$z_t = \\sum_i \\lambda_i\\,x_{i,t} + \\sqrt{1-V}\\,\\varepsilon_t, \\qquad V = \\text{Var}\\Big(\\sum_i \\lambda_i\\,x_{i,t}\\Big).$$

Pour l'année testée, les $x_{i,t}$ sont les valeurs réelles, heure par heure : ce n'est pas une prévision. Si une
variante garde une forte erreur avec ces valeurs, la cause est ailleurs. Si elle la réduit, la variable explique la
chute, sans dire si on aurait pu la prévoir. Règle écrite avant le lancement dans `docs/stochastique.md`.

Les GW français se retirent directement de la charge résiduelle. Chaque voisin garde son propre coefficient, car un GW
allemand n'a pas le même effet sur le prix français qu'un GW français. Une seconde forme, ``calibrer_plages``, donne un
$\\lambda$ par heure de Paris × saison pour tester si un $\\lambda$ unique explique que toutes les heures baissent ensemble.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE
from ppa_pricer.modele.m0 import CLES_CASE, FENETRE_ANNEES, cases, grille_annee, prix_normalises
from ppa_pricer.modele.m1 import (
    RETARDS_AJUSTEMENT,
    ajuster_deux_vitesses,
    autocorrelations,
    prix_depuis_scores,
    scores_normaux,
    simuler_latente,
)

HEURES_NUCLEAIRE = 168
SEUIL_BIAIS = 0.05
MARGE_MAE = 0.005
MOIS_ETE = (4, 8)


@dataclass(frozen=True)
class Variante:
    nom: str
    retirer: tuple[str, ...] = ()
    voisins: tuple[str, ...] = ()


NUCLEAIRE = "nucleaire_dispo_mw"
HYDRO = "hydro_fil_mw"
VOISINS = ("charge_de_mw", "charge_es_mw")
VARIANTES = {
    "A": Variante("Référence"),
    "B": Variante("Nucléaire", (NUCLEAIRE,)),
    "C": Variante("Hydraulique", (HYDRO,)),
    "D": Variante("France complète", (NUCLEAIRE, HYDRO)),
    "E": Variante("Voisins", (), VOISINS),
    "F": Variante("Tout", (NUCLEAIRE, HYDRO), VOISINS),
}


@dataclass(frozen=True)
class ParametresFacteurs:
    lois: dict[tuple[int, int, bool], np.ndarray]
    moyennes: pd.DataFrame
    ecarts: pd.DataFrame
    coefficients: pd.Series
    variance_expliquee: float
    poids_rapide: float
    phi_rapide: float
    phi_lent: float
    erreur_ajustement: float
    annee_prevue: int


@dataclass(frozen=True)
class ParametresPlages:
    lois: dict[tuple[int, int, bool], np.ndarray]
    moyennes: pd.Series
    ecarts: pd.Series
    lambdas: pd.Series
    poids_rapide: float
    phi_rapide: float
    phi_lent: float
    erreur_ajustement: float
    annee_prevue: int


def nucleaire_disponible(nucleaire: pd.Series) -> pd.Series:
    """Maximum de la production sur 7 jours glissants, centré (H14). Un trou reste un trou dans le calcul."""
    return nucleaire.rolling(HEURES_NUCLEAIRE, center=True, min_periods=HEURES_NUCLEAIRE // 2).max()


def facteurs_de_la_periode(h: pd.DataFrame, ts: pd.DatetimeIndex, variante: Variante) -> pd.DataFrame:
    """Variables de ``variante`` sur les heures ``ts``. Le nucléaire disponible n'utilise que ces heures."""
    periode = h.reindex(ts)
    charge = periode["conso_mw"] - periode["solaire_mw"] - periode["eolien_mw"]
    for colonne in variante.retirer:
        charge = charge - (nucleaire_disponible(periode["nucleaire_mw"]) if colonne == NUCLEAIRE else periode[colonne])
    return pd.DataFrame({"france": charge, **{v: periode[v] for v in variante.voisins}}, index=ts)


def _fenetre(horaire: pd.DataFrame, annee: int, variante: Variante, fenetre: int):
    """Prix, variables réduites dans leur case et scores normaux des ``fenetre`` années civiles précédant ``annee``."""
    annees = list(range(annee - fenetre, annee))
    y = prix_normalises(horaire, annees)
    h = horaire.set_index("ts_utc").sort_index()
    grille = pd.DatetimeIndex(np.concatenate([grille_annee(a).to_numpy() for a in annees]), tz="UTC")
    f = facteurs_de_la_periode(h, grille, variante).reindex(y.index)
    c = cases(y.index)
    cles = [c[k] for k in CLES_CASE]
    groupes = f.groupby(cles)
    x = (f - groupes.transform("mean")) / groupes.transform("std")
    lois = {cle: np.sort(g.to_numpy()) for cle, g in y.groupby(cles)}
    return x, scores_normaux(y), lois, groupes.mean(), groupes.std()


def calibrer_facteurs(horaire: pd.DataFrame, annee: int, variante: Variante, fenetre: int = FENETRE_ANNEES) -> ParametresFacteurs:
    """Estime la variante sur les ``fenetre`` années civiles précédant ``annee`` (aucune donnée de ``annee`` ni après)."""
    x, z, lois, moyennes, ecarts = _fenetre(horaire, annee, variante, fenetre)
    connus = x.notna().all(axis=1)
    coefficients = np.linalg.lstsq(x[connus].to_numpy(), z[connus].to_numpy(), rcond=None)[0]
    ajuste = x[connus].to_numpy() @ coefficients
    variance = float(ajuste.var())
    if not 0 <= variance < 1:
        raise ValueError(f"Part expliquée non exploitable : V = {variance}")
    bruit = pd.Series((z[connus].to_numpy() - ajuste) / np.sqrt(1 - variance), index=x.index[connus])
    w, phi_r, phi_l, erreur = ajuster_deux_vitesses(autocorrelations(bruit, RETARDS_AJUSTEMENT), RETARDS_AJUSTEMENT)
    return ParametresFacteurs(
        lois=lois,
        moyennes=moyennes,
        ecarts=ecarts,
        coefficients=pd.Series(coefficients, index=x.columns),
        variance_expliquee=variance,
        poids_rapide=w,
        phi_rapide=phi_r,
        phi_lent=phi_l,
        erreur_ajustement=erreur,
        annee_prevue=annee,
    )


def simuler_valeurs_reelles(
    p: ParametresFacteurs, horaire: pd.DataFrame, variante: Variante, n: int, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray, pd.DatetimeIndex]:
    """Prix normalisés et solaire de l'année, avec ses valeurs réelles. Une heure inconnue reste NaN."""
    ts = grille_annee(p.annee_prevue)
    h = horaire.set_index("ts_utc").sort_index()
    f = facteurs_de_la_periode(h, ts, variante)
    cle = pd.MultiIndex.from_frame(cases(ts))
    x = (f.to_numpy() - p.moyennes.reindex(cle).to_numpy()) / p.ecarts.reindex(cle).to_numpy()
    ajuste = x @ p.coefficients.to_numpy()
    z = ajuste[:, None] + np.sqrt(1 - p.variance_expliquee) * simuler_latente(p, len(ts), n, rng)
    q = np.repeat(h["solaire_mw"].reindex(ts).to_numpy()[:, None], n, axis=1)
    return prix_depuis_scores(p.lois, z, ts), q, ts


def plages(ts: pd.DatetimeIndex) -> pd.MultiIndex:
    """Plage de chaque horodatage : heure de Paris × saison (``True`` d'avril à août)."""
    local = ts.tz_convert(FUSEAU_AFFICHAGE)
    return pd.MultiIndex.from_arrays([local.hour, (local.month >= MOIS_ETE[0]) & (local.month <= MOIS_ETE[1])], names=["heure", "ete"])


def calibrer_plages(horaire: pd.DataFrame, annee: int, variante: Variante, fenetre: int = FENETRE_ANNEES) -> ParametresPlages:
    """Un $\\lambda$ par heure × saison, sur les ``fenetre`` années civiles précédant ``annee``. Une seule variable française."""
    if variante.voisins:
        raise ValueError("Le lambda par plage n'accepte qu'une variable française")
    x_cadre, z, lois, moyennes, ecarts = _fenetre(horaire, annee, variante, fenetre)
    x = x_cadre["france"]
    connus = x.notna()
    x, z = x[connus], z[connus]
    cle = plages(x.index)
    lambdas = pd.Series({p: float(np.corrcoef(x[cle == p], z[cle == p])[0, 1]) for p in cle.unique()}).rename_axis(["heure", "ete"]).sort_index()
    if not ((lambdas > -1) & (lambdas < 1)).all():
        raise ValueError("Lien entre charge et prix non estimable dans une plage")
    lam = lambdas.reindex(cle).to_numpy()
    bruit = pd.Series((z.to_numpy() - lam * x.to_numpy()) / np.sqrt(1 - lam**2), index=x.index)
    w, phi_r, phi_l, erreur = ajuster_deux_vitesses(autocorrelations(bruit, RETARDS_AJUSTEMENT), RETARDS_AJUSTEMENT)
    return ParametresPlages(lois, moyennes["france"], ecarts["france"], lambdas, w, phi_r, phi_l, erreur, annee)


def simuler_plages(p: ParametresPlages, horaire: pd.DataFrame, variante: Variante, n: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, pd.DatetimeIndex]:
    """Prix normalisés et solaire de l'année, avec ses valeurs réelles et un $\\lambda$ par plage. Une heure inconnue reste NaN."""
    ts = grille_annee(p.annee_prevue)
    h = horaire.set_index("ts_utc").sort_index()
    f = facteurs_de_la_periode(h, ts, variante)["france"].to_numpy()
    cle = pd.MultiIndex.from_frame(cases(ts))
    x = (f - p.moyennes.reindex(cle).to_numpy()) / p.ecarts.reindex(cle).to_numpy()
    lam = p.lambdas.reindex(plages(ts)).to_numpy()
    if np.isnan(lam).any():
        raise ValueError("Une plage de la période simulée n'a pas de lambda")
    z = (lam * x)[:, None] + np.sqrt(1 - lam**2)[:, None] * simuler_latente(p, len(ts), n, rng)
    q = np.repeat(h["solaire_mw"].reindex(ts).to_numpy()[:, None], n, axis=1)
    return prix_depuis_scores(p.lois, z, ts), q, ts


def taux_capture_median(y: np.ndarray, q: np.ndarray, ts: pd.DatetimeIndex) -> pd.Series:
    """Médiane du taux de capture de chaque mois de Paris, sur les heures connues ; NaN pour un mois sans heure connue."""
    mois = ts.tz_convert(FUSEAU_AFFICHAGE).month
    connus = ~(np.isnan(y).any(axis=1) | np.isnan(q).any(axis=1))
    resultats = {}
    for m in np.unique(mois):
        k = (mois == m) & connus
        resultats[int(m)] = float(np.median((q[k] * y[k]).sum(axis=0) / q[k].sum(axis=0) / y[k].mean(axis=0))) if k.any() else float("nan")
    return pd.Series(resultats)


def explique_la_chute(biais_2024: float, mae_2018_2023: float, mae_reference: float) -> bool:
    """Règle écrite avant le test : biais de 2024 sous 5 points, sans dégrader 2018–2023 de plus de 0,5 point."""
    return abs(biais_2024) < SEUIL_BIAIS and mae_2018_2023 <= mae_reference + MARGE_MAE
