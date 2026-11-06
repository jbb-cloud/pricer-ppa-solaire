"""Télécharge prix day-ahead, production solaire et consommation France (2015 → aujourd'hui),
les charge en base et les contrôle.

Usage : ``.venv/bin/python scripts/telecharger_donnees.py``
Écrit un rapport de contrôle par série dans ``reports/donnees/``. Avec ``--sans-telechargement``,
ne télécharge rien, ne touche pas à la base et régénère seulement les rapports.
"""

import sys
from pathlib import Path

import pandas as pd

from ppa_pricer.donnees.base import connexion, ecrire_serie, lire_serie
from ppa_pricer.donnees.controles import (
    ECART_CALAGE_MAX_H,
    FUSEAU_AFFICHAGE,
    PART_NUIT_MAX,
    controler_calage_solaire,
    controler_serie,
)
from ppa_pricer.donnees.energy_charts import (
    DEBUT_QUART_HEURE_PRODUCTION_UTC,
    DEBUT_QUART_HEURE_UTC,
    agreger_horaire,
    lire_prix_brut,
    lire_production_brut,
    telecharger_prix_annee,
    telecharger_production_annee,
)

RACINE = Path(__file__).resolve().parents[1]
DOSSIER_BRUT = RACINE / "data" / "raw" / "energy_charts"
BASE = RACINE / "data" / "ppa.sqlite"
DOSSIER_RAPPORTS = RACINE / "reports" / "donnees"
PREMIERE_ANNEE = 2015
ZONE = "FR"

SERIES = [
    ("Prix day-ahead", "prix_day_ahead", telecharger_prix_annee, lire_prix_brut, DEBUT_QUART_HEURE_UTC),
    (
        "Production solaire et consommation",
        "production_conso",
        telecharger_production_annee,
        lire_production_brut,
        DEBUT_QUART_HEURE_PRODUCTION_UTC,
    ),
]


def paris(ts: pd.Timestamp) -> str:
    return ts.tz_convert(FUSEAU_AFFICHAGE).strftime("%Y-%m-%d %H:%M %Z")


def section_calage(serie: pd.DataFrame) -> list[str]:
    """Section du rapport sur le calage physique du solaire : seuls les mois signalés sont listés."""
    calage = controler_calage_solaire(serie)
    suspects = calage[calage["calage_suspect"] | calage["nuit_suspecte"]]
    lignes = [
        "",
        "## Calage physique du solaire (par mois de Paris)",
        "",
        f"Alerte si l'heure moyenne de production s'écarte de plus de {ECART_CALAGE_MAX_H} h de la médiane du même "
        f"mois, ou si plus de {PART_NUIT_MAX:.1%} de l'énergie du mois est produite de 21 h à 03 h UTC. "
        "Le contrôle signale sans corriger (voir `docs/donnees.md`).",
        "",
        f"- Mois contrôlés : {len(calage)}",
        f"- Mois au calage suspect : {int(calage['calage_suspect'].sum())}",
        f"- Mois avec production de nuit : {int(calage['nuit_suspecte'].sum())}",
        "",
        "| Mois | Heure moyenne (UTC) | Référence (UTC) | Écart (h) | Part la nuit (%) | Alerte |",
        "|---|---|---|---|---|---|",
    ]
    for l in suspects.itertuples():
        alertes = [nom for nom, actif in (("calage", l.calage_suspect), ("nuit", l.nuit_suspecte)) if actif]
        lignes.append(
            f"| {l.periode} | {l.heure_moyenne_utc:.2f} | {l.reference_utc:.2f} | {l.ecart_h:+.2f} "
            f"| {l.part_nuit * 100:.2f} | {', '.join(alertes)} |"
        )
    return lignes


def rapport(titre: str, serie: pd.DataFrame, debut_quart_heure: pd.Timestamp) -> str:
    """Rapport de contrôle en Markdown : anomalies globales, puis détail par année."""
    c = controler_serie(serie, debut_quart_heure)
    colonnes = list(c["valeurs"])
    horaire = agreger_horaire(serie)

    lignes = [
        f"# Contrôle qualité — {titre} ({ZONE})",
        "",
        f"Source : Energy-Charts (Fraunhofer ISE), CC BY 4.0. Généré le "
        f"{pd.Timestamp.now(tz=FUSEAU_AFFICHAGE):%d/%m/%Y}.",
        "",
        f"- Période : {paris(c['debut_utc'])} → {paris(c['fin_utc'])}",
        f"- Passage au quart d'heure : {paris(debut_quart_heure)}",
        f"- Points : {c['n_points']}",
        f"- Doublons : {c['doublons']}",
        f"- Points mal alignés : {c['mal_alignes']}",
        f"- Trous (points absents de la grille) : {c['trous']}",
        f"- Jours au nombre d'heures anormal (changements d'heure) : {len(c['jours_heures_anormales'])}",
        "",
        "| Colonne | Valeurs manquantes | Min | Max | Valeurs négatives |",
        "|---|---|---|---|---|",
        *(
            f"| {col} | {v['manquants']} | {v['min']:.2f} | {v['max']:.2f} | {v['negatifs']} |"
            for col, v in c["valeurs"].items()
        ),
        "",
        "## Par année (UTC), après agrégation horaire",
        "",
        "Une heure est NaN si une de ses valeurs d'origine manque (règle décrite dans `docs/donnees.md`).",
        "",
        "| Année | Heures | " + " | ".join(f"{col} : heures NaN | {col} : moyenne" for col in colonnes) + " |",
        "|---|---|" + "---|---|" * len(colonnes),
    ]
    for annee, groupe in horaire.groupby(horaire["ts_utc"].dt.year):
        cellules = " | ".join(f"{groupe[col].isna().sum()} | {groupe[col].mean():.2f}" for col in colonnes)
        lignes.append(f"| {annee} | {len(groupe)} | {cellules} |")

    if "solaire_mw" in serie:
        lignes += section_calage(serie)
    if c["jours_heures_anormales"]:
        lignes += ["", "## Jours anormaux", ""]
        lignes += [f"- {j} : {n} heures" for j, n in c["jours_heures_anormales"].items()]
    if c["trous_liste"]:
        lignes += ["", "## Trous (heure de Paris)", ""]
        lignes += [f"- {paris(t)}" for t in c["trous_liste"][:50]]
        if c["trous"] > 50:
            lignes.append(f"- … et {c['trous'] - 50} autres")
    return "\n".join(lignes) + "\n"


def main() -> None:
    con = connexion(BASE)
    DOSSIER_RAPPORTS.mkdir(parents=True, exist_ok=True)
    annees = [] if "--sans-telechargement" in sys.argv else range(PREMIERE_ANNEE, pd.Timestamp.now(tz="UTC").year + 1)
    for titre, table, telecharger, lire, debut_quart_heure in SERIES:
        for annee in annees:
            n = ecrire_serie(con, table, lire(telecharger(annee, DOSSIER_BRUT)), zone=ZONE, source="energy-charts")
            print(f"{titre} {annee} : {n} points")
        texte = rapport(titre, lire_serie(con, table, zone=ZONE), debut_quart_heure)
        (DOSSIER_RAPPORTS / f"qualite_{table}_{ZONE}.md").write_text(texte)
        print(texte)


if __name__ == "__main__":
    main()
