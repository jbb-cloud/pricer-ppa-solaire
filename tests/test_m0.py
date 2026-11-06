import numpy as np
import pandas as pd
import pytest

from ppa_pricer.backtest.metriques import couverture
from ppa_pricer.modele.m0 import (
    ParametresM0,
    calibrer_m0,
    cases,
    estimer_ar1,
    faits_stylises,
    grille_annee,
    prevoir_m0,
    prix_normalises,
    simuler_prix_normalises,
    taux_capture_simules,
)


def horaire_synthetique(annees=(2020, 2021, 2022), phi=0.9, sigma=5.0, graine=1):
    """Prix = niveau de l'année × profil horaire + AR(1) ; solaire en cloche autour de midi."""
    ts = pd.date_range(f"{annees[0] - 1}-12-31T23:00Z", f"{annees[-1]}-12-31T22:00Z", freq="h")
    rng = np.random.default_rng(graine)
    x = np.zeros(len(ts))
    chocs = rng.normal(0, sigma, len(ts))
    for t in range(1, len(ts)):
        x[t] = phi * x[t - 1] + chocs[t]
    local = ts.tz_convert("Europe/Paris")
    niveau = 50 + 20 * (local.year - annees[0])
    return pd.DataFrame(
        {
            "ts_utc": ts,
            "prix_eur_mwh": niveau * (1 - 0.4 * np.exp(-(((local.hour - 13) / 3) ** 2))) + x,
            "solaire_mw": 1000 * np.clip(1 - ((local.hour + 0.5 - 13.5) / 6) ** 2, 0, None),
            "conso_mw": 50000.0,
        }
    )


def parametres_simples(sigma=0.0, phi=0.9):
    """Saisonnalité de 1 le jour, de 0,5 de 10 h à 16 h ; production seulement de 10 h à 16 h."""
    index = pd.MultiIndex.from_product([range(1, 13), range(24), [False, True]], names=["mois", "heure", "week_end"])
    saison = pd.Series([0.5 if 10 <= h <= 16 else 1.0 for _, h, _ in index], index=index)
    index_profil = pd.MultiIndex.from_product([range(1, 13), range(24)], names=["mois", "heure"])
    profil = pd.Series([1.0 if 10 <= h <= 16 else 0.0 for _, h in index_profil], index=index_profil)
    return ParametresM0(saison, profil, phi, sigma, 2024)


def test_cases_en_heure_de_paris():
    ts = pd.DatetimeIndex(pd.to_datetime(["2024-05-31T22:00Z", "2024-06-03T10:00Z", "2024-01-15T23:30Z"], utc=True))
    c = cases(ts)
    assert list(c["mois"]) == [6, 6, 1]
    assert list(c["heure"]) == [0, 12, 0]
    assert list(c["week_end"]) == [True, False, False]


def test_prix_normalises_moyenne_un_par_annee_et_fenetre_respectee():
    h = horaire_synthetique()
    y = prix_normalises(h, [2020, 2021])
    annee = y.index.tz_convert("Europe/Paris").year
    assert set(annee) == {2020, 2021}
    assert y[annee == 2020].mean() == pytest.approx(1.0)
    assert y[annee == 2021].mean() == pytest.approx(1.0)


def test_prix_normalises_ignore_les_prix_inconnus_et_refuse_une_annee_absente():
    h = horaire_synthetique()
    h.loc[100:200, "prix_eur_mwh"] = np.nan
    assert prix_normalises(h, [2020]).isna().sum() == 0
    with pytest.raises(ValueError, match="2019"):
        prix_normalises(h, [2019, 2020])


def test_estimer_ar1_retrouve_les_parametres():
    rng = np.random.default_rng(3)
    x = np.zeros(200_000)
    for t in range(1, len(x)):
        x[t] = 0.93 * x[t - 1] + rng.normal(0, 0.2)
    serie = pd.Series(x, index=pd.date_range("2020-01-01", periods=len(x), freq="h", tz="UTC"))
    phi, sigma = estimer_ar1(serie)
    assert phi == pytest.approx(0.93, abs=0.003)
    assert sigma == pytest.approx(0.2, abs=0.002)


