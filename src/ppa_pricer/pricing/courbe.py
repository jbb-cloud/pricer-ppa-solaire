"""Courbe à terme publiée et scénarios de parc solaire, pour ancrer le pricing V2.

La cotation d'un contrat calendaire donne le niveau et celle des trimestres la forme, sans parier sur l'historique. Une cotation n'est pas une espérance physique : elle
peut contenir une prime de risque, et elle bouge vite. Le fichier est daté et sourcé (H19, H20). Détails dans `docs/pricing.md`.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ppa_pricer.analyse.capture import heures_calendaires
from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE
from ppa_pricer.modele.v1 import MOIS

PARC_BASE_GW = 32.5
SCENARIOS_PARC_GW = {"Rythme de la PPE3": 37.6, "Rythme récent": 40.0, "Accélération": 42.0}
SCENARIO_CENTRAL = "Rythme récent"
TOLERANCE_COURBE = 0.01
HEURES_MIN_TRIMESTRE = 1900
TRIMESTRES = {q: [m for m in MOIS if (m - 1) // 3 + 1 == q] for q in range(1, 5)}


def lire_courbe(chemin: Path) -> pd.DataFrame:
    """Cotations ``base_eur_mwh`` et ``pointe_eur_mwh`` indexées par échéance."""
    return pd.read_csv(chemin).set_index("echeance")


def heures_mensuelles(annee: int) -> pd.Series:
    periodes = pd.period_range(f"{annee}-01", periods=12, freq="M")
    return heures_calendaires(periodes).set_axis(list(MOIS))


def niveaux_courbe(courbe: pd.DataFrame, annee: int) -> pd.Series:
    """Base de chaque trimestre. Refuse des trimestres dont la moyenne s'écarte de plus de 1 % du contrat calendaire."""
    niveaux = pd.Series({q: float(courbe.loc[f"T{q}_{annee}", "base_eur_mwh"]) for q in TRIMESTRES})
    h = heures_mensuelles(annee)
    poids = pd.Series({q: h[m].sum() for q, m in TRIMESTRES.items()})
    moyenne = (niveaux * poids).sum() / poids.sum()
    calendaire = float(courbe.loc[f"CAL_{annee}", "base_eur_mwh"])
    if abs(moyenne / calendaire - 1) > TOLERANCE_COURBE:
        raise ValueError(f"Courbe incohérente pour {annee} : trimestres à {moyenne:.2f}, contrat calendaire à {calendaire:.2f}")
    return niveaux


def baseload_courbe(niveaux: pd.Series, forme: pd.Series, annee: int) -> pd.Series:
    """Baseload de chaque mois : dans un trimestre, ``forme`` donne la répartition, et la moyenne pondérée par les heures égale le niveau du trimestre."""
    h = heures_mensuelles(annee)
    resultat = pd.Series(index=list(MOIS), dtype=float)
    for q, mois in TRIMESTRES.items():
        resultat.loc[mois] = niveaux[q] * forme.loc[mois] * h[mois].sum() / (forme.loc[mois] * h[mois]).sum()
    return resultat


def niveau_par_mois(niveaux: pd.Series) -> pd.Series:
    """Niveau du trimestre de chaque mois calendaire."""
    return pd.Series({m: float(niveaux[q]) for q, mois in TRIMESTRES.items() for m in mois})


def part_selon_parc(part_base: pd.Series, parc_gw: float, parc_base_gw: float = PARC_BASE_GW) -> pd.Series:
    """Part du solaire proportionnelle au parc : facteur de charge et consommation constants (H20)."""
    return part_base * parc_gw / parc_base_gw


def historique_pointe(horaire: pd.DataFrame) -> pd.DataFrame:
    """Par trimestre complet : base, pointe (lundi au vendredi, 8 h à 20 h à Paris), leur rapport et le taux de capture."""
    h = horaire.dropna(subset=["prix_eur_mwh", "solaire_mw"])
    local = h["ts_utc"].dt.tz_convert(FUSEAU_AFFICHAGE)
    d = pd.DataFrame(
        {
            "annee": local.dt.year,
            "trimestre": local.dt.quarter,
            "p": h["prix_eur_mwh"],
            "q": h["solaire_mw"],
            "pointe": (local.dt.day_of_week < 5) & (local.dt.hour >= 8) & (local.dt.hour < 20),
        }
    )
    lignes = []
    for (a, t), g in d.groupby(["annee", "trimestre"]):
        if len(g) >= HEURES_MIN_TRIMESTRE:
            base = g["p"].mean()
            lignes.append({"annee": a, "trimestre": t, "base": base, "rapport": g.loc[g["pointe"], "p"].mean() / base, "taux_capture": (g["p"] * g["q"]).sum() / g["q"].sum() / base})
    return pd.DataFrame(lignes)


def taux_implicite_pointe(historique: pd.DataFrame, trimestre: int, rapport: float) -> tuple[float, float]:
    """Taux de capture implicite d'un rapport pointe/base coté, par la droite observée de ce trimestre, et le R² de cette droite.

    Un rapport coté n'est pas forcément une prévision : aucun historique de cotations ne permet de tester ce passage.
    """
    g = historique[historique["trimestre"] == trimestre]
    pente, constante = np.polyfit(g["rapport"], g["taux_capture"], 1)
    r2 = float(np.corrcoef(g["rapport"], g["taux_capture"])[0, 1] ** 2)
    return float(constante + pente * rapport), r2
