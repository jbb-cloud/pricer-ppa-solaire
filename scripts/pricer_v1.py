"""Prix juste d'un PPA solaire pay-as-produced pour l'année suivante (voir `docs/pricing.md`).

Usage : ``.venv/bin/python scripts/pricer_v1.py``
Écrit dans ``reports/pricing/v1/`` : ``rapport.md``, ``prix.csv``, ``detail_mensuel.csv``.
Ne modifie ni la base ni le rapport de backtest.
"""

from pathlib import Path

import pandas as pd

from ppa_pricer.analyse.capture import charger_horaire, taux_de_capture
from ppa_pricer.backtest.metriques import mae
from ppa_pricer.backtest.walk_forward import backtest, echantillon_commun, taux_annuels
from ppa_pricer.donnees.base import connexion
from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE
from ppa_pricer.donnees.pvgis import MONTPELLIER, inclinaison_optimale, lire_profil, telecharger_profil
from ppa_pricer.modele.v1 import MOIS, derniers_douze_mois, prevoir
from ppa_pricer.pricing.v1 import (
    ANNEES_FORME,
    SCENARIOS_BASELOAD,
    baseload_mensuel,
    entrees_pricing,
    forme_baseload,
    prix_juste,
    revenu_annuel,
    taux_capture_formule,
    taux_capture_site,
    volumes_mensuels,
)

RACINE = Path(__file__).resolve().parents[1]
BASE = RACINE / "data" / "ppa.sqlite"
DOSSIER_PVGIS = RACINE / "data" / "raw" / "pvgis"
DOSSIER = RACINE / "reports" / "pricing" / "v1"
ANNEE_LIVRAISON = 2027
SITE = MONTPELLIER
SCENARIO_DETAIL = "central"
CROISSANCES = [1.0, 1.1, 1.2, 1.3, 1.4]
ANNEES_ERREURS = [2023, 2024, 2025]
NOMS_MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def nb(x: float, decimales: int = 1) -> str:
    """Nombre à virgule française."""
    return f"{x:.{decimales}f}".replace(".", ",")


def signe(x: float, decimales: int = 1) -> str:
    return f"{x:+.{decimales}f}".replace(".", ",")