def test_estimer_ar1_ignore_les_couples_non_consecutifs():
    ts = pd.to_datetime(["2020-01-01T00:00Z", "2020-01-01T01:00Z", "2020-01-01T05:00Z", "2020-01-01T06:00Z"])
    phi, sigma = estimer_ar1(pd.Series([1.0, 0.5, 100.0, 50.0], index=ts))
    assert phi == pytest.approx(0.5)
    assert sigma == pytest.approx(0.0)


def test_estimer_ar1_refuse_une_serie_sans_retour_a_la_moyenne():
    ts = pd.date_range("2020-01-01", periods=4, freq="h", tz="UTC")
    with pytest.raises(ValueError, match="non estimable"):
        estimer_ar1(pd.Series([0.0, 0.0, 0.0, 0.0], index=ts))


def test_parametres_ornstein_uhlenbeck_coherents():
    p = parametres_simples(sigma=0.2, phi=0.93)
    assert np.exp(-p.kappa_par_heure) == pytest.approx(0.93)
    assert p.demi_vie_h == pytest.approx(np.log(2) / -np.log(0.93))
    assert p.sigma_stationnaire**2 == pytest.approx(0.2**2 / (1 - 0.93**2))
    assert p.sigma_ou**2 / (2 * p.kappa_par_heure) == pytest.approx(p.sigma_stationnaire**2)


def test_calibration_sans_donnee_future_ni_trop_ancienne():
    h = horaire_synthetique(annees=(2019, 2020, 2021, 2022))
    reference = calibrer_m0(h, 2022)
    local = h["ts_utc"].dt.tz_convert("Europe/Paris").dt.year
    perturbe = h.copy()
    perturbe.loc[(local >= 2022) | (local == 2019), ["prix_eur_mwh", "solaire_mw"]] = 999.0
    apres = calibrer_m0(perturbe, 2022)
    assert apres.phi == reference.phi
    assert apres.sigma_innovation == reference.sigma_innovation
    pd.testing.assert_series_equal(apres.saisonnalite, reference.saisonnalite)
    pd.testing.assert_series_equal(apres.profil_solaire, reference.profil_solaire)


def test_calibration_retrouve_le_creux_saisonnier_et_le_retour_a_la_moyenne():
    p = calibrer_m0(horaire_synthetique(phi=0.9), 2022)
    assert p.phi == pytest.approx(0.9, abs=0.02)
    assert p.saisonnalite[(6, 13, False)] < p.saisonnalite[(6, 3, False)]
    assert p.profil_solaire[(6, 13)] > p.profil_solaire[(6, 3)]


def test_grille_annee_avec_annee_bissextile_et_bornes_de_paris():
    assert len(grille_annee(2025)) == 8760
    assert len(grille_annee(2024)) == 8784
    assert grille_annee(2025)[0] == pd.Timestamp("2024-12-31T23:00Z")
    assert grille_annee(2025)[-1] == pd.Timestamp("2025-12-31T22:00Z")


def test_simulation_sans_bruit_egale_la_saisonnalite():
    ts = grille_annee(2024)
    y = simuler_prix_normalises(parametres_simples(sigma=0.0), ts, 3, np.random.default_rng(0))
    assert y.shape == (len(ts), 3)
    heures = ts.tz_convert("Europe/Paris").hour
    assert y[heures == 12].max() == 0.5
    assert y[heures == 3].min() == 1.0


def test_simulation_reproductible_et_variance_stationnaire():
    p = parametres_simples(sigma=0.1, phi=0.9)
    ts = grille_annee(2024)
    y1 = simuler_prix_normalises(p, ts, 200, np.random.default_rng(5))
    y2 = simuler_prix_normalises(p, ts, 200, np.random.default_rng(5))
    assert np.array_equal(y1, y2)
    heures = ts.tz_convert("Europe/Paris").hour
    assert y1[heures == 3].std() == pytest.approx(p.sigma_stationnaire, rel=0.03)


