"""Audit A3 : une prévision change-t-elle si on remplace tout ce qui suit la date de coupure par des valeurs absurdes ?

Usage : ``.venv/bin/python scripts/audit_fuites.py``. Écrit ``reports/audit/fuites.md``. Ne modifie ni la base ni les autres rapports.
Les tests unitaires font déjà ce contrôle sur des données synthétiques ; celui-ci le fait sur les vraies données, de bout en bout.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ppa_pricer.analyse.capture import charger_horaire, periodes_paris, taux_de_capture
from ppa_pricer.backtest.walk_forward import prevoir_annee
from ppa_pricer.donnees.base import connexion
from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE
from ppa_pricer.donnees.energy_charts import charger_eolien
from ppa_pricer.modele import m0, m1, m2
from ppa_pricer.pricing.monte_carlo import calibrer_livraison
from ppa_pricer.pricing.v1 import entrees_pricing

RACINE = Path(__file__).resolve().parents[1]
BASE = RACINE / "data" / "ppa.sqlite"
BRUTS = RACINE / "data" / "raw" / "energy_charts"
SORTIE = RACINE / "reports" / "audit" / "fuites.md"
ANNEES = [2018, 2020, 2024, 2025, 2026]
COLONNES = ["prix_eur_mwh", "solaire_mw", "conso_mw", "eolien_mw"]
VALEUR_ABSURDE = 99_999.0
N = 40
COLONNES_V1 = ["modele_realiste", "r1_persistance", "r2_climatologie"]


def perturber(horaire: pd.DataFrame, debut: pd.Timestamp) -> pd.DataFrame:
    """Remplace par une valeur absurde toutes les valeurs connues à partir de ``debut``."""
    p = horaire.copy()
    apres = p["ts_utc"] >= debut
    p.loc[apres, COLONNES] = p.loc[apres, COLONNES].where(p.loc[apres, COLONNES].isna(), VALEUR_ABSURDE)
    return p


def main() -> None:
    horaire = charger_horaire(connexion(BASE)).merge(charger_eolien(BRUTS), on="ts_utc", how="left")
    mensuel = taux_de_capture(horaire, "M")
    lignes = ["# Audit A3 : fuites de données", "", f"Toutes les valeurs à partir du 1er janvier de l'année testée sont remplacées par {VALEUR_ABSURDE:.0f}. Identique = la prévision ne change pas d'un bit.", "",
              "| Année | V1 et références | M0 | M1 | M2 | M2, paramètres |", "|---|---|---|---|---|---|"]
    fuites = 0
    for annee in ANNEES:
        debut = pd.Timestamp(f"{annee}-01-01", tz=FUSEAU_AFFICHAGE).tz_convert("UTC")
        p = perturber(horaire, debut)
        mp = taux_de_capture(p, "M")
        a, b = prevoir_annee(mensuel, annee)[0], prevoir_annee(mp, annee)[0]
        v1 = a[COLONNES_V1].round(10).equals(b[COLONNES_V1].round(10))
        r0 = m0.prevoir_m0(horaire, annee, n=N)[0].equals(m0.prevoir_m0(p, annee, n=N)[0])
        r1 = m1.prevoir_m1(horaire, annee, n=N)[0].equals(m1.prevoir_m1(p, annee, n=N)[0])
        pm2, qm2 = m2.prevoir_m2(horaire, annee, n=N), m2.prevoir_m2(p, annee, n=N)
        r2 = pm2[0].equals(qm2[0])
        param = pm2[1].poids_charge == qm2[1].poids_charge and np.array_equal(pm2[1].croissances, qm2[1].croissances) and pm2[1].niveaux.equals(qm2[1].niveaux)
        fuites += sum(not x for x in (v1, r0, r1, r2, param))
        lignes.append(f"| {annee} | {'identique' if v1 else '**DIFFÉRENT**'} | {'identique' if r0 else '**DIFFÉRENT**'} | {'identique' if r1 else '**DIFFÉRENT**'} | {'identique' if r2 else '**DIFFÉRENT**'} | {'identique' if param else '**DIFFÉRENT**'} |")

    # Livraison 2027 : seuls les 12 derniers mois valides doivent compter. Octobre 2026, incomplet, ne doit rien changer.
    base = mensuel[mensuel["valide"]]["periode"].max()
    debut = (base + 1).start_time.tz_localize(FUSEAU_AFFICHAGE).tz_convert("UTC")
    p = perturber(horaire, debut)
    mp = taux_de_capture(p, "M")
    e0, e1 = entrees_pricing(mensuel, 2027)[0], entrees_pricing(mp, 2027)[0]
    l0, l1 = calibrer_livraison(horaire, mensuel, 2027), calibrer_livraison(p, mp, 2027)
    v = e0.equals(e1)
    l = l0.niveaux.equals(l1.niveaux) and l0.poids_charge == l1.poids_charge and np.array_equal(l0.croissances, l1.croissances)
    fuites += sum(not x for x in (v, l))
    lignes += ["", f"## Livraison 2027", "", f"Dernier mois valide : {base}. Valeurs perturbées à partir du mois suivant. Pricing V1 : {'identique' if v else '**DIFFÉRENT**'}. M2 pour le Monte-Carlo : {'identique' if l else '**DIFFÉRENT**'}.", "",
               f"**Bilan : {fuites} fuite(s) détectée(s).**", ""]
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    texte = "\n".join(lignes)
    SORTIE.write_text(texte)
    print(texte)


if __name__ == "__main__":
    main()
