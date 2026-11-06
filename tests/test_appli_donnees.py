import numpy as np
import pandas as pd
import pytest

from ppa_pricer.donnees.appli import ecrire_horaire, ecrire_profil, lire_horaire, lire_profil_secours


def horaire_simple():
    # Autour du passage à l'heure d'été 2024 (31 mars, 1 h UTC), avec des valeurs inconnues et des flottants peu ronds.
    ts = pd.date_range("2024-03-30T22:00Z", periods=6, freq="h")
    return pd.DataFrame(
        {
            "ts_utc": ts,
            "prix_eur_mwh": [55.12, np.nan, -3.5, 0.1 + 0.2, 1e-7, 1 / 3],
            "solaire_mw": [0.0, 0.0, np.nan, 12.25, 3000.0, 2 / 7],
            "conso_mw": [60000.0, 59000.0, 58000.5, np.nan, 57000.0, 56000.0],
            "eolien_mw": [1200.0, 1300.0, 1250.0, 1100.0, np.nan, 900.0],
            "autre": 1,  # colonne en trop : non exportée
        }
    )


def test_aller_retour_exact_avec_nan_et_utc(tmp_path):
    h = horaire_simple()
    ecrire_horaire(h, tmp_path)
    relu = lire_horaire(tmp_path)
    pd.testing.assert_frame_equal(relu, h.drop(columns="autre"), check_dtype=False)
    assert str(relu["ts_utc"].dt.tz) == "UTC"
    # Aucun arrondi : le flottant relu est le même.
    assert relu["prix_eur_mwh"].iloc[3] == 0.1 + 0.2
    assert relu["prix_eur_mwh"].isna().sum() == 1


def test_profil_aller_retour(tmp_path):
    profil = pd.DataFrame({"ts_utc": pd.date_range("2020-06-01", periods=3, freq="h", tz="UTC"), "duree_min": 60, "solaire_mw": [0.0, 0.31, 0.62]})
    ecrire_profil(profil, tmp_path)
    pd.testing.assert_frame_equal(lire_profil_secours(tmp_path), profil, check_dtype=False)


def test_colonne_manquante_refusee(tmp_path):
    with pytest.raises(ValueError, match="eolien_mw"):
        ecrire_horaire(horaire_simple().drop(columns="eolien_mw"), tmp_path)


def test_fichier_aux_mauvaises_colonnes_refuse(tmp_path):
    pd.DataFrame({"ts_utc": ["2024-01-01T00:00Z"], "prix": [1.0]}).to_csv(tmp_path / "horaire_fr.csv.gz", index=False)
    with pytest.raises(ValueError, match="colonnes"):
        lire_horaire(tmp_path)


def test_ecriture_reproductible(tmp_path):
    # La compression n'inscrit pas l'heure d'écriture : réexporter les mêmes données ne crée pas de différence dans git.
    a = ecrire_horaire(horaire_simple(), tmp_path / "a").read_bytes()
    b = ecrire_horaire(horaire_simple(), tmp_path / "b").read_bytes()
    assert a == b