def entier(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


def main() -> None:
    horaire = charger_horaire(connexion(BASE))
    mensuel = taux_de_capture(horaire, "M")
    chemin_profil = telecharger_profil(SITE, DOSSIER_PVGIS)
    profil = lire_profil(chemin_profil)
    volumes = volumes_mensuels(profil)

    entrees, parametres = entrees_pricing(mensuel, ANNEE_LIVRAISON)
    forme = forme_baseload(mensuel)
    base, precedents = derniers_douze_mois(mensuel)
    croissance = base["energie_solaire_mwh"].sum() / precedents["energie_solaire_mwh"].sum()

    lignes_prix = []
    for scenario, niveau in SCENARIOS_BASELOAD.items():
        b = baseload_mensuel(niveau, forme, ANNEE_LIVRAISON)
        modele = prix_juste(entrees["tc_modele"], b, volumes)
        persistance = prix_juste(entrees["tc_persistance"], b, volumes)
        lignes_prix.append(
            {
                "scenario": scenario,
                "baseload_eur_mwh": niveau,
                "prix_modele_eur_mwh": modele,
                "tc_implicite_modele": modele / niveau,
                "revenu_modele_eur_par_mwc": revenu_annuel(modele, volumes),
                "prix_persistance_eur_mwh": persistance,
                "tc_implicite_persistance": persistance / niveau,
                "revenu_persistance_eur_par_mwc": revenu_annuel(persistance, volumes),
            }
        )
    prix = pd.DataFrame(lignes_prix)

    baseload_detail = baseload_mensuel(SCENARIOS_BASELOAD[SCENARIO_DETAIL], forme, ANNEE_LIVRAISON)
    detail = entrees.assign(volume_mwh=volumes, baseload_eur_mwh=baseload_detail).rename_axis("mois").reset_index()

    DOSSIER.mkdir(parents=True, exist_ok=True)
    prix.to_csv(DOSSIER / "prix.csv", index=False, float_format="%.4f")
    detail.to_csv(DOSSIER / "detail_mensuel.csv", index=False, float_format="%.5f")

    derniere_donnee = horaire.dropna()["ts_utc"].max().tz_convert(FUSEAU_AFFICHAGE)
    annees_profil = profil["ts_utc"].dt.year
    lignes = [
        f"# Pricing V1 : PPA pay-as-produced, livraison {ANNEE_LIVRAISON}",
        "",
        f"Généré le {pd.Timestamp.now(tz=FUSEAU_AFFICHAGE):%d/%m/%Y} ; données jusqu'au "
        f"{derniere_donnee:%d/%m/%Y %H:%M}. Choix : `docs/pricing.md`.",
        "",
        f"Site : {SITE.nom.capitalize()} ({nb(SITE.latitude, 2)} N, {nb(SITE.longitude, 2)} E), 1 MWc, plein sud, "
        f"inclinaison {nb(inclinaison_optimale(chemin_profil), 0)}°, pertes {nb(SITE.pertes_pct, 0)} %. "
        f"Volume : moyenne PVGIS {annees_profil.min()}–{annees_profil.max()}, soit "
        f"{entier(volumes.sum())} MWh/MWc par an.",
        "",
        "**Ce n'est pas un prix de contrat** : c'est la valeur de l'énergie au spot, avant garanties d'origine, "
        "coûts d'équilibrage, risque de crédit et marge, avec le taux de capture national (H2) et une production "
        "payée même à prix négatif (H3).",
        "",
        "## Prix juste par scénario de baseload",
        "",
        "| Scénario | Baseload (€/MWh) | Modèle V1 (€/MWh) | Taux implicite | Persistance (€/MWh) | Taux implicite "
        "| Revenu modèle (€/MWc) | Revenu persistance (€/MWc) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for l in prix.itertuples():
        lignes.append(
            f"| {l.scenario} | {nb(l.baseload_eur_mwh, 0)} | **{nb(l.prix_modele_eur_mwh)}** "
            f"| {nb(l.tc_implicite_modele * 100)} % | **{nb(l.prix_persistance_eur_mwh)}** "
            f"| {nb(l.tc_implicite_persistance * 100)} % | {entier(l.revenu_modele_eur_par_mwc)} "
            f"| {entier(l.revenu_persistance_eur_par_mwc)} |"
        )

    volumes_nationaux = base.set_index(base["periode"].dt.month)["energie_solaire_mwh"].reindex(list(MOIS))
    part_janvier = volumes[1] / volumes.sum()
    part_janvier_nationale = volumes_nationaux[1] / volumes_nationaux.sum()
    b_central = baseload_mensuel(SCENARIOS_BASELOAD["central"], forme, ANNEE_LIVRAISON)
    lignes += [
        "",
        f"Effet du profil du site : avec les volumes nationaux des 12 derniers mois, le prix central serait de "
        f"{nb(prix_juste(entrees['tc_modele'], b_central, volumes_nationaux))} €/MWh pour le modèle et "
        f"{nb(prix_juste(entrees['tc_persistance'], b_central, volumes_nationaux))} €/MWh pour la persistance. "
        f"Le site produit plus en hiver (janvier : {nb(part_janvier * 100)} % de son volume, contre "
        f"{nb(part_janvier_nationale * 100)} % au national), quand le baseload et le taux de capture sont élevés.",
    ]

    lignes += [
        "",
        f"## Détail mensuel, scénario {SCENARIO_DETAIL}",
        "",
        f"Part du solaire prévue = part des 12 derniers mois valides ({base['periode'].iloc[0]} à "
        f"{base['periode'].iloc[-1]}) × {nb(croissance, 3)}. Forme du baseload : moyenne "
        f"{ANNEES_FORME[0]}–{ANNEES_FORME[-1]}.",
        "",
        "| Mois | Volume (MWh) | Baseload (€/MWh) | Part de base | Part prévue | Taux modèle | Taux persistance |",
        "|---|---|---|---|---|---|---|",
    ]
    for l in detail.itertuples():
        lignes.append(
            f"| {NOMS_MOIS[l.mois - 1]} | {nb(l.volume_mwh, 0)} | {nb(l.baseload_eur_mwh)} "
            f"| {nb(l.part_solaire_base * 100)} % | {nb(l.part_solaire_prevue * 100)} % "
            f"| {nb(l.tc_modele * 100)} % | {nb(l.tc_persistance * 100)} % |"
        )

    mois = pd.Series(list(MOIS), index=list(MOIS))
    lignes += [
        "",
        f"## Sensibilité à la croissance du solaire, modèle V1, scénario {SCENARIO_DETAIL}",
        "",
        "| Croissance appliquée | Prix (€/MWh) | Taux implicite | Taux mensuel le plus bas |",
        "|---|---|---|---|",
    ]
    for g in CROISSANCES:
        tc = prevoir(parametres, mois, entrees["part_solaire_base"] * g)
        p = prix_juste(tc, baseload_detail, volumes)
        lignes.append(
            f"| {signe((g - 1) * 100, 0)} % | {nb(p)} | {nb(p / SCENARIOS_BASELOAD[SCENARIO_DETAIL] * 100)} % "
            f"| {nb(tc.min() * 100)} % ({NOMS_MOIS[tc.idxmin() - 1]}) |"
        )

    previsions, _ = backtest(mensuel, [*ANNEES_ERREURS, 2026])
    annuels = taux_annuels(previsions[previsions["annee"].isin(ANNEES_ERREURS)])
    baseload_central = SCENARIOS_BASELOAD[SCENARIO_DETAIL]
    lignes += [
        "",
        "## Erreurs passées sur le taux de capture annuel",
        "",
        f"Prévision − réalisé, en points (backtest V1), et leur équivalent à un baseload de {nb(baseload_central, 0)} €/MWh. "
        "Un point positif signifie un prix trop élevé.",
        "",
        "| Année | Modèle (points) | Modèle (€/MWh) | Persistance (points) | Persistance (€/MWh) |",
        "|---|---|---|---|---|",
    ]
    for _, a in annuels.iterrows():
        e_m, e_r = a["modele_realiste"] - a["taux_capture"], a["r1_persistance"] - a["taux_capture"]
        lignes.append(
            f"| {int(a['annee'])} | {signe(e_m * 100)} | {signe(e_m * baseload_central)} "
            f"| {signe(e_r * 100)} | {signe(e_r * baseload_central)} |"
        )
    a_part = echantillon_commun(previsions[previsions["annee"] == 2026])
    lignes += [
        "",
        f"Sur les {len(a_part)} mois valides de 2026, l'erreur mensuelle moyenne vaut "
        f"{nb(mae(a_part['modele_realiste'] - a_part['taux_capture']) * 100)} points pour le modèle et "
        f"{nb(mae(a_part['r1_persistance'] - a_part['taux_capture']) * 100)} pour la persistance.",
    ]

    national = taux_de_capture(horaire, "Y").set_index("periode")["taux_capture"]
    site = taux_capture_site(horaire, profil).set_index("periode")["taux_capture"]
    formule = taux_capture_formule(mensuel, volumes)
    annees_communes = [p for p in site.index if p.year in formule.index]
    ecarts = pd.Series([formule[p.year] - site[p] for p in annees_communes])
    lignes += [
        "",
        "## Erreur de l'hypothèse H2 : formule du pricing et taux réel du site",
        "",
        "*Site réel* : prix réels et série PVGIS de l'année. *Formule V1* : taux national de chaque mois et volumes "
        f"moyens du site, comme dans le pricing. Écart absolu moyen : {nb(mae(ecarts) * 100)} point. Les données PVGIS "
        "s'arrêtent avant le régime récent, le plus cannibalisé : ce contrôle ne valide pas H2 pour 2027.",
        "",
        "| Année | National | Site réel | Formule V1 | Écart formule − site (points) |",
        "|---|---|---|---|---|",
    ]
    for p, ecart in zip(annees_communes, ecarts):
        lignes.append(
            f"| {p} | {nb(national[p] * 100)} % | {nb(site[p] * 100)} % | {nb(formule[p.year] * 100)} % "
            f"| {signe(ecart * 100)} |"
        )

    lignes += [
        "",
        "## Paramètres du modèle",
        "",
        f"Calibration sur {parametres.n_mois} mois valides, β = {nb(parametres.beta, 2)}.",
        "",
    ]
    texte = "\n".join(lignes)
    (DOSSIER / "rapport.md").write_text(texte)
    print(texte)


if __name__ == "__main__":
    main()
