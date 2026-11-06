"""Modèle V2 : taux de capture mensuel selon la part du solaire et le niveau de prix du trimestre.

$$TC_m = \\alpha_{\\text{mois}(m)} + \\beta\\, S_m + \\gamma \\ln B_{q(m)} + \\delta\\, S_m \\ln B_{q(m)}$$

Pourquoi le niveau : d'avril à septembre, la part du solaire passe seulement de 7,9 à 8,4 % entre 2023 et 2024 alors que le taux de capture tombe de 84,6 à 61,4 %, et il tient en 2026
malgré plus de solaire, quand le baseload double. Le produit $S_m \\ln B_q$ laisse la pente dépendre du niveau. Une courbe à terme donne ce niveau par trimestre pour l'année à pricer.

Limites : cette forme a été choisie après avoir vu les années de test, et seuls les mois publiés après le 29/10/2026 peuvent la juger. Le lien n'est pas causal, car le baseload contient lui-même le prix
de midi. Voir `docs/pricing.md`.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ppa_pricer.modele.v1 import MOIS, historique_avant


@dataclass(frozen=True)
class ParametresV2:
    alpha: dict[int, float]
    beta: float
    gamma: float
    delta: float
    n_mois: int
    annee_prevue: int


def niveaux_trimestriels(mensuel: pd.DataFrame) -> pd.Series:
    """Baseload de chaque trimestre sur ses mois valides, pondéré par les heures, indexé par (année, trimestre)."""
    v = mensuel[mensuel["valide"]]
    cles = [v["periode"].dt.year.rename("annee"), v["periode"].dt.quarter.rename("trimestre")]
    return (v["baseload_eur_mwh"] * v["heures_utilisees"]).groupby(cles).sum() / v["heures_utilisees"].groupby(cles).sum()


def calibrer_v2(mensuel: pd.DataFrame, annee: int) -> ParametresV2:
    """Moindres carrés sur tous les mois valides strictement antérieurs au 1er janvier de ``annee``."""
    h = historique_avant(mensuel, annee)
    niveaux = niveaux_trimestriels(h)
    ln_b = np.log(niveaux.reindex(pd.MultiIndex.from_arrays([h["periode"].dt.year, h["periode"].dt.quarter])).to_numpy())
    part = h["part_solaire"].to_numpy()
    effets = np.eye(12)[h["periode"].dt.month.to_numpy() - 1]
    x = np.column_stack([effets, part, ln_b, part * ln_b])
    b = np.linalg.lstsq(x, h["taux_capture"].to_numpy(), rcond=None)[0]
    return ParametresV2({m: float(b[m - 1]) for m in MOIS}, float(b[12]), float(b[13]), float(b[14]), len(h), annee)


def prevoir_v2(p: ParametresV2, mois: pd.Series, part_solaire: pd.Series, niveau: pd.Series) -> pd.Series:
    """Taux de capture prévu de chaque mois. Un niveau ou une part inconnus donnent NaN."""
    ln_b = np.log(niveau)
    return mois.map(p.alpha) + p.beta * part_solaire + p.gamma * ln_b + p.delta * part_solaire * ln_b


def niveau_du_trimestre(niveaux: pd.Series, annee: int, mois: pd.Series) -> pd.Series:
    """Niveau du trimestre de chaque mois de ``annee``, NaN si ce trimestre n'a aucun mois valide."""
    cles = pd.MultiIndex.from_arrays([[annee] * len(mois), (mois.to_numpy() - 1) // 3 + 1])
    return pd.Series(niveaux.reindex(cles).to_numpy(), index=mois.index)
