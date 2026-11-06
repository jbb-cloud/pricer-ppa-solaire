import numpy as np
import pandas as pd
import pytest

from ppa_pricer.modele.v1 import MOIS
from ppa_pricer.modele.v2 import prevoir_v2
from ppa_pricer.pricing.calcul import niveaux_a, preparer_marche, prix_v2, simuler_risques
from ppa_pricer.pricing.courbe import TRIMESTRES, baseload_courbe, heures_mensuelles, niveau_par_mois, part_selon_parc
from ppa_pricer.pricing.monte_carlo import CONTRAT_PAP, CONTRAT_SPOT, flux_contrats
from ppa_pricer.pricing.v1 import prix_juste
from test_monte_carlo import horaire_synthetique

ANNEE = 2027
VOLUMES = pd.Series([40.0, 60, 100, 130, 160, 170, 180, 160, 120, 80, 50, 35], index=list(MOIS))
VOLUMES_ANNUELS = pd.DataFrame({m: [VOLUMES[m] * 0.9, VOLUMES[m] * 1.1] for m in MOIS}, index=[2010, 2011])


def courbe_livraison():
    h = heures_mensuelles(ANNEE)
    t = {1: 90.0, 2: 40.0, 3: 50.0, 4: 70.0}
    moyenne = sum(t[q] * h[TRIMESTRES[q]].sum() for q in t) / h.sum()
    lignes = [{"echeance": f"T{q}_{ANNEE}", "base_eur_mwh": v, "pointe_eur_mwh": v} for q, v in t.items()]
    lignes.append({"echeance": f"CAL_{ANNEE}", "base_eur_mwh": moyenne, "pointe_eur_mwh": moyenne})
    return pd.DataFrame(lignes).set_index("echeance")


@pytest.fixture(scope="module")
def marche():
    return preparer_marche(horaire_synthetique(annees=tuple(range(2019, 2026)), fin="2026-08-31T21:00Z"), courbe_livraison(), ANNEE, np.array([0.02, -0.01, 0.03]))


def test_prix_v2_refait_a_la_main(marche):
    r = prix_v2(marche, VOLUMES, 35.0)
    assert np.isfinite(r.prix)
    part = part_selon_parc(marche.entrees["part_solaire_base"], 35.0)
    mois = pd.Series(list(MOIS), index=list(MOIS))
    tc = prevoir_v2(marche.p_v2, mois, part, niveau_par_mois(marche.niveaux))
    baseload = baseload_courbe(marche.niveaux, marche.forme, ANNEE)
    assert r.prix == pytest.approx(prix_juste(tc, baseload, VOLUMES))
    assert r.detail["revenu"].sum() / VOLUMES.sum() == pytest.approx(r.prix)
    pd.testing.assert_series_equal(r.detail["part_solaire"], part, check_names=False)


def test_niveau_egal_a_la_cotation_ne_change_rien_et_double_le_baseload(marche):
    a = prix_v2(marche, VOLUMES, 35.0)
    b = prix_v2(marche, VOLUMES, 35.0, marche.calendaire)
    assert b.prix == pytest.approx(a.prix)
    double = prix_v2(marche, VOLUMES, 35.0, 2 * marche.calendaire)
    np.testing.assert_allclose(double.detail["baseload"], 2 * a.detail["baseload"])
    # Les rapports entre trimestres sont gardés.
    k = niveaux_a(marche, 2 * marche.calendaire)
    np.testing.assert_allclose(k / k[1], marche.niveaux / marche.niveaux[1])


def test_risques_reproductibles_et_coherents(marche):
    a = simuler_risques(marche, VOLUMES_ANNUELS, (35.0,), n=200, graine=3)
    b = simuler_risques(marche, VOLUMES_ANNUELS, (35.0,), n=200, graine=3)
    np.testing.assert_array_equal(a.flux.revenu, b.flux.revenu)
    autre = simuler_risques(marche, VOLUMES_ANNUELS, (35.0,), n=200, graine=4)
    assert not np.array_equal(a.flux.revenu, autre.flux.revenu)
    # Les flux sont ceux de flux_contrats sur les mêmes tirages.
    f = flux_contrats(a.y, a.q, a.baseload)
    assert a.flux.prix[CONTRAT_PAP] == pytest.approx(f.prix[CONTRAT_PAP])
    # L'erreur de modèle multiplie les trajectoires par le nombre d'erreurs, sans changer la moyenne du spot.
    assert len(a.vendeur[CONTRAT_SPOT]) == 3 * 200
    assert a.vendeur[CONTRAT_SPOT].mean() == pytest.approx(a.flux.revenu.mean())


def test_risques_suivent_le_niveau_et_les_trimestres(marche):
    r = simuler_risques(marche, VOLUMES_ANNUELS, (35.0,), niveau=100.0, sigma=0.1, correlation=0.0, n=300, graine=1)
    assert r.baseload.mean() == pytest.approx(100.0, rel=0.03)
    trimestre = pd.date_range(f"{ANNEE - 1}-12-31T23:00Z", periods=r.y.shape[0], freq="h").tz_convert("Europe/Paris").quarter
    moyennes = pd.Series({q: r.y[trimestre == q].mean() for q in TRIMESTRES})
    np.testing.assert_allclose(moyennes / moyennes[1], marche.niveaux / marche.niveaux[1], rtol=1e-9)
