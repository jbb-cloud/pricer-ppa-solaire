import numpy as np
import pandas as pd
import pytest

from ppa_pricer.modele.m0 import estimer_ar1, grille_annee, prix_normalises
from ppa_pricer.modele.m1 import (
    ParametresM1,
    ajuster_deux_vitesses,
    autocorrelations,
    calibrer_m1,
    prevoir_m1,
    scores_normaux,
    simuler_latente,
    simuler_prix_normalises,
)

RETARDS = np.arange(1, 73)


def horaire_synthetique(annees=(2020, 2021, 2022), graine=1):
    """Prix avec un creux de midi et deux bruits, rapide et lent ; solaire en cloche autour de midi."""
    ts = pd.date_range(f"{annees[0] - 1}-12-31T23:00Z", f"{annees[-1]}-12-31T22:00Z", freq="h")
    rng = np.random.default_rng(graine)
    rapide, lent = np.zeros(len(ts)), np.zeros(len(ts))
    for t in range(1, len(ts)):
        rapide[t] = 0.8 * rapide[t - 1] + rng.normal(0, 3.0)
        lent[t] = 0.99 * lent[t - 1] + rng.normal(0, 1.0)
    local = ts.tz_convert("Europe/Paris")
    niveau = 50 + 20 * (local.year - annees[0])
    return pd.DataFrame(
        {
            "ts_utc": ts,
            "prix_eur_mwh": niveau * (1 - 0.4 * np.exp(-(((local.hour - 13) / 3) ** 2))) + rapide + lent,
            "solaire_mw": 1000 * np.clip(1 - ((local.hour + 0.5 - 13.5) / 6) ** 2, 0, None),
            "conso_mw": 50000.0,
        }
    )


def parametres_simples(lois=None, w=0.4, phi_r=0.8, phi_l=0.99):
    index = pd.MultiIndex.from_product([range(1, 13), range(24)], names=["mois", "heure"])
    profil = pd.Series([1.0 if 10 <= h <= 16 else 0.0 for _, h in index], index=index)
    if lois is None:
        lois = {(m, h, we): np.array([0.0, 1.0, 2.0]) for m in range(1, 13) for h in range(24) for we in (False, True)}
    return ParametresM1(lois, profil, w, phi_r, phi_l, 0.0, 2024)


def test_scores_normaux_rang_dans_la_case():
    # Trois lundis de juin à 10 h UTC, donc la même case : prix 30, 10, 20.
    ts = pd.to_datetime(["2024-06-03T10:00Z", "2024-06-10T10:00Z", "2024-06-17T10:00Z"])
    z = scores_normaux(pd.Series([30.0, 10.0, 20.0], index=ts))
    assert z.iloc[1] < z.iloc[2] < z.iloc[0]
    assert z.iloc[2] == pytest.approx(0.0)
    assert z.iloc[0] == pytest.approx(-z.iloc[1])


def test_scores_normaux_ex_aequo_et_cases_separees():
    # Les deux 0 reçoivent le même score ; le lundi à 11 h est dans une autre case.
    ts = pd.to_datetime(["2024-06-03T10:00Z", "2024-06-10T10:00Z", "2024-06-17T10:00Z", "2024-06-03T11:00Z"])
    z = scores_normaux(pd.Series([0.0, 0.0, 5.0, 999.0], index=ts))
    assert z.iloc[0] == z.iloc[1]
    assert z.iloc[3] == pytest.approx(0.0)


def test_autocorrelations_sur_un_ar1_et_avec_un_trou():
    rng = np.random.default_rng(2)
    x = np.zeros(100_000)
    for t in range(1, len(x)):
        x[t] = 0.9 * x[t - 1] + rng.normal()
    ts = pd.date_range("2020-01-01", periods=len(x), freq="h", tz="UTC")
    assert autocorrelations(pd.Series(x, index=ts), np.array([1, 5]))[0] == pytest.approx(0.9, abs=0.01)
    avec_trou = pd.Series(x, index=ts).drop(ts[500:600])
    assert autocorrelations(avec_trou, np.array([1, 5]))[1] == pytest.approx(0.9**5, abs=0.02)


def test_ajustement_retrouve_les_deux_vitesses():
    acf = 0.3 * 0.75**RETARDS + 0.7 * 0.99**RETARDS
    w, phi_r, phi_l, erreur = ajuster_deux_vitesses(acf, RETARDS)
    assert w == pytest.approx(0.3, abs=0.01)
    assert phi_r == pytest.approx(0.75, abs=0.01)
    assert phi_l == pytest.approx(0.99, abs=0.001)
    assert erreur < 1e-4
    assert phi_r <= phi_l


def test_demi_vies():
    p = parametres_simples(phi_r=0.5, phi_l=0.25**0.5)
    assert p.demi_vie_rapide_h == pytest.approx(1.0)
    assert p.demi_vie_lente_h == pytest.approx(1.0)


