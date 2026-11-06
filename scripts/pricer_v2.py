"""Pricing V2 : prix 2027 ancré sur la courbe à terme, scénarios de parc et Monte-Carlo (voir `docs/pricing.md`).

Usage : ``.venv/bin/python scripts/pricer_v2.py``, après ``scripts/backtest_v2.py`` et ``scripts/audit_prix.py``.
Écrit dans ``reports/pricing/v2/`` : ``rapport.md``, ``prix.csv``, ``contrats.csv``. Ne modifie ni la base ni les rapports précédents.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ppa_pricer.analyse.capture import charger_horaire
from ppa_pricer.donnees.base import connexion
from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE
from ppa_pricer.donnees.energy_charts import charger_eolien
from ppa_pricer.donnees.pvgis import MONTPELLIER, lire_profil
from ppa_pricer.modele.m0 import GRAINE, N_TRAJECTOIRES
from ppa_pricer.modele.v1 import MOIS, prevoir
from ppa_pricer.modele.v2 import prevoir_v2
from ppa_pricer.pricing.calcul import preparer_marche, prix_v2, simuler_risques
from ppa_pricer.pricing.courbe import (
    PARC_BASE_GW,
    SCENARIO_CENTRAL,
    SCENARIOS_PARC_GW,
    TRIMESTRES,
    baseload_courbe,
    heures_mensuelles,
    historique_pointe,
    lire_courbe,
    niveau_par_mois,
    part_selon_parc,
    taux_implicite_pointe,
)
from ppa_pricer.pricing.monte_carlo import (
    CONTRAT_PAP,
    CONTRAT_RUBAN,
    PLANCHERS,
    SIGMA_BASELOAD,
    CORRELATION_BASELOAD,
    flux_avec_erreurs,
    flux_contrats,
    mesures_risque,
    nom_plancher,
    parts_covariance,
    tirer_baseload,
    volumes_par_annee,
)
from ppa_pricer.pricing.v1 import baseload_mensuel, prix_juste, volumes_mensuels

RACINE = Path(__file__).resolve().parents[1]
BASE = RACINE / "data" / "ppa.sqlite"
BRUTS = RACINE / "data" / "raw" / "energy_charts"
PROFIL = RACINE / "data" / "raw" / "pvgis" / f"profil_{MONTPELLIER.nom}.json"
COURBE = RACINE / "data" / "marche" / "courbe_fr_2026-10-29.csv"
BACKTEST_PRIX = RACINE / "reports" / "audit" / "prix_backtest.csv"
PRIX_V1 = RACINE / "reports" / "pricing" / "v1" / "prix.csv"
DOSSIER = RACINE / "reports" / "pricing" / "v2"
ANNEE = 2027
NIVEAUX_SENSIBILITE = {"CAL 29 (long terme)": 62.48, "CAL 28": 69.89, "Clôture du 2 octobre, selon un relevé de Selectra": 94.36, "CAL 27, chiffre central": 122.61, "+25 %": 153.26}
ECHELLE_PRIX_NEGATIFS = 61.0
N_GRAINES = 10


def p1(x: float) -> str:
    return f"{x:.1f}".replace(".", ",").replace("-", "−")


def eur(x: float) -> str:
    return f"{round(x, -2):,.0f}".replace(",", " ").replace("-", "−")


def pct(x: float) -> str:
    return f"{x * 100:.1f}".replace(".", ",").replace("-", "−")


def main() -> None:
    horaire = charger_horaire(connexion(BASE)).merge(charger_eolien(BRUTS), on="ts_utc", how="left")
    profil = lire_profil(PROFIL)
    volumes = volumes_mensuels(profil)
    courbe = lire_courbe(COURBE)
    bp = pd.read_csv(BACKTEST_PRIX)
    marche = preparer_marche(horaire, courbe, ANNEE, (bp["m2_trajectoires"] - bp["realise"]).to_numpy())
    niveaux, calendaire, forme = marche.niveaux, marche.calendaire, marche.forme
    baseload = baseload_courbe(niveaux, forme, ANNEE)
    entrees, p_v1, p_v2 = marche.entrees, marche.p_v1, marche.p_v2
    mois = pd.Series(list(MOIS), index=list(MOIS), name="mois")
    base = entrees["part_solaire_base"]
    niveau = niveau_par_mois(niveaux)

    historique = historique_pointe(horaire)
    implicites, r2 = {}, {}
    for q in (2, 3):
        rapport = float(courbe.loc[f"T{q}_{ANNEE}", "pointe_eur_mwh"] / courbe.loc[f"T{q}_{ANNEE}", "base_eur_mwh"])
        implicites[q], r2[q] = taux_implicite_pointe(historique, q, rapport)

    def prix(tc: pd.Series, b: pd.Series = baseload) -> float:
        return prix_juste(tc, b, volumes)

    lignes_prix = []
    for nom, parc in SCENARIOS_PARC_GW.items():
        s = part_selon_parc(base, parc)
        v2 = prix_v2(marche, volumes, parc).detail["taux_capture"]
        v1 = prevoir(p_v1, mois, s)
        impl = v2.copy()
        for q, tc in implicites.items():
            impl.loc[TRIMESTRES[q]] = tc
        lignes_prix.append(
            {
                "scenario": nom,
                "parc_gw": parc,
                "coefficient": parc / PARC_BASE_GW,
                "prix_v2": prix(v2),
                "prix_v1_courbe": prix(v1),
                "prix_implicite": prix(impl),
                "prix_persistance": prix(entrees["tc_persistance"]),
                "taux_implicite_v2": prix(v2) / calendaire,
                "tc_t2": v2.loc[TRIMESTRES[2]].mean(),
                "tc_t3": v2.loc[TRIMESTRES[3]].mean(),
                "revenu_v2_mwc": prix(v2) * volumes.sum(),
            }
        )
    table = pd.DataFrame(lignes_prix).set_index("scenario")
    DOSSIER.mkdir(parents=True, exist_ok=True)
    table.to_csv(DOSSIER / "prix.csv", float_format="%.4f")
    central = table.loc[SCENARIO_CENTRAL]
    s_c = part_selon_parc(base, SCENARIOS_PARC_GW[SCENARIO_CENTRAL])
    v2_c = prevoir_v2(p_v2, mois, s_c, niveau)
    v1_off = pd.read_csv(PRIX_V1).set_index("scenario").loc["central", "prix_modele_eur_mwh"]

    lignes = [
        f"# Pricing V2 : livraison {ANNEE}",
        "",
        f"Généré le {pd.Timestamp.now(tz=FUSEAU_AFFICHAGE):%d/%m/%Y}. Choix, limites et attentes : `docs/pricing.md`. Site : Montpellier, 1 MWc, {volumes.sum():.0f} MWh/an.",
        "",
        "**Ce n'est pas un prix de contrat** : valeur de l'énergie au spot, avant garanties d'origine, équilibrage, crédit et marge. Ce prix suit la cotation, qui bouge vite. La forme du taux de capture a été choisie après avoir vu les années de test. Horizon d'un an : le niveau de 2027 ne vaut pas pour la suite.",
        "",
        "## La courbe utilisée",
        "",
        "Clôture du 29/10/2026, relevée sur Selectra, qui cite EEX. Pas de lecture directe d'EEX.",
        "",
        "| Échéance | Base (€/MWh) | Pointe (€/MWh) | Pointe / base |",
        "|---|---|---|---|",
    ]
    for e, r in courbe.iterrows():
        lignes.append(f"| {e.replace('_', ' ')} | {p1(r['base_eur_mwh'])} | {p1(r['pointe_eur_mwh'])} | {r['pointe_eur_mwh'] / r['base_eur_mwh']:.2f} |".replace("0.", "0,").replace("1.", "1,"))
    lignes += [
        "",
        "## Prix du pay-as-produced",
        "",
        f"**Chiffre central : {p1(central['prix_v2'])} €/MWh**, soit {pct(central['taux_implicite_v2'])} % du baseload et {eur(central['revenu_v2_mwc'])} €/MWc par an, pour un parc de {central['parc_gw']:.0f} GW. La V1 officielle, à 61 €/MWh, reste à {p1(v1_off)} €/MWh.",
        "",
        "| Parc à mi-2027 | GW | Part × | **V2 : part et niveau** | V1 : part seule | Persistance | Implicite de la courbe en T2 et T3 | Taux V2 T2 / T3 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for nom, r in table.iterrows():
        lignes.append(f"| {nom} | {p1(r['parc_gw'])} | {r['coefficient']:.3f} | **{p1(r['prix_v2'])}** | {p1(r['prix_v1_courbe'])} | {p1(r['prix_persistance'])} | {p1(r['prix_implicite'])} | {pct(r['tc_t2'])} % / {pct(r['tc_t3'])} % |".replace("0.", "0,").replace("1.", "1,"))
    lignes += [
        "",
        f"Taux implicite de la courbe : T2 {pct(implicites[2])} % (R² de la droite {r2[2]:.2f}), T3 {pct(implicites[3])} % (R² {r2[3]:.2f}), sur {len(historique[historique['trimestre'] == 2])} années. Aucun historique de cotations ne permet de tester ce passage.".replace("0.", "0,"),
        "",
        f"## Détail mensuel, {SCENARIO_CENTRAL.lower()}",
        "",
        "| Mois | Volume (MWh) | Baseload (€/MWh) | Part du solaire | Taux V2 | Taux V1 | Persistance |",
        "|---|---|---|---|---|---|---|",
    ]
    v1_c = prevoir(p_v1, mois, s_c)
    for m in MOIS:
        lignes.append(f"| {m} | {volumes[m]:.0f} | {p1(baseload[m])} | {pct(s_c[m])} % | {pct(v2_c[m])} % | {pct(v1_c[m])} % | {pct(entrees['tc_persistance'][m])} % |")

    revenu_mois = baseload * v2_c * volumes
    parts_q = {q: revenu_mois[m].sum() / revenu_mois.sum() for q, m in TRIMESTRES.items()}
    lignes += ["", "Part du revenu et du volume par trimestre : " + " ; ".join(f"T{q} {pct(parts_q[q])} % du revenu, {pct(volumes[m].sum() / volumes.sum())} % du volume" for q, m in TRIMESTRES.items()) + "."]

    lignes += ["", "## Sensibilité au niveau", "", "Mêmes rapports entre trimestres, parc central. Le taux de capture bouge avec le niveau : le prix n'est pas proportionnel.", "", "| Niveau annuel | €/MWh | Prix V2 | Taux implicite |", "|---|---|---|---|"]
    for nom, n in NIVEAUX_SENSIBILITE.items():
        pr = prix_v2(marche, volumes, SCENARIOS_PARC_GW[SCENARIO_CENTRAL], n).prix
        lignes.append(f"| {nom} | {p1(n)} | {p1(pr)} | {pct(pr / n)} % |")
    h = heures_mensuelles(ANNEE)
    cal_seul = prix(prevoir_v2(p_v2, mois, s_c, pd.Series(calendaire, index=list(MOIS))), baseload_mensuel(calendaire, forme, ANNEE))
    lignes += ["", f"Avec CAL 27 seul et la forme 2024–2025, sans les trimestres : {p1(cal_seul)} €/MWh."]

    # Monte-Carlo.
    table_volumes = volumes_par_annee(profil)
    erreurs = marche.erreurs
    parcs = tuple(SCENARIOS_PARC_GW.values())

    def tirage(graine: int):
        return simuler_risques(marche, table_volumes, parcs, n=N_TRAJECTOIRES, graine=graine)

    mc = tirage(GRAINE)
    y, q, tc0, aleas, b, f, v_e, a_e = mc.y, mc.q, mc.taux_capture, mc.aleas, mc.baseload, mc.flux, mc.vendeur, mc.acheteur
    lignes_c = []
    for cote, sans, avec in (("vendeur", f.vendeur, v_e), ("acheteur", f.acheteur, a_e)):
        for contrat in sans:
            r, e = mesures_risque(sans[contrat]), mesures_risque(avec[contrat])
            lignes_c.append({"contrat": contrat, "cote": cote, "moyenne": r["moyenne"], "ecart_type_erreur": e["ecart_type"], "var_95_erreur": e["var"], "cvar_95_erreur": e["cvar"], "var_95_sans": r["var"], "correlation_baseload": float(np.corrcoef(sans[contrat], b)[0, 1])})
    contrats = pd.DataFrame(lignes_c)
    contrats.to_csv(DOSSIER / "contrats.csv", index=False, float_format="%.2f")
    spot_e = mesures_risque(v_e[contrats.iloc[0]["contrat"]])
    tc_annuel = f.revenu / (f.volume * b)
    lignes += [
        "",
        "## Monte-Carlo : le risque",
        "",
        f"{N_TRAJECTOIRES} trajectoires, graine {GRAINE}. Baseload de moyenne {p1(calendaire)} €/MWh, σ = {SIGMA_BASELOAD:.2f}, corrélation de {CORRELATION_BASELOAD:.2f} avec le taux de capture. Chaque trajectoire tire l'un des 3 scénarios de parc. Prix de M2, calés en espérance sur les trimestres de la courbe. L'erreur de modèle combine chaque trajectoire à chacune des 8 erreurs de site du backtest, sans tirage.".replace("0.25", "0,25").replace("0.65", "0,65"),
        "",
        f"**Revenu moyen au spot : {eur(f.revenu.mean())} €/MWc. VaR à 95 % avec erreur de modèle : {eur(spot_e['var'])} €, soit {spot_e['var'] / f.revenu.mean() * 100:.0f} % du revenu moyen.** Prix juste du Monte-Carlo : {p1(f.prix[CONTRAT_PAP])} €/MWh, à comparer au prix central de {p1(central['prix_v2'])} €/MWh, qui vient du modèle V2. Taux de capture annuel : médiane {pct(np.median(tc_annuel))} %, intervalle à 90 % de {pct(np.quantile(tc_annuel, 0.05))} à {pct(np.quantile(tc_annuel, 0.95))} %.",
        "",
        "| Contrat | Côté | Prix (€/MWh) | Flux moyen | Écart-type | VaR 95 % | CVaR 95 % | VaR sans erreur | Corrélation avec le baseload |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for _, c in contrats.iterrows():
        pr = f.prix.get(c["contrat"])
        lignes.append(f"| {c['contrat']} | {c['cote']} | {'—' if pr is None else p1(pr)} | {eur(c['moyenne'])} | {eur(c['ecart_type_erreur'])} | **{eur(c['var_95_erreur'])}** | {eur(c['cvar_95_erreur'])} | {eur(c['var_95_sans'])} | {f'{c.correlation_baseload:+.2f}'.replace('.', ',').replace('-', '−')} |")

    parts = parts_covariance(f.revenu, f.volume, b)
    lignes += ["", "### D'où vient le risque du spot", "", "Parts de la variance de ln R attribuées par covariance : leur somme vaut 100 %.", "", f"Baseload {pct(parts['baseload'])} %, taux de capture {pct(parts['taux_capture'])} %, volume {pct(parts['volume'])} %.", "",
               "### Sensibilités de la VaR du spot", "", "| Hypothèse | VaR sans erreur | VaR avec erreur | VaR avec erreur / revenu moyen |", "|---|---|---|---|"]
    variations = pd.read_csv(RACINE / "reports" / "analyse" / "taux_capture_annuel.csv")
    annees_b = variations[variations["valide"]].copy()
    annees_b["annee"] = annees_b["periode"].astype(str).str[:4].astype(int)
    series = annees_b[annees_b["annee"] <= 2025].set_index("annee")["baseload_eur_mwh"]
    rapports = (series / series.shift(1)).dropna().to_numpy()
    r_emp = np.random.default_rng([GRAINE, ANNEE, 3])
    cas = [(f"σ = 0,25, corrélation 0,65 (chiffre principal)", b), ("σ = 0,25, corrélation 0,26", tirer_baseload(tc0, aleas, calendaire, 0.25, 0.26)), ("σ = 0,25, indépendant", tirer_baseload(tc0, aleas, calendaire, 0.25, 0.0)), ("σ = 0,17, corrélation 0,65", tirer_baseload(tc0, aleas, calendaire, 0.17, 0.65)),
           ("Variations historiques du baseload, crise comprise", calendaire * r_emp.choice(rapports / rapports.mean(), N_TRAJECTOIRES)), ("Baseload fixé à la cotation", np.full(N_TRAJECTOIRES, calendaire))]
    for nom, bb in cas:
        g = flux_contrats(y, q, bb, ())
        ve, _ = flux_avec_erreurs(g, bb, erreurs)
        m = mesures_risque(ve[contrats.iloc[0]["contrat"]])
        lignes.append(f"| {nom} | {eur(mesures_risque(g.revenu)['var'])} | {eur(m['var'])} | {m['var'] / m['moyenne'] * 100:.0f} % |")

    # Prix négatifs à l'échelle de 61 €/MWh.
    prix_h = y * b
    corrige = np.where(y < 0, y * ECHELLE_PRIX_NEGATIFS, prix_h)
    lignes += ["", "### Plancher : prix négatifs multipliés par le baseload, ou non", "", f"Dans $p_t = B\\,y_t$, un prix négatif grossit avec $B$. La seconde colonne garde les prix négatifs à l'échelle de {ECHELLE_PRIX_NEGATIFS:.0f} €/MWh.", "", "| Plancher (€/MWh) | Prime, formule du modèle | Prime, prix négatifs à l'échelle de 61 €/MWh |", "|---|---|---|"]
    for k in PLANCHERS:
        p2 = (q * np.maximum(k - corrige, 0)).sum(axis=0).mean() / f.volume.mean()
        lignes.append(f"| {k:.0f} | {p1(f.prix[nom_plancher(k)])} | {p1(p2)} |")
    lignes += ["", f"Heures à prix négatif simulées : {(y < 0).sum(axis=0).mean():.0f} par an, contre 583 d'octobre 2025 à septembre 2026. Prix moyen quand il est négatif : {p1(prix_h[y < 0].mean())} €/MWh simulés, contre −11,5 €/MWh sur ces 12 mois.".replace(".", ",", 0)]

    mesures = []
    for g in [GRAINE, *range(1, N_GRAINES)]:
        r = tirage(g)
        ff, ve, ae = r.flux, r.vendeur, r.acheteur
        mesures.append({"k": ff.prix[CONTRAT_PAP], "spot": mesures_risque(ve[contrats.iloc[0]["contrat"]])["var"], "acheteur": mesures_risque(ae[CONTRAT_PAP])["var"], "vendeur": mesures_risque(ve[CONTRAT_PAP])["var"], "ruban_a": mesures_risque(ae[CONTRAT_RUBAN])["var"], "ruban_v": mesures_risque(ve[CONTRAT_RUBAN])["var"]})
    m = pd.DataFrame(mesures)
    lignes += ["", f"### Stabilité sur {N_GRAINES} graines", "", "| Grandeur | Minimum | Moyenne | Maximum |", "|---|---|---|---|", f"| Prix juste du Monte-Carlo (€/MWh) | {p1(m['k'].min())} | {p1(m['k'].mean())} | {p1(m['k'].max())} |"]
    for cle, nom in (("spot", "VaR du spot"), ("acheteur", "VaR de l'acheteur en pay-as-produced"), ("vendeur", "VaR du vendeur en pay-as-produced"), ("ruban_a", "VaR de l'acheteur du ruban"), ("ruban_v", "VaR du vendeur du ruban")):
        lignes.append(f"| {nom} (€) | {eur(m[cle].min())} | {eur(m[cle].mean())} | {eur(m[cle].max())} |")
    lignes.append("")
    texte = "\n".join(lignes)
    (DOSSIER / "rapport.md").write_text(texte)
    print(texte)


if __name__ == "__main__":
    main()
