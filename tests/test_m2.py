import json
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from ppa_pricer.donnees.energy_charts import charger_eolien, lire_eolien_brut
from ppa_pricer.modele.m0 import cases, grille_annee
from ppa_pricer.modele.m1 import prix_depuis_scores, simuler_latente
from ppa_pricer.modele.m2 import (
    calibrer_m2,
    croissances_passees,
    formes_meteo,
    positions_source,
    prevoir_m2,
    simuler_m2,
    taux_capture_trajectoires,
    tirer_meteo,
)

LAMBDA = 0.6


def horaire_synthetique(annees=(2019, 2020, 2021, 2022), graine=1, croissance=0.2):
    """Prix dont le rang dans la case suit la charge résiduelle avec un poids connu ; solaire en cloche qui croît."""
    ts = pd.date_range(f"{annees[0] - 1}-12-31T23:00Z", f"{annees[-1]}-12-31T22:00Z", freq="h")
    rng = np.random.default_rng(graine)
    local = ts.tz_convert("Europe/Paris")
    meteo = np.zeros(len(ts))
    for t in range(1, len(ts)):
        meteo[t] = 0.95 * meteo[t - 1] + rng.normal(0, 0.3)
    solaire = 1000 * (1 + croissance) ** (local.year - annees[0]) * np.clip(1 - ((local.hour + 0.5 - 13.5) / 6) ** 2, 0, None) * np.clip(1 + 0.2 * meteo, 0.1, None)
    eolien = 500 * np.clip(1 + 0.5 * meteo, 0, None)
    conso = 5000 + 800 * np.sin(2 * np.pi * local.hour / 24) + 300 * rng.normal(size=len(ts))
    horaire = pd.DataFrame({"ts_utc": ts, "solaire_mw": solaire, "eolien_mw": eolien, "conso_mw": conso})
    charge = pd.Series(conso - solaire - eolien, index=ts)
    c = cases(ts)
    groupes = charge.groupby([c[k] for k in ["mois", "heure", "week_end"]])
    x = ((charge - groupes.transform("mean")) / groupes.transform("std")).to_numpy()
    horaire["prix_eur_mwh"] = (50 + 20 * (local.year - annees[0])) * (1 + 0.1 * (LAMBDA * x + np.sqrt(1 - LAMBDA**2) * rng.normal(size=len(ts))))
    return horaire


def annee_paris(h):
    return h["ts_utc"].dt.tz_convert("Europe/Paris").dt.year


def test_lambda_retrouve_le_poids_de_la_charge():
    assert calibrer_m2(horaire_synthetique(), 2022).poids_charge == pytest.approx(LAMBDA, abs=0.04)


def test_calibration_sans_donnee_future():
    h = horaire_synthetique()
    reference = calibrer_m2(h, 2022)
    perturbe = h.copy()
    perturbe.loc[annee_paris(h) >= 2022, ["prix_eur_mwh", "solaire_mw", "eolien_mw", "conso_mw"]] = 999.0
    apres = calibrer_m2(perturbe, 2022)
    assert apres.poids_charge == reference.poids_charge
    assert apres.phi_lent == reference.phi_lent
    np.testing.assert_array_equal(apres.croissances, reference.croissances)
    pd.testing.assert_series_equal(apres.charge_moyenne, reference.charge_moyenne)
    pd.testing.assert_series_equal(apres.niveaux, reference.niveaux)
    assert all(np.array_equal(apres.lois[c], reference.lois[c]) for c in reference.lois)


def test_les_annees_avant_la_fenetre_ne_changent_que_les_croissances():
    h = horaire_synthetique()
    reference = calibrer_m2(h, 2022)
    perturbe = h.copy()
    perturbe.loc[annee_paris(h) == 2019, ["prix_eur_mwh", "eolien_mw", "conso_mw"]] = 999.0
    perturbe.loc[annee_paris(h) == 2019, "solaire_mw"] *= 2
    apres = calibrer_m2(perturbe, 2022)
    assert apres.poids_charge == reference.poids_charge
    pd.testing.assert_frame_equal(apres.formes[2021], reference.formes[2021])
    assert apres.croissances[-1] == reference.croissances[-1]
    assert apres.croissances[0] != reference.croissances[0]


def test_croissances_passees_seulement():
    h = horaire_synthetique(croissance=0.2)
    assert croissances_passees(h, 2022) == pytest.approx([0.2, 0.2], abs=0.02)
    with pytest.raises(ValueError, match="croissance"):
        croissances_passees(h, 2020)