def test_latente_variance_un_et_memoire_theorique():
    p = parametres_simples(w=0.3, phi_r=0.8, phi_l=0.98)
    z = simuler_latente(p, 4000, 400, np.random.default_rng(4))
    assert z.std() == pytest.approx(1.0, abs=0.02)
    theorie = 0.3 * 0.8**24 + 0.7 * 0.98**24
    observee = np.mean([np.corrcoef(z[24:, i], z[:-24, i])[0, 1] for i in range(z.shape[1])])
    assert observee == pytest.approx(theorie, abs=0.02)


def test_calibration_sans_donnee_future_ni_trop_ancienne():
    h = horaire_synthetique(annees=(2019, 2020, 2021, 2022))
    reference = calibrer_m1(h, 2022)
    annee = h["ts_utc"].dt.tz_convert("Europe/Paris").dt.year
    perturbe = h.copy()
    perturbe.loc[(annee >= 2022) | (annee == 2019), ["prix_eur_mwh", "solaire_mw"]] = 999.0
    apres = calibrer_m1(perturbe, 2022)
    assert apres.phi_rapide == reference.phi_rapide
    assert apres.phi_lent == reference.phi_lent
    assert apres.poids_rapide == reference.poids_rapide
    assert all(np.array_equal(apres.lois[c], reference.lois[c]) for c in reference.lois)
    pd.testing.assert_series_equal(apres.profil_solaire, reference.profil_solaire)


def test_fenetre_d_un_an_n_utilise_que_l_annee_precedente():
    h = horaire_synthetique()
    annee = h["ts_utc"].dt.tz_convert("Europe/Paris").dt.year
    perturbe = h.copy()
    perturbe.loc[annee == 2020, "prix_eur_mwh"] = 999.0
    assert calibrer_m1(perturbe, 2022, fenetre=1).phi_lent == calibrer_m1(h, 2022, fenetre=1).phi_lent


def test_calibration_retrouve_deux_vitesses_distinctes():
    p = calibrer_m1(horaire_synthetique(), 2022)
    assert p.demi_vie_rapide_h < 10 < p.demi_vie_lente_h
    assert 0 < p.poids_rapide < 1


def test_un_pic_change_peu_la_dynamique_contrairement_a_l_ar1():
    h = horaire_synthetique()
    pic = h.copy()
    local = pic["ts_utc"].dt.tz_convert("Europe/Paris")
    pic.loc[(local.dt.year == 2020) & (local.dt.month == 11) & (local.dt.day == 7) & (local.dt.hour == 18), "prix_eur_mwh"] = 20_000.0
    sans, avec = calibrer_m1(h, 2022), calibrer_m1(pic, 2022)
    assert avec.phi_lent == pytest.approx(sans.phi_lent, abs=0.005)
    assert avec.poids_rapide == pytest.approx(sans.poids_rapide, abs=0.03)

    def phi_ar1(horaire):
        y = prix_normalises(horaire, [2020, 2021])
        return estimer_ar1(y - y.mean())[0]

    assert abs(phi_ar1(pic) - phi_ar1(h)) > 0.1


def test_simulation_reste_dans_les_valeurs_observees_de_la_case():
    p = parametres_simples()
    y = simuler_prix_normalises(p, grille_annee(2024), 5, np.random.default_rng(0))
    assert y.min() >= 0.0
    assert y.max() <= 2.0


def test_simulation_reproduit_un_amas_de_prix_a_zero():
    # 30 % de la loi de chaque case vaut exactement 0.
    loi = np.r_[np.zeros(30), np.linspace(0.5, 1.5, 70)]
    lois = {(m, h, we): loi for m in range(1, 13) for h in range(24) for we in (False, True)}
    y = simuler_prix_normalises(parametres_simples(lois), grille_annee(2024), 200, np.random.default_rng(1))
    assert (y == 0).mean() == pytest.approx(0.295, abs=0.03)


def test_simulation_conserve_la_moyenne_de_la_case():
    lois = {(m, h, we): np.linspace(0.0, 2.0, 41) * (0.5 if 10 <= h <= 16 else 1.0) for m in range(1, 13) for h in range(24) for we in (False, True)}
    ts = grille_annee(2024)
    y = simuler_prix_normalises(parametres_simples(lois), ts, 400, np.random.default_rng(3))
    heures = ts.tz_convert("Europe/Paris").hour
    assert y[heures == 12].mean() == pytest.approx(0.5, abs=0.03)
    assert y[heures == 3].mean() == pytest.approx(1.0, abs=0.05)


def test_simulation_refuse_une_case_sans_observation():
    p = parametres_simples()
    lois = {c: v for c, v in p.lois.items() if c != (6, 12, False)}
    with pytest.raises(ValueError, match="case"):
        simuler_prix_normalises(parametres_simples(lois), grille_annee(2024), 1, np.random.default_rng(0))


def test_prevision_ordonnee_et_reproductible():
    h = horaire_synthetique()
    prevision, _ = prevoir_m1(h, 2022, n=50)
    assert list(prevision["mois"]) == list(range(1, 13))
    assert (prevision["tc_bas"] <= prevision["tc"]).all()
    assert (prevision["tc"] <= prevision["tc_haut"]).all()
    pd.testing.assert_frame_equal(prevision, prevoir_m1(h, 2022, n=50)[0])
