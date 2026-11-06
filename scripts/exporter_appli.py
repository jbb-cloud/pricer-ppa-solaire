"""Exporte les données de l'appli dans ``data/appli/`` (voir `src/ppa_pricer/donnees/appli.py`).

Usage : ``.venv/bin/python scripts/exporter_appli.py``, après ``scripts/telecharger_donnees.py``.
Vérifie ensuite que le prix V2 central calculé sur les fichiers exportés est exactement celui calculé sur la base.
"""

from pathlib import Path

import pandas as pd

from ppa_pricer.analyse.capture import charger_horaire
from ppa_pricer.donnees.appli import ecrire_horaire, ecrire_profil, lire_horaire, lire_profil_secours
from ppa_pricer.donnees.base import connexion
from ppa_pricer.donnees.energy_charts import charger_eolien
from ppa_pricer.donnees.pvgis import MONTPELLIER, lire_profil
from ppa_pricer.pricing.calcul import preparer_marche, prix_v2
from ppa_pricer.pricing.courbe import SCENARIO_CENTRAL, SCENARIOS_PARC_GW, lire_courbe
from ppa_pricer.pricing.v1 import volumes_mensuels

RACINE = Path(__file__).resolve().parents[1]
BASE = RACINE / "data" / "ppa.sqlite"
BRUTS = RACINE / "data" / "raw" / "energy_charts"
PROFIL = RACINE / "data" / "raw" / "pvgis" / f"profil_{MONTPELLIER.nom}.json"
COURBE = RACINE / "data" / "marche" / "courbe_fr_2026-10-29.csv"
BACKTEST_PRIX = RACINE / "reports" / "audit" / "prix_backtest.csv"
DOSSIER = RACINE / "data" / "appli"
ANNEE = 2027


def prix_central(horaire: pd.DataFrame, profil: pd.DataFrame) -> float:
    bp = pd.read_csv(BACKTEST_PRIX)
    marche = preparer_marche(horaire, lire_courbe(COURBE), ANNEE, (bp["m2_trajectoires"] - bp["realise"]).to_numpy())
    return prix_v2(marche, volumes_mensuels(profil), SCENARIOS_PARC_GW[SCENARIO_CENTRAL]).prix


def main() -> None:
    horaire = charger_horaire(connexion(BASE)).merge(charger_eolien(BRUTS), on="ts_utc", how="left")
    profil = lire_profil(PROFIL)
    for chemin in (ecrire_horaire(horaire, DOSSIER), ecrire_profil(profil, DOSSIER)):
        print(f"{chemin.relative_to(RACINE)} : {chemin.stat().st_size / 1e6:.1f} Mo")
    avant, apres = prix_central(horaire, profil), prix_central(lire_horaire(DOSSIER), lire_profil_secours(DOSSIER))
    print(f"Prix V2 central : {avant:.10f} sur la base, {apres:.10f} sur les fichiers exportés")
    if avant != apres:
        raise SystemExit("Les fichiers exportés ne redonnent pas le même prix")


if __name__ == "__main__":
    main()
