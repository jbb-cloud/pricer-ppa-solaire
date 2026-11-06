"""Prix day-ahead, production solaire et consommation France depuis l'API Energy-Charts.

Energy-Charts (Fraunhofer ISE) redistribue les prix day-ahead publiés par SMARD
(Bundesnetzagentur) et la production publiée par ENTSO-E, sous licence CC BY 4.0. L'API ne
demande pas de jeton, ce qui en fait la source la plus simple pour démarrer ; ENTSO-E servira
de référence de contrôle plus tard.

Choix de modélisation :
- les horodatages de l'API sont des secondes Unix, donc sans ambiguïté : on les garde en UTC ;
- un prix absent (``null`` dans le JSON) reste NaN, jamais 0 ;
- la durée de chaque point (60 ou 15 minutes) est déduite de la date et non de l'écart avec le
  point suivant : un trou dans la série ferait sinon croire à une durée plus longue ;
- le day-ahead européen est passé au pas de 15 minutes pour la livraison du 1er octobre 2025
  à 00:00 heure de Paris, soit le 30 septembre 2025 à 22:00 UTC (constaté dans les données) ;
- les fichiers de production et de consommation passent au pas de 15 minutes le 1er janvier 2026
  à 00:00 heure de Paris, soit le 31 décembre 2025 à 23:00 UTC (constaté dans les données) ;
- ENTSO-E est pourtant au quart d'heure dès fin 2024 : en 2025, chaque valeur horaire d'Energy-Charts
  reprend le premier quart d'heure de l'heure, pas leur moyenne (`docs/donnees.md`). On la garde telle
  que publiée (H8).
"""

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

URL_API = "https://api.energy-charts.info"
DEBUT_QUART_HEURE_UTC = pd.Timestamp("2025-09-30T22:00Z")
DEBUT_QUART_HEURE_PRODUCTION_UTC = pd.Timestamp("2025-12-31T23:00Z")
ESSAIS_MAX = 5
PAUSE_ENTRE_APPELS_S = 10


def telecharger_prix_annee(annee: int, dossier: Path, zone: str = "FR", forcer: bool = False) -> Path:
    """Télécharge les prix day-ahead d'une année civile (en UTC) et enregistre le JSON brut."""
    chemin = dossier / f"prix_{zone}_{annee}.json"
    return _telecharger_annee(f"{URL_API}/price", {"bzn": zone}, annee, chemin, forcer)


def telecharger_production_annee(annee: int, dossier: Path, pays: str = "fr", forcer: bool = False) -> Path:
    """Télécharge la production par filière et la consommation d'une année civile (en UTC)."""
    chemin = dossier / f"production_{pays}_{annee}.json"
    return _telecharger_annee(f"{URL_API}/public_power", {"country": pays}, annee, chemin, forcer)


