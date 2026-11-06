"""Audit, blocs C et D : hypothèses de prix, backtest du prix annuel et calibrage de la VaR (`docs/audit.md`).

Usage : ``.venv/bin/python scripts/audit_prix.py``, après ``scripts/backtest_m2.py``. Écrit ``reports/audit/prix.md`` et ``reports/audit/prix_backtest.csv``.
Ne modifie ni la base ni les autres rapports. Les scénarios officiels ne changent pas : tout ce qui suit est rapporté comme sensibilité.
"""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from ppa_pricer.analyse.capture import charger_horaire, taux_de_capture
from ppa_pricer.backtest.metriques import mae
from ppa_pricer.backtest.prix import forme_connue, taux_implicite
from ppa_pricer.backtest.walk_forward import taux_annuels
from ppa_pricer.donnees.base import connexion
from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE
from ppa_pricer.donnees.energy_charts import charger_eolien
from ppa_pricer.donnees.pvgis import MONTPELLIER, lire_profil
from ppa_pricer.modele import m2
from ppa_pricer.modele.m0 import GRAINE, N_TRAJECTOIRES
from ppa_pricer.modele.v1 import MOIS, prevoir
from ppa_pricer.pricing.monte_carlo import (
    CONTRAT_PAP,
    calibrer_livraison,
    flux_contrats,
    mesures_risque,
    revenu_avec_erreur,
    simuler_livraison,
    taux_capture_annuel,
    tirer_baseload,
    volumes_par_annee,
)
from ppa_pricer.pricing.v1 import ANNEES_FORME, baseload_mensuel, entrees_pricing, forme_baseload, prix_juste, taux_capture_formule, volumes_mensuels

RACINE = Path(__file__).resolve().parents[1]
BASE = RACINE / "data" / "ppa.sqlite"
BRUTS = RACINE / "data" / "raw" / "energy_charts"
PROFIL = RACINE / "data" / "raw" / "pvgis" / f"profil_{MONTPELLIER.nom}.json"
PREVISIONS = RACINE / "reports" / "backtest" / "m2" / "previsions.csv"
CONTROLE = RACINE / "reports" / "pricing" / "monte_carlo" / "controle.csv"
DOSSIER = RACINE / "reports" / "audit"
ANNEES = list(range(2018, 2026))
ANNEE_LIVRAISON = 2027
BASELOAD_OFFICIEL = 61.0
SIGMAS = (0.25, 0.17)
Z_90 = 1.645
SEUIL_SOLIDE = 0.05
# Cotations relevées le 30/10/2026 sur https://selectra.info/energie/actualites/prix-electricite/2026-10-28, qui cite EEX : clôture du 27/10/2026, base, €/MWh.
COURBE_PUBLIQUE = {"CAL_2027": 120.34, "CAL_2028": 70.75, "CAL_2029": 62.53, "T1": 189.77, "T2": 77.99, "T3": 95.11}
TRIMESTRES = {1: (1, 2, 3), 2: (4, 5, 6), 3: (7, 8, 9), 4: (10, 11, 12)}


def eur(x: float) -> str:
    return f"{round(x, -2):,.0f}".replace(",", " ").replace("-", "−")


def p1(x: float) -> str:
    return f"{x:.1f}".replace(".", ",").replace("-", "−")


def pt(x: float) -> str:
    return f"{x * 100:.1f}".replace(".", ",").replace("-", "−")


def heures_trimestre(annee: int) -> dict[int, int]:
    h = pd.date_range(f"{annee}-01-01", f"{annee + 1}-01-01", freq="h", inclusive="left", tz="Europe/Paris").month
    return {q: int(np.isin(h, mois).sum()) for q, mois in TRIMESTRES.items()}


def baseload_courbe(forme: pd.Series, annee: int) -> pd.Series:
    """Baseload mensuel calé sur la courbe publique par trimestre ; dans un trimestre, la forme reste celle de ``forme``. T4 se déduit de CAL et de T1 à T3."""
    h = heures_trimestre(annee)
    t = {q: COURBE_PUBLIQUE[f"T{q}"] for q in (1, 2, 3)}
    t[4] = (COURBE_PUBLIQUE["CAL_2027"] * sum(h.values()) - sum(t[q] * h[q] for q in (1, 2, 3))) / h[4]
    resultat = pd.Series(index=list(MOIS), dtype=float)
    for q, mois in TRIMESTRES.items():
        resultat.loc[list(mois)] = t[q] * forme.loc[list(mois)] / forme.loc[list(mois)].mean()
    return resultat


