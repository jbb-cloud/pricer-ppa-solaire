"""Précalcule le profil PVGIS des villes de l'appli (voir `docs/interface.md`), pour éviter 15 à 30 s d'attente par ville.

Usage : ``.venv/bin/python scripts/precalculer_villes.py``. Plein sud, inclinaison optimale, 1 MWc, toutes les années
disponibles, comme Montpellier dans les rapports. Montpellier, déjà livré, est sauté ; une ville déjà présente aussi.
Les appels sont faits l'un après l'autre, pour ne pas surcharger l'API publique.
"""

from pathlib import Path

from ppa_pricer.donnees.appli import VILLES, ecrire_profil_ville, lire_profil_ville
from ppa_pricer.donnees.pvgis import Site, profil_en_direct

DOSSIER = Path(__file__).resolve().parents[1] / "data" / "appli"


def main() -> None:
    for ville, (lat, lon) in VILLES.items():
        if ville == "Montpellier" or lire_profil_ville(ville, DOSSIER) is not None:
            continue
        profil, inclinaison = profil_en_direct(Site(ville, lat, lon), annees=None, delai_s=300)
        chemin = ecrire_profil_ville(profil, inclinaison, ville, DOSSIER)
        print(f"{ville} : {inclinaison:.0f}°, {len(profil)} heures, {chemin.stat().st_size / 1e6:.2f} Mo", flush=True)


if __name__ == "__main__":
    main()