def test_regle_h4_ne_garde_que_la_derniere_croissance():
    h = horaire_synthetique()
    assert list(calibrer_m2(h, 2022, regle_croissance="h4").croissances) == [croissances_passees(h, 2022)[-1]]
    with pytest.raises(ValueError, match="Règle"):
        calibrer_m2(h, 2022, regle_croissance="autre")


def test_fenetre_d_un_an_n_utilise_que_l_annee_precedente():
    h = horaire_synthetique()
    p = calibrer_m2(h, 2022, fenetre=1)
    assert sorted(p.formes) == [2021]
    perturbe = h.copy()
    perturbe.loc[annee_paris(h) == 2020, "prix_eur_mwh"] = 999.0
    assert calibrer_m2(perturbe, 2022, fenetre=1).poids_charge == p.poids_charge


@pytest.mark.parametrize("annee, source", [(2024, 2023), (2024, 2022), (2023, 2021), (2025, 2024)])
def test_positions_restent_dans_l_annee_source_et_gardent_le_jour(annee, source):
    # Années bissextiles comprises : la dernière semaine, courte, ne doit pas sortir de l'année source.
    ts = grille_annee(annee)
    forme = pd.DataFrame({"solaire_mw": 1.0}, index=grille_annee(source))
    positions = positions_source(ts, annee, source, forme)
    assert positions.min() >= 0 and positions.max() < len(forme)
    origine = forme.index[positions]
    assert (origine.day_of_week == ts.day_of_week).all()
    assert (origine.hour == ts.hour).all()
    # Même saison : au plus 3 semaines d'écart dans l'année.
    ecart = np.abs(origine.day_of_year - ts.day_of_year)
    assert np.minimum(ecart, 366 - ecart).max() <= 21


def test_une_semaine_incomplete_est_remplacee_sans_inventer_de_valeur():
    ts = grille_annee(2023)
    forme = pd.DataFrame({"solaire_mw": 1.0}, index=grille_annee(2022))
    forme.iloc[3000:3010] = np.nan
    positions = positions_source(ts, 2023, 2022, forme)
    assert forme["solaire_mw"].to_numpy()[positions].min() == 1.0
    assert not np.isnan(forme["solaire_mw"].to_numpy()[positions]).any()


def test_une_annee_sans_semaine_complete_est_refusee():
    forme = pd.DataFrame({"solaire_mw": np.nan}, index=grille_annee(2022))
    with pytest.raises(ValueError, match="semaine complète"):
        positions_source(grille_annee(2023), 2023, 2022, forme)


def test_les_formes_sont_divisees_par_la_moyenne_annuelle_et_gardent_les_trous():
    h = horaire_synthetique()
    h.loc[(annee_paris(h) == 2021).idxmax(), "eolien_mw"] = np.nan
    forme = formes_meteo(h, [2021])[2021]
    assert forme.mean().to_numpy() == pytest.approx(1.0)
    assert forme["eolien_mw"].isna().sum() == 1


def test_la_meteo_ne_vient_que_de_la_fenetre():
    p = calibrer_m2(horaire_synthetique(), 2022)
    # Marqueur : chaque année de la fenêtre a une forme constante égale à son numéro.
    formes = {a: pd.DataFrame(float(a), index=f.index, columns=f.columns) for a, f in p.formes.items()}
    niveaux = pd.Series(1.0, index=p.niveaux.index)
    p = replace(p, formes=formes, niveaux=niveaux, croissances=np.array([0.0]))
    ts = grille_annee(2022)
    meteo = tirer_meteo(p, ts, 20, np.random.default_rng(0))
    assert set(np.unique(meteo["conso_mw"])) == {2020.0, 2021.0}
    # Les trois séries viennent de la même année, et chaque semaine forme un bloc.
    np.testing.assert_array_equal(meteo["solaire_mw"], meteo["conso_mw"])
    np.testing.assert_array_equal(meteo["eolien_mw"], meteo["conso_mw"])
    assert np.unique(meteo["conso_mw"][:168, 0]).size == 1


def test_le_niveau_du_parc_suit_la_croissance_tiree():
    p = calibrer_m2(horaire_synthetique(), 2022)
    ts = grille_annee(2022)
    q0 = tirer_meteo(replace(p, croissances=np.array([0.0])), ts, 50, np.random.default_rng(0))["solaire_mw"]
    q5 = tirer_meteo(replace(p, croissances=np.array([0.5])), ts, 50, np.random.default_rng(0))["solaire_mw"]
    assert q5.mean() / q0.mean() == pytest.approx(1.5)
    assert q0.mean() == pytest.approx(p.niveaux["solaire_mw"], rel=0.05)


