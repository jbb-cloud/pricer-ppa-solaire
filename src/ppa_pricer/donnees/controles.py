"""Contrôles qualité d'une série (prix ou production) à résolution d'origine.

Chaque contrôle compte les anomalies au lieu de les corriger : la décision de quoi faire d'un
trou ou d'un doublon se prend ensuite, en connaissance de cause.

- doublons : deux points au même horodatage ;
- mal alignés : un point horaire qui ne tombe pas sur une heure pleine, ou un point au quart
  d'heure qui ne tombe pas sur :00, :15, :30, :45 ;
- trous : points attendus sur la grille (60 minutes avant le passage au quart d'heure,
  15 minutes après) mais absents de la source ;
- valeurs manquantes : points présents mais sans valeur ;
- changements d'heure : nombre d'heures par jour civil de Paris (23 au printemps, 25 à
  l'automne, 24 sinon). En UTC la série n'a pas de changement d'heure ; ce contrôle vérifie
  qu'une source n'a pas mal converti une heure locale (heure dupliquée ou perdue) ;
- calage du solaire : heure moyenne de production et production de nuit, mois par mois. Les
  contrôles précédents vérifient la grille temporelle, pas la plausibilité physique des valeurs.
"""

import pandas as pd

FUSEAU_AFFICHAGE = "Europe/Paris"
# Seuils du contrôle de calage du solaire : hypothèse H7 de `docs/hypotheses.md`.
ECART_CALAGE_MAX_H = 0.2
PART_NUIT_MAX = 0.001
# Il fait nuit partout en France métropolitaine, toute l'année, de 21 h à 03 h UTC.
HEURES_NUIT_UTC = (21, 22, 23, 0, 1, 2)


def grille_attendue(debut: pd.Timestamp, fin: pd.Timestamp, debut_quart_heure: pd.Timestamp) -> pd.DatetimeIndex:
    """Horodatages attendus entre ``debut`` et ``fin`` inclus, selon le régime de résolution."""
    horaire = pd.date_range(debut, min(fin, debut_quart_heure - pd.Timedelta("1h")), freq="h")
    quart = pd.date_range(max(debut, debut_quart_heure), fin, freq="15min")
    return horaire.append(quart)


def heures_par_jour_paris(ts_horaires: pd.Series) -> pd.Series:
    """Nombre d'heures de chaque jour civil de Paris, à partir d'horodatages horaires en UTC."""
    return ts_horaires.dt.tz_convert(FUSEAU_AFFICHAGE).dt.date.value_counts().sort_index()


def heures_attendues_par_jour(jours: pd.Index) -> pd.Series:
    """23, 24 ou 25 selon le changement d'heure de chaque jour civil de Paris."""
    debut = pd.DatetimeIndex(pd.to_datetime(jours)).tz_localize(FUSEAU_AFFICHAGE)
    fin = (pd.DatetimeIndex(pd.to_datetime(jours)) + pd.Timedelta("1D")).tz_localize(FUSEAU_AFFICHAGE)
    return pd.Series(((fin - debut) / pd.Timedelta("1h")).astype(int), index=jours)


def controler_calage_solaire(serie: pd.DataFrame) -> pd.DataFrame:
    """Plausibilité physique d'une série ``ts_utc``, ``duree_min``, ``solaire_mw``, mois par mois.

    Le midi solaire ne bouge pas d'une année à l'autre : en UTC, l'heure moyenne de production
    d'un mois doit rester proche de celle du même mois des autres années. Une série décalée
    passe tous les contrôles de grille, mais pas celui-ci.

    - ``heure_moyenne_utc`` : moyenne du milieu de chaque période, pondérée par l'énergie ;
    - ``reference_utc`` : médiane de cette heure sur les mêmes mois calendaires de la série. Elle
      ne demande pas de choisir à la main une période « propre » et résiste tant que les années
      décalées restent minoritaires ;
    - ``part_nuit`` : part de l'énergie du mois produite aux heures ``HEURES_NUIT_UTC``.

    Les mois suivent le calendrier de Paris. Les points sans valeur sont ignorés, jamais comptés
    comme 0. Le contrôle signale sans corriger.
    """
    s = serie.dropna(subset=["solaire_mw"])
    ts = s["ts_utc"]
    periode = ts.dt.tz_convert(FUSEAU_AFFICHAGE).dt.tz_localize(None).dt.to_period("M").rename("periode")
    milieu = ts.dt.hour + ts.dt.minute / 60 + s["duree_min"] / 120
    energie = s["solaire_mw"] * s["duree_min"] / 60
    total = energie.groupby(periode).sum()

    resultat = pd.DataFrame(
        {
            "heure_moyenne_utc": (milieu * energie).groupby(periode).sum() / total,
            "part_nuit": energie.where(ts.dt.hour.isin(HEURES_NUIT_UTC), 0.0).groupby(periode).sum() / total,
        }
    )
    resultat["reference_utc"] = resultat["heure_moyenne_utc"].groupby(resultat.index.month).transform("median")
    resultat["ecart_h"] = resultat["heure_moyenne_utc"] - resultat["reference_utc"]
    resultat["calage_suspect"] = resultat["ecart_h"].abs() > ECART_CALAGE_MAX_H
    resultat["nuit_suspecte"] = resultat["part_nuit"] > PART_NUIT_MAX
    return resultat.reset_index()


def controler_serie(serie: pd.DataFrame, debut_quart_heure: pd.Timestamp) -> dict:
    """Résumé des anomalies d'une série ``ts_utc``, ``duree_min`` et colonnes de valeurs.

    ``debut_quart_heure`` est la date (UTC) à partir de laquelle la série est au pas de
    15 minutes ; elle diffère entre les prix et la production.
    """
    ts = serie["ts_utc"]
    secondes = (ts - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()
    mal_alignes = (secondes % (serie["duree_min"] * 60) != 0).sum()
    presents = pd.DatetimeIndex(ts.drop_duplicates())
    trous = grille_attendue(ts.min(), ts.max(), debut_quart_heure).difference(presents)

    heures = ts.dt.floor("h").drop_duplicates()
    # Les jours incomplets aux bords de la série (début et fin) ne sont pas des anomalies.
    par_jour = heures_par_jour_paris(heures).iloc[1:-1]
    attendu = heures_attendues_par_jour(par_jour.index)
    jours_anormaux = par_jour[par_jour != attendu]

    colonnes = [c for c in serie.columns if c not in ("ts_utc", "duree_min")]
    return {
        "debut_utc": ts.min(),
        "fin_utc": ts.max(),
        "n_points": len(serie),
        "doublons": int(ts.duplicated().sum()),
        "mal_alignes": int(mal_alignes),
        "trous": len(trous),
        "trous_liste": list(trous),
        "jours_heures_anormales": {str(j): int(n) for j, n in jours_anormaux.items()},
        "valeurs": {
            c: {
                "manquants": int(serie[c].isna().sum()),
                "min": float(serie[c].min()),
                "max": float(serie[c].max()),
                "negatifs": int((serie[c] < 0).sum()),
            }
            for c in colonnes
        },
    }
