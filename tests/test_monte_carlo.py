import numpy as np
import pandas as pd
import pytest

from ppa_pricer.analyse.capture import taux_de_capture
from ppa_pricer.modele.m0 import cases, grille_annee
from ppa_pricer.modele.m2 import calibrer_m2
from ppa_pricer.pricing.monte_carlo import (
    CONTRAT_PAP,
    CONTRAT_RUBAN,
    CONTRAT_SPOT,
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


def flux_simple(planchers=(0.0, 10.0), n_h=48, n=200, graine=1):
    rng = np.random.default_rng(graine)
    y = rng.uniform(-0.1, 2.0, (n_h, n))
    y = y / y.mean(axis=0)
    q = rng.uniform(0, 3.0, (n_h, n))
    b = 60 * np.exp(0.2 * rng.standard_normal(n))
    return y, q, b, flux_contrats(y, q, b, planchers)


def test_vendeur_plus_acheteur_egale_le_revenu_au_spot_pour_chaque_contrat():
    _, _, _, f = flux_simple()
    for nom, a in f.acheteur.items():
        np.testing.assert_allclose(f.vendeur[nom] + a, f.revenu)
    np.testing.assert_array_equal(f.vendeur[CONTRAT_SPOT], f.revenu)
    assert CONTRAT_SPOT not in f.acheteur


def test_le_prix_juste_annule_l_esperance_de_l_acheteur():
    _, _, _, f = flux_simple()
    for nom, a in f.acheteur.items():
        assert a.mean() == pytest.approx(0.0, abs=1e-8)


def test_pay_as_produced_calcule_a_la_main():
    y = np.array([[0.5, 1.5], [1.5, 0.5]])
    q = np.array([[1.0, 2.0], [3.0, 2.0]])
    b = np.array([10.0, 20.0])
    f = flux_contrats(y, q, b, planchers=())
    # Revenus : 1×5 + 3×15 = 50 et 2×30 + 2×10 = 80. Volumes : 4 et 4.
    np.testing.assert_allclose(f.revenu, [50.0, 80.0])
    assert f.prix[CONTRAT_PAP] == pytest.approx(65 / 4)
    np.testing.assert_allclose(f.vendeur[CONTRAT_PAP], [65.0, 65.0])
    np.testing.assert_allclose(f.acheteur[CONTRAT_PAP], [-15.0, 15.0])


def test_plancher_calcule_a_la_main():
    y = np.array([[0.5], [1.5]])
    q = np.array([[2.0], [1.0]])
    f = flux_contrats(y, q, np.array([10.0]), planchers=(8.0,))
    # Prix 5 puis 15 : le put paie (8 − 5) × 2 = 6 sur 3 MWh, soit une prime de 2 €/MWh.
    assert f.prix[nom_plancher(8.0)] == pytest.approx(2.0)
    assert f.acheteur[nom_plancher(8.0)][0] == pytest.approx(0.0)


def test_la_prime_de_plancher_croit_avec_le_plancher_et_reste_positive():
    _, _, _, f = flux_simple(planchers=(0.0, 10.0, 20.0, 40.0))
    primes = [f.prix[nom_plancher(k)] for k in (0.0, 10.0, 20.0, 40.0)]
    assert primes[0] >= 0 and primes == sorted(primes)


def test_un_plancher_reduit_la_var_du_vendeur():
    _, _, _, f = flux_simple(planchers=(40.0,))
    assert mesures_risque(f.vendeur[nom_plancher(40.0)])["var"] < mesures_risque(f.vendeur[CONTRAT_SPOT])["var"]


def test_ruban_prix_juste_et_acheteur_expose_au_seul_baseload():
    y, q, b, f = flux_simple()
    assert f.prix[CONTRAT_RUBAN] == pytest.approx(b.mean())
    puissance = q.sum(axis=0).mean() / y.shape[0]
    np.testing.assert_allclose(f.acheteur[CONTRAT_RUBAN], puissance * y.shape[0] * (b - b.mean()))


def test_le_vendeur_du_ruban_perd_quand_le_baseload_monte_si_le_taux_de_capture_est_faible():
    # Toute la production tombe à des heures à faible prix : le vendeur capte peu du baseload qu'il a vendu.
    y = np.tile(np.r_[np.full(12, 0.5), np.full(12, 1.5)][:, None], (1, 300))
    q = np.tile(np.r_[np.full(12, 1.0), np.zeros(12)][:, None], (1, 300))
    b = np.linspace(30.0, 90.0, 300)
    v = flux_contrats(y, q, b, planchers=()).vendeur[CONTRAT_RUBAN]
    assert np.corrcoef(v, b)[0, 1] < -0.99
    assert np.corrcoef(flux_contrats(y, q, b, planchers=()).vendeur[CONTRAT_SPOT], b)[0, 1] > 0.99


def test_le_revenu_realise_change_les_flux_mais_pas_les_prix():
    y, q, b, f = flux_simple()
    realise = f.revenu * 0.9
    g = flux_contrats(y, q, b, (0.0, 10.0), revenu_realise=realise)
    assert g.prix == f.prix
    np.testing.assert_allclose(g.vendeur[CONTRAT_PAP], f.vendeur[CONTRAT_PAP])
    np.testing.assert_allclose(g.acheteur[CONTRAT_PAP], f.acheteur[CONTRAT_PAP] - 0.1 * f.revenu)
    for nom, a in g.acheteur.items():
        np.testing.assert_allclose(g.vendeur[nom] + a, realise)


def test_var_et_cvar_calculees_a_la_main():
    x = np.arange(1.0, 101.0)
    r = mesures_risque(x)
    assert r["moyenne"] == pytest.approx(50.5)
    assert r["var"] == pytest.approx(np.quantile(50.5 - x, 0.95))
    assert r["cvar"] == pytest.approx((50.5 - x[:5]).mean())
    assert r["cvar"] >= r["var"]


def test_baseload_a_la_bonne_moyenne_et_au_bon_ecart():
    rng = np.random.default_rng(3)
    n = 200_000
    b = tirer_baseload(rng.normal(size=n), rng.standard_normal(n), 61.0, sigma=0.25, correlation=0.65)
    assert b.mean() == pytest.approx(61.0, rel=0.005)
    assert np.log(b).std() == pytest.approx(0.25, rel=0.01)


@pytest.mark.parametrize("rho", [0.0, 0.65])
def test_baseload_correle_au_taux_de_capture(rho):
    rng = np.random.default_rng(4)
    n = 50_000
    tc = rng.uniform(0.3, 0.7, n)
    b = tirer_baseload(tc, rng.standard_normal(n), 61.0, 0.25, rho)
    gauss = pd.Series(tc).rank().to_numpy()
    assert np.corrcoef(gauss, pd.Series(b).rank().to_numpy())[0, 1] == pytest.approx(rho * 0.98, abs=0.03)


def test_l_erreur_de_modele_est_centree_et_change_le_taux_de_capture():
    rng = np.random.default_rng(5)
    r, v, b = np.full(20_000, 30_000.0), np.full(20_000, 1500.0), np.full(20_000, 40.0)
    avec = revenu_avec_erreur(r, v, b, np.array([0.0, 0.02, 0.10]), rng)
    assert avec.mean() == pytest.approx(r.mean(), rel=0.003)
    tc = avec / (v * b)
    assert set(np.round(np.unique(tc), 4)) == {round(0.5 - e, 4) for e in (-0.04, -0.02, 0.06)}


def test_parts_de_variance_somme_a_un():
    rng = np.random.default_rng(6)
    n = 5000
    q, b, tc = 1500 * np.exp(0.03 * rng.normal(size=n)), 60 * np.exp(0.25 * rng.normal(size=n)), 0.5 * np.exp(0.1 * rng.normal(size=n))
    p = parts_variance(q * b * tc, q, b)
    assert sum(p.values()) == pytest.approx(1.0)
    assert p["baseload"] > p["taux_capture"] > p["volume"]
    assert abs(p["covariances"]) < 0.03


def test_parts_de_variance_refuse_un_taux_negatif():
    with pytest.raises(ValueError, match="négatif"):
        parts_variance(np.array([-1.0, 2.0]), np.ones(2), np.ones(2))


def test_figer_une_source_enleve_son_risque():
    rng = np.random.default_rng(7)
    n = 5000
    q, b, tc = np.full(n, 1500.0), 60 * np.exp(0.25 * rng.normal(size=n)), np.full(n, 0.5)
    v = var_en_figeant(q * b * tc, q, b)
    assert v["baseload"] == pytest.approx(0.0, abs=1e-6)
    assert v["volume"] == pytest.approx(v["taux_capture"], rel=1e-6)


def profil_horaire(annees=(2021, 2022)):
    ts = pd.date_range(f"{annees[0] - 1}-12-31T23:00Z", f"{annees[-1]}-12-31T22:00Z", freq="h")
    local = ts.tz_convert("Europe/Paris")
    return pd.DataFrame({"ts_utc": ts, "duree_min": 60, "solaire_mw": 0.5 + 0.1 * (local.year - annees[0])})


def test_volumes_par_annee_sur_les_annees_completes():
    profil = profil_horaire()
    table = volumes_par_annee(profil)
    assert list(table.index) == [2021, 2022]
    assert list(table.columns) == list(range(1, 13))
    assert table.loc[2021, 1] == pytest.approx(0.5 * 744)
    assert table.loc[2022, 2] == pytest.approx(0.6 * 672)
    # Une année tronquée n'est pas gardée.
    assert list(volumes_par_annee(profil[profil["ts_utc"] < "2022-06-01"]).index) == [2021]


def horaire_synthetique(annees=(2019, 2020, 2021, 2022), fin="2023-08-31T21:00Z"):
    ts = pd.date_range(f"{annees[0] - 1}-12-31T23:00Z", fin, freq="h")
    rng = np.random.default_rng(1)
    local = ts.tz_convert("Europe/Paris")
    solaire = 1000 * 1.2 ** (local.year - annees[0]) * np.clip(1 - ((local.hour + 0.5 - 13.5) / 6) ** 2, 0, None) * rng.uniform(0.6, 1.4, len(ts))
    eolien = rng.uniform(100, 900, len(ts))
    conso = 5000 + 800 * np.sin(2 * np.pi * local.hour / 24) + 300 * rng.normal(size=len(ts))
    charge = pd.Series(conso - solaire - eolien, index=ts)
    c = cases(ts)
    g = charge.groupby([c[k] for k in ["mois", "heure", "week_end"]])
    x = ((charge - g.transform("mean")) / g.transform("std")).to_numpy()
    prix = 50 * (1 + 0.2 * (0.6 * x + 0.8 * rng.normal(size=len(ts))))
    return pd.DataFrame({"ts_utc": ts, "prix_eur_mwh": prix, "solaire_mw": solaire, "eolien_mw": eolien, "conso_mw": conso})


def test_calibrer_livraison_fenetre_niveaux_et_horizon():
    h = horaire_synthetique()
    mensuel = taux_de_capture(h, "M")
    p = calibrer_livraison(h, mensuel, 2024)
    reference = calibrer_m2(h, 2023)
    assert p.annee_prevue == 2024
    assert sorted(p.formes) == [2021, 2022]
    assert p.poids_charge == reference.poids_charge
    # 12 derniers mois : sept. 2022 à août 2023, milieu au 1er mars 2023 ; milieu de 2024 au 1er juillet : 16 mois.
    np.testing.assert_allclose(p.croissances, (1 + reference.croissances) ** (16 / 12) - 1)
    assert p.niveaux["solaire_mw"] > reference.niveaux["solaire_mw"]


def test_calibrer_livraison_refuse_une_annee_deja_commencee_dans_les_donnees():
    h = horaire_synthetique()
    with pytest.raises(ValueError, match="année future"):
        calibrer_livraison(h, taux_de_capture(h, "M"), 2023)


def test_simulation_normalisee_et_volumes_du_site_respectes():
    h = horaire_synthetique()
    p = calibrer_livraison(h, taux_de_capture(h, "M"), 2024)
    volumes = pd.DataFrame({m: [100.0 + m, 200.0 + m] for m in range(1, 13)}, index=[2010, 2011])
    ts, y, q = simuler_livraison(p, volumes, 40, np.random.default_rng(0))
    np.testing.assert_allclose(y.mean(axis=0), 1.0)
    mois = ts.tz_convert("Europe/Paris").month
    janvier = q[mois == 1].sum(axis=0)
    assert set(np.round(janvier, 6)) <= {101.0, 201.0}
    decembre = q[mois == 12].sum(axis=0)
    # Une trajectoire garde la même année PVGIS pour tous ses mois.
    np.testing.assert_allclose(decembre - janvier, 11.0)


def test_taux_capture_annuel_calcule_a_la_main():
    y = np.array([[0.5], [1.5]])
    q = np.array([[3.0], [1.0]])
    assert taux_capture_annuel(y, q)[0] == pytest.approx((1.5 + 1.5) / 4 / 1.0)
