import numpy as np
import pandas as pd
import pytest

from ppa_pricer.analyse.capture import taux_de_capture
from ppa_pricer.backtest.metriques import (
    biais,
    diebold_mariano,
    mae,
    mae_ponderee,
    skill_score,
    variance_long_terme,
)
from ppa_pricer.backtest.references import climatologie, persistance
from ppa_pricer.backtest.walk_forward import METHODES, prevoir_annee, taux_annuels
from ppa_pricer.modele.v1 import calibrer, prevoir_part_solaire

ALPHA = {m: 1.0 + 0.01 * m for m in range(1, 13)}
BETA = -3.0


def mensuel_synthetique(debut="2015-01", fin="2020-12", bruit=0.0, seed=0):
    """Mois où TC = α_mois + β·S (+ bruit) et où la part du solaire croît de 10 % par an."""
    rng = np.random.default_rng(seed)
    periodes = pd.period_range(debut, fin, freq="M")
    annees = periodes.year - periodes.year.min()
    part = 0.02 * 1.1 ** annees.to_numpy() * (1 + 0.3 * np.sin(periodes.month.to_numpy() / 12 * np.pi))
    tc = np.array([ALPHA[m] for m in periodes.month]) + BETA * part + bruit * rng.standard_normal(len(periodes))
    return pd.DataFrame(
        {
            "periode": periodes,
            "valide": True,
            "taux_capture": tc,
            "part_solaire": part,
            "energie_solaire_mwh": part * 1e6,
            "baseload_eur_mwh": 50.0,
            "heures_utilisees": 720,
        }
    )


def test_calibration_retrouve_les_vrais_parametres():
    p = calibrer(mensuel_synthetique(), 2020)
    assert p.beta == pytest.approx(BETA)
    assert p.alpha[6] == pytest.approx(ALPHA[6])
    assert p.n_mois == 60


def test_calibration_refuse_un_mois_sans_historique():
    m = mensuel_synthetique()
    m = m[m["periode"].dt.month != 3]
    with pytest.raises(ValueError, match="mois \\[3\\]"):
        calibrer(m, 2020)


def test_aucune_donnee_future_n_influence_la_prevision():
    m = mensuel_synthetique(bruit=0.05)
    reference, _ = prevoir_annee(m, 2019)
    perturbe = m.copy()
    futur = perturbe["periode"].dt.year >= 2019
    perturbe.loc[futur, ["taux_capture", "part_solaire", "energie_solaire_mwh"]] = 999.0
    apres, _ = prevoir_annee(perturbe, 2019)
    # Le modèle conditionnel reçoit par construction la part réalisée de l'année prévue : il est exclu.
    for colonne in ["modele_realiste", "r1_persistance", "r2_climatologie", "part_solaire_prevue"]:
        pd.testing.assert_series_equal(reference[colonne], apres[colonne])


def test_part_solaire_prevue_hypothese_h4():
    m = mensuel_synthetique()
    prevue = prevoir_part_solaire(m, 2019)
    juin_2018 = m.loc[m["periode"] == pd.Period("2018-06", "M"), "part_solaire"].iloc[0]
    assert prevue[6] == pytest.approx(juin_2018 * 1.1)


def test_references_naives():
    m = mensuel_synthetique(bruit=0.05)
    juin = m[m["periode"].dt.month == 6]
    juin = juin.set_index(juin["periode"].dt.year)["taux_capture"]
    assert persistance(m, 2019)[6] == pytest.approx(juin[2018])
    assert climatologie(m, 2019)[6] == pytest.approx(juin.loc[2015:2018].mean())


def test_metriques_simples():
    e = pd.Series([0.1, -0.3])
    assert mae(e) == pytest.approx(0.2)
    assert biais(e) == pytest.approx(-0.1)
    assert mae_ponderee(e, pd.Series([3.0, 1.0])) == pytest.approx((0.3 + 0.3) / 4)
    assert skill_score(0.03, 0.04) == pytest.approx(0.25)


def test_variance_long_terme_sans_retard_est_la_variance():
    d = np.array([1.0, -2.0, 0.5, 3.0])
    assert variance_long_terme(d, 0) == pytest.approx(d.var())


def test_variance_long_terme_un_retard_calcul_manuel():
    d = np.array([1.0, 2.0, 4.0, 1.0])
    c = d - d.mean()
    attendu = c @ c / 4 + 2 * 0.5 * (c[1:] @ c[:-1]) / 4
    assert variance_long_terme(d, 1) == pytest.approx(attendu)


def test_diebold_mariano_signe_et_significativite():
    rng = np.random.default_rng(1)
    bonne = pd.Series(0.02 * rng.standard_normal(96))
    mauvaise = pd.Series(0.10 * rng.standard_normal(96))
    dm = diebold_mariano(bonne, mauvaise)
    assert dm.statistique < 0
    assert dm.p_valeur < 0.01
    assert dm.n == 96


def test_taux_annuel_avec_previsions_parfaites_egale_le_realise():
    rng = np.random.default_rng(2)
    ts = pd.date_range("2023-12-31T23:00Z", "2024-12-31T22:00Z", freq="h")
    heure = ts.tz_convert("Europe/Paris").hour.to_numpy()
    soleil = np.clip(np.sin((heure - 6) / 12 * np.pi), 0, None)
    horaire = pd.DataFrame(
        {
            "ts_utc": ts,
            "prix_eur_mwh": 60 + 20 * rng.standard_normal(len(ts)) - 30 * soleil,
            "solaire_mw": 5000 * soleil * rng.uniform(0.5, 1, len(ts)),
            "conso_mw": 50000.0,
        }
    )
    mensuel = taux_de_capture(horaire, "M")
    annuel = taux_de_capture(horaire, "Y")
    previsions = mensuel.assign(annee=2024, **{m: mensuel["taux_capture"] for m in METHODES})
    resultat = taux_annuels(previsions).iloc[0]
    assert resultat["taux_capture"] == pytest.approx(annuel["taux_capture"].iloc[0])
    assert resultat["modele_realiste"] == pytest.approx(annuel["taux_capture"].iloc[0])
