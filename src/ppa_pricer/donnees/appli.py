"""Données de l'appli : une table horaire France et le profil PVGIS de secours, en CSV compressé dans ``data/appli/``.

L'appli tourne ainsi sans la base SQLite ni les 185 Mo de données brutes. Les fichiers sont produits par
``scripts/exporter_appli.py`` à partir de la base, à précision complète : l'appli redonne exactement les chiffres des
rapports. Ils ne vivent que dans le dépôt privé, car la licence de la production Energy-Charts n'est pas confirmée
(voir `docs/interface.md`). ``profil_du_site`` fournit le profil d'un lieu choisi dans l'appli.
Heures en UTC ; une donnée inconnue reste vide dans le CSV et redevient NaN à la lecture.
"""

import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ppa_pricer.donnees.pvgis import ORIENTATION_SUD, ErreurPVGIS, Site, profil_en_direct

COLONNES_HORAIRE = ["ts_utc", "prix_eur_mwh", "solaire_mw", "conso_mw", "eolien_mw"]
COLONNES_PROFIL = ["ts_utc", "duree_min", "solaire_mw"]
FICHIER_HORAIRE = "horaire_fr.csv.gz"
FICHIER_PROFIL = "profil_montpellier.csv.gz"
DOSSIER_VILLES = "villes"  # profils précalculés des autres villes, plein sud à l'inclinaison optimale, toutes les années
FICHIER_INCLINAISONS = "inclinaisons.csv"


def _ecrire(table: pd.DataFrame, colonnes: list[str], chemin: Path) -> Path:
    manquantes = set(colonnes) - set(table.columns)
    if manquantes:
        raise ValueError(f"Colonnes manquantes : {sorted(manquantes)}")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    sortie = table[colonnes].copy()
    sortie["ts_utc"] = sortie["ts_utc"].dt.strftime("%Y-%m-%dT%H:%MZ")
    # Sans float_format, pandas écrit la représentation la plus courte qui relit le même flottant : aucun arrondi.
    sortie.to_csv(chemin, index=False, compression={"method": "gzip", "mtime": 0})
    return chemin


def _lire(chemin: Path, colonnes: list[str]) -> pd.DataFrame:
    table = pd.read_csv(chemin)
    if list(table.columns) != colonnes:
        raise ValueError(f"{chemin} : colonnes {list(table.columns)}, attendues {colonnes}")
    table["ts_utc"] = pd.to_datetime(table["ts_utc"], format="%Y-%m-%dT%H:%MZ", utc=True)
    return table


def ecrire_horaire(horaire: pd.DataFrame, dossier: Path) -> Path:
    return _ecrire(horaire, COLONNES_HORAIRE, Path(dossier) / FICHIER_HORAIRE)


def lire_horaire(dossier: Path) -> pd.DataFrame:
    """Table horaire France : ``ts_utc``, prix, solaire, consommation, éolien."""
    return _lire(Path(dossier) / FICHIER_HORAIRE, COLONNES_HORAIRE)


def ecrire_profil(profil: pd.DataFrame, dossier: Path) -> Path:
    return _ecrire(profil, COLONNES_PROFIL, Path(dossier) / FICHIER_PROFIL)


def lire_profil_secours(dossier: Path) -> pd.DataFrame:
    """Profil PVGIS de Montpellier (1 MWc), utilisé quand l'API PVGIS ne répond pas."""
    return _lire(Path(dossier) / FICHIER_PROFIL, COLONNES_PROFIL)


def nom_fichier_ville(ville: str) -> str:
    """``Orléans`` → ``profil_orleans.csv.gz`` : sans accent ni espace."""
    simple = unicodedata.normalize("NFKD", ville).encode("ascii", "ignore").decode().lower().replace(" ", "-")
    return f"profil_{simple}.csv.gz"


def ecrire_profil_ville(profil: pd.DataFrame, inclinaison: float, ville: str, dossier: Path) -> Path:
    """Profil précalculé d'une ville (1 MWc) et son inclinaison optimale, ajoutée ou remplacée dans l'index."""
    d = Path(dossier) / DOSSIER_VILLES
    chemin = _ecrire(profil, COLONNES_PROFIL, d / nom_fichier_ville(ville))
    index = d / FICHIER_INCLINAISONS
    table = pd.read_csv(index) if index.exists() else pd.DataFrame(columns=["ville", "inclinaison"])
    table = pd.concat([table[table["ville"] != ville], pd.DataFrame({"ville": [ville], "inclinaison": [inclinaison]})])
    table.sort_values("ville").to_csv(index, index=False)
    return chemin


