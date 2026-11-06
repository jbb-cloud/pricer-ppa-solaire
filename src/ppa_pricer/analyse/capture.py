"""Taux de capture solaire historiques, mensuels et annuels.

Définitions (voir `docs/perimetre.md`), pour une période (mois ou année) :
- baseload $B$ : moyenne simple des prix horaires ;
- prix capté $C = \\sum_h q_h p_h / \\sum_h q_h$, avec $q_h$ la production solaire nationale ;
- taux de capture $TC = C / B$ ;
- part du solaire $S = \\sum_h q_h / \\sum_h \\text{conso}_h$.

Choix (décidés le 29/10/2026, voir `docs/donnees.md`) :
- les périodes suivent le calendrier civil de Paris (convention des contrats) ; seule
  l'affectation d'une heure à sa période utilise l'heure locale, les données restent en UTC ;
- toutes les grandeurs d'une période sont calculées sur les mêmes heures : celles où prix,
  solaire et consommation sont tous connus ;
- une période est valide si au plus 5 % de ses heures calendaires manquent (heures absentes
  ou avec une valeur NaN) ; sinon ses grandeurs sont NaN ;
- le taux de capture annuel est le prix capté annuel divisé par le baseload annuel (et non la
  moyenne des 12 mois) : les mois où le solaire produit le plus pèsent plus, comme dans le
  revenu réel d'un parc.

Limite connue : si le baseload d'une période est proche de 0, le ratio devient instable.
"""

import sqlite3

import pandas as pd

from ppa_pricer.donnees.base import lire_serie
from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE
from ppa_pricer.donnees.energy_charts import agreger_horaire

SEUIL_MANQUANT = 0.05
COLONNES_HORAIRES = ["prix_eur_mwh", "solaire_mw", "conso_mw"]
GRANDEURS = ["baseload_eur_mwh", "prix_capte_eur_mwh", "taux_capture", "part_solaire",
             "energie_solaire_mwh", "conso_mwh"]


def charger_horaire(con: sqlite3.Connection, zone: str = "FR") -> pd.DataFrame:
    """Série horaire UTC ``ts_utc``, ``prix_eur_mwh``, ``solaire_mw``, ``conso_mw`` depuis la base."""
    prix = agreger_horaire(lire_serie(con, "prix_day_ahead", zone))
    production = agreger_horaire(lire_serie(con, "production_conso", zone))
    return prix.merge(production, on="ts_utc", how="outer").sort_values("ts_utc", ignore_index=True)


def periodes_paris(ts_utc: pd.Series, frequence: str) -> pd.Series:
    """Période civile de Paris (``"M"`` mois, ``"Y"`` année) de chaque horodatage UTC."""
    return ts_utc.dt.tz_convert(FUSEAU_AFFICHAGE).dt.tz_localize(None).dt.to_period(frequence)


def heures_calendaires(periodes: pd.Index) -> pd.Series:
    """Nombre d'heures de chaque période à Paris (changements d'heure compris)."""
    debut = pd.DatetimeIndex([p.start_time for p in periodes]).tz_localize(FUSEAU_AFFICHAGE)
    fin = pd.DatetimeIndex([(p + 1).start_time for p in periodes]).tz_localize(FUSEAU_AFFICHAGE)
    return pd.Series(((fin - debut) / pd.Timedelta("1h")).astype(int), index=periodes)


def taux_de_capture(horaire: pd.DataFrame, frequence: str = "M", seuil_manquant: float = SEUIL_MANQUANT) -> pd.DataFrame:
    """Baseload, prix capté, taux de capture et part du solaire par période civile de Paris.

    Une ligne par période présente dans ``horaire`` ; les colonnes ``heures_attendues``,
    ``heures_utilisees``, ``part_manquante`` et ``valide`` disent sur quoi repose le calcul.
    """
    periode = periodes_paris(horaire["ts_utc"], frequence)
    utilisable = horaire[COLONNES_HORAIRES].notna().all(axis=1)
    h = horaire[utilisable].assign(
        periode=periode[utilisable],
        recette=lambda d: d["prix_eur_mwh"] * d["solaire_mw"],
    )
    g = h.groupby("periode")
    resultat = pd.DataFrame(
        {
            "heures_utilisees": g.size(),
            "baseload_eur_mwh": g["prix_eur_mwh"].mean(),
            "prix_capte_eur_mwh": g["recette"].sum() / g["solaire_mw"].sum(),
            "energie_solaire_mwh": g["solaire_mw"].sum(),
            "conso_mwh": g["conso_mw"].sum(),
        }
    )
    toutes = pd.Index(sorted(periode.unique()), name="periode")
    resultat = resultat.reindex(toutes)
    resultat["heures_utilisees"] = resultat["heures_utilisees"].fillna(0).astype(int)
    resultat["heures_attendues"] = heures_calendaires(toutes)
    resultat["part_manquante"] = 1 - resultat["heures_utilisees"] / resultat["heures_attendues"]
    resultat["valide"] = resultat["part_manquante"] <= seuil_manquant
    resultat["taux_capture"] = resultat["prix_capte_eur_mwh"] / resultat["baseload_eur_mwh"]
    resultat["part_solaire"] = resultat["energie_solaire_mwh"] / resultat["conso_mwh"]
    resultat.loc[~resultat["valide"], GRANDEURS] = float("nan")
    colonnes = ["heures_attendues", "heures_utilisees", "part_manquante", "valide", *GRANDEURS]
    return resultat[colonnes].reset_index()
