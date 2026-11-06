"""Modèle V1 : régression du taux de capture mensuel sur la part du solaire.

$$TC_m = \\alpha_{\\text{mois}(m)} + \\beta\\, S_m + \\varepsilon_m$$

- $\\alpha_{\\text{mois}}$ : 12 constantes, une par mois calendaire, pour le niveau saisonnier
  normal du taux de capture ;
- $\\beta$ : une pente commune, la baisse du taux de capture par unité de part du solaire ;
- estimation par moindres carrés ordinaires sur tous les mois valides strictement antérieurs
  au 1er janvier de l'année prévue (fenêtre expansive).

Forme fixée dans `docs/perimetre.md` avant d'avoir vu les données ; elle n'a pas été modifiée
après l'analyse descriptive, pour que le backtest reste objectif.

La part du solaire de l'année prévue est soit la part réalisée (variante conditionnelle, qui
teste la relation seule), soit une prévision (variante réaliste, hypothèse H4) :
$\\hat S_{m,T} = S_{m,T-1} \\times E_{T-1} / E_{T-2}$, avec $E$ la production solaire annuelle.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

MOIS = range(1, 13)


@dataclass(frozen=True)
class ParametresV1:
    alpha: dict[int, float]
    beta: float
    n_mois: int
    annee_prevue: int


def historique_avant(mensuel: pd.DataFrame, annee: int) -> pd.DataFrame:
    """Mois valides strictement antérieurs au 1er janvier de ``annee`` (aucune donnée future)."""
    avant = mensuel["periode"].dt.year < annee
    return mensuel[avant & mensuel["valide"]].dropna(subset=["taux_capture", "part_solaire"])


def calibrer(mensuel: pd.DataFrame, annee: int) -> ParametresV1:
    """Estime $\\alpha$ et $\\beta$ sur les mois antérieurs à ``annee``."""
    h = historique_avant(mensuel, annee)
    mois = h["periode"].dt.month
    absents = set(MOIS) - set(mois)
    if absents:
        raise ValueError(f"Calibration pour {annee} impossible : aucun historique pour les mois {sorted(absents)}")
    x = np.column_stack([(mois == m).to_numpy(dtype=float) for m in MOIS] + [h["part_solaire"].to_numpy()])
    coefficients, *_ = np.linalg.lstsq(x, h["taux_capture"].to_numpy(), rcond=None)
    return ParametresV1(
        alpha={m: float(a) for m, a in zip(MOIS, coefficients[:12])},
        beta=float(coefficients[12]),
        n_mois=len(h),
        annee_prevue=annee,
    )


def prevoir(parametres: ParametresV1, mois: pd.Series, part_solaire: pd.Series) -> pd.Series:
    """Taux de capture prévu pour chaque (mois calendaire, part du solaire)."""
    return mois.map(parametres.alpha) + parametres.beta * part_solaire


def prevoir_part_solaire(mensuel: pd.DataFrame, annee: int) -> pd.Series:
    """Hypothèse H4 : part du même mois en T−1 × croissance de la production solaire T−2 → T−1.

    Renvoie une série indexée par le mois calendaire (1 à 12). N'utilise que les années T−1 et
    T−2 ; une valeur manquante en T−1 donne NaN pour ce mois.
    """
    annees = mensuel["periode"].dt.year
    production = mensuel.groupby(annees)["energie_solaire_mwh"].sum(min_count=12)
    croissance = production.get(annee - 1, np.nan) / production.get(annee - 2, np.nan)
    precedente = mensuel[annees == annee - 1]
    part = precedente.set_index(precedente["periode"].dt.month)["part_solaire"]
    return (part * croissance).reindex(list(MOIS))


def derniers_douze_mois(mensuel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Les 12 derniers mois valides et les 12 mois d'avant ; refuse une fenêtre interrompue."""
    valides = mensuel[mensuel["valide"]].sort_values("periode")
    base, precedents = valides.tail(12), valides.iloc[-24:-12]
    attendu = pd.period_range(end=base["periode"].iloc[-1], periods=24, freq="M")
    if [*precedents["periode"], *base["periode"]] != list(attendu):
        raise ValueError("Les 24 derniers mois valides ne sont pas consécutifs")
    return base, precedents


def prevoir_part_solaire_glissante(mensuel: pd.DataFrame) -> pd.Series:
    """Hypothèse H4 glissante : part du mois dans les 12 derniers mois valides × leur croissance.

    H4 demande une année T−1 complète ; cette version utilise les 12 derniers mois valides, pour
    prévoir une année dont la précédente n'est pas terminée. Quand ces 12 mois forment une année
    civile, elle donne exactement H4. Renvoie une série indexée par le mois calendaire (1 à 12).
    """
    base, precedents = derniers_douze_mois(mensuel)
    croissance = base["energie_solaire_mwh"].sum() / precedents["energie_solaire_mwh"].sum()
    part = base.set_index(base["periode"].dt.month)["part_solaire"]
    return (part * croissance).reindex(list(MOIS))
