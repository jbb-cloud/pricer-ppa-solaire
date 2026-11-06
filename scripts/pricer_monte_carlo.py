"""Monte-Carlo de pricing : distribution du revenu et risques par contrat (voir `docs/pricing.md`).

Usage : ``.venv/bin/python scripts/pricer_monte_carlo.py``, après ``scripts/backtest_m2.py`` et ``scripts/pricer_v1.py``.
Écrit dans ``reports/pricing/monte_carlo/`` : ``rapport.md``, ``contrats.csv``, ``controle.csv``.
Ne modifie ni la base ni les rapports précédents.
"""

from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd

from ppa_pricer.analyse.capture import charger_horaire, taux_de_capture
from ppa_pricer.backtest.walk_forward import taux_annuels
from ppa_pricer.donnees.base import connexion
from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE
from ppa_pricer.donnees.energy_charts import charger_eolien
from ppa_pricer.donnees.pvgis import MONTPELLIER, lire_profil
from ppa_pricer.modele import m2
from ppa_pricer.modele.m0 import GRAINE, N_TRAJECTOIRES, grille_annee
from ppa_pricer.pricing.monte_carlo import (
    CONTRAT_PAP,
    CONTRAT_RUBAN,
    CONTRAT_SPOT,
    CORRELATION_BASELOAD,
    PLANCHERS,
    SIGMA_BASELOAD,
    calibrer_livraison,
    flux_contrats,
    mesures_risque,
    nom_plancher,
    parts_variance,
    revenu_avec_erreur,
    simuler_livraison,
    taux_capture_annuel,
    tirer_baseload,
    var_en_figeant,
    volumes_par_annee,
)
from ppa_pricer.pricing.v1 import SCENARIOS_BASELOAD

RACINE = Path(__file__).resolve().parents[1]
BASE = RACINE / "data" / "ppa.sqlite"
BRUTS = RACINE / "data" / "raw" / "energy_charts"
PROFIL = RACINE / "data" / "raw" / "pvgis" / f"profil_{MONTPELLIER.nom}.json"
PREVISIONS_M2 = RACINE / "reports" / "backtest" / "m2" / "previsions.csv"
PRIX_V1 = RACINE / "reports" / "pricing" / "v1" / "prix.csv"
DOSSIER = RACINE / "reports" / "pricing" / "monte_carlo"
ANNEE_LIVRAISON = 2027
ANNEES_CONTROLE = list(range(2018, 2026))
N_BOOTSTRAP = 2000
N_TIRAGES_ERREUR = 30
MOYENNE_BASELOAD = SCENARIOS_BASELOAD["central"]
SENSIBILITES = [(SIGMA_BASELOAD, CORRELATION_BASELOAD), (SIGMA_BASELOAD, 0.0), (0.17, CORRELATION_BASELOAD), (0.17, 0.0), (0.0, 0.0)]


def eur(x: float) -> str:
    """Montant arrondi à la centaine d'euros : la précision du Monte-Carlo ne permet pas mieux."""
    return f"{round(x, -2):,.0f}".replace(",", " ").replace("-", "−")


