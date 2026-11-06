import json

import numpy as np
import pandas as pd
import pytest

from ppa_pricer.donnees.energy_charts import charger_filiere
from ppa_pricer.modele.facteurs import (
    MOIS_ETE,
    ParametresPlages,
    HYDRO,
    NUCLEAIRE,
    VARIANTES,
    Variante,
    calibrer_facteurs,
    calibrer_plages,
    explique_la_chute,
    facteurs_de_la_periode,
    nucleaire_disponible,
    plages,
    simuler_plages,
    simuler_valeurs_reelles,
    taux_capture_median,
)
from ppa_pricer.modele.m0 import cases, grille_annee
from ppa_pricer.modele.m2 import calibrer_m2


def horaire_synthetique(annees=(2019, 2020, 2021, 2022), graine=1, poids=(0.5, 0.3)):
    """Le rang du prix suit la charge française et une charge voisine, avec des poids connus."""
    ts = pd.date_range(f"{annees[0] - 1}-12-31T23:00Z", f"{annees[-1]}-12-31T22:00Z", freq="h")
    rng = np.random.default_rng(graine)
    local = ts.tz_convert("Europe/Paris")
    solaire = 1000 * np.clip(1 - ((local.hour + 0.5 - 13.5) / 6) ** 2, 0, None) * rng.uniform(0.5, 1.5, len(ts))
    h = pd.DataFrame(
        {
            "ts_utc": ts,
            "solaire_mw": solaire,
            "eolien_mw": rng.uniform(100, 900, len(ts)),
            "conso_mw": 5000 + 800 * np.sin(2 * np.pi * local.hour / 24) + 300 * rng.normal(size=len(ts)),
            "nucleaire_mw": 3000.0 + 100 * rng.normal(size=len(ts)),
            HYDRO: 400 + 50 * rng.normal(size=len(ts)),
            "charge_de_mw": 40000 + 3000 * rng.normal(size=len(ts)),
            "charge_es_mw": 20000 + 2000 * rng.normal(size=len(ts)),
        }
    )
    c = cases(ts)

    def reduite(s):
        g = pd.Series(s, index=ts).groupby([c[k] for k in ["mois", "heure", "week_end"]])
        return ((pd.Series(s, index=ts) - g.transform("mean")) / g.transform("std")).to_numpy()

    france = reduite((h["conso_mw"] - h["solaire_mw"] - h["eolien_mw"]).to_numpy())
    allemagne = reduite(h["charge_de_mw"].to_numpy())
    bruit = rng.normal(size=len(ts)) * np.sqrt(1 - poids[0] ** 2 - poids[1] ** 2)
    h["prix_eur_mwh"] = 50 * (1 + 0.1 * (poids[0] * france + poids[1] * allemagne + bruit))
    return h


VOISIN = Variante("Allemagne", (), ("charge_de_mw",))


def test_nucleaire_disponible_prend_le_maximum_de_la_semaine():
    ts = pd.date_range("2024-01-01", periods=500, freq="h", tz="UTC")
    s = pd.Series(10.0, index=ts)
    s.iloc[250] = 40.0
    d = nucleaire_disponible(s)
    assert d.iloc[250] == 40.0
    assert d.iloc[250 - 83] == 40.0 and d.iloc[250 + 84] == 40.0
    assert d.iloc[100] == 10.0


def test_les_six_variantes_sont_celles_du_protocole():
    assert list(VARIANTES) == list("ABCDEF")
    assert VARIANTES["A"].retirer == () and VARIANTES["A"].voisins == ()
    assert VARIANTES["D"].retirer == (NUCLEAIRE, HYDRO) and VARIANTES["D"].voisins == ()
    assert VARIANTES["F"].retirer == VARIANTES["D"].retirer and VARIANTES["F"].voisins == VARIANTES["E"].voisins


def test_reference_proche_du_lambda_de_m2():
    h = horaire_synthetique()
    assert calibrer_facteurs(h, 2022, VARIANTES["A"]).coefficients["france"] == pytest.approx(calibrer_m2(h, 2022).poids_charge, abs=0.01)


