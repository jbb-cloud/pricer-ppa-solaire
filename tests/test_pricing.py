import json

import numpy as np
import pandas as pd
import pytest

from ppa_pricer.analyse.capture import heures_calendaires, taux_de_capture
from ppa_pricer.donnees.pvgis import inclinaison_optimale, lire_profil
from ppa_pricer.modele.v1 import calibrer, prevoir_part_solaire, prevoir_part_solaire_glissante
from ppa_pricer.pricing.v1 import (
    baseload_mensuel,
    entrees_pricing,
    forme_baseload,
    prix_juste,
    revenu_annuel,
    taux_capture_formule,
    taux_capture_site,
    volumes_mensuels,
)

MOIS = list(range(1, 13))


def serie_mois(valeurs: dict, defaut: float = 0.0) -> pd.Series:
    return pd.Series([valeurs.get(m, defaut) for m in MOIS], index=MOIS, dtype=float)


def mensuel_synthetique(debut="2015-01", fin="2020-12"):
    """Mois complets où le solaire croît de 10 % par an, avec un taux de capture linéaire en S."""
    periodes = pd.period_range(debut, fin, freq="M")
    annees = (periodes.year - 2015).to_numpy()
    mois = periodes.month.to_numpy()
    part = 0.02 * 1.1**annees * (1 + 0.3 * np.sin(mois / 12 * np.pi))
    return pd.DataFrame(
        {
            "periode": periodes,
            "valide": True,
            "taux_capture": 1.0 + 0.01 * mois - 3.0 * part,
            "part_solaire": part,
            "energie_solaire_mwh": part * 1e6,
            "baseload_eur_mwh": 50.0 + mois,
            "heures_utilisees": 720,
        }
    )


def test_prix_juste_calcul_a_la_main():
    tc = serie_mois({1: 1.0, 7: 0.5}, defaut=0.8)
    baseload = serie_mois({1: 100.0, 7: 50.0}, defaut=70.0)
    volumes = serie_mois({1: 1.0, 7: 3.0})
    assert prix_juste(tc, baseload, volumes) == pytest.approx((1 * 100 * 1 + 0.5 * 50 * 3) / 4)


def test_prix_juste_taux_et_baseload_constants():
    assert prix_juste(serie_mois({}, 0.5), serie_mois({}, 60.0), serie_mois({}, 7.0)) == pytest.approx(30.0)


def test_prix_juste_avec_une_entree_inconnue_donne_nan():
    tc = serie_mois({3: np.nan}, defaut=0.5)
    assert np.isnan(prix_juste(tc, serie_mois({}, 60.0), serie_mois({}, 1.0)))
    volumes = serie_mois({3: np.nan}, defaut=1.0)
    assert np.isnan(prix_juste(serie_mois({}, 0.5), serie_mois({}, 60.0), volumes))


def test_revenu_annuel():
    assert revenu_annuel(30.0, serie_mois({}, 100.0)) == pytest.approx(30.0 * 1200)


def test_baseload_mensuel_respecte_le_niveau_annuel():
    forme = serie_mois({1: 1.5, 5: 0.4}, defaut=1.0)
    for annee, heures_fevrier in [(2027, 672), (2028, 696)]:
        baseload = baseload_mensuel(61.0, forme, annee)
        heures = heures_calendaires(pd.period_range(f"{annee}-01", periods=12, freq="M")).set_axis(MOIS)
        assert heures[2] == heures_fevrier
        assert (baseload * heures).sum() / heures.sum() == pytest.approx(61.0)
    assert baseload[1] / baseload[5] == pytest.approx(1.5 / 0.4)


def test_forme_baseload_moyenne_des_rapports_annuels():
    m = mensuel_synthetique("2023-01", "2024-12")
    m["baseload_eur_mwh"] = 100.0
    m.loc[m["periode"] == pd.Period("2024-06", "M"), "baseload_eur_mwh"] = 40.0
    forme = forme_baseload(m, annees=(2023, 2024))
    annuel_2024 = (100.0 * 11 + 40.0) / 12
    assert forme[6] == pytest.approx((1.0 + 40.0 / annuel_2024) / 2)
    assert forme[1] == pytest.approx((1.0 + 100.0 / annuel_2024) / 2)


