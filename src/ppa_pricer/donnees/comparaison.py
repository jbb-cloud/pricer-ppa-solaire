"""Comparaison de sources : d'où vient le décalage du solaire, et que pèse le choix de la source ?

La règle d'attribution est fixée dans le journal de `docs/perimetre.md` avant d'avoir vu les données
ENTSO-E. Toutes les séries reçues ici sont horaires, en MW ou en €/MWh, indexées par ``ts_utc``, sur
une grille régulière (celle de ``agreger_horaire``). Tout se calcule sur les heures communes : un
écart de couverture ne doit pas passer pour un écart de valeur. Mois et années suivent Paris.
"""

import numpy as np
import pandas as pd

from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE

SEUIL_ORIGINE_H = 0.1
PART_MOIS_ORIGINE = 0.8
RETARDS_TESTES_H = range(-2, 3)
TOLERANCE_ECART = 0.01


def _periodes(index: pd.DatetimeIndex, frequence: str) -> pd.PeriodIndex:
    return index.tz_convert(FUSEAU_AFFICHAGE).tz_localize(None).to_period(frequence)


def comparer_solaire(a: pd.Series, b: pd.Series) -> pd.DataFrame:
    """Par mois : heures moyennes de production de ``a`` et ``b``, écart, rapport d'énergie, corrélation.

    ``retard_h`` est le décalage, de −2 à +2 h, qui maximise la corrélation : positif si ``a`` est en
    retard sur ``b``.
    """
    commun = pd.DataFrame({"a": a, "b": b}).dropna()
    commun = commun.assign(mois=_periodes(commun.index, "M"), heure=commun.index.hour + 0.5)
    decales = {l: b.shift(l).reindex(commun.index) for l in RETARDS_TESTES_H}
    lignes = []
    for mois, g in commun.groupby("mois"):
        energie_a, energie_b = g["a"].sum(), g["b"].sum()
        correlations = {l: g["a"].corr(d.loc[g.index]) for l, d in decales.items()}
        connues = {l: c for l, c in correlations.items() if pd.notna(c)}
        heure_a = (g["heure"] * g["a"]).sum() / energie_a if energie_a else np.nan
        heure_b = (g["heure"] * g["b"]).sum() / energie_b if energie_b else np.nan
        lignes.append(
            {
                "periode": mois,
                "heures_communes": len(g),
                "heure_a": heure_a,
                "heure_b": heure_b,
                "ecart_h": heure_a - heure_b,
                "rapport_energie": energie_a / energie_b if energie_b else np.nan,
                "correlation": correlations[0],
                "retard_h": max(connues, key=connues.get) if connues else np.nan,
            }
        )
    return pd.DataFrame(lignes)


def comparer_premier_quart(horaire: pd.Series, natif: pd.Series, tolerance_mw: float = 0.5) -> dict:
    """Une série horaire reprend-elle le premier quart d'heure de chaque heure d'une série plus fine, ou leur moyenne ?

    ``natif`` est au pas de 15 minutes. Une heure compte comme égale si l'écart reste sous ``tolerance_mw``. Reprendre le premier
    quart d'heure donne une valeur centrée sur h + 7,5 min au lieu de h + 30 min : la courbe semble 0,375 h trop tard.
    """
    commun = horaire.dropna().index.intersection(natif.dropna().index)
    valeurs = horaire.reindex(commun)
    moyenne = natif.groupby(natif.index.floor("h")).mean().reindex(commun)
    return {
        "heures": len(commun),
        "part_premier_quart": float(((valeurs - natif.reindex(commun)).abs() < tolerance_mw).mean()),
        "part_moyenne": float(((valeurs - moyenne).abs() < tolerance_mw).mean()),
        "ecart_absolu_moyenne_mw": float((valeurs - moyenne).abs().mean()),
    }


def attribuer_origine(comparaison: pd.DataFrame, mois_signales: list[pd.Period]) -> dict:
    """Applique la règle figée : le décalage vient de la source si au moins 80 % des mois signalés ont
    un écart d'au plus 0,1 h. Un mois signalé absent de la comparaison compte comme un mois non proche.
    """
    ecarts = comparaison.set_index("periode")["ecart_h"].reindex(mois_signales)
    proches = int((ecarts.abs() <= SEUIL_ORIGINE_H).sum())
    part = proches / len(mois_signales)
    return {
        "n_signales": len(mois_signales),
        "n_proches": proches,
        "part": part,
        "origine": "source" if part >= PART_MOIS_ORIGINE else "apres_entsoe",
    }


def comparer_valeurs(a: pd.Series, b: pd.Series, frequence: str = "Y") -> pd.DataFrame:
    """Par période : moyennes de ``a`` et ``b`` et écarts horaires, sur les heures communes."""
    commun = pd.DataFrame({"a": a, "b": b}).dropna()
    commun = commun.assign(ecart=commun["a"] - commun["b"], periode=_periodes(commun.index, frequence))
    g = commun.groupby("periode")
    return (
        pd.DataFrame(
            {
                "heures_communes": g.size(),
                "moyenne_a": g["a"].mean(),
                "moyenne_b": g["b"].mean(),
                "ecart_moyen": g["ecart"].mean(),
                "ecart_absolu_moyen": g["ecart"].apply(lambda e: e.abs().mean()),
                "ecart_absolu_max": g["ecart"].apply(lambda e: e.abs().max()),
                "heures_differentes": g["ecart"].apply(lambda e: int((e.abs() > TOLERANCE_ECART).sum())),
            }
        )
        .reset_index()
    )


def horaire_variante(horaire: pd.DataFrame, **remplacements: pd.Series) -> pd.DataFrame:
    """Copie de ``horaire`` où des colonnes viennent d'une autre source.

    Une heure absente de cette source devient NaN : on ne complète jamais avec Energy-Charts, pour ne
    pas mélanger deux sources sans le voir.
    """
    variante = horaire.copy()
    for colonne, serie in remplacements.items():
        variante[colonne] = serie.reindex(variante["ts_utc"]).to_numpy()
    return variante
