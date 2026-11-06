import numpy as np
import pandas as pd
import pytest

from ppa_pricer.backtest.prix import forme_connue, taux_implicite
from ppa_pricer.backtest.robustesse import bootstrap_skill, skill_global, skill_sans_chaque_annee
from ppa_pricer.modele.v1 import MOIS
from ppa_pricer.pricing.v1 import baseload_mensuel


def table_simple():
    # Année 2020 : méthode à 1 point, référence à 2. Année 2021 : méthode à 3, référence à 2.
    return pd.DataFrame(
        {
            "annee": [2020, 2020, 2021, 2021],
            "taux_capture": [1.0, 1.0, 1.0, 1.0],
            "m": [1.01, 0.99, 1.03, 0.97],
            "r": [1.02, 0.98, 1.02, 0.98],
        }
    )


def test_skill_global_a_la_main():
    assert skill_global(table_simple(), "m", "r") == pytest.approx(1 - 8 / 8)


def test_skill_sans_chaque_annee_a_la_main():
    s = skill_sans_chaque_annee(table_simple(), "m", "r")
    assert s[2020] == pytest.approx(1 - 3 / 2)
    assert s[2021] == pytest.approx(1 - 1 / 2)


def test_skill_ignore_les_mois_inconnus():
    t = table_simple()
    t.loc[0, "m"] = np.nan
    assert skill_global(t, "m", "r") == pytest.approx(1 - 7 / 6)


def test_bootstrap_ne_prend_que_des_annees_entieres():
    s = bootstrap_skill(table_simple(), "m", "r", 20_000, np.random.default_rng(0))
    # Deux années : tirages possibles 2020-2020, 2020-2021 et 2021-2021.
    assert set(np.round(np.unique(s), 6)) == {0.5, 0.0, -0.5}
    assert (s == 0.5).mean() == pytest.approx(0.25, abs=0.01)
    assert (s == -0.5).mean() == pytest.approx(0.25, abs=0.01)


def test_taux_implicite_a_la_main():
    forme = pd.Series(1.0, index=list(MOIS))
    tc = pd.Series([0.5] * 6 + [1.0] * 6, index=list(MOIS))
    volumes = pd.Series([1.0] * 6 + [3.0] * 6, index=list(MOIS))
    assert taux_implicite(tc, forme, volumes, 2023) == pytest.approx((6 * 0.5 + 18 * 1.0) / 24)


def test_taux_implicite_tient_compte_de_la_forme():
    # Des mois d'été moins chers baissent le prix capté par un parc qui produit surtout l'été.
    tc = pd.Series(1.0, index=list(MOIS))
    volumes = pd.Series([1.0] * 3 + [5.0] * 6 + [1.0] * 3, index=list(MOIS))
    plate = pd.Series(1.0, index=list(MOIS))
    creuse = pd.Series([1.5] * 3 + [0.5] * 6 + [1.5] * 3, index=list(MOIS))
    assert taux_implicite(tc, plate, volumes, 2023) == pytest.approx(1.0)
    assert taux_implicite(tc, creuse, volumes, 2023) < 0.75
    assert baseload_mensuel(1.0, creuse, 2023).mean() == pytest.approx(1.0, abs=0.01)


def test_forme_connue_n_utilise_que_les_deux_annees_precedentes():
    periodes = pd.period_range("2019-01", "2022-12", freq="M")
    base = pd.DataFrame({"periode": periodes, "valide": True, "heures_utilisees": 720.0, "baseload_eur_mwh": 50.0 + periodes.month})
    reference = forme_connue(base, 2022)
    perturbe = base.copy()
    perturbe.loc[perturbe["periode"].dt.year.isin([2019, 2022]), "baseload_eur_mwh"] = 1.0 + perturbe["periode"].dt.month**3
    pd.testing.assert_series_equal(forme_connue(perturbe, 2022), reference)