def test_un_lambda_nul_redonne_exactement_le_modele_sans_charge():
    p = replace(calibrer_m2(horaire_synthetique(), 2022), poids_charge=0.0)
    ts = grille_annee(2022)
    y, _ = simuler_m2(p, ts, 5, np.random.default_rng(3))
    rng = np.random.default_rng(3)
    tirer_meteo(p, ts, 5, rng)
    np.testing.assert_array_equal(y, prix_depuis_scores(p.lois, simuler_latente(p, len(ts), 5, rng), ts))


def test_le_prix_reste_dans_les_valeurs_observees_de_la_case():
    p = calibrer_m2(horaire_synthetique(), 2022)
    p = replace(p, croissances=np.array([5.0]))
    ts = grille_annee(2022)
    y, _ = simuler_m2(p, ts, 5, np.random.default_rng(0))
    c = cases(ts)
    for i in (10, 3000, 6000):
        loi = p.lois[(c["mois"].iloc[i], c["heure"].iloc[i], c["week_end"].iloc[i])]
        assert loi.min() <= y[i].min() and y[i].max() <= loi.max()


def test_plus_de_solaire_baisse_le_taux_de_capture():
    p = calibrer_m2(horaire_synthetique(), 2022)
    ts = grille_annee(2022)

    def tc_moyen(g):
        y, q = simuler_m2(replace(p, croissances=np.array([g])), ts, 30, np.random.default_rng(1))
        return taux_capture_trajectoires(y, q, ts).median(axis=1).mean()

    assert tc_moyen(1.0) < tc_moyen(0.0)


def test_taux_capture_calcule_a_la_main():
    ts = pd.date_range("2024-06-30T20:00Z", periods=4, freq="h", tz=None)
    # Deux heures en juin, deux en juillet (heure de Paris), une trajectoire.
    y = np.array([[10.0], [20.0], [30.0], [50.0]])
    q = np.array([[1.0], [3.0], [1.0], [1.0]])
    tc = taux_capture_trajectoires(y, q, ts)
    assert tc.loc[6, 0] == pytest.approx((10 + 60) / 4 / 15)
    assert tc.loc[7, 0] == pytest.approx((30 + 50) / 2 / 40)


def test_prevision_ordonnee_et_reproductible():
    h = horaire_synthetique()
    prevision, _ = prevoir_m2(h, 2022, n=30)
    assert list(prevision["mois"]) == list(range(1, 13))
    assert (prevision["tc_bas"] <= prevision["tc"]).all() and (prevision["tc"] <= prevision["tc_haut"]).all()
    pd.testing.assert_frame_equal(prevision, prevoir_m2(h, 2022, n=30)[0])


def ecrire_production(chemin, debut, n, terrestre, en_mer=None):
    types = [{"name": "Wind onshore", "data": terrestre}]
    if en_mer is not None:
        types.append({"name": "Wind offshore", "data": en_mer})
    ts = pd.date_range(debut, periods=n, freq="h")
    chemin.write_text(json.dumps({"unix_seconds": [int(t.timestamp()) for t in ts], "production_types": types}))


def test_eolien_en_mer_absent_compte_pour_zero(tmp_path):
    f = tmp_path / "production_fr_2020.json"
    ecrire_production(f, "2020-01-01T00:00Z", 3, [10.0, None, 30.0])
    e = lire_eolien_brut(f)
    assert e["eolien_mw"].iloc[0] == 10.0
    assert np.isnan(e["eolien_mw"].iloc[1])
    assert e["eolien_mw"].iloc[2] == 30.0


def test_eolien_en_mer_vide_au_debut_puis_trou_reste_manquant(tmp_path):
    f = tmp_path / "production_fr_2023.json"
    ecrire_production(f, "2023-01-01T00:00Z", 4, [10.0] * 4, [None, 5.0, None, 7.0])
    e = lire_eolien_brut(f)["eolien_mw"].to_numpy()
    assert e[0] == 10.0 and e[1] == 15.0 and np.isnan(e[2]) and e[3] == 17.0


def test_charger_eolien_retire_les_doublons_entre_fichiers(tmp_path):
    ecrire_production(tmp_path / "production_fr_2020.json", "2020-12-31T22:00Z", 2, [1.0, 2.0])
    ecrire_production(tmp_path / "production_fr_2021.json", "2020-12-31T23:00Z", 2, [2.0, 3.0])
    e = charger_eolien(tmp_path)
    assert list(e["eolien_mw"]) == [1.0, 2.0, 3.0]
    with pytest.raises(FileNotFoundError):
        charger_eolien(tmp_path, pays="de")