def main() -> None:
    horaire = charger_horaire(connexion(BASE)).merge(charger_eolien(BRUTS), on="ts_utc", how="left")
    mensuel = taux_de_capture(horaire, "M")
    annuel = taux_de_capture(horaire, "Y")
    profil = lire_profil(PROFIL)
    volumes = volumes_mensuels(profil)
    table_volumes = volumes_par_annee(profil)
    entrees, parametres = entrees_pricing(mensuel, ANNEE_LIVRAISON)
    forme = forme_baseload(mensuel, ANNEES_FORME)
    mois = pd.Series(list(MOIS), index=list(MOIS), name="mois")

    def prix_v1(tc: pd.Series, niveau: float = BASELOAD_OFFICIEL, f: pd.Series = forme, v: pd.Series = volumes) -> float:
        return prix_juste(tc, baseload_mensuel(niveau, f, ANNEE_LIVRAISON), v)

    lignes = ["# Audit, blocs C et D : prix et risque", "", "Plan et seuils : `docs/audit.md`. Les scénarios officiels ne changent pas : tout ici est une sensibilité.", ""]

    # C1 : le baseload.
    m = mensuel[mensuel["valide"] | (mensuel["periode"] >= pd.Period("2025-10", "M"))].copy()
    recents = m[m["periode"] >= pd.Period("2025-10", "M")]
    lignes += ["## C1. Le baseload de 61 €/MWh", "", "| Période | Baseload (€/MWh) |", "|---|---|"]
    for _, r in recents.iterrows():
        if r["valide"]:
            lignes.append(f"| {r['periode']} | {p1(r['baseload_eur_mwh'])} |")
    a = annuel.set_index(annuel["periode"].dt.year)["baseload_eur_mwh"]
    prix_h = horaire.dropna(subset=["prix_eur_mwh"]).set_index("ts_utc")["prix_eur_mwh"]
    local_h = prix_h.index.tz_convert(FUSEAU_AFFICHAGE)
    moyenne_2026 = float(prix_h[local_h.year == 2026].mean())
    octobre_2026 = float(prix_h[(local_h.year == 2026) & (local_h.month == 10)].mean())
    valides = mensuel[mensuel["valide"]].tail(12)
    derniers = (valides["baseload_eur_mwh"] * valides["heures_utilisees"]).sum() / valides["heures_utilisees"].sum()
    h = heures_trimestre(ANNEE_LIVRAISON)
    t4 = (COURBE_PUBLIQUE["CAL_2027"] * sum(h.values()) - sum(COURBE_PUBLIQUE[f"T{q}"] * h[q] for q in (1, 2, 3))) / h[4]
    lignes += ["", f"12 derniers mois valides : **{p1(derniers)} €/MWh**. Année 2026 jusqu'au 29/10 : **{p1(moyenne_2026)} €/MWh**. Octobre 2026, incomplet : {p1(octobre_2026)} €/MWh. 2025 : {p1(a[2025])} €/MWh.", "",
               "| Cotation publique, base, clôture du 27/10/2026 (Selectra, qui cite EEX) | €/MWh |", "|---|---|"]
    for k, v in COURBE_PUBLIQUE.items():
        lignes.append(f"| {k.replace('_', ' ')} | {p1(v)} |")
    lignes += [f"| T4, déduit de CAL et de T1 à T3 | {p1(t4)} |", "", f"Le scénario central de {BASELOAD_OFFICIEL:.0f} €/MWh vaut **{BASELOAD_OFFICIEL / COURBE_PUBLIQUE['CAL_2027'] * 100:.0f} %** de cette cotation, et le scénario haut de 77 €/MWh en vaut {77 / COURBE_PUBLIQUE['CAL_2027'] * 100:.0f} %. Il reste proche de CAL 2029 ({p1(COURBE_PUBLIQUE['CAL_2029'])} €/MWh) : plausible à long terme, pas pour une livraison en 2027.", ""]

    # C2 : classement des hypothèses.
    pl = calibrer_livraison(horaire, mensuel, ANNEE_LIVRAISON)
    rng_base = [GRAINE, ANNEE_LIVRAISON]

    def prix_m2(p: m2.ParametresM2) -> float:
        rng = np.random.default_rng(rng_base)
        _, y, q = simuler_livraison(p, table_volumes, N_TRAJECTOIRES, rng)
        return float((q * y).sum() / q.sum()) * BASELOAD_OFFICIEL

    tc_v1 = entrees["tc_modele"]
    tc_pers = entrees["tc_persistance"]
    reference = prix_v1(tc_v1)
    p_h4 = replace(pl, croissances=pl.croissances[-1:])
    p_zero = replace(pl, croissances=np.array([0.0]))
    p_un_an = m2.calibrer_m2(horaire, 2026, fenetre=1)
    p_un_an = replace(p_un_an, annee_prevue=ANNEE_LIVRAISON, niveaux=pl.niveaux, croissances=pl.croissances)
    prix_m2_base = prix_m2(pl)
    volumes_nationaux = pd.Series({k: mensuel[mensuel["valide"]].tail(12).set_index(mensuel[mensuel["valide"]].tail(12)["periode"].dt.month)["energie_solaire_mwh"][k] for k in MOIS})
    courbe = baseload_courbe(forme, ANNEE_LIVRAISON)
    prix_courbe_v1 = prix_juste(tc_v1, courbe, volumes)
    prix_courbe_pers = prix_juste(tc_pers, courbe, volumes)
    lignes_c2 = [
        ("Baseload", "scénarios bas et haut (50 et 77 €/MWh)", prix_v1(tc_v1, 50.0), prix_v1(tc_v1, 77.0)),
        ("Baseload", "2026 jusqu'au 29/10, puis cotation CAL 2027 avec la forme 2024–2025", prix_v1(tc_v1, moyenne_2026), prix_v1(tc_v1, COURBE_PUBLIQUE["CAL_2027"])),
        ("Baseload", "cotation CAL 2027 et trimestres publics, taux V1 puis persistance", prix_courbe_v1, prix_courbe_pers),
        ("Modèle", "M2 au Monte-Carlo, puis persistance", prix_m2_base, prix_v1(tc_pers)),
        ("Croissance du solaire, V1", "+40 % puis aucune", prix_v1(prevoir(parametres, mois, entrees["part_solaire_base"] * 1.4)), prix_v1(prevoir(parametres, mois, entrees["part_solaire_base"])))
        ,
        ("Croissance du solaire, M2", "aucune, puis la dernière croissance seule (H4)", prix_m2(p_zero), prix_m2(p_h4)),
        ("Fenêtre de M2", "1 an", prix_m2(p_un_an), prix_m2_base),
        ("Forme du baseload", "2025 seule, puis 2023–2025", prix_v1(tc_v1, f=forme_baseload(mensuel, (2025,))), prix_v1(tc_v1, f=forme_baseload(mensuel, (2023, 2024, 2025)))),
        ("Profil du site", "volumes nationaux au lieu du site", prix_v1(tc_v1, v=volumes_nationaux), reference),
        ("Source du solaire (rapport des sources)", "RTE, puis tout ENTSO-E", 29.9, 33.1),
    ]
    lignes_c2.sort(key=lambda x: -abs(x[3] - x[2]))
    lignes += ["## C2. Quelle hypothèse déplace le plus le prix 2027 ?", "", f"Référence : V1, baseload de {BASELOAD_OFFICIEL:.0f} €/MWh, soit **{p1(reference)} €/MWh**. Une seule hypothèse change à la fois.", "",
               "| Hypothèse | Variation | Prix bas | Prix haut | Étendue (€/MWh) |", "|---|---|---|---|---|"]
    for nom, detail, a_, b_ in lignes_c2:
        lignes.append(f"| {nom} | {detail} | {p1(min(a_, b_))} | {p1(max(a_, b_))} | {p1(abs(b_ - a_))} |")

    # D1 : backtest du prix annuel.
    p = pd.read_csv(PREVISIONS)
    p = p[p["annee"].isin(ANNEES)]
    realise = taux_capture_formule(mensuel, volumes)
    lignes_d1 = []
    for annee in ANNEES:
        g = p[p["annee"] == annee].set_index("mois")
        fc = forme_connue(mensuel, annee)
        m_a = mensuel[(mensuel["periode"].dt.year == annee) & mensuel["valide"]]
        b_annuel = (m_a["baseload_eur_mwh"] * m_a["heures_utilisees"]).sum() / m_a["heures_utilisees"].sum()
        f_reelle = (m_a["baseload_eur_mwh"] / b_annuel).set_axis(m_a["periode"].dt.month)
        pm = m2.calibrer_m2(horaire, annee)
        rng = np.random.default_rng([GRAINE, annee])
        _, y, q = simuler_livraison(pm, table_volumes, N_TRAJECTOIRES, rng)
        tc_t = taux_capture_annuel(y, q)
        lignes_d1.append(
            {
                "annee": annee,
                "baseload": b_annuel,
                "realise": realise[annee],
                "annee_precedente": realise.get(annee - 1, np.nan),
                "r1_forme_connue": taux_implicite(g["r1_persistance"], fc, volumes, annee),
                "v1_forme_connue": taux_implicite(g["modele_realiste"], fc, volumes, annee),
                "v1_forme_realisee": taux_implicite(g["modele_realiste"], f_reelle, volumes, annee),
                "m1_forme_connue": taux_implicite(g["tc_m1"], fc, volumes, annee),
                "m2_forme_connue": taux_implicite(g["tc_m2"], fc, volumes, annee),
                "m2_trajectoires": float((q * y).sum() / q.sum()),
                "m2_bas": float(np.quantile(tc_t, 0.05)),
                "m2_haut": float(np.quantile(tc_t, 0.95)),
            }
        )
    d1 = pd.DataFrame(lignes_d1)
    d1.to_csv(DOSSIER / "prix_backtest.csv", index=False, float_format="%.5f")
    methodes = {"annee_precedente": "Taux annuel de l'année précédente", "r1_forme_connue": "R1 mensuel, forme connue", "v1_forme_connue": "V1, forme connue", "v1_forme_realisee": "V1, forme réalisée (irréaliste)", "m1_forme_connue": "M1, forme connue", "m2_forme_connue": "M2 médian, forme connue", "m2_trajectoires": "M2, trajectoires (comme le Monte-Carlo)"}
    lignes += ["", "## D1. Backtest du prix annuel, 2018–2025", "", "Prix prévu pour un baseload annuel de 1, avec la forme connue à l'avance (les deux années précédentes), face au prix réalisé selon la formule du pricing. Le niveau annuel n'est pas prévu : il relève du marché à terme. Erreur en points de baseload ; à 61 €/MWh, 1 point vaut 0,61 €/MWh.", "",
               "| Méthode | Erreur moyenne (points) | Biais (points) | Erreur la plus forte (points) | Erreur moyenne à 61 €/MWh | Solide (sous 5 points) |", "|---|---|---|---|---|---|"]
    for c, nom in methodes.items():
        e = (d1[c] - d1["realise"]).dropna()
        lignes.append(f"| {nom} | {pt(e.abs().mean())} | {pt(e.mean())} | {pt(e.abs().max())} | {p1(e.abs().mean() * BASELOAD_OFFICIEL)} €/MWh | {'oui' if e.abs().mean() < SEUIL_SOLIDE else '**non**'} |")
    lignes += ["", "| Année | Baseload | Réalisé | Année précédente | V1 | M2 trajectoires | Intervalle à 90 % de M2 | Dans l'intervalle |", "|---|---|---|---|---|---|---|---|"]
    for _, r in d1.iterrows():
        dedans = r["m2_bas"] <= r["realise"] <= r["m2_haut"]
        lignes.append(f"| {int(r['annee'])} | {p1(r['baseload'])} | {pt(r['realise'])} | {pt(r['annee_precedente'])} | {pt(r['v1_forme_connue'])} | {pt(r['m2_trajectoires'])} | {pt(r['m2_bas'])} à {pt(r['m2_haut'])} | {'oui' if dedans else '**non**'} |")
    n_dedans = int(((d1["realise"] >= d1["m2_bas"]) & (d1["realise"] <= d1["m2_haut"])).sum())
    lignes += ["", f"Le taux annuel du site réalisé tombe dans l'intervalle de M2 **{n_dedans} années sur {len(d1)}**, pour 7,2 attendues."]

    # D2 : calibrage de la VaR.
    b = annuel[annuel["valide"]].set_index(annuel[annuel["valide"]]["periode"].dt.year)["baseload_eur_mwh"]
    b = b[b.index <= 2025]
    variations = np.log(b).diff().dropna()
    lignes += ["", "## D2. Calibrage de la VaR", "", "### Le baseload sort-il de l'intervalle à 90 %, centré sur l'année précédente ?", "", "| σ | Années hors de l'intervalle, sur " + str(len(variations)) + " | Attendu | Années concernées |", "|---|---|---|---|"]
    for s in SIGMAS:
        dehors = variations[variations.abs() > Z_90 * s]
        lignes.append(f"| {s:.2f} | {len(dehors)} | {0.1 * len(variations):.0f} | {', '.join(str(x) for x in dehors.index)} |".replace("0.", "0,"))
    rng = np.random.default_rng([GRAINE, ANNEE_LIVRAISON])
    _, y, q = simuler_livraison(pl, table_volumes, N_TRAJECTOIRES, rng)
    tc0 = taux_capture_annuel(y, q)
    aleas = rng.standard_normal(N_TRAJECTOIRES)
    b_off = tirer_baseload(tc0, aleas, BASELOAD_OFFICIEL)
    unite = (q * y).sum(axis=0)
    volume = q.sum(axis=0)
    rapports = np.exp(variations.to_numpy())
    r_emp = np.random.default_rng([GRAINE, ANNEE_LIVRAISON, 3])
    b_emp = BASELOAD_OFFICIEL * r_emp.choice(rapports / rapports.mean(), N_TRAJECTOIRES)
    c = pd.read_csv(CONTROLE)
    err_traj = (c["mediane"] - c["realise"]).to_numpy()
    err_site = (d1["m2_trajectoires"] - d1["realise"]).to_numpy()

    def bilan(baseload: np.ndarray, erreurs: np.ndarray | None) -> tuple[float, float, float]:
        vals, moy = [], []
        for i in range(30):
            r = unite * baseload
            if erreurs is not None:
                r = revenu_avec_erreur(r, volume, baseload, erreurs, np.random.default_rng([GRAINE, ANNEE_LIVRAISON, 200 + i]))
            m_ = mesures_risque(r)
            vals.append(m_["var"])
            moy.append(m_["moyenne"])
        return float(np.mean(vals)), float(np.mean(moy)), float(np.mean(vals) / np.mean(moy))

    cas = [
        ("σ = 0,25, corrélation 0,65, sans erreur de modèle", b_off, None),
        ("Idem, erreur du taux national sur les trajectoires", b_off, err_traj),
        ("Idem, erreur du prix du site (D1)", b_off, err_site),
        ("Variations historiques du baseload, crise comprise, sans erreur", b_emp, None),
        ("Variations historiques, erreur du prix du site (D1)", b_emp, err_site),
    ]
    lignes += ["", "### VaR à 95 % du spot, baseload de moyenne 61 €/MWh", "", "Moyenne sur 30 tirages de l'erreur. Le rapport au revenu moyen ne dépend pas du niveau du baseload : à 120 €/MWh, les montants sont environ 2 fois plus élevés.", "", "| Cas | VaR 95 % | Revenu moyen | VaR / revenu moyen |", "|---|---|---|---|"]
    for nom, baseload, e_ in cas:
        v, moy, part = bilan(baseload, e_)
        lignes.append(f"| {nom} | {eur(v)} € | {eur(moy)} € | {part * 100:.0f} % |")
    lignes.append("")
    texte = "\n".join(lignes)
    (DOSSIER / "prix.md").write_text(texte)
    print(texte)


if __name__ == "__main__":
    main()
