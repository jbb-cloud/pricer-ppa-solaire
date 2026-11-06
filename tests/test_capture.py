import numpy as np
import pandas as pd
import pytest

from ppa_pricer.analyse.capture import heures_calendaires, taux_de_capture


def horaire(debut_utc, prix, solaire, conso):
    ts = pd.date_range(debut_utc, periods=len(prix), freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "ts_utc": ts,
            "prix_eur_mwh": np.array(prix, dtype=float),
            "solaire_mw": np.array(solaire, dtype=float),
            "conso_mw": np.array(conso, dtype=float),
        }
    )


def test_taux_de_capture_cas_simple():
    # Nuit à 100 €/MWh sans soleil, midi à 50 €/MWh avec 10 MW : B = 75, C = 50, TC = 2/3.
    h = horaire("2024-06-01T00:00Z", [100, 50], [0, 10], [40, 40])
    tc = taux_de_capture(h, seuil_manquant=1.0).iloc[0]
    assert tc["baseload_eur_mwh"] == pytest.approx(75)
    assert tc["prix_capte_eur_mwh"] == pytest.approx(50)
    assert tc["taux_capture"] == pytest.approx(2 / 3)
    assert tc["part_solaire"] == pytest.approx(10 / 80)


def test_prix_capte_pondere_par_la_production():
    h = horaire("2024-06-01T00:00Z", [40, 80], [30, 10], [50, 50])
    tc = taux_de_capture(h, seuil_manquant=1.0).iloc[0]
    assert tc["prix_capte_eur_mwh"] == pytest.approx((40 * 30 + 80 * 10) / 40)


def test_prix_negatifs_inclus_dans_le_prix_capte():
    # Hypothèse H3 : la production est payée même à prix négatif.
    h = horaire("2024-06-01T00:00Z", [-20, 60], [10, 10], [50, 50])
    tc = taux_de_capture(h, seuil_manquant=1.0).iloc[0]
    assert tc["prix_capte_eur_mwh"] == pytest.approx(20)


def test_heure_incomplete_exclue_de_toutes_les_grandeurs():
    # La 3e heure a un prix très élevé mais pas de solaire connu : elle ne doit compter ni
    # dans le baseload ni dans le prix capté.
    h = horaire("2024-06-01T00:00Z", [100, 50, 1000], [0, 10, np.nan], [40, 40, 40])
    tc = taux_de_capture(h, seuil_manquant=1.0).iloc[0]
    assert tc["heures_utilisees"] == 2
    assert tc["baseload_eur_mwh"] == pytest.approx(75)


def test_heure_affectee_au_mois_de_paris():
    # 31/03/2024 22:00 UTC = 1er avril 00:00 à Paris (heure d'été) : l'heure est en avril.
    h = horaire("2024-03-31T21:00Z", [10, 20], [1, 1], [1, 1])
    tc = taux_de_capture(h, seuil_manquant=1.0)
    assert [str(p) for p in tc["periode"]] == ["2024-03", "2024-04"]


def test_heures_calendaires_avec_changements_d_heure():
    mois = pd.PeriodIndex(["2024-03", "2024-06", "2024-10"], freq="M")
    assert list(heures_calendaires(mois)) == [743, 720, 745]
    assert list(heures_calendaires(pd.PeriodIndex(["2024"], freq="Y"))) == [8784]


def test_mois_trop_incomplet_invalide_et_nan():
    # Juin 2024 compte 720 heures ; on n'en fournit que 2 (part manquante > 5 %).
    h = horaire("2024-06-01T00:00Z", [100, 50], [0, 10], [40, 40])
    tc = taux_de_capture(h).iloc[0]
    assert not tc["valide"]
    assert np.isnan(tc["taux_capture"])


def test_taux_annuel_n_est_pas_la_moyenne_des_mois():
    # Deux mois : janvier peu de soleil (TC 0,5), juin beaucoup de soleil (TC 1).
    # Le TC annuel est le prix capté annuel / baseload annuel, dominé par juin.
    janvier = horaire("2024-01-10T00:00Z", [100, 20], [0, 1], [10, 10])
    juin = horaire("2024-06-10T00:00Z", [60, 60], [10, 10], [10, 10])
    h = pd.concat([janvier, juin], ignore_index=True)
    annuel = taux_de_capture(h, frequence="Y", seuil_manquant=1.0).iloc[0]
    capte = (20 * 1 + 60 * 10 + 60 * 10) / 21
    baseload = (100 + 20 + 60 + 60) / 4
    assert annuel["taux_capture"] == pytest.approx(capte / baseload)
    mensuel = taux_de_capture(h, seuil_manquant=1.0)["taux_capture"]
    assert annuel["taux_capture"] != pytest.approx(mensuel.mean())