def test_la_regression_retrouve_les_deux_poids():
    p = calibrer_facteurs(horaire_synthetique(), 2022, VOISIN)
    assert p.coefficients["france"] == pytest.approx(0.5, abs=0.04)
    assert p.coefficients["charge_de_mw"] == pytest.approx(0.3, abs=0.04)
    assert p.variance_expliquee == pytest.approx(0.5**2 + 0.3**2, abs=0.05)


@pytest.mark.parametrize("nom", ["B", "F"])
def test_la_calibration_ne_voit_aucune_heure_de_l_annee_testee(nom):
    h = horaire_synthetique()
    reference = calibrer_facteurs(h, 2022, VARIANTES[nom])
    annee = h["ts_utc"].dt.tz_convert("Europe/Paris").dt.year
    perturbe = h.copy()
    # Le maximum glissant du nucléaire ne doit pas regarder les premières heures de 2022.
    perturbe.loc[annee >= 2022, ["prix_eur_mwh", "solaire_mw", "eolien_mw", "conso_mw", "nucleaire_mw", HYDRO, "charge_de_mw", "charge_es_mw"]] = 99999.0
    apres = calibrer_facteurs(perturbe, 2022, VARIANTES[nom])
    pd.testing.assert_series_equal(apres.coefficients, reference.coefficients)
    pd.testing.assert_frame_equal(apres.moyennes, reference.moyennes)
    assert apres.phi_lent == reference.phi_lent


def test_les_annees_avant_la_fenetre_sont_ignorees():
    h = horaire_synthetique()
    annee = h["ts_utc"].dt.tz_convert("Europe/Paris").dt.year
    perturbe = h.copy()
    perturbe.loc[annee == 2019, ["prix_eur_mwh", "nucleaire_mw"]] = 99999.0
    assert calibrer_facteurs(perturbe, 2022, VARIANTES["B"]).coefficients["france"] == calibrer_facteurs(h, 2022, VARIANTES["B"]).coefficients["france"]


def test_plus_de_nucleaire_l_annee_testee_baisse_les_prix():
    h = horaire_synthetique()
    p = calibrer_facteurs(h, 2022, VARIANTES["B"])
    annee = h["ts_utc"].dt.tz_convert("Europe/Paris").dt.year
    plus = h.copy()
    plus.loc[annee == 2022, "nucleaire_mw"] += 1000.0
    y0, _, _ = simuler_valeurs_reelles(p, h, VARIANTES["B"], 20, np.random.default_rng(0))
    y1, _, _ = simuler_valeurs_reelles(p, plus, VARIANTES["B"], 20, np.random.default_rng(0))
    assert y1.mean() < y0.mean()


def test_la_production_de_la_trajectoire_est_le_solaire_reel():
    h = horaire_synthetique()
    p = calibrer_facteurs(h, 2022, VARIANTES["A"])
    _, q, ts = simuler_valeurs_reelles(p, h, VARIANTES["A"], 3, np.random.default_rng(0))
    reel = h.set_index("ts_utc")["solaire_mw"].reindex(ts).to_numpy()
    np.testing.assert_array_equal(q[:, 2], reel)


def test_une_heure_inconnue_reste_inconnue_et_sort_du_taux_de_capture():
    h = horaire_synthetique()
    p = calibrer_facteurs(h, 2022, VARIANTES["A"])
    trou = h.copy()
    ts = grille_annee(2022)
    trou.loc[trou["ts_utc"] == ts[3000], "eolien_mw"] = np.nan
    y, q, ts = simuler_valeurs_reelles(p, trou, VARIANTES["A"], 3, np.random.default_rng(0))
    assert np.isnan(y[3000]).all()
    assert np.isfinite(y[3001]).all()
    assert np.isfinite(taux_capture_median(y, q, ts)).all()


def test_un_mois_sans_heure_connue_donne_nan():
    ts = pd.date_range("2024-06-30T20:00Z", periods=4, freq="h")
    y = np.array([[1.0], [1.0], [np.nan], [np.nan]])
    q = np.ones_like(y)
    tc = taux_capture_median(y, q, ts)
    assert tc[6] == pytest.approx(1.0) and np.isnan(tc[7])


