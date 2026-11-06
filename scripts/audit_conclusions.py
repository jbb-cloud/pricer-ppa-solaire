"""Audit, bloc B : les conclusions tiennent-elles avec d'autres graines, sans une année, et avec un autre nombre de retards ?

Usage : ``.venv/bin/python scripts/audit_conclusions.py``, après ``scripts/backtest_m2.py``. Écrit ``reports/audit/conclusions.md``.
Ne modifie ni la base ni les autres rapports. Les graines sont fixées à l'avance : 1 à 9, plus la graine officielle.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ppa_pricer.analyse.capture import charger_horaire, taux_de_capture
from ppa_pricer.backtest.metriques import couverture, diebold_mariano, mae
from ppa_pricer.backtest.robustesse import bootstrap_skill, skill_global, skill_sans_chaque_annee
from ppa_pricer.donnees.base import connexion
from ppa_pricer.donnees.energy_charts import charger_eolien
from ppa_pricer.donnees.pvgis import MONTPELLIER, lire_profil
from ppa_pricer.modele import m1, m2
from ppa_pricer.modele.m0 import GRAINE, N_TRAJECTOIRES
from ppa_pricer.pricing.monte_carlo import calibrer_livraison, flux_contrats, mesures_risque, nom_plancher, simuler_livraison, taux_capture_annuel, tirer_baseload, volumes_par_annee, CONTRAT_PAP, CONTRAT_RUBAN

RACINE = Path(__file__).resolve().parents[1]
BASE = RACINE / "data" / "ppa.sqlite"
BRUTS = RACINE / "data" / "raw" / "energy_charts"
PROFIL = RACINE / "data" / "raw" / "pvgis" / f"profil_{MONTPELLIER.nom}.json"
PREVISIONS = RACINE / "reports" / "backtest" / "m2" / "previsions.csv"
SORTIE = RACINE / "reports" / "audit" / "conclusions.md"
ANNEES = list(range(2018, 2026))
GRAINES = [GRAINE, *range(1, 10)]
N_BOOTSTRAP = 10_000
RETARDS = [5, 11, 17]
COUPLES = [("modele_realiste", "r1_persistance", "V1 contre R1"), ("modele_realiste", "r2_climatologie", "V1 contre R2"), ("tc_m2", "r1_persistance", "M2 contre R1"), ("tc_m2", "modele_realiste", "M2 contre V1"), ("tc_m2", "tc_m1", "M2 contre M1")]


def nb(x: float, d: int = 2) -> str:
    return f"{x:+.{d}f}".replace(".", ",").replace("-", "−")


def pt(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}".replace(".", ",")


def eur(x: float) -> str:
    return f"{round(x, -2):,.0f}".replace(",", " ")


def main() -> None:
    p = pd.read_csv(PREVISIONS)
    officiel = p[p["annee"].isin(ANNEES)].dropna(subset=["taux_capture", "modele_realiste", "r1_persistance", "r2_climatologie", "tc_m2", "tc_m1"])
    horaire = charger_horaire(connexion(BASE)).merge(charger_eolien(BRUTS), on="ts_utc", how="left")

    lignes = ["# Audit, bloc B : robustesse des conclusions", "", f"{len(officiel)} mois, 2018–2025. Plan et seuils : `docs/audit.md`.", ""]

    # B1 : graines.
    lignes += ["## B1. Graines", "", f"{len(GRAINES)} graines, {N_TRAJECTOIRES} trajectoires. Seuil : verdict et classement inchangés.", "",
               "| Modèle | Graine | MAE | Biais | Skill vs R1 | Skill vs V1 | Couverture |", "|---|---|---|---|---|---|---|"]
    mae_r1, mae_v1 = mae(officiel["r1_persistance"] - officiel["taux_capture"]), mae(officiel["modele_realiste"] - officiel["taux_capture"])
    resume = {}
    for nom, prevoir in (("M2", m2.prevoir_m2), ("M1", m1.prevoir_m1)):
        lignes_modele = []
        for g in GRAINES:
            morceaux = [prevoir(horaire, a, graine=g)[0].assign(annee=a) for a in ANNEES]
            t = officiel[["annee", "mois", "taux_capture"]].merge(pd.concat(morceaux), on=["annee", "mois"])
            e = t["tc"] - t["taux_capture"]
            lignes_modele.append({"graine": g, "mae": mae(e), "biais": e.mean(), "skill_r1": 1 - mae(e) / mae_r1, "skill_v1": 1 - mae(e) / mae_v1, "couverture": couverture(t["taux_capture"], t["tc_bas"], t["tc_haut"])})
        r = pd.DataFrame(lignes_modele)
        resume[nom] = r
        for _, x in r.iterrows():
            lignes.append(f"| {nom} | {int(x['graine'])} | {pt(x['mae'], 2)} | {pt(x['biais'], 2)} | {nb(x['skill_r1'], 3)} | {nb(x['skill_v1'], 3)} | {pt(x['couverture'])} % |")
    lignes += ["", "| Modèle | MAE, étendue | Skill vs R1, étendue | Skill vs V1, étendue | Graines avec skill vs V1 > 0 | Couverture, étendue | Critère atteint |", "|---|---|---|---|---|---|---|"]
    for nom, r in resume.items():
        atteint = ((r["skill_r1"] > 0) & (r["skill_v1"] > 0) & (r["couverture"] >= 0.85) & (r["couverture"] <= 0.95)).sum()
        lignes.append(f"| {nom} | {pt(r['mae'].min(), 2)} à {pt(r['mae'].max(), 2)} | {nb(r['skill_r1'].min(), 3)} à {nb(r['skill_r1'].max(), 3)} | {nb(r['skill_v1'].min(), 3)} à {nb(r['skill_v1'].max(), 3)} | {int((r['skill_v1'] > 0).sum())} sur {len(r)} | {pt(r['couverture'].min())} à {pt(r['couverture'].max())} % | {int(atteint)} sur {len(r)} |")

    # Monte-Carlo sur les mêmes graines.
    mensuel = taux_de_capture(horaire, "M")
    pl = calibrer_livraison(horaire, mensuel, 2027)
    volumes = volumes_par_annee(lire_profil(PROFIL))
    mesures = []
    for g in GRAINES:
        rng = np.random.default_rng([g, 2027])
        _, y, q = simuler_livraison(pl, volumes, N_TRAJECTOIRES, rng)
        tc = taux_capture_annuel(y, q)
        f = flux_contrats(y, q, tirer_baseload(tc, rng.standard_normal(N_TRAJECTOIRES), 61.0))
        mesures.append({"k": f.prix[CONTRAT_PAP], "var": mesures_risque(f.revenu)["var"], "var_ruban_a": mesures_risque(f.acheteur[CONTRAT_RUBAN])["var"], "var_ruban_v": mesures_risque(f.vendeur[CONTRAT_RUBAN])["var"],
                        "prime_20": f.prix[nom_plancher(20.0)], "var_pl0": mesures_risque(f.vendeur[nom_plancher(0.0)])["var"], "var_pl20": mesures_risque(f.vendeur[nom_plancher(20.0)])["var"]})
    mc = pd.DataFrame(mesures)
    d = {"k": ("Prix juste du pay-as-produced (€/MWh)", 1), "prime_20": ("Prime du plancher à 20 €/MWh (€/MWh)", 1)}
    lignes += ["", "### Monte-Carlo 2027, sans erreur de modèle", "", "| Grandeur | Minimum | Moyenne | Maximum |", "|---|---|---|---|"]
    for cle, (nom, dec) in d.items():
        lignes.append(f"| {nom} | {mc[cle].min():.{dec}f} | {mc[cle].mean():.{dec}f} | {mc[cle].max():.{dec}f} |".replace(".", ","))
    for cle, nom in (("var", "VaR du spot (€)"), ("var_ruban_v", "VaR du vendeur du ruban (€)"), ("var_ruban_a", "VaR de l'acheteur du ruban (€)"), ("var_pl0", "VaR du vendeur, plancher à 0 €/MWh (€)"), ("var_pl20", "VaR du vendeur, plancher à 20 €/MWh (€)")):
        lignes.append(f"| {nom} | {eur(mc[cle].min())} | {eur(mc[cle].mean())} | {eur(mc[cle].max())} |")
    lignes += ["", f"Plancher à 0 €/MWh au-dessus du spot : {int((mc['var_pl0'] > mc['var']).sum())} graines sur {len(mc)}. Plancher à 20 €/MWh sous le spot : {int((mc['var_pl20'] < mc['var']).sum())} sur {len(mc)}. Ruban : VaR acheteur au-dessus du vendeur sur {int((mc['var_ruban_a'] > mc['var_ruban_v']).sum())} graines sur {len(mc)}."]

    # B2 : année retirée.
    lignes += ["", "## B2. Année retirée", "", "Skill en retirant l'année de la colonne. Critère de la V1 : skill > 0 contre R1 et contre R2.", "", "| Comparaison | Tout | " + " | ".join(str(a) for a in ANNEES) + " | Retraits où le skill reste > 0 |", "|---|---|" + "---|" * (len(ANNEES) + 1)]
    for a, b, nom in COUPLES:
        s = skill_sans_chaque_annee(officiel, a, b)
        lignes.append(f"| {nom} | {nb(skill_global(officiel, a, b))} | " + " | ".join(nb(s[x]) for x in ANNEES) + f" | {int((s > 0).sum())} sur {len(s)} |")
    v1r1, v1r2 = skill_sans_chaque_annee(officiel, "modele_realiste", "r1_persistance"), skill_sans_chaque_annee(officiel, "modele_realiste", "r2_climatologie")
    lignes += ["", f"Critère de la V1 maintenu pour {int(((v1r1 > 0) & (v1r2 > 0)).sum())} retraits sur {len(v1r1)}."]

    # B3 : bootstrap par années entières.
    rng = np.random.default_rng([GRAINE, 3])
    lignes += ["", "## B3. Intervalle de confiance du skill", "", f"Bootstrap par années entières, {N_BOOTSTRAP} tirages. Avec 8 blocs, c'est un ordre de grandeur.", "", "| Comparaison | Skill | 5 % | 95 % | Part des tirages avec skill > 0 |", "|---|---|---|---|---|"]
    for a, b, nom in COUPLES:
        s = bootstrap_skill(officiel, a, b, N_BOOTSTRAP, rng)
        lignes.append(f"| {nom} | {nb(skill_global(officiel, a, b))} | {nb(np.quantile(s, 0.05))} | {nb(np.quantile(s, 0.95))} | {pt((s > 0).mean(), 0)} % |")

    # Avec 2026.
    avec_2026 = p.dropna(subset=["taux_capture", "modele_realiste", "r1_persistance", "r2_climatologie", "tc_m2", "tc_m1"])
    lignes += ["", "### En ajoutant les mois valides de 2026 (hors protocole)", "", f"{len(avec_2026)} mois.", "", "| Comparaison | 2018–2025 | Avec 2026 | 2026 seul |", "|---|---|---|---|"]
    for a, b, nom in COUPLES:
        lignes.append(f"| {nom} | {nb(skill_global(officiel, a, b))} | {nb(skill_global(avec_2026, a, b))} | {nb(skill_global(avec_2026[avec_2026['annee'] == 2026], a, b))} |")

    # B4 : retards de Newey-West.
    lignes += ["", "## B4. Diebold-Mariano selon le nombre de retards", "", "| Comparaison | " + " | ".join(f"p, {r} retards" for r in RETARDS) + " | Conclusion à 5 % |", "|---|" + "---|" * (len(RETARDS) + 1)]
    for a, b, nom in COUPLES:
        ps = [diebold_mariano(officiel[a] - officiel["taux_capture"], officiel[b] - officiel["taux_capture"], retards=r).p_valeur for r in RETARDS]
        conclusion = "stable" if len({x < 0.05 for x in ps}) == 1 else "**instable**"
        lignes.append(f"| {nom} | " + " | ".join(f"{x:.3f}".replace(".", ",") for x in ps) + f" | {conclusion} ({'significatif' if ps[1] < 0.05 else 'non significatif'} à 11 retards) |")
    lignes.append("")
    texte = "\n".join(lignes)
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(texte)
    print(texte)


if __name__ == "__main__":
    main()
