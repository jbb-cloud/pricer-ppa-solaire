"""Références naïves à battre, définies dans `docs/perimetre.md`.

- R1, persistance : le taux de capture du même mois l'année précédente ;
- R2, moyenne climatologique : la moyenne du taux de capture de ce mois calendaire sur toutes
  les années antérieures.

Comme le portefeuille 1/N sur les actions, elles n'ont aucun paramètre estimé : un modèle qui
ne les bat pas n'apporte rien.
"""

import pandas as pd

from ppa_pricer.modele.v1 import MOIS, historique_avant


def persistance(mensuel: pd.DataFrame, annee: int) -> pd.Series:
    """R1 : taux de capture du même mois en T−1, indexé par le mois calendaire."""
    precedente = mensuel[(mensuel["periode"].dt.year == annee - 1) & mensuel["valide"]]
    return precedente.set_index(precedente["periode"].dt.month)["taux_capture"].reindex(list(MOIS))


def climatologie(mensuel: pd.DataFrame, annee: int) -> pd.Series:
    """R2 : moyenne du taux de capture de chaque mois calendaire sur les années antérieures."""
    h = historique_avant(mensuel, annee)
    return h.groupby(h["periode"].dt.month)["taux_capture"].mean().reindex(list(MOIS))