def prix(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def pct(x: float) -> str:
    return f"{x * 100:.1f}".replace(".", ",").replace("-", "−")


def erreurs_annuelles() -> pd.Series:
    """Erreur annuelle de M2 en backtest (prévision − réalisé), indexée par l'année."""
    p = pd.read_csv(PREVISIONS_M2)
    p = p[p["annee"].isin(ANNEES_CONTROLE)]
    annuels = taux_annuels(p.assign(modele_conditionnel=p["tc_m2"])).set_index("annee")
    return annuels["modele_conditionnel"] - annuels["taux_capture"]


def controle(horaire: pd.DataFrame, erreurs: pd.Series) -> pd.DataFrame:
    """Le taux de capture annuel national réalisé tombe-t-il dans l'intervalle à 90 %, sans puis avec l'erreur de modèle ?"""
    annuel = taux_de_capture(horaire, "Y")
    annuel = annuel[annuel["valide"]].set_index(annuel[annuel["valide"]]["periode"].dt.year)["taux_capture"]
    lignes = []
    for annee in ANNEES_CONTROLE:
        p = m2.calibrer_m2(horaire, annee)
        rng = np.random.default_rng([GRAINE, annee])
        ts = grille_annee(annee)
        y, q = m2.simuler_m2(p, ts, N_TRAJECTOIRES, rng)
        tc = taux_capture_annuel(y, q)
        connues = erreurs[erreurs.index < annee].to_numpy()
        ligne = {"annee": annee, "realise": annuel[annee], "bas": np.quantile(tc, 0.05), "mediane": np.median(tc), "haut": np.quantile(tc, 0.95), "n_erreurs": len(connues)}
        if len(connues) >= 2:
            avec = tc - rng.choice(connues - connues.mean(), N_TRAJECTOIRES)
            ligne |= {"bas_erreur": np.quantile(avec, 0.05), "haut_erreur": np.quantile(avec, 0.95)}
        lignes.append(ligne)
    return pd.DataFrame(lignes)


def main() -> None:
    horaire = charger_horaire(connexion(BASE)).merge(charger_eolien(BRUTS), on="ts_utc", how="left")
    mensuel = taux_de_capture(horaire, "M")
    p = calibrer_livraison(horaire, mensuel, ANNEE_LIVRAISON)
    volumes = volumes_par_annee(lire_profil(PROFIL))
    rng = np.random.default_rng([GRAINE, ANNEE_LIVRAISON])
    ts, y, q = simuler_livraison(p, volumes, N_TRAJECTOIRES, rng)
    tc_modele = taux_capture_annuel(y, q)
    aleas = rng.standard_normal(N_TRAJECTOIRES)
    baseload = tirer_baseload(tc_modele, aleas, MOYENNE_BASELOAD)
    erreurs = erreurs_annuelles()

    f = flux_contrats(y, q, baseload)
    tc = f.revenu / (f.volume * baseload)
    rng_erreur = deepcopy(rng)
    avec_erreur = revenu_avec_erreur(f.revenu, f.volume, baseload, erreurs.to_numpy(), rng)
    g = flux_contrats(y, q, baseload, revenu_realise=avec_erreur)

    lignes_csv = []
    for cote, sans, avec in (("vendeur", f.vendeur, g.vendeur), ("acheteur", f.acheteur, g.acheteur)):
        for contrat in sans:
            r, e = mesures_risque(sans[contrat]), mesures_risque(avec[contrat])
            lignes_csv.append({"contrat": contrat, "cote": cote, "moyenne": e["moyenne"], "ecart_type": e["ecart_type"], "var_95": e["var"], "cvar_95": e["cvar"], "var_95_sans_erreur": r["var"], "cvar_95_sans_erreur": r["cvar"], "correlation_baseload": float(np.corrcoef(avec[contrat], baseload)[0, 1])})
    contrats = pd.DataFrame(lignes_csv)
    DOSSIER.mkdir(parents=True, exist_ok=True)
    contrats.to_csv(DOSSIER / "contrats.csv", index=False, float_format="%.2f")

    amorce = np.random.default_rng([GRAINE, ANNEE_LIVRAISON, 1])
    indices = amorce.integers(N_TRAJECTOIRES, size=(N_BOOTSTRAP, N_TRAJECTOIRES))
    var_boot = np.array([mesures_risque(avec_erreur[i])["var"] for i in indices])
    prix_boot = f.revenu[indices].mean(axis=1) / f.volume[indices].mean(axis=1)

    v1 = pd.read_csv(PRIX_V1).set_index("scenario").loc["central"]
    a_b = f.prix[CONTRAT_PAP]
    a_b_fixe = flux_contrats(y, q, np.full(N_TRAJECTOIRES, MOYENNE_BASELOAD), ()).prix[CONTRAT_PAP]
    derniers = p.niveaux["solaire_mw"] / 1000

    lignes = [
        "# Monte-Carlo de pricing : livraison 2027",
        "",
        f"Généré le {pd.Timestamp.now(tz=FUSEAU_AFFICHAGE):%d/%m/%Y}. {N_TRAJECTOIRES} trajectoires, graine {GRAINE}. Choix et attentes : `docs/pricing.md`.",
        "",
        f"Site : Montpellier, 1 MWc, {f.volume.mean():.0f} MWh/an en moyenne. Baseload de moyenne {MOYENNE_BASELOAD:.0f} €/MWh, σ = {f"{SIGMA_BASELOAD:.2f}".replace(".", ",")}, corrélation de {f"{CORRELATION_BASELOAD:.2f}".replace(".", ",")} avec le taux de capture. "
        f"Solaire national de départ : {prix(derniers)} GW en moyenne. Fenêtre M2 : {min(p.formes)}–{max(p.formes)}.",
        "",
        "**Ce n'est pas un prix de contrat** : valeur de l'énergie au spot, avant garanties d'origine, équilibrage, crédit et marge. Montants arrondis à la centaine d'euros. Horizon d'un an : ce résultat ne s'étend pas à un PPA de 10 à 20 ans.",
        "",
        "## Prix justes",
        "",
        "| Contrat | Prix juste (€/MWh) |",
        "|---|---|",
        f"| **Pay-as-produced, Monte-Carlo** | **{prix(a_b)}** (erreur d'échantillonnage à 90 % : {prix(np.quantile(prix_boot, 0.05))} à {prix(np.quantile(prix_boot, 0.95))}) |",
        f"| Pay-as-produced, baseload fixé à {MOYENNE_BASELOAD:.0f} | {prix(a_b_fixe)} |",
        f"| Pay-as-produced, V1 | {prix(v1['prix_modele_eur_mwh'])} |",
        f"| Pay-as-produced, persistance | {prix(v1['prix_persistance_eur_mwh'])} |",
    ]
    for k in PLANCHERS:
        lignes.append(f"| Prime du plancher à {k:.0f} €/MWh | {prix(f.prix[nom_plancher(k)])} |")
    lignes += [
        f"| Ruban | {prix(f.prix[CONTRAT_RUBAN])} |",
        "",
        f"Taux de capture annuel du site : médiane de {pct(np.median(tc))} %, intervalle à 90 % de {pct(np.quantile(tc, 0.05))} à {pct(np.quantile(tc, 0.95))} %, avant erreur de modèle.",
        "",
        "## Risque par contrat (€/MWc sur l'année)",
        "",
        "VaR et CVaR à 95 %, pertes mesurées par rapport au flux moyen. Le chiffre principal inclut l'erreur de modèle. Pour le plancher, cette erreur ne modifie pas la valeur du put.",
        "",
        f"VaR du spot avec erreur de modèle, erreur d'échantillonnage à 90 % : {eur(np.quantile(var_boot, 0.05))} à {eur(np.quantile(var_boot, 0.95))} €.",
        "",
        "| Contrat | Côté | Flux moyen | Écart-type | VaR 95 % | CVaR 95 % | VaR sans erreur de modèle | Corrélation avec le baseload |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for _, c in contrats.iterrows():
        lignes.append(f"| {c['contrat']} | {c['cote']} | {eur(c['moyenne'])} | {eur(c['ecart_type'])} | **{eur(c['var_95'])}** | {eur(c['cvar_95'])} | {eur(c['var_95_sans_erreur'])} | {f'{c.correlation_baseload:+.2f}'.replace('.', ',').replace('-', '−')} |")

    parts = parts_variance(f.revenu, f.volume, baseload)
    figee = var_en_figeant(f.revenu, f.volume, baseload)
    entiere = mesures_risque(f.revenu)["var"]
    lignes += [
        "",
        "## D'où vient le risque du spot",
        "",
        "Sans erreur de modèle. Chaque source figée laisse la VaR des deux autres.",
        "",
        "| Source | Part de la variance de ln R | VaR en figeant cette source |",
        "|---|---|---|",
        f"| Baseload | {pct(parts['baseload'])} % | {eur(figee['baseload'])} |",
        f"| Taux de capture | {pct(parts['taux_capture'])} % | {eur(figee['taux_capture'])} |",
        f"| Volume | {pct(parts['volume'])} % | {eur(figee['volume'])} |",
        f"| Covariances | {pct(parts['covariances'])} % | — |",
        f"| Tout | 100 % | {eur(entiere)} |",
        "",
        "## Sensibilités du spot",
        "",
        "| σ du baseload | Corrélation | Prix juste (€/MWh) | VaR 95 %, sans erreur | VaR 95 %, avec erreur |",
        "|---|---|---|---|---|",
    ]
    for sigma, rho in SENSIBILITES:
        b = tirer_baseload(tc_modele, aleas, MOYENNE_BASELOAD, sigma, rho)
        s = flux_contrats(y, q, b, ())
        e = revenu_avec_erreur(s.revenu, s.volume, b, erreurs.to_numpy(), deepcopy(rng_erreur))
        lignes.append(f"| {f'{sigma:.2f}'.replace('.', ',')} | {f'{rho:.2f}'.replace('.', ',')} | {prix(s.prix[CONTRAT_PAP])} | {eur(mesures_risque(s.revenu)['var'])} | {eur(mesures_risque(e)['var'])} |")
    lignes += ["", "### Baseload fixé par scénario", "", "| Scénario | Baseload | Prix juste (€/MWh) | VaR 95 %, sans erreur | VaR 95 %, avec erreur |", "|---|---|---|---|---|"]
    for nom, niveau in SCENARIOS_BASELOAD.items():
        b = np.full(N_TRAJECTOIRES, niveau)
        s = flux_contrats(y, q, b, ())
        e = revenu_avec_erreur(s.revenu, s.volume, b, erreurs.to_numpy(), deepcopy(rng_erreur))
        lignes.append(f"| {nom} | {niveau:.0f} | {prix(s.prix[CONTRAT_PAP])} | {eur(mesures_risque(s.revenu)['var'])} | {eur(mesures_risque(e)['var'])} |")

    ctrl = controle(horaire, erreurs)
    ctrl.to_csv(DOSSIER / "controle.csv", index=False, float_format="%.5f")
    dedans = (ctrl["realise"] >= ctrl["bas"]) & (ctrl["realise"] <= ctrl["haut"])
    avec_e = ctrl.dropna(subset=["bas_erreur"])
    dedans_e = (avec_e["realise"] >= avec_e["bas_erreur"]) & (avec_e["realise"] <= avec_e["haut_erreur"])
    lignes += [
        "",
        "## Contrôle en walk-forward : taux de capture annuel national",
        "",
        f"Dans l'intervalle à 90 % de M2 : **{int(dedans.sum())} années sur {len(ctrl)}**, sans erreur de modèle. Avec les seules erreurs connues avant l'année : {int(dedans_e.sum())} sur {len(avec_e)}. Huit années ne valident pas une VaR : c'est un contrôle de bon sens, sans verdict.",
        "",
        "| Année | Réalisé | Médiane M2 | Intervalle sans erreur | Intervalle avec les erreurs connues |",
        "|---|---|---|---|---|",
    ]
    for _, r in ctrl.iterrows():
        inter = "—" if pd.isna(r.get("bas_erreur")) else f"{pct(r['bas_erreur'])} à {pct(r['haut_erreur'])}"
        lignes.append(f"| {int(r['annee'])} | {pct(r['realise'])} | {pct(r['mediane'])} | {pct(r['bas'])} à {pct(r['haut'])} | {inter} |")
    erreurs_trajectoires = ctrl.set_index("annee")["mediane"] - ctrl.set_index("annee")["realise"]
    baseload_fixe = np.full(N_TRAJECTOIRES, MOYENNE_BASELOAD)
    revenu_fixe = flux_contrats(y, q, baseload_fixe, ()).revenu
    lignes += [
        "",
        "## Après coup : l'erreur de modèle retenue était sous-estimée",
        "",
        "H17 mesure l'erreur annuelle avec le baseload et les volumes mensuels réalisés. Or le Monte-Carlo simule aussi quels mois sont chers : l'erreur à comparer se lit sur les trajectoires. "
        "Ce résultat vient après le lancement : il ne remplace pas le chiffre principal fixé d'avance, mais il dit que ce chiffre est trop faible.",
        "",
        "| Erreur annuelle (points) | " + " | ".join(str(a) for a in erreurs.index) + " | Écart-type |",
        "|---|" + "---|" * (len(erreurs) + 1),
        "| H17, mois réalisés | " + " | ".join(pct(v) for v in erreurs) + f" | {pct(erreurs.std())} |",
        "| Sur les trajectoires | " + " | ".join(pct(v) for v in erreurs_trajectoires) + f" | {pct(erreurs_trajectoires.std())} |",
        "",
        f"Moyenne sur {N_TIRAGES_ERREUR} tirages de l'erreur, sur le même jeu de trajectoires :",
        "",
        "| Erreur de modèle | VaR 95 % du spot | VaR 95 % à baseload fixé | Taux de capture du site, 5 % à 95 % |",
        "|---|---|---|---|",
    ]
    for nom, jeu in (("Aucune", None), ("H17, chiffre principal", erreurs), ("Mesurée sur les trajectoires", erreurs_trajectoires)):
        var_spot, var_fixe, taux = [], [], []
        for i in range(N_TIRAGES_ERREUR):
            r = np.random.default_rng([GRAINE, ANNEE_LIVRAISON, 100 + i])
            a = f.revenu if jeu is None else revenu_avec_erreur(f.revenu, f.volume, baseload, jeu.to_numpy(), r)
            b = revenu_fixe if jeu is None else revenu_avec_erreur(revenu_fixe, f.volume, baseload_fixe, jeu.to_numpy(), r)
            var_spot.append(mesures_risque(a)["var"])
            var_fixe.append(mesures_risque(b)["var"])
            taux.append(b / (f.volume * MOYENNE_BASELOAD))
        taux = np.concatenate(taux)
        lignes.append(f"| {nom} | {eur(np.mean(var_spot))} | {eur(np.mean(var_fixe))} | {pct(np.quantile(taux, 0.05))} à {pct(np.quantile(taux, 0.95))} % |")
    lignes.append("")
    texte = "\n".join(lignes)
    (DOSSIER / "rapport.md").write_text(texte)
    print(texte)


if __name__ == "__main__":
    main()
