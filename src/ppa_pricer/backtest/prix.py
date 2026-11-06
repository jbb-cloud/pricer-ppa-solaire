"""Backtest du prix annuel : l'erreur qu'on aurait faite sur le prix, et pas seulement sur le taux de capture mensuel.

Le backtest du taux annuel de la V1 utilise le baseload et les volumes mensuels **réalisés**. Or, pour pricer une année future, il faut aussi deviner quels mois
seront chers : la forme du baseload. Ici, le prix prévu utilise la forme connue à l'avance, celle des deux années précédentes, et le niveau annuel réalisé :
on mesure donc le profil et la forme, sans le niveau, qui relève du marché à terme. Le résultat se lit en part du baseload annuel.
"""

import pandas as pd

from ppa_pricer.pricing.v1 import baseload_mensuel, forme_baseload, prix_juste


def taux_implicite(taux_capture: pd.Series, forme: pd.Series, volumes: pd.Series, annee: int) -> float:
    """Prix juste d'un baseload annuel de 1 : le taux de capture annuel du site selon la formule du pricing."""
    return prix_juste(taux_capture, baseload_mensuel(1.0, forme, annee), volumes)


def forme_connue(mensuel: pd.DataFrame, annee: int) -> pd.Series:
    """Forme mensuelle du baseload connue avant ``annee`` : la moyenne de ses deux années précédentes."""
    return forme_baseload(mensuel, (annee - 2, annee - 1))
