"""Backtest walk-forward du modèle M1, face à M0, à la V1 et aux références (`docs/stochastique.md`).

Usage : ``.venv/bin/python scripts/backtest_m1.py``
Écrit dans ``reports/backtest/m1/`` : ``rapport.md``, ``previsions.csv``, ``parametres.csv``.
Ne modifie ni la base ni les rapports précédents.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ppa_pricer.analyse.capture import charger_horaire, taux_de_capture
from ppa_pricer.backtest.metriques import biais, couverture, diebold_mariano, mae, mae_ponderee, skill_score
from ppa_pricer.backtest.walk_forward import METHODES, backtest, taux_annuels
from ppa_pricer.donnees.base import connexion
from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE
from ppa_pricer.modele import m0, m1

RACINE = Path(__file__).resolve().parents[1]
BASE = RACINE / "data" / "ppa.sqlite"
DOSSIER = RACINE / "reports" / "backtest" / "m1"
ANNEES_OFFICIELLES = list(range(2018, 2026))
ANNEE_A_PART = 2026
ANNEES_DIAGNOSTIC = [2019, 2025]
N_DIAGNOSTIC = 20
COUVERTURE_MIN, COUVERTURE_MAX = 0.85, 0.95
INTERVALLES = {"M1": "m1", "M1 sur 1 an (sensibilité)": "m1_1an", "M0": "m0"}
NOMS = {
    "tc_m1": "M1",
    "tc_m1_1an": "M1 sur 1 an (sensibilité)",
    "tc_m0": "M0",
    "modele_realiste": "Modèle V1, réaliste",
    "r1_persistance": "R1 persistance",
    "r2_climatologie": "R2 climatologie",
}
FAITS = {
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


def pts(x: float) -> str:
    """Valeur en points de taux de capture (0,05 → « 5,0 »)."""
    return "n.d." if pd.isna(x) else f"{x * 100:.1f}".replace(".", ",")


def nb(x: float, decimales: int = 2) -> str:
    return "n.d." if pd.isna(x) else f"{x:.{decimales}f}".replace(".", ",")


def signe(x: float) -> str:
    return "n.d." if pd.isna(x) else f"{x:+.2f}".replace(".", ",")


def renommer(prevision: pd.DataFrame, nom: str) -> pd.DataFrame:
    return prevision.rename(columns={"tc": f"tc_{nom}", "tc_bas": f"tc_{nom}_bas", "tc_haut": f"tc_{nom}_haut"})


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


def tableau_intervalles(e: pd.DataFrame) -> list[str]:
    lignes = ["| Méthode | Couverture | Largeur moyenne | Réalisé au-dessus | Réalisé en dessous |", "|---|---|---|---|---|"]
    for nom, cle in INTERVALLES.items():
        bas, haut = e[f"tc_{cle}_bas"], e[f"tc_{cle}_haut"]
        lignes.append(
            f"| {nom} | {pts(couverture(e['taux_capture'], bas, haut))} % | {pts((haut - bas).mean())} "
            f"| {int((e['taux_capture'] > haut).sum())} | {int((e['taux_capture'] < bas).sum())} |"
        )
    return lignes


def main() -> None:
    horaire = charger_horaire(connexion(BASE))
    mensuel = taux_de_capture(horaire, "M")
    annees = [*ANNEES_OFFICIELLES, ANNEE_A_PART]

    previsions, _ = backtest(mensuel, annees)
    morceaux, lignes_parametres, modeles_m1, modeles_m0 = [], [], {}, {}
    for annee in annees:
        p_m1, modele = m1.prevoir_m1(horaire, annee)
        p_1an, modele_1an = m1.prevoir_m1(horaire, annee, fenetre=1)
        p_m0, modele_m0 = m0.prevoir_m0(horaire, annee)
        p_m0 = p_m0.rename(columns={"tc_m0": "tc", "tc_m0_bas": "tc_bas", "tc_m0_haut": "tc_haut"})
        combine = renommer(p_m1, "m1").merge(renommer(p_1an, "m1_1an"), on="mois").merge(renommer(p_m0, "m0"), on="mois")
        morceaux.append(combine.assign(annee=annee))
        modeles_m1[annee], modeles_m0[annee] = modele, modele_m0
        lignes_parametres.append(
            {
                "annee": annee,
                "poids_rapide": modele.poids_rapide,
                "demi_vie_rapide_h": modele.demi_vie_rapide_h,
                "demi_vie_lente_h": modele.demi_vie_lente_h,
                "erreur_ajustement": modele.erreur_ajustement,
                "demi_vie_m0_h": modele_m0.demi_vie_h,
                "poids_rapide_1an": modele_1an.poids_rapide,
                "demi_vie_lente_1an_h": modele_1an.demi_vie_lente_h,
            }
        )
    previsions = previsions.merge(pd.concat(morceaux, ignore_index=True), on=["annee", "mois"], validate="one_to_one")
    parametres = pd.DataFrame(lignes_parametres)

    DOSSIER.mkdir(parents=True, exist_ok=True)
    previsions.to_csv(DOSSIER / "previsions.csv", index=False, float_format="%.5f")
    parametres.to_csv(DOSSIER / "parametres.csv", index=False, float_format="%.5f")

    colonnes = ["taux_capture", *METHODES, *[f"tc_{c}{s}" for c in INTERVALLES.values() for s in ("", "_bas", "_haut")]]
    officiel = previsions[previsions["annee"].isin(ANNEES_OFFICIELLES)].dropna(subset=colonnes).sort_values("periode", ignore_index=True)
    a_part = previsions[previsions["annee"] == ANNEE_A_PART].dropna(subset=colonnes).sort_values("periode", ignore_index=True)
    e_m1 = officiel["tc_m1"] - officiel["taux_capture"]

    skill_r1 = skill_score(mae(e_m1), mae(officiel["r1_persistance"] - officiel["taux_capture"]))
    skill_v1 = skill_score(mae(e_m1), mae(officiel["modele_realiste"] - officiel["taux_capture"]))
    couvert = couverture(officiel["taux_capture"], officiel["tc_m1_bas"], officiel["tc_m1_haut"])
    atteint = skill_r1 > 0 and skill_v1 > 0 and COUVERTURE_MIN <= couvert <= COUVERTURE_MAX

    derniere = horaire.dropna()["ts_utc"].max().tz_convert(FUSEAU_AFFICHAGE)
    lignes = [
        "# Backtest du modèle M1",
        "",
        f"Généré le {pd.Timestamp.now(tz=FUSEAU_AFFICHAGE):%d/%m/%Y} ; données jusqu'au {derniere:%d/%m/%Y %H:%M}. "
        f"{m1.N_TRAJECTOIRES} trajectoires par année, graine {m1.GRAINE}. Protocole, définition et attentes : "
        "`docs/stochastique.md`. Erreurs en points de taux de capture (prévision − réalisé).",
        "",
        "## Verdict (2018–2025, M1 sur 2 ans)",
        "",
        f"Critère : skill > 0 contre R1 **et** contre la V1, et couverture entre 85 et 95 %. Skill vs R1 = {signe(skill_r1)}, "
        f"skill vs V1 = {signe(skill_v1)}, couverture = {pts(couvert)} % → **critère {'ATTEINT' if atteint else 'NON ATTEINT'}**.",
        "",
        "Aucun mois publié après le 29/10/2026 n'est encore complet : le test sur données réellement inconnues reste à faire.",
        "",
        f"## Précision 2018–2025 ({len(officiel)} mois)",
        "",
        *tableau_precision(officiel),
        "",
        "## Diebold-Mariano (perte absolue, Newey-West 11 retards, Student n−1)",
        "",
        "Statistique négative : M1 se trompe moins que l'autre méthode.",
        "",
        "| Comparaison | Écart moyen de perte | Statistique | p-value |",
        "|---|---|---|---|",
    ]
    for autre in ["r1_persistance", "modele_realiste", "tc_m0"]:
        dm = diebold_mariano(e_m1, officiel[autre] - officiel["taux_capture"])
        lignes.append(f"| M1 vs {NOMS[autre]} | {pts(dm.ecart_moyen)} | {signe(dm.statistique)} | {nb(dm.p_valeur, 3)} |")

    lignes += ["", "## Intervalle à 90 % du taux de capture mensuel, 2018–2025", "", *tableau_intervalles(officiel), "",
               "| Année | MAE M1 | MAE M1 sur 1 an | MAE M0 | MAE V1 | MAE R1 | Couverture M1 | Couverture M1 sur 1 an | Couverture M0 |",
               "|---|---|---|---|---|---|---|---|---|"]
    for annee, g in officiel.groupby("annee"):
        lignes.append(
            f"| {annee} | {pts(mae(g['tc_m1'] - g['taux_capture']))} | {pts(mae(g['tc_m1_1an'] - g['taux_capture']))} "
            f"| {pts(mae(g['tc_m0'] - g['taux_capture']))} | {pts(mae(g['modele_realiste'] - g['taux_capture']))} "
            f"| {pts(mae(g['r1_persistance'] - g['taux_capture']))} | {pts(couverture(g['taux_capture'], g['tc_m1_bas'], g['tc_m1_haut']))} % "
            f"| {pts(couverture(g['taux_capture'], g['tc_m1_1an_bas'], g['tc_m1_1an_haut']))} % "
            f"| {pts(couverture(g['taux_capture'], g['tc_m0_bas'], g['tc_m0_haut']))} % |"
        )

    annuels_m1 = taux_annuels(officiel.assign(modele_conditionnel=officiel["tc_m1"]))
    annuels_m0 = taux_annuels(officiel.assign(modele_conditionnel=officiel["tc_m0"])).set_index("annee")
    lignes += ["", "## Taux de capture annuel (baseload et volumes réalisés)", "",
               "| Année | Réalisé | Erreur M1 | Erreur M0 | Erreur V1 | Erreur R1 |", "|---|---|---|---|---|---|"]
    for _, a in annuels_m1.iterrows():
        lignes.append(
            f"| {int(a['annee'])} | {pts(a['taux_capture'])} | {pts(a['modele_conditionnel'] - a['taux_capture'])} "
            f"| {pts(annuels_m0.loc[a['annee'], 'modele_conditionnel'] - a['taux_capture'])} "
            f"| {pts(a['modele_realiste'] - a['taux_capture'])} | {pts(a['r1_persistance'] - a['taux_capture'])} |"
        )

    lignes += ["", f"## {ANNEE_A_PART}, rapporté à part ({len(a_part)} mois valides)", "", *tableau_precision(a_part), "", *tableau_intervalles(a_part), "",
               "| Mois | Réalisé | M1 | Intervalle M1 | M0 | V1 | R1 |", "|---|---|---|---|---|---|---|"]
    for _, r in a_part.iterrows():
        lignes.append(
            f"| {r['periode']} | {pts(r['taux_capture'])} | {pts(r['tc_m1'])} | {pts(r['tc_m1_bas'])} à {pts(r['tc_m1_haut'])} "
            f"| {pts(r['tc_m0'])} | {pts(r['modele_realiste'])} | {pts(r['r1_persistance'])} |"
        )

    lignes += ["", "## Paramètres estimés", "", "Fenêtre de 2 ans. La dernière colonne rappelle la demi-vie unique de M0.", "",
               "| Année prévue | Poids rapide | Demi-vie rapide (h) | Demi-vie lente (h) | Erreur d'ajustement | Demi-vie M0 (h) |", "|---|---|---|---|---|---|"]
    for _, p in parametres.iterrows():
        lignes.append(
            f"| {int(p['annee'])} | {nb(p['poids_rapide'])} | {nb(p['demi_vie_rapide_h'], 1)} | {nb(p['demi_vie_lente_h'], 1)} "
            f"| {nb(p['erreur_ajustement'], 3)} | {nb(p['demi_vie_m0_h'], 1)} |"
        )

    lignes += ["", "## Diagnostics : simulations et réalité", "",
               f"Moyenne sur {N_DIAGNOSTIC} trajectoires, face à l'année réelle. Prix en part du baseload de l'année.", ""]
    for annee in ANNEES_DIAGNOSTIC:
        ts = m0.grille_annee(annee)
        simules = {}
        for nom, module, modele in [("M1", m1, modeles_m1[annee]), ("M0", m0, modeles_m0[annee])]:
            y = module.simuler_prix_normalises(modele, ts, N_DIAGNOSTIC, np.random.default_rng([m1.GRAINE, annee, 1]))
            simules[nom] = pd.DataFrame([m0.faits_stylises(pd.Series(y[:, i], index=ts)) for i in range(N_DIAGNOSTIC)]).mean()
        reels = m0.faits_stylises(m0.prix_normalises(horaire, [annee]))
        lignes += [f"### {annee}", "", "| Propriété | M1 | M0 | Réel |", "|---|---|---|---|"]
        lignes += [f"| {nom} | {nb(simules['M1'][cle])} | {nb(simules['M0'][cle])} | {nb(reels[cle])} |" for cle, nom in FAITS.items()]
        lignes.append("")

    texte = "\n".join(lignes)
    (DOSSIER / "rapport.md").write_text(texte)
    print(texte)


if __name__ == "__main__":
    main()
