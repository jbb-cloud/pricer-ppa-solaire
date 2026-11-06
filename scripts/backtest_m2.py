"""Backtest walk-forward du modèle M2, face à M1, à la V1 et aux références (`docs/stochastique.md`).

Usage : ``.venv/bin/python scripts/backtest_m2.py``
Écrit dans ``reports/backtest/m2/`` : ``rapport.md``, ``previsions.csv``, ``parametres.csv``.
Ne modifie ni la base ni les rapports précédents. L'éolien vient des fichiers bruts Energy-Charts.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ppa_pricer.analyse.capture import charger_horaire, taux_de_capture
from ppa_pricer.backtest.metriques import biais, couverture, diebold_mariano, mae, mae_ponderee, skill_score
from ppa_pricer.backtest.walk_forward import METHODES, backtest, taux_annuels
from ppa_pricer.donnees.base import connexion
from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE
from ppa_pricer.donnees.energy_charts import charger_eolien
from ppa_pricer.modele import m0, m1, m2

RACINE = Path(__file__).resolve().parents[1]
BASE = RACINE / "data" / "ppa.sqlite"
BRUTS = RACINE / "data" / "raw" / "energy_charts"
DOSSIER = RACINE / "reports" / "backtest" / "m2"
ANNEES_OFFICIELLES = list(range(2018, 2026))
ANNEE_A_PART = 2026
ANNEES_DIAGNOSTIC = [2019, 2025]
N_DIAGNOSTIC = 20
COUVERTURE_MIN, COUVERTURE_MAX = 0.85, 0.95
INTERVALLES = {"M2": "m2", "M2 avec H4 (sensibilité)": "m2_h4", "M2 sur 1 an (sensibilité)": "m2_1an", "M1": "m1"}
NOMS = {
    "tc_m2": "M2",
    "tc_m2_h4": "M2 avec H4 (sensibilité)",
    "tc_m2_1an": "M2 sur 1 an (sensibilité)",
    "tc_m1": "M1",
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
    lignes = ["| Méthode | Couverture | Largeur moyenne | Réalisé au-dessus | Réalisé en dessous | Bornes basses sous 0 |", "|---|---|---|---|---|---|"]
    for nom, cle in INTERVALLES.items():
        bas, haut = e[f"tc_{cle}_bas"], e[f"tc_{cle}_haut"]
        lignes.append(
            f"| {nom} | {pts(couverture(e['taux_capture'], bas, haut))} % | {pts((haut - bas).mean())} "
            f"| {int((e['taux_capture'] > haut).sum())} | {int((e['taux_capture'] < bas).sum())} | {int((bas < 0).sum())} |"
        )
    return lignes


def croissance_realisee(solaire: pd.Series, annee: int) -> float:
    """Croissance du solaire sur la partie connue de ``annee``, face à la même période de l'année précédente."""
    local = solaire.index.tz_convert(FUSEAU_AFFICHAGE)
    connue = local[local.year == annee].max()
    fin_avant = connue - pd.DateOffset(years=1)
    pendant = solaire[local.year == annee]
    avant = solaire[(local.year == annee - 1) & (local <= fin_avant)]
    return pendant.mean() / avant.mean() - 1


