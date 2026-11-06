"""Backtest walk-forward du modèle M0 (protocole de `docs/stochastique.md`).

Usage : ``.venv/bin/python scripts/backtest_m0.py``
Écrit dans ``reports/backtest/m0/`` : ``rapport.md``, ``previsions.csv``, ``parametres.csv``.
Ne modifie ni la base ni le rapport de la V1.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ppa_pricer.analyse.capture import charger_horaire, taux_de_capture
from ppa_pricer.backtest.metriques import biais, couverture, diebold_mariano, mae, mae_ponderee, skill_score
from ppa_pricer.backtest.walk_forward import METHODES, backtest, echantillon_commun, taux_annuels
from ppa_pricer.donnees.base import connexion
from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE
from ppa_pricer.modele.m0 import GRAINE, N_TRAJECTOIRES, calibrer_m0, faits_stylises, grille_annee, prevoir_m0, prix_normalises, simuler_prix_normalises

RACINE = Path(__file__).resolve().parents[1]
BASE = RACINE / "data" / "ppa.sqlite"
DOSSIER = RACINE / "reports" / "backtest" / "m0"
ANNEES_OFFICIELLES = list(range(2018, 2026))
ANNEE_A_PART = 2026
ANNEES_DIAGNOSTIC = [2019, 2025]
N_DIAGNOSTIC = 20
COLONNES_M0 = ["tc_m0", "tc_m0_bas", "tc_m0_haut"]
NOMS = {
    "tc_m0": "M0",
    "modele_realiste": "Modèle V1, réaliste",
    "r1_persistance": "R1 persistance",
    "r2_climatologie": "R2 climatologie",
}


def pts(x: float) -> str:
    """Valeur en points de taux de capture (0,05 → « 5,0 »)."""
    return "n.d." if pd.isna(x) else f"{x * 100:.1f}".replace(".", ",")


def nb(x: float, decimales: int = 2) -> str:
    return "n.d." if pd.isna(x) else f"{x:.{decimales}f}".replace(".", ",")


def signe(x: float) -> str:
    return "n.d." if pd.isna(x) else f"{x:+.2f}".replace(".", ",")


def tableau_precision(e: pd.DataFrame) -> list[str]:
    erreurs = {m: e[m] - e["taux_capture"] for m in NOMS}
    maes = {m: mae(erreurs[m]) for m in NOMS}
    lignes = ["| Méthode | MAE | MAE pondérée | Biais | Skill vs R1 | Skill vs V1 |", "|---|---|---|---|---|---|"]
    for m in NOMS:
        lignes.append(
            f"| {NOMS[m]} | {pts(maes[m])} | {pts(mae_ponderee(erreurs[m], e['energie_solaire_mwh']))} | {pts(biais(erreurs[m]))} "
            f"| {signe(skill_score(maes[m], maes['r1_persistance']))} | {signe(skill_score(maes[m], maes['modele_realiste']))} |"
        )
    return lignes


def tableau_intervalle(e: pd.DataFrame) -> list[str]:
    dessus, dessous = e["taux_capture"] > e["tc_m0_haut"], e["taux_capture"] < e["tc_m0_bas"]
    return [
        f"Couverture : **{pts(couverture(e['taux_capture'], e['tc_m0_bas'], e['tc_m0_haut']))} %**, pour une cible de 85 à 95 %. "
        f"Largeur moyenne : {pts((e['tc_m0_haut'] - e['tc_m0_bas']).mean())} points. Réalisé au-dessus de l'intervalle : "
        f"{int(dessus.sum())} mois ; en dessous : {int(dessous.sum())} mois, sur {len(e)}.",
    ]


def main() -> None:
    horaire = charger_horaire(connexion(BASE))
    mensuel = taux_de_capture(horaire, "M")
    annees = [*ANNEES_OFFICIELLES, ANNEE_A_PART]

    v1, _ = backtest(mensuel, annees)
    morceaux, lignes_parametres, modeles = [], [], {}
    for annee in annees:
        prevision, p = prevoir_m0(horaire, annee)
        morceaux.append(prevision.assign(annee=annee))
        modeles[annee] = p
        lignes_parametres.append(
            {
                "annee": annee,
                "phi": p.phi,
                "demi_vie_h": p.demi_vie_h,
                "sigma_innovation": p.sigma_innovation,
                "sigma_stationnaire": p.sigma_stationnaire,
                "sigma_ou": p.sigma_ou,
            }
        )
    previsions = v1.merge(pd.concat(morceaux, ignore_index=True), on=["annee", "mois"], validate="one_to_one")
    parametres = pd.DataFrame(lignes_parametres)

    DOSSIER.mkdir(parents=True, exist_ok=True)
    previsions.to_csv(DOSSIER / "previsions.csv", index=False, float_format="%.5f")
    parametres.to_csv(DOSSIER / "parametres.csv", index=False, float_format="%.5f")

    colonnes = ["taux_capture", *METHODES, *COLONNES_M0]
    officiel = previsions[previsions["annee"].isin(ANNEES_OFFICIELLES)].dropna(subset=colonnes).sort_values("periode", ignore_index=True)
    a_part = previsions[previsions["annee"] == ANNEE_A_PART].dropna(subset=colonnes).sort_values("periode", ignore_index=True)
    e_m0 = officiel["tc_m0"] - officiel["taux_capture"]

    derniere = horaire.dropna()["ts_utc"].max().tz_convert(FUSEAU_AFFICHAGE)
    lignes = [
        "# Backtest du modèle M0",
        "",
        f"Généré le {pd.Timestamp.now(tz=FUSEAU_AFFICHAGE):%d/%m/%Y} ; données jusqu'au {derniere:%d/%m/%Y %H:%M}. "
        f"{N_TRAJECTOIRES} trajectoires par année, graine {GRAINE}. Protocole et attentes : `docs/stochastique.md`. "
        "M0 est une référence, **sans verdict**. Erreurs en points de taux de capture (prévision − réalisé).",
        "",
        f"## Précision 2018–2025 ({len(officiel)} mois)",
        "",
        *tableau_precision(officiel),
        "",
        "## Diebold-Mariano (perte absolue, Newey-West 11 retards, Student n−1)",
        "",
        "Statistique négative : M0 se trompe moins que l'autre méthode.",
        "",
        "| Comparaison | Écart moyen de perte | Statistique | p-value |",
        "|---|---|---|---|",
    ]
    for autre in ["r1_persistance", "modele_realiste"]:
        dm = diebold_mariano(e_m0, officiel[autre] - officiel["taux_capture"])
        lignes.append(f"| M0 vs {NOMS[autre]} | {pts(dm.ecart_moyen)} | {signe(dm.statistique)} | {nb(dm.p_valeur, 3)} |")

    lignes += ["", "## Intervalle à 90 % du taux de capture mensuel", "", *tableau_intervalle(officiel), "",
               "| Année | MAE M0 | MAE V1 | MAE R1 | Couverture | Largeur moyenne |", "|---|---|---|---|---|---|"]
    for annee, g in officiel.groupby("annee"):
        lignes.append(
            f"| {annee} | {pts(mae(g['tc_m0'] - g['taux_capture']))} | {pts(mae(g['modele_realiste'] - g['taux_capture']))} "
            f"| {pts(mae(g['r1_persistance'] - g['taux_capture']))} | {pts(couverture(g['taux_capture'], g['tc_m0_bas'], g['tc_m0_haut']))} % "
            f"| {pts((g['tc_m0_haut'] - g['tc_m0_bas']).mean())} |"
        )

    annuels = taux_annuels(officiel.assign(modele_conditionnel=officiel["tc_m0"]))
    lignes += ["", "## Taux de capture annuel (baseload et volumes réalisés)", "",
               "| Année | Réalisé | Erreur M0 | Erreur V1 | Erreur R1 |", "|---|---|---|---|---|"]
    for _, a in annuels.iterrows():
        lignes.append(
            f"| {int(a['annee'])} | {pts(a['taux_capture'])} | {pts(a['modele_conditionnel'] - a['taux_capture'])} "
            f"| {pts(a['modele_realiste'] - a['taux_capture'])} | {pts(a['r1_persistance'] - a['taux_capture'])} |"
        )

    lignes += ["", f"## {ANNEE_A_PART}, rapporté à part ({len(a_part)} mois valides)", "", *tableau_precision(a_part), "", *tableau_intervalle(a_part), "",
               "| Mois | Réalisé | M0 | Intervalle M0 | V1 | R1 |", "|---|---|---|---|---|---|"]
    for _, r in a_part.iterrows():
        lignes.append(
            f"| {r['periode']} | {pts(r['taux_capture'])} | {pts(r['tc_m0'])} | {pts(r['tc_m0_bas'])} à {pts(r['tc_m0_haut'])} "
            f"| {pts(r['modele_realiste'])} | {pts(r['r1_persistance'])} |"
        )

    lignes += ["", "## Paramètres estimés", "", "Écarts-types en part du baseload annuel.", "",
               "| Année prévue | φ | Demi-vie (h) | σ des chocs horaires | σ de long terme |", "|---|---|---|---|---|"]
    for _, p in parametres.iterrows():
        lignes.append(f"| {int(p['annee'])} | {nb(p['phi'], 3)} | {nb(p['demi_vie_h'], 1)} | {nb(p['sigma_innovation'], 3)} | {nb(p['sigma_stationnaire'], 3)} |")

    lignes += ["", "## Diagnostics : simulations et réalité", "",
               f"Moyenne sur {N_DIAGNOSTIC} trajectoires, face à l'année réelle. Prix en part du baseload de l'année.", ""]
    noms_faits = {
        "autocorr_1h": "Autocorrélation à 1 h",
        "autocorr_24h": "Autocorrélation à 24 h",
        "autocorr_48h": "Autocorrélation à 48 h",
        "autocorr_168h": "Autocorrélation à 168 h",
        "kurtosis": "Kurtosis du résidu",
        "part_negative": "Part d'heures négatives",
        "mediane_midi": "Prix médian à midi, avril–août",
        "q05": "Quantile 5 %",
        "q95": "Quantile 95 %",
    }
    for annee in ANNEES_DIAGNOSTIC:
        ts = grille_annee(annee)
        y = simuler_prix_normalises(modeles[annee], ts, N_DIAGNOSTIC, np.random.default_rng([GRAINE, annee, 1]))
        simules = pd.DataFrame([faits_stylises(pd.Series(y[:, i], index=ts)) for i in range(N_DIAGNOSTIC)]).mean()
        reels = faits_stylises(prix_normalises(horaire, [annee]))
        lignes += [f"### {annee}", "", "| Propriété | Simulé | Réel |", "|---|---|---|"]
        lignes += [f"| {nom} | {nb(simules[cle])} | {nb(reels[cle])} |" for cle, nom in noms_faits.items()]
        lignes.append("")

    texte = "\n".join(lignes)
    (DOSSIER / "rapport.md").write_text(texte)
    print(texte)


if __name__ == "__main__":
    main()