def test_forme_baseload_ignore_les_autres_annees_et_les_mois_invalides():
    m = mensuel_synthetique("2023-01", "2024-12")
    m["baseload_eur_mwh"] = 100.0
    m.loc[m["periode"] == pd.Period("2023-06", "M"), "baseload_eur_mwh"] = 1.0
    assert forme_baseload(m, annees=(2024,))[6] == pytest.approx(1.0)
    m.loc[m["periode"] == pd.Period("2024-06", "M"), "valide"] = False
    assert np.isnan(forme_baseload(m, annees=(2024,))[6])


def profil_constant(debut, fin, puissance=1.0):
    ts = pd.date_range(debut, fin, freq="h")
    return pd.DataFrame({"ts_utc": ts, "duree_min": 60, "solaire_mw": puissance})


def test_volumes_mensuels_moyenne_des_annees():
    profil = profil_constant("2020-12-31T23:00Z", "2022-12-31T22:00Z")
    janvier_2022 = (profil["ts_utc"] >= "2021-12-31T23:00Z") & (profil["ts_utc"] < "2022-01-31T23:00Z")
    profil.loc[janvier_2022, "solaire_mw"] = 3.0
    volumes = volumes_mensuels(profil)
    assert volumes[1] == pytest.approx((744 + 3 * 744) / 2)
    assert volumes[6] == pytest.approx(720)


def test_volumes_mensuels_ecarte_le_mois_presque_vide_en_fin_de_serie():
    # La dernière heure UTC de 2021 tombe le 1er janvier 2022 à Paris : ce mois n'a qu'une heure.
    profil = profil_constant("2020-12-31T23:00Z", "2021-12-31T23:00Z")
    assert volumes_mensuels(profil)[1] == pytest.approx(744)


def test_volumes_mensuels_tiennent_compte_de_la_duree_des_points():
    ts = pd.date_range("2025-12-31T23:00Z", "2026-01-31T22:45Z", freq="15min")
    profil = pd.DataFrame({"ts_utc": ts, "duree_min": 15, "solaire_mw": 2.0})
    assert volumes_mensuels(profil)[1] == pytest.approx(2.0 * 744)


def test_h4_glissante_egale_h4_sur_une_annee_civile():
    m = mensuel_synthetique()
    coupe = m[m["periode"] <= pd.Period("2018-12", "M")]
    pd.testing.assert_series_equal(
        prevoir_part_solaire_glissante(coupe), prevoir_part_solaire(coupe, 2019), check_names=False
    )


def test_h4_glissante_utilise_les_douze_derniers_mois_valides():
    m = mensuel_synthetique()
    coupe = m[m["periode"] <= pd.Period("2019-09", "M")]
    partie = coupe.set_index("periode")
    croissance = (
        partie.loc["2018-10":"2019-09", "energie_solaire_mwh"].sum()
        / partie.loc["2017-10":"2018-09", "energie_solaire_mwh"].sum()
    )
    prevue = prevoir_part_solaire_glissante(coupe)
    assert prevue[1] == pytest.approx(partie.loc["2019-01", "part_solaire"] * croissance)
    assert prevue[12] == pytest.approx(partie.loc["2018-12", "part_solaire"] * croissance)


def test_h4_glissante_refuse_une_fenetre_interrompue():
    m = mensuel_synthetique()
    m.loc[m["periode"] == pd.Period("2020-03", "M"), "valide"] = False
    with pytest.raises(ValueError, match="consécutifs"):
        prevoir_part_solaire_glissante(m)