def main() -> None:
    horaire = charger_horaire(connexion(BASE)).merge(charger_eolien(BRUTS), on="ts_utc", how="left")
    mensuel = taux_de_capture(horaire, "M")
    annees = [*ANNEES_OFFICIELLES, ANNEE_A_PART]

    previsions, _ = backtest(mensuel, annees)
    morceaux, lignes_parametres, modeles_m2, modeles_m1 = [], [], {}, {}
    solaire = horaire.dropna(subset=["solaire_mw"]).set_index("ts_utc")["solaire_mw"]
    for annee in annees:
        p_m2, modele = m2.prevoir_m2(horaire, annee)
        p_h4, _ = m2.prevoir_m2(horaire, annee, regle_croissance="h4")
        p_1an, modele_1an = m2.prevoir_m2(horaire, annee, fenetre=1)
        p_m1, modele_m1 = m1.prevoir_m1(horaire, annee)
        combine = renommer(p_m2, "m2").merge(renommer(p_h4, "m2_h4"), on="mois").merge(renommer(p_1an, "m2_1an"), on="mois").merge(renommer(p_m1, "m1"), on="mois")
        morceaux.append(combine.assign(annee=annee))
        modeles_m2[annee], modeles_m1[annee] = modele, modele_m1
        lignes_parametres.append(
            {
                "annee": annee,
                "lambda": modele.poids_charge,
                "poids_rapide": modele.poids_rapide,
                "demi_vie_rapide_h": modele.demi_vie_rapide_h,
                "demi_vie_lente_h": modele.demi_vie_lente_h,
                "erreur_ajustement": modele.erreur_ajustement,
                "n_croissances": len(modele.croissances),
                "croissance_mediane": float(np.median(modele.croissances)),
                "croissance_h4": float(modele.croissances[-1]),
                "croissance_realisee": croissance_realisee(solaire, annee),
                "lambda_1an": modele_1an.poids_charge,
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
    e_m2 = officiel["tc_m2"] - officiel["taux_capture"]

    skill_r1 = skill_score(mae(e_m2), mae(officiel["r1_persistance"] - officiel["taux_capture"]))
    skill_v1 = skill_score(mae(e_m2), mae(officiel["modele_realiste"] - officiel["taux_capture"]))
    couvert = couverture(officiel["taux_capture"], officiel["tc_m2_bas"], officiel["tc_m2_haut"])
    atteint = skill_r1 > 0 and skill_v1 > 0 and COUVERTURE_MIN <= couvert <= COUVERTURE_MAX

    derniere = horaire.dropna()["ts_utc"].max().tz_convert(FUSEAU_AFFICHAGE)
    lignes = [
        "# Backtest du modèle M2",
        "",
        f"Généré le {pd.Timestamp.now(tz=FUSEAU_AFFICHAGE):%d/%m/%Y} ; données jusqu'au {derniere:%d/%m/%Y %H:%M}. "
        f"{m2.N_TRAJECTOIRES} trajectoires par année, graine {m2.GRAINE}. Protocole, définition et attentes : "
        "`docs/stochastique.md`. Erreurs en points de taux de capture (prévision − réalisé).",
        "",
        "## Verdict (2018–2025, M2 sur 2 ans, croissance tirée)",
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
        "Statistique négative : M2 se trompe moins que l'autre méthode.",
        "",
        "| Comparaison | Écart moyen de perte | Statistique | p-value |",
        "|---|---|---|---|",
    ]
    for autre in ["r1_persistance", "modele_realiste", "tc_m1"]:
        dm = diebold_mariano(e_m2, officiel[autre] - officiel["taux_capture"])
        lignes.append(f"| M2 vs {NOMS[autre]} | {pts(dm.ecart_moyen)} | {signe(dm.statistique)} | {nb(dm.p_valeur, 3)} |")

    lignes += ["", "## Intervalle à 90 % du taux de capture mensuel, 2018–2025", "", *tableau_intervalles(officiel), "",
               "| Année | MAE M2 | Biais M2 | MAE M2 H4 | MAE M2 sur 1 an | MAE M1 | MAE V1 | MAE R1 | Couverture M2 | Largeur M2 | Couverture M1 |",
               "|---|---|---|---|---|---|---|---|---|---|---|"]
    for annee, g in officiel.groupby("annee"):
        lignes.append(
            f"| {annee} | {pts(mae(g['tc_m2'] - g['taux_capture']))} | {pts(biais(g['tc_m2'] - g['taux_capture']))} "
            f"| {pts(mae(g['tc_m2_h4'] - g['taux_capture']))} | {pts(mae(g['tc_m2_1an'] - g['taux_capture']))} "
            f"| {pts(mae(g['tc_m1'] - g['taux_capture']))} | {pts(mae(g['modele_realiste'] - g['taux_capture']))} "
            f"| {pts(mae(g['r1_persistance'] - g['taux_capture']))} | {pts(couverture(g['taux_capture'], g['tc_m2_bas'], g['tc_m2_haut']))} % "
            f"| {pts((g['tc_m2_haut'] - g['tc_m2_bas']).mean())} | {pts(couverture(g['taux_capture'], g['tc_m1_bas'], g['tc_m1_haut']))} % |"
        )

    annuels_m2 = taux_annuels(officiel.assign(modele_conditionnel=officiel["tc_m2"]))
    annuels_m1 = taux_annuels(officiel.assign(modele_conditionnel=officiel["tc_m1"])).set_index("annee")
    lignes += ["", "## Taux de capture annuel (baseload et volumes réalisés)", "",
               "| Année | Réalisé | Erreur M2 | Erreur M1 | Erreur V1 | Erreur R1 |", "|---|---|---|---|---|---|"]
    for _, a in annuels_m2.iterrows():
        lignes.append(
            f"| {int(a['annee'])} | {pts(a['taux_capture'])} | {pts(a['modele_conditionnel'] - a['taux_capture'])} "
            f"| {pts(annuels_m1.loc[a['annee'], 'modele_conditionnel'] - a['taux_capture'])} "
            f"| {pts(a['modele_realiste'] - a['taux_capture'])} | {pts(a['r1_persistance'] - a['taux_capture'])} |"
        )

    lignes += ["", f"## {ANNEE_A_PART}, rapporté à part ({len(a_part)} mois valides)", "", *tableau_precision(a_part), "", *tableau_intervalles(a_part), "",
               "| Mois | Réalisé | M2 | Intervalle M2 | M1 | V1 | R1 |", "|---|---|---|---|---|---|---|"]
    for _, r in a_part.iterrows():
        lignes.append(
            f"| {r['periode']} | {pts(r['taux_capture'])} | {pts(r['tc_m2'])} | {pts(r['tc_m2_bas'])} à {pts(r['tc_m2_haut'])} "
            f"| {pts(r['tc_m1'])} | {pts(r['modele_realiste'])} | {pts(r['r1_persistance'])} |"
        )

    lignes += ["", "## Paramètres estimés", "", "Fenêtre de 2 ans. Croissance réalisée : donnée pour comparer, jamais utilisée par le modèle.", "",
               "| Année prévue | λ | Poids rapide | Demi-vie rapide (h) | Demi-vie lente (h) | Croissances connues | Médiane | H4 | Réalisée | λ sur 1 an |",
               "|---|---|---|---|---|---|---|---|---|---|"]
    for _, p in parametres.iterrows():
        lignes.append(
            f"| {int(p['annee'])} | {nb(p['lambda'])} | {nb(p['poids_rapide'])} | {nb(p['demi_vie_rapide_h'], 1)} | {nb(p['demi_vie_lente_h'], 1)} "
            f"| {int(p['n_croissances'])} | {pts(p['croissance_mediane'])} % | {pts(p['croissance_h4'])} % | {pts(p['croissance_realisee'])} % | {nb(p['lambda_1an'])} |"
        )

    lignes += ["", "## Diagnostics : simulations et réalité", "",
               f"Moyenne sur {N_DIAGNOSTIC} trajectoires, face à l'année réelle. Prix en part du baseload de l'année.", ""]
    for annee in ANNEES_DIAGNOSTIC:
        ts = m0.grille_annee(annee)
        y_m2, _ = m2.simuler_m2(modeles_m2[annee], ts, N_DIAGNOSTIC, np.random.default_rng([m2.GRAINE, annee, 1]))
        y_m1 = m1.simuler_prix_normalises(modeles_m1[annee], ts, N_DIAGNOSTIC, np.random.default_rng([m2.GRAINE, annee, 1]))
        simules = {nom: pd.DataFrame([m0.faits_stylises(pd.Series(y[:, i], index=ts)) for i in range(N_DIAGNOSTIC)]).mean() for nom, y in (("M2", y_m2), ("M1", y_m1))}
        reels = m0.faits_stylises(m0.prix_normalises(horaire, [annee]))
        lignes += [f"### {annee}", "", "| Propriété | M2 | M1 | Réel |", "|---|---|---|---|"]
        lignes += [f"| {nom} | {nb(simules['M2'][cle])} | {nb(simules['M1'][cle])} | {nb(reels[cle])} |" for cle, nom in FAITS.items()]
        lignes.append("")

    texte = "\n".join(lignes)
    (DOSSIER / "rapport.md").write_text(texte)
    print(texte)


if __name__ == "__main__":
    main()