def test_taux_capture_calcule_a_la_main():
    ts = pd.date_range("2024-06-30T20:00Z", periods=4, freq="h")
    y = np.array([[10.0, 10.0], [20.0, 40.0], [30.0, 30.0], [50.0, 50.0]])
    q = np.array([[1.0, 1.0], [3.0, 3.0], [1.0, 1.0], [1.0, 1.0]])
    tc = taux_capture_median(y, q, ts)
    assert tc[6] == pytest.approx(np.median([(10 + 60) / 4 / 15, (10 + 120) / 4 / 25]))
    assert tc[7] == pytest.approx((30 + 50) / 2 / 40)


@pytest.mark.parametrize(
    "biais, mae, reference, attendu",
    [
        (0.049, 0.030, 0.030, True),
        (-0.049, 0.030, 0.030, True),
        (0.05, 0.030, 0.030, False),
        (-0.06, 0.030, 0.030, False),
        (0.01, 0.0351, 0.030, False),
        (0.01, 0.0349, 0.030, True),
    ],
)
def test_regle_ecrite_avant_le_test(biais, mae, reference, attendu):
    assert explique_la_chute(biais, mae, reference) is attendu


def ecrire(chemin, debut, pas, valeurs):
    ts = pd.date_range(debut, periods=len(valeurs), freq=pas)
    chemin.write_text(json.dumps({"unix_seconds": [int(t.timestamp()) for t in ts], "production_types": [{"name": "Nuclear", "data": valeurs}]}))


def test_charger_filiere_au_quart_d_heure_et_a_l_heure(tmp_path):
    ecrire(tmp_path / "production_de_2020.json", "2020-01-01T00:00Z", "15min", [1.0, 2.0, 3.0, 6.0, 10.0, None, 10.0, 10.0])
    d = charger_filiere(tmp_path, "Nuclear", "nuc", pays="de")
    assert d["nuc"].iloc[0] == 3.0
    assert np.isnan(d["nuc"].iloc[1])
    ecrire(tmp_path / "production_fr_2020.json", "2020-01-01T00:00Z", "h", [5.0, None, 7.0])
    f = charger_filiere(tmp_path, "Nuclear", "nuc", pays="fr")
    assert f["nuc"].iloc[0] == 5.0 and np.isnan(f["nuc"].iloc[1]) and f["nuc"].iloc[2] == 7.0


def test_charger_filiere_passage_au_quart_d_heure_et_doublons(tmp_path):
    ecrire(tmp_path / "production_fr_2025.json", "2025-12-31T22:00Z", "h", [5.0, 7.0])
    ecrire(tmp_path / "production_fr_2026.json", "2025-12-31T23:00Z", "15min", [7.0, 9.0, 9.0, 11.0])
    f = charger_filiere(tmp_path, "Nuclear", "nuc")
    assert list(f["nuc"]) == [5.0, pytest.approx(9.0)]


def test_charger_filiere_refuse_un_pays_absent(tmp_path):
    with pytest.raises(FileNotFoundError):
        charger_filiere(tmp_path, "Nuclear", "nuc", pays="xx")


def test_les_plages_suivent_l_heure_et_la_saison_de_paris():
    # 31/03 à 22 h UTC : déjà le 1er avril à minuit à Paris.
    ts = pd.DatetimeIndex(["2024-03-31T21:00Z", "2024-03-31T22:00Z", "2024-08-31T21:59Z", "2024-08-31T22:00Z"])
    p = plages(ts)
    assert list(p.get_level_values("heure")) == [23, 0, 23, 0]
    assert list(p.get_level_values("ete")) == [False, True, True, False]
    assert MOIS_ETE == (4, 8)


def horaire_lambda_variable():
    """Le prix suit la charge à midi d'été avec un poids de 0,8, et ne la suit presque pas ailleurs (0,2)."""
    h = horaire_synthetique(poids=(0.0, 0.0))
    ts = pd.DatetimeIndex(h["ts_utc"])
    c = cases(ts)
    charge = pd.Series((h["conso_mw"] - h["solaire_mw"] - h["eolien_mw"] - nucleaire_disponible(h["nucleaire_mw"]).to_numpy() - h[HYDRO]).to_numpy(), index=ts)
    g = charge.groupby([c[k] for k in ["mois", "heure", "week_end"]])
    x = ((charge - g.transform("mean")) / g.transform("std")).fillna(0).to_numpy()
    midi_ete = (c["heure"].between(11, 16) & c["mois"].between(4, 8)).to_numpy()
    lam = np.where(midi_ete, 0.8, 0.2)
    bruit = np.random.default_rng(9).normal(size=len(ts))
    h["prix_eur_mwh"] = 50 * (1 + 0.1 * (lam * x + np.sqrt(1 - lam**2) * bruit))
    return h


