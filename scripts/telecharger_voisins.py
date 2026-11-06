"""Télécharge la production et les prix de l'Allemagne et de l'Espagne depuis Energy-Charts, 2015–2026.

Usage : ``.venv/bin/python scripts/telecharger_voisins.py``
Écrit dans ``data/raw/energy_charts/``, sans toucher à la base. Un fichier déjà présent n'est pas retéléchargé.
Le marché allemand s'appelait DE-AT-LU jusqu'au 30/09/2018, puis DE-LU.
"""

from pathlib import Path

from ppa_pricer.donnees.energy_charts import telecharger_prix_annee, telecharger_production_annee

DOSSIER = Path(__file__).resolve().parents[1] / "data" / "raw" / "energy_charts"
ANNEES = range(2015, 2027)
PRODUCTION = ["de", "es"]
PRIX = {"ES": ANNEES, "DE-AT-LU": range(2015, 2019), "DE-LU": range(2018, 2027)}


def main() -> None:
    fichiers = []
    for pays in PRODUCTION:
        for annee in ANNEES:
            fichiers.append(telecharger_production_annee(annee, DOSSIER, pays=pays))
    for zone, annees in PRIX.items():
        for annee in annees:
            fichiers.append(telecharger_prix_annee(annee, DOSSIER, zone=zone))
    total = sum(f.stat().st_size for f in fichiers)
    print(f"{len(fichiers)} fichiers, {total / 1e6:.1f} Mo")


if __name__ == "__main__":
    main()