def test_entrees_pricing_modele_et_persistance():
    m = mensuel_synthetique("2015-01", "2020-09")
    entrees, parametres = entrees_pricing(m, 2022)
    assert parametres.n_mois == len(m)
    juin_2020 = m[m["periode"] == pd.Period("2020-06", "M")].iloc[0]
    assert entrees.loc[6, "tc_persistance"] == pytest.approx(juin_2020["taux_capture"])
    assert entrees.loc[6, "part_solaire_base"] == pytest.approx(juin_2020["part_solaire"])
    attendu = parametres.alpha[6] + parametres.beta * entrees.loc[6, "part_solaire_prevue"]
    assert entrees.loc[6, "tc_modele"] == pytest.approx(attendu)


def test_entrees_pricing_utilise_les_memes_parametres_que_la_calibration():
    m = mensuel_synthetique("2015-01", "2020-09")
    _, parametres = entrees_pricing(m, 2022)
    assert parametres.beta == pytest.approx(calibrer(m, 2022).beta)


def test_entrees_pricing_refuse_une_annee_deja_commencee():
    with pytest.raises(ValueError, match="année future"):
        entrees_pricing(mensuel_synthetique("2015-01", "2020-09"), 2020)


def test_taux_capture_site_egal_au_national_avec_le_meme_profil_quelle_que_soit_l_echelle():
    rng = np.random.default_rng(3)
    ts = pd.date_range("2023-12-31T23:00Z", "2024-12-31T22:00Z", freq="h")
    horaire = pd.DataFrame(
        {
            "ts_utc": ts,
            "prix_eur_mwh": 60 + 20 * rng.standard_normal(len(ts)),
            "solaire_mw": 5000 * rng.uniform(0, 1, len(ts)),
            "conso_mw": 50000.0,
        }
    )
    profil = horaire[["ts_utc", "solaire_mw"]].assign(duree_min=60, solaire_mw=lambda d: d["solaire_mw"] / 5000)
    site = taux_capture_site(horaire, profil)
    assert site["taux_capture"].iloc[0] == pytest.approx(taux_de_capture(horaire, "Y")["taux_capture"].iloc[0])


def test_taux_capture_formule_calcul_a_la_main():
    m = mensuel_synthetique("2023-01", "2024-12")
    m["taux_capture"] = 0.8
    m["baseload_eur_mwh"] = 60.0
    annee_2024 = m["periode"].dt.year == 2024
    m.loc[annee_2024 & (m["periode"].dt.month == 7), ["taux_capture", "baseload_eur_mwh"]] = [0.5, 30.0]
    volumes = serie_mois({1: 1.0, 7: 3.0})
    formule = taux_capture_formule(m, volumes)
    baseload_2024 = (60.0 * 11 + 30.0) / 12
    assert formule[2023] == pytest.approx(0.8)
    assert formule[2024] == pytest.approx((0.8 * 60 * 1 + 0.5 * 30 * 3) / 4 / baseload_2024)


def test_taux_capture_formule_ecarte_une_annee_incomplete():
    m = mensuel_synthetique("2023-01", "2024-12")
    m.loc[m["periode"] == pd.Period("2023-03", "M"), "valide"] = False
    assert list(taux_capture_formule(m, serie_mois({}, 1.0)).index) == [2024]


def test_lire_profil_pvgis(tmp_path):
    donnees = {
        "inputs": {"mounting_system": {"fixed": {"slope": {"value": 39}}}},
        "outputs": {"hourly": [{"time": "20200615:1210", "P": 500000.0}, {"time": "20200615:1310", "P": 0.0}]},
    }
    chemin = tmp_path / "profil.json"
    chemin.write_text(json.dumps(donnees))
    profil = lire_profil(chemin)
    assert list(profil.columns) == ["ts_utc", "duree_min", "solaire_mw"]
    assert profil["ts_utc"].iloc[0] == pd.Timestamp("2020-06-15T12:00Z")
    assert profil["solaire_mw"].iloc[0] == pytest.approx(0.5)
    assert profil["solaire_mw"].iloc[1] == 0.0
    assert inclinaison_optimale(chemin) == 39.0
