"""Compare Energy-Charts à ENTSO-E et à RTE, et rejoue le backtest et le pricing en sensibilité.

Usage : ``.venv/bin/python scripts/comparer_sources.py``
Demande ``ENTSOE_API_KEY`` dans ``.env``. Écrit ``reports/donnees/comparaison_sources_FR.md``.
Ne modifie ni la base, ni le rapport de backtest, ni le rapport de pricing.
"""

from pathlib import Path

import pandas as pd

from ppa_pricer.analyse.capture import charger_horaire, taux_de_capture
from ppa_pricer.backtest.metriques import diebold_mariano, mae, skill_score
from ppa_pricer.backtest.walk_forward import backtest, echantillon_commun, taux_annuels
from ppa_pricer.donnees.base import connexion, lire_serie
from ppa_pricer.donnees.comparaison import (
    PART_MOIS_ORIGINE,
    SEUIL_ORIGINE_H,
    attribuer_origine,
    comparer_premier_quart,
    comparer_solaire,
    comparer_valeurs,
    horaire_variante,
)
from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE, controler_calage_solaire
from ppa_pricer.donnees.energy_charts import agreger_horaire
from ppa_pricer.donnees.entsoe import SERIES, AucuneDonnee, lire_annees, lire_cle, telecharger_annee
from ppa_pricer.donnees.pvgis import MONTPELLIER, lire_profil, telecharger_profil
from ppa_pricer.donnees.rte import lire_export, telecharger_export
from ppa_pricer.pricing.v1 import SCENARIOS_BASELOAD, baseload_mensuel, entrees_pricing, forme_baseload, prix_juste, volumes_mensuels

RACINE = Path(__file__).resolve().parents[1]
BASE = RACINE / "data" / "ppa.sqlite"
FICHIER_CLE = RACINE / ".env"
DOSSIER_ENTSOE = RACINE / "data" / "raw" / "entsoe"
DOSSIER_RTE = RACINE / "data" / "raw" / "rte"
DOSSIER_PVGIS = RACINE / "data" / "raw" / "pvgis"
RAPPORT = RACINE / "reports" / "donnees" / "comparaison_sources_FR.md"
PREMIERE_ANNEE = 2015
ANNEES_OFFICIELLES = list(range(2018, 2026))
ANNEES_TC = [2023, 2024, 2025]
ANNEE_LIVRAISON = 2027


def nb(x: float, decimales: int = 2) -> str:
    return "n.d." if pd.isna(x) else f"{x:.{decimales}f}".replace(".", ",")


def signe(x: float, decimales: int = 2) -> str:
    return "n.d." if pd.isna(x) else f"{x:+.{decimales}f}".replace(".", ",")


def en_horaire(serie: pd.DataFrame, colonne: str) -> pd.Series:
    """Une colonne d'une série d'origine, au pas horaire, indexée par ``ts_utc``."""
    return agreger_horaire(serie[["ts_utc", "duree_min", colonne]]).set_index("ts_utc")[colonne]


def bilan_variante(horaire: pd.DataFrame, volumes: pd.Series) -> dict:
    """Backtest 2018–2025 et prix central 2027 pour une variante de données."""
    mensuel = taux_de_capture(horaire, "M")
    previsions, _ = backtest(mensuel, ANNEES_OFFICIELLES)
    commun = echantillon_commun(previsions)
    e_m, e_r1 = commun["modele_realiste"] - commun["taux_capture"], commun["r1_persistance"] - commun["taux_capture"]
    e_r2 = commun["r2_climatologie"] - commun["taux_capture"]
    dm = diebold_mariano(e_m, e_r1)
    annuels = taux_annuels(previsions).set_index("annee")
    entrees, parametres = entrees_pricing(mensuel, ANNEE_LIVRAISON)
    baseload = baseload_mensuel(SCENARIOS_BASELOAD["central"], forme_baseload(mensuel), ANNEE_LIVRAISON)
    return {
        "n_mois": len(commun),
        "mae": mae(e_m) * 100,
        "mae_r1": mae(e_r1) * 100,
        "mae_r2": mae(e_r2) * 100,
        "skill_r1": skill_score(mae(e_m), mae(e_r1)),
        "skill_r2": skill_score(mae(e_m), mae(e_r2)),
        "p_r1": dm.p_valeur,
        "tc": {a: annuels["taux_capture"].get(a, float("nan")) * 100 for a in ANNEES_TC},
        "prix_modele": prix_juste(entrees["tc_modele"], baseload, volumes),
        "prix_persistance": prix_juste(entrees["tc_persistance"], baseload, volumes),
        "beta": parametres.beta,
    }


