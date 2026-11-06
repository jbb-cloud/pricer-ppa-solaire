import json

import numpy as np
import pandas as pd
import pytest

from ppa_pricer.donnees.base import connexion, ecrire_serie, lire_serie
from ppa_pricer.donnees.controles import controler_calage_solaire, controler_serie, heures_attendues_par_jour
from ppa_pricer.donnees.energy_charts import (
    DEBUT_QUART_HEURE_UTC,
    agreger_horaire,
    lire_prix_brut,
    lire_production_brut,
)


def ecrire_json(chemin, ts_iso, prix):
    secondes = [int(pd.Timestamp(t).timestamp()) for t in ts_iso]
    chemin.write_text(json.dumps({"unix_seconds": secondes, "price": prix}))
    return chemin


def serie(ts_iso, prix, duree_min):
    return pd.DataFrame(
        {
            "ts_utc": pd.to_datetime(ts_iso, utc=True),
            "duree_min": duree_min,
            "prix_eur_mwh": np.array(prix, dtype=float),
        }
    )


def test_lecture_garde_les_prix_absents_en_nan(tmp_path):
    chemin = ecrire_json(tmp_path / "p.json", ["2020-01-01T00:00Z", "2020-01-01T01:00Z"], [40.5, None])
    prix = lire_prix_brut(chemin)
    assert str(prix["ts_utc"].dt.tz) == "UTC"
    assert prix["prix_eur_mwh"].iloc[0] == 40.5
    assert np.isnan(prix["prix_eur_mwh"].iloc[1])


def test_lecture_deduit_la_duree_du_passage_au_quart_d_heure(tmp_path):
    ts = ["2025-09-30T21:00Z", "2025-09-30T22:00Z", "2025-09-30T22:15Z"]
    prix = lire_prix_brut(ecrire_json(tmp_path / "p.json", ts, [70.0, 60.0, 61.0]))
    assert list(prix["duree_min"]) == [60, 15, 15]


def test_agregation_moyenne_des_quatre_quarts_d_heure():
    ts = ["2025-10-01T00:00Z", "2025-10-01T00:15Z", "2025-10-01T00:30Z", "2025-10-01T00:45Z"]
    horaire = agreger_horaire(serie(ts, [10, 20, 30, 40], 15))
    assert len(horaire) == 1
    assert horaire["prix_eur_mwh"].iloc[0] == pytest.approx(25.0)


def test_agregation_heure_incomplete_donne_nan():
    ts = ["2025-10-01T00:00Z", "2025-10-01T00:15Z", "2025-10-01T00:30Z", "2025-10-01T00:45Z"]
    horaire = agreger_horaire(serie(ts, [10, np.nan, 30, 40], 15))
    assert np.isnan(horaire["prix_eur_mwh"].iloc[0])


def test_agregation_ajoute_les_heures_absentes_en_nan():
    horaire = agreger_horaire(serie(["2020-01-01T00:00Z", "2020-01-01T02:00Z"], [10, 30], 60))
    assert list(horaire["ts_utc"].dt.hour) == [0, 1, 2]
    assert np.isnan(horaire["prix_eur_mwh"].iloc[1])
    assert horaire["prix_eur_mwh"].iloc[2] == 30


def test_base_aller_retour_sans_doublon_et_nan_preserve(tmp_path):
    con = connexion(tmp_path / "test.sqlite")
    prix = serie(["2020-01-01T00:00Z", "2020-01-01T01:00Z"], [42.0, np.nan], 60)
    ecrire_serie(con, "prix_day_ahead", prix, zone="FR", source="test")
    ecrire_serie(con, "prix_day_ahead", prix, zone="FR", source="test")
    relu = lire_serie(con, "prix_day_ahead", zone="FR")
    assert len(relu) == 2
    assert relu["ts_utc"].equals(prix["ts_utc"])
    assert np.isnan(relu["prix_eur_mwh"].iloc[1])


def test_heures_attendues_aux_changements_d_heure():
    jours = pd.Index(pd.to_datetime(["2025-03-30", "2025-06-15", "2025-10-26"]).date)
    assert list(heures_attendues_par_jour(jours)) == [23, 24, 25]


def test_controle_serie_propre_aucune_anomalie():
    # Trois jours civils de Paris autour du changement d'heure d'automne 2024.
    ts = pd.date_range("2024-10-25T22:00Z", "2024-10-28T22:59Z", freq="h")
    rapport = controler_serie(serie(ts, np.arange(len(ts)), 60), DEBUT_QUART_HEURE_UTC)
    assert rapport["doublons"] == rapport["trous"] == rapport["mal_alignes"] == 0
    assert rapport["jours_heures_anormales"] == {}


def test_controle_detecte_doublon_trou_et_desalignement():
    ts = ["2020-01-01T00:00Z", "2020-01-01T00:00Z", "2020-01-01T02:00Z", "2020-01-01T03:30Z"]
    rapport = controler_serie(serie(ts, [1, 1, 2, 3], 60), DEBUT_QUART_HEURE_UTC)
    assert rapport["doublons"] == 1
    assert rapport["trous"] == 2  # 01:00 et 03:00 manquent (03:30 ne remplace pas 03:00)
    assert rapport["mal_alignes"] == 1  # 03:30 n'est pas une heure pleine


def serie_solaire(debut="2020-01-01T00:00Z", fin="2022-12-31T22:59Z"):
    """Trois ans de production en cloche autour de 12 h UTC, sans rien la nuit."""
    ts = pd.date_range(debut, fin, freq="h")
    puissance = 1000 * np.clip(1 - ((ts.hour + 0.5 - 12) / 5) ** 2, 0, None)
    return pd.DataFrame({"ts_utc": ts, "duree_min": 60, "solaire_mw": puissance})


