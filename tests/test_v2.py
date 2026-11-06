import numpy as np
import pandas as pd
import pytest

from ppa_pricer.modele.v1 import MOIS
from ppa_pricer.modele.v2 import ParametresV2, calibrer_v2, niveau_du_trimestre, niveaux_trimestriels, prevoir_v2
from ppa_pricer.pricing.courbe import (
    PARC_BASE_GW,
    TRIMESTRES,
    baseload_courbe,
    heures_mensuelles,
    historique_pointe,
    niveau_par_mois,
    niveaux_courbe,
    part_selon_parc,
    taux_implicite_pointe,
)
from ppa_pricer.pricing.monte_carlo import CONTRAT_PAP, CONTRAT_SPOT, caler_trimestres, flux_avec_erreurs, flux_contrats, mesures_risque, parts_covariance, parts_variance


def mensuel_synthetique(annees=range(2016, 2024), beta=-3.0, gamma=0.05, delta=0.4, bruit=0.0):
    """Taux de capture généré exactement par la forme du modèle V2, avec un niveau propre à chaque trimestre."""
    rng = np.random.default_rng(1)
    lignes = []
    for a in annees:
        niveaux = {q: 40.0 * np.exp(rng.normal(0, 0.5)) for q in range(1, 5)}
        for m in MOIS:
            part = 0.01 * (1 + 0.2 * (a - annees[0])) * (1 + np.sin(np.pi * m / 12)) * rng.uniform(0.9, 1.1)
            b = niveaux[(m - 1) // 3 + 1]
            lignes.append(
                {
                    "periode": pd.Period(f"{a}-{m:02d}", "M"),
                    "valide": True,
                    "heures_utilisees": 720,
                    "baseload_eur_mwh": b,
                    "part_solaire": part,
                    "taux_capture": 0.8 + 0.01 * m + beta * part + gamma * np.log(b) + delta * part * np.log(b) + bruit * rng.normal(),
                }
            )
    return pd.DataFrame(lignes)


def test_calibration_retrouve_les_parametres():
    p = calibrer_v2(mensuel_synthetique(), 2024)
    assert p.beta == pytest.approx(-3.0, abs=1e-6)
    assert p.gamma == pytest.approx(0.05, abs=1e-6)
    assert p.delta == pytest.approx(0.4, abs=1e-6)
    assert p.alpha[5] == pytest.approx(0.85, abs=1e-6)
    assert p.n_mois == 96


def test_calibration_sans_donnee_future():
    m = mensuel_synthetique(bruit=0.01)
    reference = calibrer_v2(m, 2022)
    perturbe = m.copy()
    apres = perturbe["periode"].dt.year >= 2022
    perturbe.loc[apres, ["taux_capture", "part_solaire", "baseload_eur_mwh"]] = 999.0
    autre = calibrer_v2(perturbe, 2022)
    assert autre.beta == reference.beta and autre.delta == reference.delta and autre.alpha == reference.alpha


def test_prevision_a_la_main():
    p = ParametresV2({m: 1.0 for m in MOIS}, beta=-2.0, gamma=0.1, delta=0.5, n_mois=1, annee_prevue=2027)
    mois = pd.Series([4], index=[4])
    r = prevoir_v2(p, mois, pd.Series([0.1], index=[4]), pd.Series([np.e], index=[4]))
    assert r[4] == pytest.approx(1.0 - 0.2 + 0.1 + 0.05)


def test_le_niveau_change_la_pente():
    p = ParametresV2({m: 1.0 for m in MOIS}, beta=-10.0, gamma=0.0, delta=1.5, n_mois=1, annee_prevue=2027)
    mois = pd.Series([6], index=[6])
    effet = lambda b: prevoir_v2(p, mois, pd.Series([0.2], index=[6]), pd.Series([b], index=[6]))[6] - prevoir_v2(p, mois, pd.Series([0.1], index=[6]), pd.Series([b], index=[6]))[6]
    assert abs(effet(120.0)) < abs(effet(40.0))


def test_un_niveau_inconnu_donne_nan():
    p = ParametresV2({m: 1.0 for m in MOIS}, -2.0, 0.1, 0.5, 1, 2027)
    assert np.isnan(prevoir_v2(p, pd.Series([4], index=[4]), pd.Series([0.1], index=[4]), pd.Series([np.nan], index=[4]))[4])


def test_niveaux_trimestriels_ponderes_par_les_heures_et_mois_valides():
    m = pd.DataFrame(
        {
            "periode": pd.period_range("2024-01", periods=3, freq="M"),
            "valide": [True, True, False],
            "heures_utilisees": [100, 300, 500],
            "baseload_eur_mwh": [10.0, 50.0, 999.0],
        }
    )
    n = niveaux_trimestriels(m)
    assert n[(2024, 1)] == pytest.approx(40.0)
    s = niveau_du_trimestre(n, 2024, pd.Series([2, 5], index=[2, 5]))
    assert s[2] == pytest.approx(40.0) and np.isnan(s[5])


def courbe_simple():
    # Trimestres dont la moyenne pondérée par les heures de 2027 redonne le contrat calendaire.
    h = heures_mensuelles(2027)
    t = {1: 190.0, 2: 80.0, 3: 96.0, 4: 120.0}
    moyenne = sum(t[q] * h[TRIMESTRES[q]].sum() for q in t) / h.sum()
    lignes = [{"echeance": f"T{q}_2027", "base_eur_mwh": v, "pointe_eur_mwh": v} for q, v in t.items()] + [{"echeance": "CAL_2027", "base_eur_mwh": moyenne, "pointe_eur_mwh": moyenne}]
    return pd.DataFrame(lignes).set_index("echeance"), moyenne


def test_niveaux_courbe_et_controle_de_coherence():
    c, _ = courbe_simple()
    assert niveaux_courbe(c, 2027)[2] == 80.0
    c.loc["CAL_2027", "base_eur_mwh"] = 90.0
    with pytest.raises(ValueError, match="incohérente"):
        niveaux_courbe(c, 2027)


def test_baseload_courbe_respecte_chaque_trimestre_et_le_calendaire():
    c, moyenne = courbe_simple()
    niveaux = niveaux_courbe(c, 2027)
    forme = pd.Series([1.3, 1.1, 0.9, 0.7, 0.5, 0.6, 0.8, 0.9, 0.8, 1.0, 1.2, 1.4], index=list(MOIS))
    b = baseload_courbe(niveaux, forme, 2027)
    h = heures_mensuelles(2027)
    for q, mois in TRIMESTRES.items():
        assert (b[mois] * h[mois]).sum() / h[mois].sum() == pytest.approx(niveaux[q])
    assert (b * h).sum() / h.sum() == pytest.approx(moyenne)
    # La répartition dans le trimestre suit la forme.
    assert b[1] / b[2] == pytest.approx(1.3 / 1.1)


def test_niveau_par_mois():
    c, _ = courbe_simple()
    n = niveau_par_mois(niveaux_courbe(c, 2027))
    assert n[5] == 80.0 and n[12] == 120.0


def test_part_selon_parc_proportionnelle():
    part = pd.Series([0.1, 0.2], index=[4, 5])
    r = part_selon_parc(part, PARC_BASE_GW * 1.2)
    assert r[5] == pytest.approx(0.24)


def horaire_pointe():
    ts = pd.date_range("2023-12-31T23:00Z", "2024-12-31T22:00Z", freq="h")
    local = ts.tz_convert("Europe/Paris")
    pointe = (local.day_of_week < 5) & (local.hour >= 8) & (local.hour < 20)
    return pd.DataFrame({"ts_utc": ts, "prix_eur_mwh": np.where(pointe, 40.0, 60.0), "solaire_mw": np.where(pointe, 10.0, 0.0)})


def test_historique_pointe_a_la_main():
    h = historique_pointe(horaire_pointe())
    assert list(h["trimestre"]) == [1, 2, 3, 4]
    g = h.iloc[1]
    part_pointe = 5 / 14
    assert g["rapport"] == pytest.approx(40.0 / g["base"], rel=1e-9)
    assert g["taux_capture"] == pytest.approx(40.0 / g["base"], rel=1e-9)
    assert g["base"] == pytest.approx(40.0 * part_pointe + 60.0 * (1 - part_pointe), abs=0.01)


def test_un_trimestre_incomplet_est_ecarte():
    h = horaire_pointe()
    assert list(historique_pointe(h[h["ts_utc"] < "2024-05-01"])["trimestre"]) == [1]


def test_taux_implicite_sur_une_droite_exacte():
    g = pd.DataFrame({"trimestre": 2, "rapport": [0.7, 0.9, 1.1], "taux_capture": [0.3, 0.6, 0.9]})
    tc, r2 = taux_implicite_pointe(g, 2, 0.8)
    assert tc == pytest.approx(0.45) and r2 == pytest.approx(1.0)


def test_caler_trimestres_atteint_les_cibles_sans_changer_les_rapports():
    ts = pd.date_range("2026-12-31T23:00Z", "2027-12-31T22:00Z", freq="h")
    rng = np.random.default_rng(0)
    y = rng.uniform(0.5, 1.5, (len(ts), 30))
    cibles = {1: 1.6, 2: 0.6, 3: 0.8, 4: 1.0}
    c = caler_trimestres(y, ts, cibles)
    q = ts.tz_convert("Europe/Paris").quarter
    for t, v in cibles.items():
        assert c[q == t].mean() == pytest.approx(v)
        rapport = c[q == t] / y[q == t]
        assert rapport.max() == pytest.approx(rapport.min())


def flux_simple(n=400):
    rng = np.random.default_rng(2)
    y = rng.uniform(0.0, 2.0, (48, n))
    y = y / y.mean(axis=0)
    q = rng.uniform(0.5, 3.0, (48, n))
    b = 60 * np.exp(0.2 * rng.standard_normal(n))
    return flux_contrats(y, q, b, (10.0,)), b


def test_flux_avec_erreurs_identite_et_moyenne():
    f, b = flux_simple()
    erreurs = np.array([-0.05, 0.0, 0.02, 0.2])
    v, a = flux_avec_erreurs(f, b, erreurs)
    assert len(v[CONTRAT_SPOT]) == 400 * 4
    # L'erreur est centrée : le revenu moyen de chaque trajectoire ne change pas.
    assert v[CONTRAT_SPOT].mean() == pytest.approx(f.revenu.mean())
    # Le vendeur en pay-as-produced ne dépend pas du prix, l'acheteur si.
    assert v[CONTRAT_PAP].std() == pytest.approx(f.vendeur[CONTRAT_PAP].std())
    assert a[CONTRAT_PAP].std() > f.acheteur[CONTRAT_PAP].std()
    for c, x in a.items():
        np.testing.assert_allclose(v[c] + x, v[CONTRAT_SPOT])


def test_flux_avec_erreurs_ne_depend_pas_de_l_ordre():
    f, b = flux_simple()
    v1, _ = flux_avec_erreurs(f, b, np.array([0.0, 0.1]))
    v2, _ = flux_avec_erreurs(f, b, np.array([0.1, 0.0]))
    assert mesures_risque(v1[CONTRAT_SPOT])["var"] == pytest.approx(mesures_risque(v2[CONTRAT_SPOT])["var"])


def test_parts_covariance_somme_a_un():
    rng = np.random.default_rng(3)
    n = 5000
    q, tc = 1500 * np.exp(0.03 * rng.normal(size=n)), 0.5 * np.exp(0.1 * rng.normal(size=n))
    b = 60 * np.exp(0.25 * rng.normal(size=n))
    r = q * b * tc
    p = parts_covariance(r, q, b)
    assert sum(p.values()) == pytest.approx(1.0)
    assert p["baseload"] > p["taux_capture"] > p["volume"]
    # Sans corrélation entre facteurs, les deux décompositions se rejoignent.
    assert p["baseload"] == pytest.approx(parts_variance(r, q, b)["baseload"], abs=0.03)
