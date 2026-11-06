"""Analyse historique : taux de capture mensuels et annuels, et graphiques.

Usage : ``.venv/bin/python scripts/analyser.py``
Écrit dans ``reports/analyse/`` : ``taux_capture_mensuel.csv``, ``taux_capture_annuel.csv`` et
les graphiques PNG.
"""

from pathlib import Path

from ppa_pricer.analyse.capture import charger_horaire, taux_de_capture
from ppa_pricer.analyse.graphiques import produire_tous
from ppa_pricer.donnees.base import connexion

RACINE = Path(__file__).resolve().parents[1]
BASE = RACINE / "data" / "ppa.sqlite"
DOSSIER = RACINE / "reports" / "analyse"


def main() -> None:
    horaire = charger_horaire(connexion(BASE))
    mensuel = taux_de_capture(horaire, frequence="M")
    annuel = taux_de_capture(horaire, frequence="Y")

    DOSSIER.mkdir(parents=True, exist_ok=True)
    mensuel.to_csv(DOSSIER / "taux_capture_mensuel.csv", index=False, float_format="%.4f")
    annuel.to_csv(DOSSIER / "taux_capture_annuel.csv", index=False, float_format="%.4f")
    for chemin in produire_tous(horaire, mensuel, annuel, DOSSIER):
        print(chemin.relative_to(RACINE))

    colonnes = ["periode", "baseload_eur_mwh", "prix_capte_eur_mwh", "taux_capture", "part_solaire"]
    print(annuel[colonnes].to_string(index=False, float_format=lambda v: f"{v:.3f}"))


if __name__ == "__main__":
    main()