def ligne_du_mois(calage, mois):
    return calage[calage["periode"] == pd.Period(mois, "M")].iloc[0]


def test_calage_serie_propre_aucune_alerte():
    calage = controler_calage_solaire(serie_solaire())
    assert calage["heure_moyenne_utc"].to_numpy() == pytest.approx(12.0)
    assert not calage["calage_suspect"].any()
    assert not calage["nuit_suspecte"].any()


def test_calage_detecte_un_mois_decale_que_la_grille_ne_voit_pas():
    s = serie_solaire()
    juin = s["ts_utc"].dt.strftime("%Y-%m") == "2021-06"
    # Une heure de retard en juin 2021 : la grille temporelle reste parfaite.
    s.loc[juin, "solaire_mw"] = s["solaire_mw"].shift(1)[juin]
    grille = controler_serie(s.rename(columns={"solaire_mw": "valeur"}), pd.Timestamp("2030-01-01T00:00Z"))
    assert grille["doublons"] == grille["trous"] == grille["mal_alignes"] == 0

    calage = controler_calage_solaire(s)
    assert ligne_du_mois(calage, "2021-06")["ecart_h"] == pytest.approx(1.0)
    assert list(calage.loc[calage["calage_suspect"], "periode"].astype(str)) == ["2021-06"]


def test_calage_heure_moyenne_identique_au_pas_horaire_et_au_quart_d_heure():
    ts_horaire = pd.to_datetime(["2026-06-15T11:00Z"])
    ts_quart = pd.date_range("2026-06-15T11:00Z", periods=4, freq="15min")
    horaire = pd.DataFrame({"ts_utc": ts_horaire, "duree_min": 60, "solaire_mw": [800.0]})
    quart = pd.DataFrame({"ts_utc": ts_quart, "duree_min": 15, "solaire_mw": [800.0] * 4})
    assert controler_calage_solaire(horaire)["heure_moyenne_utc"].iloc[0] == pytest.approx(11.5)
    assert controler_calage_solaire(quart)["heure_moyenne_utc"].iloc[0] == pytest.approx(11.5)


def test_calage_production_de_nuit_signalee_au_dela_du_seuil():
    s = serie_solaire()
    s.loc[s["ts_utc"] == pd.Timestamp("2021-06-15T23:00Z"), "solaire_mw"] = 5000.0  # environ 2,5 % du mois
    s.loc[s["ts_utc"] == pd.Timestamp("2021-07-15T23:00Z"), "solaire_mw"] = 1.0  # trace sous le seuil
    calage = controler_calage_solaire(s)
    assert ligne_du_mois(calage, "2021-06")["nuit_suspecte"]
    assert not ligne_du_mois(calage, "2021-07")["nuit_suspecte"]
    assert ligne_du_mois(calage, "2021-07")["part_nuit"] > 0


def test_calage_ignore_les_valeurs_manquantes():
    s = pd.DataFrame(
        {
            "ts_utc": pd.to_datetime(["2021-06-15T10:00Z", "2021-06-15T12:00Z", "2021-06-15T14:00Z"]),
            "duree_min": 60,
            "solaire_mw": [100.0, np.nan, 100.0],
        }
    )
    assert controler_calage_solaire(s)["heure_moyenne_utc"].iloc[0] == pytest.approx(12.5)


def test_lecture_production_garde_les_zeros_et_les_nan(tmp_path):
    ts = ["2025-12-31T22:00Z", "2025-12-31T23:00Z", "2025-12-31T23:15Z"]
    donnees = {
        "unix_seconds": [int(pd.Timestamp(t).timestamp()) for t in ts],
        "production_types": [
            {"name": "Nuclear", "data": [50000, 50000, 50000]},
            {"name": "Solar", "data": [0.0, None, 0.0]},
            {"name": "Load", "data": [60000, 61000, None]},
        ],
    }
    chemin = tmp_path / "prod.json"
    chemin.write_text(json.dumps(donnees))
    prod = lire_production_brut(chemin)
    assert list(prod.columns) == ["ts_utc", "duree_min", "solaire_mw", "conso_mw"]
    assert list(prod["duree_min"]) == [60, 15, 15]
    assert prod["solaire_mw"].iloc[0] == 0.0  # la nuit, zéro réel
    assert np.isnan(prod["solaire_mw"].iloc[1])
    assert np.isnan(prod["conso_mw"].iloc[2])


def test_agregation_traite_chaque_colonne_separement():
    ts = ["2026-01-01T00:00Z", "2026-01-01T00:15Z", "2026-01-01T00:30Z", "2026-01-01T00:45Z"]
    prod = pd.DataFrame(
        {
            "ts_utc": pd.to_datetime(ts, utc=True),
            "duree_min": 15,
            "solaire_mw": [0.0, 0.0, 0.0, 0.0],
            "conso_mw": [100.0, np.nan, 100.0, 100.0],
        }
    )
    horaire = agreger_horaire(prod)
    assert horaire["solaire_mw"].iloc[0] == 0.0
    assert np.isnan(horaire["conso_mw"].iloc[0])


def test_base_production_aller_retour(tmp_path):
    con = connexion(tmp_path / "test.sqlite")
    prod = pd.DataFrame(
        {
            "ts_utc": pd.to_datetime(["2020-06-01T12:00Z"], utc=True),
            "duree_min": [60],
            "solaire_mw": [8000.0],
            "conso_mw": [np.nan],
        }
    )
    ecrire_serie(con, "production_conso", prod, zone="FR", source="test")
    relu = lire_serie(con, "production_conso", zone="FR")
    assert relu["solaire_mw"].iloc[0] == 8000.0
    assert np.isnan(relu["conso_mw"].iloc[0])
