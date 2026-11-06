"""Profil de production d'un site photovoltaïque depuis l'API PVGIS (Commission européenne).

PVGIS simule, heure par heure et année après année, la production d'un système décrit par sa
position, sa puissance et ses pertes, à partir de données d'ensoleillement satellitaires. L'API
ne demande pas de jeton.

Choix de modélisation (voir `docs/pricing.md`) :
- orientation plein sud et inclinaison optimale calculée par PVGIS : configuration courante d'un
  parc au sol fixe ;
- pertes du système de 14 %, valeur proposée par défaut par PVGIS ;
- les horodatages de PVGIS sont en UTC, à la minute 10 de chaque heure (par exemple 12:10) :
  chaque valeur est rattachée à l'heure qui la contient. Cela suffit pour les volumes mensuels de
  la V1. Pour un calcul heure par heure, l'heure moyenne de production mesurée correspond à la
  minute 10 plutôt qu'au milieu de l'heure : le profil paraît alors environ 0,3 h trop tardif ;
- la puissance de PVGIS est en W, convertie en MW comme le reste du projet ;
- l'appli demande 10 années (2014–2023) pour un nouveau site : environ 13 s, contre 25 à 30 s pour toutes les années
  (mesuré le 04/11/2026). Le Monte-Carlo tire alors l'année météo parmi 10 au lieu de 19.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests

URL_API = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"
ORIENTATION_SUD = 0
ANNEES_APPLI = (2014, 2023)


class ErreurPVGIS(Exception):
    """PVGIS refuse la demande (lieu en mer, hors couverture…) ou ne répond pas."""


@dataclass(frozen=True)
class Site:
    nom: str
    latitude: float
    longitude: float
    puissance_kwc: float = 1000.0
    pertes_pct: float = 14.0


MONTPELLIER = Site("montpellier", 43.61, 3.88)


def telecharger_profil(site: Site, dossier: Path, forcer: bool = False) -> Path:
    """Télécharge la série horaire du site (toutes les années disponibles) et enregistre le JSON brut.

    Le fichier n'est pas re-téléchargé s'il existe déjà : une simulation passée ne change pas.
    """
    chemin = dossier / f"profil_{site.nom}.json"
    if chemin.exists() and not forcer:
        return chemin
    chemin.parent.mkdir(parents=True, exist_ok=True)
    reponse = requests.get(URL_API, params=parametres_api(site), timeout=300)
    reponse.raise_for_status()
    chemin.write_text(reponse.text)
    return chemin


def parametres_api(
    site: Site, inclinaison: float | None = None, orientation: float = ORIENTATION_SUD, annees: tuple[int, int] | None = None
) -> dict:
    """Paramètres de l'API. ``inclinaison`` à ``None`` : PVGIS calcule l'inclinaison optimale. ``orientation`` : 0 plein sud,
    −90 est, +90 ouest. ``annees`` à ``None`` : toutes les années disponibles."""
    parametres = {
        "lat": site.latitude,
        "lon": site.longitude,
        "pvcalculation": 1,
        "peakpower": site.puissance_kwc,
        "loss": site.pertes_pct,
        "aspect": orientation,
        "outputformat": "json",
        "browser": 0,
    }
    if inclinaison is None:
        parametres["optimalinclination"] = 1
    else:
        parametres["angle"] = inclinaison
    if annees is not None:
        parametres["startyear"], parametres["endyear"] = annees
    return parametres


def profil_depuis_json(donnees: dict) -> pd.DataFrame:
    """Réponse JSON de PVGIS en DataFrame ``ts_utc``, ``duree_min``, ``solaire_mw``."""
    brut = pd.DataFrame(donnees["outputs"]["hourly"])
    ts = pd.to_datetime(brut["time"], format="%Y%m%d:%H%M", utc=True).dt.floor("h")
    return pd.DataFrame({"ts_utc": ts, "duree_min": 60, "solaire_mw": brut["P"].astype(float) / 1e6})


def lire_profil(chemin: Path) -> pd.DataFrame:
    """Lit un JSON brut PVGIS en DataFrame ``ts_utc``, ``duree_min``, ``solaire_mw``."""
    return profil_depuis_json(json.loads(Path(chemin).read_text()))


def profil_en_direct(
    site: Site, inclinaison: float | None = None, orientation: float = ORIENTATION_SUD, annees: tuple[int, int] | None = ANNEES_APPLI, delai_s: float = 90
) -> tuple[pd.DataFrame, float]:
    """Profil du site demandé à l'API, et inclinaison retenue (l'optimale si ``inclinaison`` est ``None``).

    Lève ``ErreurPVGIS`` avec le message de PVGIS si la demande est refusée, ou si l'API ne répond pas à temps.
    """
    if not 0 <= (inclinaison if inclinaison is not None else 0) <= 90 or not -180 <= orientation <= 180 or site.puissance_kwc <= 0:
        raise ValueError("Inclinaison entre 0 et 90°, orientation entre −180 et 180°, puissance positive")
    try:
        reponse = requests.get(URL_API, params=parametres_api(site, inclinaison, orientation, annees), timeout=delai_s)
    except requests.RequestException as e:
        raise ErreurPVGIS(f"PVGIS ne répond pas : {e}") from e
    if reponse.status_code != 200:
        try:
            message = reponse.json().get("message", reponse.text)
        except ValueError:
            message = reponse.text
        raise ErreurPVGIS(f"PVGIS refuse la demande ({reponse.status_code}) : {message}")
    donnees = reponse.json()
    return profil_depuis_json(donnees), float(donnees["inputs"]["mounting_system"]["fixed"]["slope"]["value"])


def inclinaison_optimale(chemin: Path) -> float:
    """Inclinaison en degrés retenue par PVGIS pour le site, lue dans le JSON brut."""
    return float(json.loads(Path(chemin).read_text())["inputs"]["mounting_system"]["fixed"]["slope"]["value"])
