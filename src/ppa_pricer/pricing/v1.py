"""Pricing V1 : prix juste d'un PPA solaire pay-as-produced d'un an.

$$\\text{prix juste} = \\frac{\\sum_m B_m\\, \\widehat{TC}_m\\, V_m}{\\sum_m V_m}$$

- $B_m$ : baseload du mois dans un scénario, un niveau annuel × une forme mensuelle ;
- $\\widehat{TC}_m$ : taux de capture national prévu (hypothèse H2 : celui du site lui est égal) ;
- $V_m$ : volume mensuel du site, tiré du profil PVGIS.

C'est une valeur de l'énergie au spot, avant garanties d'origine, coûts d'équilibrage, risque de
crédit et marge : pas un prix de contrat. Choix détaillés dans `docs/pricing.md`.
"""

import pandas as pd

from ppa_pricer.analyse.capture import SEUIL_MANQUANT, heures_calendaires, periodes_paris, taux_de_capture
from ppa_pricer.modele.v1 import MOIS, ParametresV1, calibrer, derniers_douze_mois, prevoir, prevoir_part_solaire_glissante

# Hypothèse H5, en €/MWh : baseloads observés en 2018, en 2025 et sur oct. 2025 – sept. 2026.
SCENARIOS_BASELOAD = {"bas": 50.0, "central": 61.0, "haut": 77.0}
ANNEES_FORME = (2024, 2025)


def volumes_mensuels(profil: pd.DataFrame, seuil_manquant: float = SEUIL_MANQUANT) -> pd.Series:
    """Volume moyen en MWh de chaque mois calendaire de Paris, sur les mois complets du profil.

    Prendre la moyenne de toutes les années donne un volume médian d'année météo, sans parier sur
    une année particulière. Les mois trop incomplets, comme l'heure isolée que crée la conversion
    à Paris en fin de série, sont écartés : ils feraient baisser la moyenne.
    """
    mois = periodes_paris(profil["ts_utc"], "M")
    energie = (profil["solaire_mw"] * profil["duree_min"] / 60).groupby(mois).sum(min_count=1)
    heures = profil.groupby(mois).size()
    complets = heures >= heures_calendaires(heures.index) * (1 - seuil_manquant)
    energie = energie[complets]
    return energie.groupby(energie.index.month).mean().reindex(list(MOIS))


def forme_baseload(mensuel: pd.DataFrame, annees: tuple[int, ...] = ANNEES_FORME) -> pd.Series:
    """Baseload de chaque mois calendaire rapporté à celui de son année, moyenné sur ``annees``.

    Sans cette forme, les mois d'été, où le solaire produit le plus et où le baseload est bas,
    compteraient au niveau annuel.
    """
    h = mensuel[mensuel["periode"].dt.year.isin(annees) & mensuel["valide"]]
    annee = h["periode"].dt.year
    pondere = h["baseload_eur_mwh"] * h["heures_utilisees"]
    annuel = pondere.groupby(annee).transform("sum") / h["heures_utilisees"].groupby(annee).transform("sum")
    return (h["baseload_eur_mwh"] / annuel).groupby(h["periode"].dt.month).mean().reindex(list(MOIS))


def baseload_mensuel(niveau: float, forme: pd.Series, annee: int) -> pd.Series:
    """Baseload de chaque mois de ``annee``, dont la moyenne pondérée par les heures vaut ``niveau``."""
    periodes = pd.period_range(f"{annee}-01", periods=12, freq="M")
    heures = heures_calendaires(periodes).set_axis(list(MOIS))
    return niveau * forme * heures.sum() / (forme * heures).sum()


def prix_juste(taux_capture: pd.Series, baseload: pd.Series, volumes: pd.Series) -> float:
    """Prix juste en €/MWh. Une entrée inconnue donne NaN, jamais un prix calculé sur moins de mois."""
    return float((taux_capture * baseload * volumes).sum(skipna=False) / volumes.sum(skipna=False))


def revenu_annuel(prix: float, volumes: pd.Series) -> float:
    """Revenu annuel en € d'un PPA pay-as-produced payé à ``prix`` sur ``volumes``."""
    return prix * float(volumes.sum(skipna=False))


def entrees_pricing(mensuel: pd.DataFrame, annee: int) -> tuple[pd.DataFrame, ParametresV1]:
    """Part du solaire et taux de capture prévus pour chaque mois de ``annee``, modèle et persistance.

    La persistance reprend le taux de capture du même mois dans les 12 derniers mois valides. Elle
    sert de point de comparaison : le backtest ne permet pas d'affirmer que le modèle fait mieux.
    Refuse une année déjà couverte par ces 12 mois, qui utiliserait des données futures.
    """
    base, _ = derniers_douze_mois(mensuel)
    if base["periode"].iloc[-1].year >= annee:
        raise ValueError(f"Les données vont jusqu'à {base['periode'].iloc[-1]} : {annee} n'est pas une année future")
    parametres = calibrer(mensuel, annee)
    mois = pd.Series(list(MOIS), index=list(MOIS), name="mois")
    part_prevue = prevoir_part_solaire_glissante(mensuel)
    base = base.set_index(base["periode"].dt.month).reindex(list(MOIS))
    entrees = pd.DataFrame(
        {
            "part_solaire_base": base["part_solaire"],
            "part_solaire_prevue": part_prevue,
            "tc_modele": prevoir(parametres, mois, part_prevue),
            "tc_persistance": base["taux_capture"],
        }
    )
    return entrees, parametres


def taux_capture_site(horaire: pd.DataFrame, profil: pd.DataFrame) -> pd.DataFrame:
    """Taux de capture annuel du site avec les prix réels, pour mesurer l'erreur de H2.

    On remplace la production nationale par celle du site, aux heures communes, puis on applique
    le même calcul. Seules les années valides sont renvoyées.
    """
    site = horaire.drop(columns="solaire_mw").merge(profil[["ts_utc", "solaire_mw"]], on="ts_utc", how="inner")
    annuel = taux_de_capture(site, "Y")
    return annuel.loc[annuel["valide"], ["periode", "taux_capture"]].reset_index(drop=True)


def taux_capture_formule(mensuel: pd.DataFrame, volumes: pd.Series) -> pd.Series:
    """Taux de capture annuel d'un site selon la formule du pricing, avec les grandeurs réalisées.

    $\\sum_m TC_m B_m V_m / (B_T \\sum_m V_m)$, avec le taux national de chaque mois. Comparé au
    taux réel du site, il mesure l'erreur de H2 telle que le pricing l'utilise. Seules les années
    dont les 12 mois sont valides sont renvoyées, indexées par l'année.
    """
    resultats = {}
    valides = mensuel[mensuel["valide"]]
    for annee, m in valides.groupby(valides["periode"].dt.year):
        if len(m) == 12:
            baseload_annuel = (m["baseload_eur_mwh"] * m["heures_utilisees"]).sum() / m["heures_utilisees"].sum()
            v = m["periode"].dt.month.map(volumes)
            resultats[annee] = prix_juste(m["taux_capture"], m["baseload_eur_mwh"], v) / baseload_annuel
    return pd.Series(resultats, dtype=float)
