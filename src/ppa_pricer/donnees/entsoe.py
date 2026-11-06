"""Prix day-ahead, production solaire et consommation France depuis ENTSO-E Transparency.

ENTSO-E sert de source de contrôle pour Energy-Charts (voir `docs/donnees.md`) : ces séries ne sont
pas chargées en base et n'entrent pas dans le verdict de la V1.

Choix de modélisation :
- un fichier XML brut par année civile UTC et par série : une année passée ne se re-télécharge pas ;
- le jeton reste dans ``.env``. L'URL d'une requête le contient, donc les exceptions de ``requests``
  ne sont jamais recopiées telles quelles dans un message d'erreur ;
- la durée de chaque point vient de la résolution du document (``PT60M``, ``PT30M``, ``PT15M``) ;
- courbe ``A03`` : une position absente reprend la valeur précédente, car ENTSO-E ne répète pas une
  valeur identique. Courbe ``A01`` : une position absente est un point manquant et le reste ;
- production solaire : on garde les séries de production (``inBiddingZone``), pas la consommation
  de la filière (``outBiddingZone``).
"""

import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import requests

URL_API = "https://web-api.tp.entsoe.eu/api"
DOMAINE_FR = "10YFR-RTE------C"
ESSAIS_MAX = 4
PAUSE_ENTRE_APPELS_S = 1
CODES_A_REESSAYER = {429, 500, 502, 503, 504}

SERIES = {
    "solaire": {"documentType": "A75", "processType": "A16", "psrType": "B16", "in_Domain": DOMAINE_FR},
    "conso": {"documentType": "A65", "processType": "A16", "outBiddingZone_Domain": DOMAINE_FR},
    "prix": {"documentType": "A44", "in_Domain": DOMAINE_FR, "out_Domain": DOMAINE_FR},
}


class AucuneDonnee(Exception):
    """ENTSO-E répond correctement, mais n'a pas de donnée pour cette demande."""


def lire_cle(chemin: Path) -> str:
    """Jeton ``ENTSOE_API_KEY`` lu dans ``.env`` ; le message d'erreur ne cite jamais le contenu du fichier."""
    chemin = Path(chemin)
    if chemin.exists():
        for ligne in chemin.read_text().splitlines():
            nom, separateur, valeur = ligne.strip().partition("=")
            if separateur and nom.strip() == "ENTSOE_API_KEY" and valeur.strip().strip("\"'"):
                return valeur.strip().strip("\"'")
    raise ValueError(f"Aucune ligne ENTSOE_API_KEY=... dans {chemin}")


def _raison_refus(texte: str, cle: str) -> str:
    """Motif d'un document d'erreur ENTSO-E, sans le jeton."""
    try:
        raison = ET.fromstring(texte).findtext("{*}Reason/{*}text", default="")
    except ET.ParseError:
        raison = ""
    return raison.replace(cle, "***")[:200]


def _demander(parametres: dict, cle: str) -> requests.Response:
    """Envoie la requête avec des reprises ; aucune erreur renvoyée ne contient l'URL."""
    raison = ""
    for essai in range(ESSAIS_MAX):
        try:
            reponse = requests.get(URL_API, params={"securityToken": cle, **parametres}, timeout=300)
        except requests.RequestException as erreur:
            raison = type(erreur).__name__
        else:
            if reponse.status_code == 200:
                return reponse
            raison = f"HTTP {reponse.status_code} {_raison_refus(reponse.text, cle)}".strip()
            if reponse.status_code not in CODES_A_REESSAYER:
                break
        if essai < ESSAIS_MAX - 1:
            time.sleep(15 * (essai + 1))
    raise RuntimeError(f"Requête ENTSO-E refusée : {raison}") from None


def telecharger_annee(serie: str, annee: int, dossier: Path, cle: str, forcer: bool = False) -> Path:
    """Télécharge une année civile UTC d'une série et enregistre le XML brut.

    Le fichier d'une année passée n'est pas re-téléchargé ; celui de l'année en cours l'est toujours.
    """
    chemin = dossier / f"{serie}_FR_{annee}.xml"
    maintenant = pd.Timestamp.now(tz="UTC")
    if chemin.exists() and not forcer and annee < maintenant.year:
        return chemin
    debut = pd.Timestamp(f"{annee}-01-01", tz="UTC")
    fin = min(pd.Timestamp(f"{annee + 1}-01-01", tz="UTC"), maintenant.floor("h"))
    parametres = {**SERIES[serie], "periodStart": f"{debut:%Y%m%d%H%M}", "periodEnd": f"{fin:%Y%m%d%H%M}"}
    texte = _demander(parametres, cle).text
    if ET.fromstring(texte).tag.endswith("Acknowledgement_MarketDocument"):
        raise AucuneDonnee(f"{serie} {annee} : {_raison_refus(texte, cle)}")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte)
    time.sleep(PAUSE_ENTRE_APPELS_S)
    return chemin


def _points(periode: ET.Element, courbe: str) -> pd.DataFrame:
    """Points d'une période ENTSO-E en DataFrame ``ts_utc``, ``duree_min``, ``valeur``."""
    debut = pd.Timestamp(periode.findtext("{*}timeInterval/{*}start"))
    fin = pd.Timestamp(periode.findtext("{*}timeInterval/{*}end"))
    resolution = periode.findtext("{*}resolution")
    correspondance = re.fullmatch(r"PT(\d+)M", resolution)
    if correspondance is None:
        raise ValueError(f"Résolution ENTSO-E non prévue : {resolution}")
    duree = int(correspondance.group(1))
    points = periode.findall("{*}Point")
    valeurs = pd.Series(
        [float(p.findtext("{*}quantity", default=p.findtext("{*}price.amount"))) for p in points],
        index=[int(p.findtext("{*}position")) for p in points],
        dtype=float,
    )
    if courbe == "A03":
        n_points = int((fin - debut) / pd.Timedelta(minutes=duree))
        valeurs = valeurs.reindex(range(1, n_points + 1)).ffill()
    ts = debut + (valeurs.index.to_numpy() - 1) * pd.Timedelta(minutes=duree)
    return pd.DataFrame({"ts_utc": ts, "duree_min": duree, "valeur": valeurs.to_numpy()})


def lire_xml(chemin: Path, serie: str) -> pd.DataFrame:
    """Lit un XML brut en DataFrame ``ts_utc``, ``duree_min``, ``valeur``, trié dans le temps."""
    racine = ET.fromstring(Path(chemin).read_text())
    morceaux = []
    for serie_temporelle in racine.findall("{*}TimeSeries"):
        if serie == "solaire" and serie_temporelle.find("{*}inBiddingZone_Domain.mRID") is None:
            continue
        courbe = serie_temporelle.findtext("{*}curveType", default="A01")
        morceaux += [_points(p, courbe) for p in serie_temporelle.findall("{*}Period")]
    if not morceaux:
        return pd.DataFrame({"ts_utc": pd.to_datetime([], utc=True), "duree_min": [], "valeur": []})
    return pd.concat(morceaux, ignore_index=True).sort_values("ts_utc", ignore_index=True)


def lire_annees(dossier: Path, serie: str) -> pd.DataFrame:
    """Toutes les années téléchargées d'une série, doublons éventuels compris."""
    fichiers = sorted(Path(dossier).glob(f"{serie}_FR_*.xml"))
    return pd.concat([lire_xml(f, serie) for f in fichiers], ignore_index=True).sort_values("ts_utc", ignore_index=True)