def lire_profil_ville(ville: str, dossier: Path) -> tuple[pd.DataFrame, float] | None:
    """Profil précalculé (1 MWc) et inclinaison d'une ville, ou ``None`` si elle n'a pas été précalculée."""
    d = Path(dossier) / DOSSIER_VILLES
    chemin, index = d / nom_fichier_ville(ville), d / FICHIER_INCLINAISONS
    if not chemin.exists() or not index.exists():
        return None
    inclinaisons = pd.read_csv(index).set_index("ville")["inclinaison"]
    if ville not in inclinaisons:
        return None
    return _lire(chemin, COLONNES_PROFIL), float(inclinaisons[ville])


# Centres-villes approximatifs, pour choisir un lieu sans saisir de coordonnées.
VILLES = {
    "Montpellier": (43.61, 3.88),
    "Ajaccio": (41.93, 8.74),
    "Bordeaux": (44.84, -0.58),
    "Clermont-Ferrand": (45.78, 3.08),
    "Dijon": (47.32, 5.04),
    "Grenoble": (45.19, 5.72),
    "Lille": (50.63, 3.06),
    "Lyon": (45.76, 4.84),
    "Marseille": (43.30, 5.37),
    "Nantes": (47.22, -1.55),
    "Nice": (43.70, 7.27),
    "Orléans": (47.90, 1.90),
    "Paris": (48.86, 2.35),
    "Rennes": (48.11, -1.68),
    "Strasbourg": (48.57, 7.75),
    "Toulouse": (43.60, 1.44),
}
INCLINAISON_MONTPELLIER = 39.0  # optimale selon PVGIS, lue dans data/raw/pvgis/profil_montpellier.json


@dataclass(frozen=True)
class ProfilSite:
    profil: pd.DataFrame  # ts_utc, duree_min, solaire_mw pour la puissance demandée
    inclinaison: float
    source: str  # "cache" (ville livrée avec l'appli), "pvgis" (demande en direct) ou "secours" (PVGIS indisponible)
    avertissement: str | None = None


def profil_du_site(
    latitude: float, longitude: float, puissance_mwc: float, dossier: Path, inclinaison: float | None = None, orientation: float = ORIENTATION_SUD
) -> ProfilSite:
    """Profil de production du site.

    Une ville de ``VILLES``, plein sud à l'inclinaison optimale, est livrée avec l'appli (toutes les années, comme Montpellier
    dans les rapports) : aucun appel. Sinon, l'API PVGIS est appelée sur 2014–2023, ce qui prend 15 à 30 s. Si elle refuse ou ne répond pas, on retombe sur Montpellier,
    avec un avertissement que l'appli affiche : le prix n'est alors pas celui du site demandé.
    """
    if puissance_mwc <= 0:
        raise ValueError("La puissance doit être positive")

    def secours(source: str, avertissement: str | None = None) -> ProfilSite:
        profil = lire_profil_secours(dossier)
        profil["solaire_mw"] *= puissance_mwc
        return ProfilSite(profil, INCLINAISON_MONTPELLIER, source, avertissement)

    ville = next((v for v, c in VILLES.items() if c == (latitude, longitude)), None)
    if ville is not None and inclinaison is None and orientation == ORIENTATION_SUD:
        if ville == "Montpellier":
            return secours("cache")
        cache = lire_profil_ville(ville, dossier)
        if cache is not None:
            profil, retenue = cache
            profil["solaire_mw"] *= puissance_mwc
            return ProfilSite(profil, retenue, "cache")
    site = Site("demande", latitude, longitude, puissance_kwc=puissance_mwc * 1000)
    try:
        profil, retenue = profil_en_direct(site, inclinaison, orientation)
    except ErreurPVGIS as e:
        return secours("secours", f"{e}. Profil de Montpellier (plein sud, 39°) utilisé à la place.")
    return ProfilSite(profil, retenue, "pvgis")