def _telecharger_annee(url: str, parametres: dict, annee: int, chemin: Path, forcer: bool) -> Path:
    """Télécharge une année civile UTC et enregistre la réponse brute dans ``chemin``.

    Le fichier d'une année passée n'est pas re-téléchargé s'il existe déjà ; celui de l'année
    en cours l'est toujours, puisqu'il se complète chaque jour.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    annee_en_cours = pd.Timestamp.now(tz="UTC").year
    if chemin.exists() and not forcer and annee < annee_en_cours:
        return chemin

    parametres = {**parametres, "start": f"{annee}-01-01T00:00Z", "end": f"{annee}-12-31T23:59Z"}
    for essai in range(ESSAIS_MAX):
        try:
            reponse = requests.get(url, params=parametres, timeout=120)
            reponse.raise_for_status()
            break
        except requests.RequestException as erreur:
            if essai == ESSAIS_MAX - 1:
                raise
            # L'API limite le rythme des appels (erreur 429) et indique dans l'en-tête
            # Retry-After combien de secondes attendre ; on attend au moins ce délai.
            demande = getattr(erreur.response, "headers", {}).get("Retry-After", "0")
            time.sleep(max(float(demande), 15 * (essai + 1)))
    chemin.write_text(reponse.text)
    time.sleep(PAUSE_ENTRE_APPELS_S)
    return chemin


def lire_prix_brut(chemin: Path) -> pd.DataFrame:
    """Lit un JSON brut de prix en DataFrame ``ts_utc``, ``duree_min``, ``prix_eur_mwh``.

    ``ts_utc`` est le début de la période de livraison.
    """
    donnees = json.loads(Path(chemin).read_text())
    ts = _horodatages(donnees, DEBUT_QUART_HEURE_UTC)
    return ts.assign(prix_eur_mwh=_valeurs(donnees["price"], len(ts), chemin))


def lire_production_brut(chemin: Path) -> pd.DataFrame:
    """Lit un JSON brut de production en DataFrame ``ts_utc``, ``duree_min``, ``solaire_mw``, ``conso_mw``.

    Les valeurs sont des puissances moyennes en MW sur la période. Seuls le solaire (« Solar »)
    et la consommation (« Load ») sont gardés pour la V1 ; les autres filières restent dans le
    JSON brut. Un solaire à 0 la nuit est un vrai zéro (production nulle), pas une donnée
    manquante : les données manquantes arrivent en ``null``.
    """
    donnees = json.loads(Path(chemin).read_text())
    ts = _horodatages(donnees, DEBUT_QUART_HEURE_PRODUCTION_UTC)
    series = {s["name"]: s["data"] for s in donnees["production_types"]}
    return ts.assign(
        solaire_mw=_valeurs(series["Solar"], len(ts), chemin),
        conso_mw=_valeurs(series["Load"], len(ts), chemin),
    )


def lire_eolien_brut(chemin: Path) -> pd.DataFrame:
    """Lit l'éolien d'un JSON brut de production en DataFrame ``ts_utc``, ``duree_min``, ``eolien_mw``.

    Somme de l'éolien terrestre et en mer. L'éolien en mer n'existe pas dans les fichiers avant 2023
    et commence vide en 2023 : il compte pour 0 avant sa première valeur publiée (hypothèse H11),
    parce que le parc était absent ou négligeable. Après cette valeur, un trou reste NaN.
    """
    donnees = json.loads(Path(chemin).read_text())
    ts = _horodatages(donnees, DEBUT_QUART_HEURE_PRODUCTION_UTC)
    series = {s["name"]: s["data"] for s in donnees["production_types"]}
    terrestre = _valeurs(series["Wind onshore"], len(ts), chemin)
    en_mer = _valeurs(series.get("Wind offshore", [None] * len(ts)), len(ts), chemin)
    connues = np.flatnonzero(np.isfinite(en_mer))
    en_mer[: connues[0] if len(connues) else len(en_mer)] = 0.0
    return ts.assign(eolien_mw=terrestre + en_mer)


def charger_eolien(dossier: Path, pays: str = "fr") -> pd.DataFrame:
    """Éolien horaire ``ts_utc``, ``eolien_mw`` de tous les fichiers bruts de production de ``dossier``."""
    fichiers = sorted(Path(dossier).glob(f"production_{pays}_*.json"))
    if not fichiers:
        raise FileNotFoundError(f"Aucun fichier de production dans {dossier}")
    serie = pd.concat([lire_eolien_brut(f) for f in fichiers], ignore_index=True)
    return agreger_horaire(serie.drop_duplicates("ts_utc").sort_values("ts_utc"))


def charger_filiere(dossier: Path, serie: str, colonne: str, pays: str = "fr") -> pd.DataFrame:
    """Une série de production (``Nuclear``, ``Residual load``...) au pas horaire : ``ts_utc``, ``colonne``.

    Le pas des fichiers diffère selon les pays : l'Allemagne est au quart d'heure dès 2015. La durée d'un point est donc
    constatée, comme l'écart à son plus proche voisin, et non déduite d'une date de passage propre à la France.
    """
    fichiers = sorted(Path(dossier).glob(f"production_{pays}_*.json"))
    if not fichiers:
        raise FileNotFoundError(f"Aucun fichier de production {pays} dans {dossier}")
    morceaux = []
    for chemin in fichiers:
        donnees = json.loads(chemin.read_text())
        ts = pd.to_datetime(donnees["unix_seconds"], unit="s", utc=True)
        valeurs = {s["name"]: s["data"] for s in donnees["production_types"]}[serie]
        morceaux.append(pd.DataFrame({"ts_utc": ts, colonne: _valeurs(valeurs, len(ts), chemin)}))
    points = pd.concat(morceaux, ignore_index=True).drop_duplicates("ts_utc").sort_values("ts_utc", ignore_index=True)
    ecart = points["ts_utc"].diff()
    duree = pd.concat([ecart, ecart.shift(-1)], axis=1).min(axis=1).dt.total_seconds().div(60).clip(upper=60)
    return agreger_horaire(points.assign(duree_min=duree))


def _horodatages(donnees: dict, debut_quart_heure: pd.Timestamp) -> pd.DataFrame:
    """Horodatages UTC et durée de chaque point, déduite de la date de passage au quart d'heure."""
    ts = pd.to_datetime(donnees["unix_seconds"], unit="s", utc=True)
    return pd.DataFrame({"ts_utc": ts, "duree_min": np.where(ts >= debut_quart_heure, 15, 60)})


def _valeurs(liste: list, n_attendu: int, chemin: Path) -> np.ndarray:
    """Convertit une liste JSON (avec des ``null``) en tableau de flottants avec NaN."""
    if len(liste) != n_attendu:
        raise ValueError(f"{chemin} : nombre de valeurs différent du nombre d'horodatages")
    return pd.array(liste, dtype="Float64").to_numpy(dtype=float, na_value=np.nan)


def agreger_horaire(serie: pd.DataFrame) -> pd.DataFrame:
    """Ramène toutes les colonnes de valeurs d'une série au pas horaire (V1 du modèle).

    La valeur d'une heure au pas de 15 minutes est la moyenne simple de ses 4 quarts d'heure.
    Pour un prix, c'est le prix d'un produit qui livre une puissance constante pendant l'heure ;
    pour une puissance en MW, c'est la puissance moyenne de l'heure, égale à l'énergie produite
    en MWh. Si un seul des 4 quarts d'heure manque, l'heure est NaN : on ne fabrique pas de
    valeur à partir d'une heure incomplète. Chaque colonne est traitée séparément. Les heures
    totalement absentes de la source sont ajoutées avec des NaN, pour que la grille horaire
    soit complète et que les trous restent visibles.
    """
    colonnes = [c for c in serie.columns if c not in ("ts_utc", "duree_min")]
    heure = serie["ts_utc"].dt.floor("h")
    groupes = serie.groupby(heure)[colonnes]
    attendu = 60 / serie.groupby(heure)["duree_min"].first()
    complet = groupes.count().eq(attendu, axis=0)
    horaire = groupes.mean().where(complet)
    grille = pd.date_range(horaire.index.min(), horaire.index.max(), freq="h", name="ts_utc")
    return horaire.reindex(grille).reset_index()