def test_calibrer_plages_retrouve_les_deux_poids():
    p = calibrer_plages(horaire_lambda_variable(), 2022, VARIANTES["D"])
    assert len(p.lambdas) == 48
    assert p.lambdas.loc[(13, True)] == pytest.approx(0.8, abs=0.08)
    assert p.lambdas.loc[(13, False)] == pytest.approx(0.2, abs=0.12)
    assert p.lambdas.loc[(3, True)] == pytest.approx(0.2, abs=0.12)


def test_calibrer_plages_ne_voit_aucune_heure_de_l_annee_testee():
    h = horaire_lambda_variable()
    reference = calibrer_plages(h, 2022, VARIANTES["D"])
    annee = h["ts_utc"].dt.tz_convert("Europe/Paris").dt.year
    perturbe = h.copy()
    perturbe.loc[annee >= 2022, ["prix_eur_mwh", "solaire_mw", "eolien_mw", "conso_mw", "nucleaire_mw", HYDRO]] = 99999.0
    apres = calibrer_plages(perturbe, 2022, VARIANTES["D"])
    pd.testing.assert_series_equal(apres.lambdas, reference.lambdas)
    assert apres.phi_lent == reference.phi_lent


def test_calibrer_plages_refuse_les_voisins():
    with pytest.raises(ValueError, match="française"):
        calibrer_plages(horaire_synthetique(), 2022, VARIANTES["F"])


def test_simuler_plages_avec_lambda_constant_redonne_le_lambda_unique():
    h = horaire_synthetique()
    v = VARIANTES["D"]
    p = calibrer_plages(h, 2022, v)
    q = calibrer_facteurs(h, 2022, v)
    constant = pd.Series(float(q.coefficients["france"]), index=p.lambdas.index)
    p_c = ParametresPlages(p.lois, p.moyennes, p.ecarts, constant, q.poids_rapide, q.phi_rapide, q.phi_lent, 0.0, 2022)
    y_c, _, _ = simuler_plages(p_c, h, v, 5, np.random.default_rng(2))
    y_u, _, _ = simuler_valeurs_reelles(q, h, v, 5, np.random.default_rng(2))
    # Le lambda unique utilise V = Var(ajusté), très proche de lambda^2 : l'écart reste négligeable.
    assert np.nanmean(np.abs(y_c - y_u)) < 0.01


def test_un_lambda_plus_fort_baisse_davantage_l_heure_touchee():
    h = horaire_lambda_variable()
    v = VARIANTES["D"]
    p = calibrer_plages(h, 2022, v)
    annee = h["ts_utc"].dt.tz_convert("Europe/Paris").dt.year
    plus = h.copy()
    plus.loc[annee == 2022, "nucleaire_mw"] += 1500.0
    y0, _, ts = simuler_plages(p, h, v, 50, np.random.default_rng(0))
    y1, _, _ = simuler_plages(p, plus, v, 50, np.random.default_rng(0))
    c = cases(ts)
    midi_ete = (c["heure"].between(11, 16) & c["mois"].between(4, 8)).to_numpy()
    assert (y0 - y1)[midi_ete].mean() > 2 * (y0 - y1)[~midi_ete].mean()


def test_une_heure_inconnue_reste_inconnue_avec_les_plages():
    h = horaire_synthetique()
    v = VARIANTES["D"]
    p = calibrer_plages(h, 2022, v)
    ts = grille_annee(2022)
    trou = h.copy()
    trou.loc[trou["ts_utc"] == ts[3000], HYDRO] = np.nan
    y, _, _ = simuler_plages(p, trou, v, 3, np.random.default_rng(0))
    assert np.isnan(y[3000]).all() and np.isfinite(y[3001]).all()
