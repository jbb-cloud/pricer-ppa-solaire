"""Production solaire et consommation France depuis l'export éCO2mix de RTE (ODRÉ).

Sert de source de contrôle pour Energy-Charts (voir `docs/donnees.md`) : ces séries ne sont pas
chargées en base et n'entrent pas dans le verdict de la V1.

Choix de modélisation :
- jeu de données consolidé et définitif ``eco2mix-national-cons-def``, qui s'arrête quelques mois
  avant aujourd'hui ;
- l'export contient aussi des lignes :15 et :45 sans valeur de solaire : on garde les points
  :00 et :30, qui forment une série au pas de 30 minutes ;
- la convention d'horodatage de RTE n'est pas vérifiée. Son heure moyenne de production est plus
  tardive que celle d'Energy-Charts les années sans anomalie : comparer les écarts entre périodes
  plutôt que leur niveau.
"""

from pathlib import Path

import pandas as pd
import requests

URL_EXPORT = "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/eco2mix-national-cons-def/exports/csv"
PREMIERE_DATE = "2015-01-01"


def telecharger_export(dossier: Path, forcer: bool = False) -> Path:
    """Télécharge le solaire et la consommation en heures UTC et enregistre le CSV brut."""
    chemin = dossier / "eco2mix_national.csv"
    if chemin.exists() and not forcer:
        return chemin
    parametres = {
        "select": "date_heure,solaire,consommation",
        "where": f'date_heure>="{PREMIERE_DATE}"',
        "timezone": "UTC",
        "delimiter": ";",
    }
    reponse = requests.get(URL_EXPORT, params=parametres, timeout=600)
    reponse.raise_for_status()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(reponse.content)
    return chemin


def lire_export(chemin: Path) -> pd.DataFrame:
    """Lit le CSV brut en DataFrame ``ts_utc``, ``duree_min``, ``solaire_mw``, ``conso_mw``. Le vide reste NaN."""
    brut = pd.read_csv(chemin, sep=";", encoding="utf-8-sig")
    ts = pd.to_datetime(brut["date_heure"], utc=True)
    serie = pd.DataFrame(
        {"ts_utc": ts, "duree_min": 30, "solaire_mw": brut["solaire"].astype(float), "conso_mw": brut["consommation"].astype(float)}
    )
    return serie[ts.dt.minute.isin([0, 30])].sort_values("ts_utc", ignore_index=True)