def construire_rapport(horaire, solaire_ec, entsoe, rte, natif_entsoe, natif_rte, doublons, doublons_rte, manquants, volumes) -> str:
    """Texte du rapport à partir des séries déjà lues (voir ``main``)."""
    signales = controler_calage_solaire(solaire_ec)
    mois_signales = list(signales.loc[signales["calage_suspect"], "periode"])
    ec_solaire = horaire.set_index("ts_utc")["solaire_mw"]
    ec_prix = horaire.set_index("ts_utc")["prix_eur_mwh"]
    ec_conso = horaire.set_index("ts_utc")["conso_mw"]

    vs_entsoe = comparer_solaire(ec_solaire, entsoe["solaire"])
    vs_rte = comparer_solaire(ec_solaire, rte["solaire"])
    verdict = attribuer_origine(vs_entsoe, mois_signales)
    conclusion = (
        "**Le décalage vient de la source** : il est déjà présent chez ENTSO-E ou en amont."
        if verdict["origine"] == "source"
        else "**Le décalage apparaît après ENTSO-E** : les deux séries divergent sur trop de mois signalés."
    )

    lignes = [
        "# Comparaison des sources : Energy-Charts, ENTSO-E et RTE",
        "",
        f"Généré le {pd.Timestamp.now(tz=FUSEAU_AFFICHAGE):%d/%m/%Y}. Règle et choix : `docs/perimetre.md` et "
        "`docs/donnees.md`. Tous les écarts sont calculés sur les heures communes à deux sources. Ce rapport ne "
        "change ni le verdict ni les données officielles de la V1.",
        "",
        "## Origine du décalage du solaire",
        "",
        f"Règle figée avant de voir les données : écart d'heure moyenne Energy-Charts − ENTSO-E d'au plus "
        f"{nb(SEUIL_ORIGINE_H, 1)} h sur au moins {PART_MOIS_ORIGINE:.0%} des mois signalés.".replace(".", ",", 0),
        "",
        f"Résultat : **{verdict['n_proches']} mois sur {verdict['n_signales']}** ({nb(verdict['part'] * 100, 0)} %). {conclusion}",
        "",
        "| Mois signalé | Energy-Charts (h UTC) | ENTSO-E (h UTC) | Écart EC − ENTSO-E (h) | Retard EC / ENTSO-E (h) "
        "| Énergie EC / ENTSO-E | RTE (h UTC) | Écart EC − RTE (h) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    e = vs_entsoe.set_index("periode")
    r = vs_rte.set_index("periode")
    for mois in mois_signales:
        ligne_e = e.loc[mois] if mois in e.index else None
        ligne_r = r.loc[mois] if mois in r.index else None
        lignes.append(
            f"| {mois} | {nb(ligne_e['heure_a']) if ligne_e is not None else 'n.d.'} "
            f"| {nb(ligne_e['heure_b']) if ligne_e is not None else 'n.d.'} "
            f"| {signe(ligne_e['ecart_h']) if ligne_e is not None else 'n.d.'} "
            f"| {signe(ligne_e['retard_h'], 0) if ligne_e is not None else 'n.d.'} "
            f"| {nb(ligne_e['rapport_energie']) if ligne_e is not None else 'n.d.'} "
            f"| {nb(ligne_r['heure_b']) if ligne_r is not None else 'n.d.'} "
            f"| {signe(ligne_r['ecart_h']) if ligne_r is not None else 'n.d.'} |"
        )

    lignes += [
        "",
        "Ce résultat mêle deux anomalies distinctes : voir la dernière section du rapport.",
        "",
        "## Solaire : les trois sources par année",
        "",
        "Écart d'heure moyenne et rapport d'énergie, Energy-Charts rapporté à chaque source.",
        "",
        "| Année | Écart EC − ENTSO-E, moyen (h) | Énergie EC / ENTSO-E | Écart EC − RTE, moyen (h) | Énergie EC / RTE |",
        "|---|---|---|---|---|",
    ]
    annee_e = vs_entsoe.groupby(vs_entsoe["periode"].dt.year)
    annee_r = vs_rte.groupby(vs_rte["periode"].dt.year)
    energie_e = comparer_valeurs(ec_solaire, entsoe["solaire"]).set_index("periode")
    energie_r = comparer_valeurs(ec_solaire, rte["solaire"]).set_index("periode")
    for annee in range(PREMIERE_ANNEE, pd.Timestamp.now(tz="UTC").year + 1):
        p = pd.Period(str(annee), "Y")
        lignes.append(
            f"| {annee} | {signe(annee_e['ecart_h'].mean().get(annee, float('nan')))} "
            f"| {nb(energie_e['moyenne_a'].get(p, float('nan')) / energie_e['moyenne_b'].get(p, float('nan')))} "
            f"| {signe(annee_r['ecart_h'].mean().get(annee, float('nan')))} "
            f"| {nb(energie_r['moyenne_a'].get(p, float('nan')) / energie_r['moyenne_b'].get(p, float('nan')))} |"
        )

    lignes += [
        "",
        "## Contrôle de calage appliqué à chaque source",
        "",
        "| Source | Mois contrôlés | Calage suspect | Production de nuit |",
        "|---|---|---|---|",
    ]
    for nom, natif in [("Energy-Charts", solaire_ec), ("ENTSO-E", natif_entsoe), ("RTE", natif_rte)]:
        c = controler_calage_solaire(natif)
        lignes.append(f"| {nom} | {len(c)} | {int(c['calage_suspect'].sum())} | {int(c['nuit_suspecte'].sum())} |")

    lignes += ["", "## Prix day-ahead : Energy-Charts et ENTSO-E", "",
               "| Année | Heures communes | Baseload EC (€/MWh) | Baseload ENTSO-E (€/MWh) | Écart absolu moyen | Écart absolu max "
               "| Heures différentes |", "|---|---|---|---|---|---|---|"]
    for l in comparer_valeurs(ec_prix, entsoe["prix"]).itertuples():
        lignes.append(
            f"| {l.periode} | {l.heures_communes} | {nb(l.moyenne_a)} | {nb(l.moyenne_b)} | {nb(l.ecart_absolu_moyen, 3)} "
            f"| {nb(l.ecart_absolu_max, 3)} | {l.heures_differentes} |"
        )
    mensuel_prix = comparer_valeurs(ec_prix, entsoe["prix"], "M")
    recents = mensuel_prix[mensuel_prix["periode"] >= pd.Period("2026-07", "M")]
    lignes += ["", "Mois récents, dont les prix élevés d'août et septembre 2026 :", "",
               "| Mois | Baseload EC (€/MWh) | Baseload ENTSO-E (€/MWh) | Écart absolu max |", "|---|---|---|---|"]
    for l in recents.itertuples():
        lignes.append(f"| {l.periode} | {nb(l.moyenne_a)} | {nb(l.moyenne_b)} | {nb(l.ecart_absolu_max, 3)} |")

    lignes += ["", "## Consommation : Energy-Charts rapporté aux deux autres sources", "",
               "| Année | Conso EC / ENTSO-E | Écart absolu moyen (MW) | Conso EC / RTE | Écart absolu moyen (MW) |", "|---|---|---|---|---|"]
    conso_e = comparer_valeurs(ec_conso, entsoe["conso"]).set_index("periode")
    conso_r = comparer_valeurs(ec_conso, rte["conso"]).set_index("periode")
    for p in conso_e.index.union(conso_r.index):
        lignes.append(
            f"| {p} | {nb(conso_e['moyenne_a'].get(p, float('nan')) / conso_e['moyenne_b'].get(p, float('nan')), 3)} "
            f"| {nb(conso_e['ecart_absolu_moyen'].get(p, float('nan')), 0)} "
            f"| {nb(conso_r['moyenne_a'].get(p, float('nan')) / conso_r['moyenne_b'].get(p, float('nan')), 3)} "
            f"| {nb(conso_r['ecart_absolu_moyen'].get(p, float('nan')), 0)} |"
        )

    variantes = {
        "Officiel (Energy-Charts)": horaire,
        "Solaire ENTSO-E": horaire_variante(horaire, solaire_mw=entsoe["solaire"]),
        "Tout ENTSO-E": horaire_variante(horaire, solaire_mw=entsoe["solaire"], conso_mw=entsoe["conso"], prix_eur_mwh=entsoe["prix"]),
        "Solaire RTE": horaire_variante(horaire, solaire_mw=rte["solaire"]),
    }
    lignes += ["", "## Rejeu du backtest et du pricing, à titre de sensibilité", "",
               "Une heure absente d'une source reste inconnue : on ne complète jamais avec Energy-Charts. Le prix est celui du "
               f"scénario central, livraison {ANNEE_LIVRAISON}, site de Montpellier.", "",
               "| Variante | Mois | MAE modèle | MAE R1 | MAE R2 | Skill R1 | Skill R2 | p DM R1 | TC 2023 | TC 2024 | TC 2025 "
               "| β | Prix modèle | Prix persistance |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for nom, h in variantes.items():
        try:
            b = bilan_variante(h, volumes)
        except ValueError as erreur:
            lignes.append(f"| {nom} | non calculable : {erreur} |" + " |" * 12)
            continue
        lignes.append(
            f"| {nom} | {b['n_mois']} | {nb(b['mae'])} | {nb(b['mae_r1'])} | {nb(b['mae_r2'])} | {signe(b['skill_r1'])} | {signe(b['skill_r2'])} "
            f"| {nb(b['p_r1'], 3)} | {nb(b['tc'][2023])} | {nb(b['tc'][2024])} | {nb(b['tc'][2025])} | {nb(b['beta'])} "
            f"| {nb(b['prix_modele'], 1)} | {nb(b['prix_persistance'], 1)} |"
        )

    lignes += ["", "## Couverture et doublons", ""]
    lignes += [f"- {serie} ENTSO-E : {n} doublons retirés" for serie, n in doublons.items()]
    lignes += [f"- {serie} ENTSO-E {annee} : aucune donnée renvoyée" for serie, annee in manquants]
    lignes.append(f"- RTE : {doublons_rte} points en double, heures concernées laissées inconnues")
    return "\n".join(lignes) + "\n"


def section_deux_anomalies(horaire: pd.DataFrame, natifs: dict[str, pd.DataFrame], entsoe: dict[str, pd.Series], rte: dict[str, pd.Series]) -> str:
    """Analyse écrite après le résultat de la règle : les mois signalés relèvent de deux anomalies distinctes."""
    ec = horaire.set_index("ts_utc")
    lignes = [
        "",
        "## Après coup : deux anomalies distinctes",
        "",
        "La règle supposait une seule cause. Ses 20 mois en mêlent deux, ce qu'elle ne pouvait pas dire. Cette section est écrite après son résultat.",
        "",
        "**2025 : Energy-Charts garde le premier quart d'heure.** ENTSO-E passe au quart d'heure fin 2024, mais les fichiers Energy-Charts restent horaires jusqu'à fin 2025. Une valeur horaire est alors centrée sur h + 7,5 min au lieu de h + 30 min : la courbe semble 0,375 h trop tard.",
        "",
        "| Série, 2025 | Heures | Égale au premier quart d'heure | Égale à la moyenne de l'heure | Écart absolu moyen à la moyenne (MW) |",
        "|---|---|---|---|---|",
    ]
    for serie, colonne in (("solaire", "solaire_mw"), ("conso", "conso_mw")):
        natif = natifs[serie].set_index("ts_utc")["valeur"]
        periode = ec.loc["2025-01-01":"2025-12-31 22:00", colonne]
        r = comparer_premier_quart(periode, natif)
        lignes.append(f"| {serie} | {r['heures']} | {r['part_premier_quart'] * 100:.2f} % | {r['part_moyenne'] * 100:.2f} % | {r['ecart_absolu_moyenne_mw']:.0f} |".replace(".", ","))
    face_entsoe = comparer_solaire(ec["solaire_mw"], entsoe["solaire"]).set_index("periode")
    face_rte = comparer_solaire(ec["solaire_mw"], rte["solaire"]).set_index("periode")
    lignes += [
        "",
        "**2023–2024 : l'anomalie est déjà dans ENTSO-E.** Energy-Charts égale ENTSO-E, et les deux divergent de RTE. Un retard positif signifie qu'Energy-Charts est en retard sur RTE.",
        "",
        "| Mois | Écart EC − ENTSO-E (h) | Écart EC − RTE (h) | Meilleur retard face à RTE (h) | Corrélation à 0 h, face à RTE |",
        "|---|---|---|---|---|",
    ]
    for mois in pd.period_range("2023-08", "2024-04", freq="M"):
        lignes.append(
            f"| {mois} | {face_entsoe.loc[mois, 'ecart_h']:+.2f} | {face_rte.loc[mois, 'ecart_h']:+.2f} | {int(face_rte.loc[mois, 'retard_h']):+d} | {face_rte.loc[mois, 'correlation']:.3f} |".replace(".", ",")
        )
    lignes.append("")
    return "\n".join(lignes)


def main() -> None:
    cle = lire_cle(FICHIER_CLE)
    manquants = []
    for serie in SERIES:
        for annee in range(PREMIERE_ANNEE, pd.Timestamp.now(tz="UTC").year + 1):
            try:
                telecharger_annee(serie, annee, DOSSIER_ENTSOE, cle)
            except AucuneDonnee:
                manquants.append((serie, annee))

    con = connexion(BASE)
    horaire = charger_horaire(con)
    solaire_ec = lire_serie(con, "production_conso", zone="FR")

    doublons, entsoe, natifs = {}, {}, {}
    for serie in SERIES:
        brut = lire_annees(DOSSIER_ENTSOE, serie)
        doublons[serie] = int(brut["ts_utc"].duplicated().sum())
        natifs[serie] = brut.drop_duplicates("ts_utc", ignore_index=True)
        entsoe[serie] = en_horaire(natifs[serie], "valeur")
    natif_entsoe = natifs["solaire"].rename(columns={"valeur": "solaire_mw"})

    natif_rte = lire_export(telecharger_export(DOSSIER_RTE))
    doublons_rte = int(natif_rte["ts_utc"].duplicated().sum())
    rte = {"solaire": en_horaire(natif_rte, "solaire_mw"), "conso": en_horaire(natif_rte, "conso_mw")}

    volumes = volumes_mensuels(lire_profil(telecharger_profil(MONTPELLIER, DOSSIER_PVGIS)))
    texte = construire_rapport(horaire, solaire_ec, entsoe, rte, natif_entsoe, natif_rte, doublons, doublons_rte, manquants, volumes)
    texte += section_deux_anomalies(horaire, natifs, entsoe, rte)
    RAPPORT.write_text(texte)
    print(texte)


if __name__ == "__main__":
    main()