def test_simulation_refuse_une_case_sans_observation():
    p = parametres_simples()
    incomplet = ParametresM0(p.saisonnalite.drop((6, 12, False)), p.profil_solaire, p.phi, p.sigma_innovation, 2024)
    with pytest.raises(ValueError, match="case"):
        simuler_prix_normalises(incomplet, grille_annee(2024), 1, np.random.default_rng(0))


def test_taux_de_capture_simule_calcul_a_la_main():
    # Deux heures de juin : prix 1 sans production, prix 0,5 avec production : B = 0,75, C = 0,5.
    ts = pd.DatetimeIndex(pd.to_datetime(["2024-06-03T01:00Z", "2024-06-03T10:00Z"], utc=True))
    y = np.array([[1.0], [0.5]])
    profil = pd.Series([0.0, 10.0], index=pd.MultiIndex.from_tuples([(6, 3), (6, 12)], names=["mois", "heure"]))
    assert taux_capture_simules(y, ts, profil).loc[6, 0] == pytest.approx(0.5 / 0.75)


def test_taux_de_capture_ne_depend_pas_du_niveau_du_baseload():
    p = parametres_simples(sigma=0.05)
    ts = grille_annee(2024)
    y = simuler_prix_normalises(p, ts, 5, np.random.default_rng(1))
    a = taux_capture_simules(y, ts, p.profil_solaire)
    b = taux_capture_simules(3 * y, ts, p.profil_solaire)
    pd.testing.assert_frame_equal(a, b)


def test_taux_de_capture_refuse_un_profil_incomplet():
    p = parametres_simples()
    ts = grille_annee(2024)
    with pytest.raises(ValueError, match="profil"):
        taux_capture_simules(np.ones((len(ts), 1)), ts, p.profil_solaire.drop((6, 12)))


def test_prevision_encadre_le_taux_sans_bruit_et_reste_reproductible():
    h = horaire_synthetique()
    prevision, p = prevoir_m0(h, 2022, n=100)
    assert list(prevision["mois"]) == list(range(1, 13))
    assert (prevision["tc_m0_bas"] <= prevision["tc_m0"]).all()
    assert (prevision["tc_m0"] <= prevision["tc_m0_haut"]).all()
    ts = grille_annee(2022)
    sans_bruit = ParametresM0(p.saisonnalite, p.profil_solaire, p.phi, 0.0, 2022)
    y = simuler_prix_normalises(sans_bruit, ts, 1, np.random.default_rng(0))
    attendu = taux_capture_simules(y, ts, p.profil_solaire)[0].to_numpy()
    assert prevision["tc_m0"].to_numpy() == pytest.approx(attendu, abs=0.05)
    pd.testing.assert_frame_equal(prevision, prevoir_m0(h, 2022, n=100)[0])


def test_faits_stylises_d_un_ar1_gaussien():
    rng = np.random.default_rng(7)
    ts = pd.date_range("2019-01-01", periods=200_000, freq="h", tz="UTC")
    x = np.zeros(len(ts))
    for t in range(1, len(ts)):
        x[t] = 0.9 * x[t - 1] + rng.normal(0, 0.05)
    faits = faits_stylises(pd.Series(1 + x, index=ts))
    assert faits["autocorr_1h"] == pytest.approx(0.9, abs=0.01)
    assert faits["autocorr_24h"] == pytest.approx(0.9**24, abs=0.02)
    assert faits["kurtosis"] == pytest.approx(3.0, abs=0.1)
    assert faits["part_negative"] == 0.0
    assert faits["mediane_midi"] == pytest.approx(1.0, abs=0.01)


def test_couverture():
    realise = pd.Series([0.5, 0.2, 0.9, 0.3])
    assert couverture(realise, pd.Series([0.4, 0.4, 0.4, 0.3]), pd.Series([0.6, 0.6, 0.6, 0.6])) == pytest.approx(0.5)
