import traceback

import numpy as np
import pandas as pd
import pytest
import requests

from ppa_pricer.donnees import entsoe as module_entsoe
from ppa_pricer.donnees.comparaison import attribuer_origine, comparer_premier_quart, comparer_solaire, comparer_valeurs, horaire_variante
from ppa_pricer.donnees.energy_charts import agreger_horaire
from ppa_pricer.donnees.entsoe import AucuneDonnee, lire_annees, lire_cle, lire_xml, telecharger_annee
from ppa_pricer.donnees.rte import lire_export

ESPACE = 'xmlns="urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0"'
JETON = "jeton-secret-de-test"


def serie_xml(points, debut="2022-06-14T22:00Z", fin="2022-06-15T00:00Z", resolution="PT60M", courbe="A01", zone="inBiddingZone_Domain.mRID", champ="quantity"):
    lignes = "".join(f"<Point><position>{p}</position><{champ}>{v}</{champ}></Point>" for p, v in points)
    return (
        f"<TimeSeries><{zone}>10YFR-RTE------C</{zone}><curveType>{courbe}</curveType><Period>"
        f"<timeInterval><start>{debut}</start><end>{fin}</end></timeInterval>"
        f"<resolution>{resolution}</resolution>{lignes}</Period></TimeSeries>"
    )


def document(*series):
    return f"<GL_MarketDocument {ESPACE}>{''.join(series)}</GL_MarketDocument>"


def ecrire(tmp_path, texte, nom="doc.xml"):
    chemin = tmp_path / nom
    chemin.write_text(texte)
    return chemin


def test_lire_xml_horodatage_et_valeurs(tmp_path):
    lu = lire_xml(ecrire(tmp_path, document(serie_xml([(1, 100), (2, 200)]))), "solaire")
    assert list(lu["ts_utc"]) == [pd.Timestamp("2022-06-14T22:00Z"), pd.Timestamp("2022-06-14T23:00Z")]
    assert list(lu["valeur"]) == [100.0, 200.0]
    assert list(lu["duree_min"]) == [60, 60]


def test_lire_xml_resolution_au_quart_d_heure(tmp_path):
    lu = lire_xml(ecrire(tmp_path, document(serie_xml([(1, 1), (2, 2)], resolution="PT15M"))), "solaire")
    assert lu["ts_utc"].iloc[1] == pd.Timestamp("2022-06-14T22:15Z")
    assert lu["duree_min"].iloc[0] == 15


def test_lire_xml_courbe_a01_position_absente_reste_absente(tmp_path):
    points = [(1, 10), (3, 30)]
    lu = lire_xml(ecrire(tmp_path, document(serie_xml(points, fin="2022-06-15T01:00Z"))), "solaire")
    assert len(lu) == 2
    assert lu["ts_utc"].iloc[1] == pd.Timestamp("2022-06-15T00:00Z")


def test_lire_xml_courbe_a03_position_absente_reprend_la_valeur(tmp_path):
    texte = document(serie_xml([(1, 10), (3, 30)], fin="2022-06-15T02:00Z", courbe="A03", zone="in_Domain.mRID", champ="price.amount"))
    lu = lire_xml(ecrire(tmp_path, texte), "prix")
    assert list(lu["valeur"]) == [10.0, 10.0, 30.0, 30.0]


def test_lire_xml_solaire_ignore_la_consommation_de_la_filiere(tmp_path):
    texte = document(serie_xml([(1, 5)], zone="outBiddingZone_Domain.mRID"), serie_xml([(1, 100)]))
    assert list(lire_xml(ecrire(tmp_path, texte), "solaire")["valeur"]) == [100.0]


def test_lire_xml_conso_garde_outbiddingzone(tmp_path):
    texte = document(serie_xml([(1, 50000)], zone="outBiddingZone_Domain.mRID"))
    assert list(lire_xml(ecrire(tmp_path, texte), "conso")["valeur"]) == [50000.0]


def test_lire_xml_refuse_une_resolution_inconnue(tmp_path):
    with pytest.raises(ValueError, match="Résolution"):
        lire_xml(ecrire(tmp_path, document(serie_xml([(1, 1)], resolution="P1D"))), "solaire")


def test_lire_annees_assemble_et_trie(tmp_path):
    ecrire(tmp_path, document(serie_xml([(1, 2)], debut="2023-01-01T00:00Z", fin="2023-01-01T01:00Z")), "solaire_FR_2023.xml")
    ecrire(tmp_path, document(serie_xml([(1, 1)], debut="2022-01-01T00:00Z", fin="2022-01-01T01:00Z")), "solaire_FR_2022.xml")
    assert list(lire_annees(tmp_path, "solaire")["valeur"]) == [1.0, 2.0]


def test_lire_cle(tmp_path):
    chemin = ecrire(tmp_path, f'# commentaire\nAUTRE=1\nENTSOE_API_KEY="{JETON}"\n', ".env")
    assert lire_cle(chemin) == JETON


def test_lire_cle_absente_ne_cite_pas_le_contenu(tmp_path):
    chemin = ecrire(tmp_path, "AUTRE=valeur-privee\n", ".env")
    with pytest.raises(ValueError) as erreur:
        lire_cle(chemin)
    assert "valeur-privee" not in str(erreur.value)
    with pytest.raises(ValueError):
        lire_cle(tmp_path / "absent")


def test_erreur_reseau_ne_contient_jamais_le_jeton(monkeypatch, tmp_path):
    def echec(url, params, timeout):
        raise requests.ConnectionError(f"{url}?securityToken={params['securityToken']}")

    monkeypatch.setattr(module_entsoe.requests, "get", echec)
    monkeypatch.setattr(module_entsoe.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError) as erreur:
        telecharger_annee("solaire", 2020, tmp_path, JETON)
    assert JETON not in "".join(traceback.format_exception(erreur.value))


def test_refus_http_ne_contient_jamais_le_jeton(monkeypatch, tmp_path):
    class Reponse:
        status_code = 401
        text = f"<Acknowledgement_MarketDocument><Reason><text>jeton {JETON} refusé</text></Reason></Acknowledgement_MarketDocument>"

    monkeypatch.setattr(module_entsoe.requests, "get", lambda url, params, timeout: Reponse())
    with pytest.raises(RuntimeError) as erreur:
        telecharger_annee("solaire", 2020, tmp_path, JETON)
    assert JETON not in str(erreur.value)
    assert "401" in str(erreur.value)


def test_reponse_sans_donnee_ne_cree_pas_de_fichier(monkeypatch, tmp_path):
    class Reponse:
        status_code = 200
        text = "<Acknowledgement_MarketDocument><Reason><text>No matching data</text></Reason></Acknowledgement_MarketDocument>"

    monkeypatch.setattr(module_entsoe.requests, "get", lambda url, params, timeout: Reponse())
    with pytest.raises(AucuneDonnee, match="No matching data"):
        telecharger_annee("solaire", 2020, tmp_path, JETON)
    assert list(tmp_path.iterdir()) == []


def test_annee_passee_non_retelechargee(monkeypatch, tmp_path):
    fichier = ecrire(tmp_path, document(serie_xml([(1, 1)])), "solaire_FR_2020.xml")
    monkeypatch.setattr(module_entsoe.requests, "get", lambda *a, **k: pytest.fail("appel réseau inattendu"))
    assert telecharger_annee("solaire", 2020, tmp_path, JETON) == fichier


def test_lire_export_rte_garde_les_demi_heures_et_les_vides(tmp_path):
    texte = (
        "﻿date_heure;solaire;consommation\n"
        "2022-06-15T12:45:00+00:00;;\n"
        "2022-06-15T12:30:00+00:00;;50000\n"
        "2022-06-15T12:15:00+00:00;;\n"
        "2022-06-15T12:00:00+00:00;8000;49000\n"
    )
    lu = lire_export(ecrire(tmp_path, texte, "rte.csv"))
    assert list(lu["ts_utc"]) == [pd.Timestamp("2022-06-15T12:00Z"), pd.Timestamp("2022-06-15T12:30Z")]
    assert lu["solaire_mw"].iloc[0] == 8000.0
    assert np.isnan(lu["solaire_mw"].iloc[1])
    assert list(lu["duree_min"]) == [30, 30]


def test_agregation_horaire_au_pas_de_30_minutes():
    ts = pd.to_datetime(["2022-06-15T12:00Z", "2022-06-15T12:30Z", "2022-06-15T13:00Z"])
    serie = pd.DataFrame({"ts_utc": ts, "duree_min": 30, "valeur": [10.0, 20.0, 30.0]})
    horaire = agreger_horaire(serie)
    assert horaire["valeur"].iloc[0] == pytest.approx(15.0)
    assert np.isnan(horaire["valeur"].iloc[1])


def test_agregation_horaire_avec_un_point_en_double_donne_nan():
    ts = pd.to_datetime(["2022-10-30T01:00Z", "2022-10-30T01:00Z", "2022-10-30T01:30Z", "2022-10-30T01:30Z"])
    serie = pd.DataFrame({"ts_utc": ts, "duree_min": 30, "valeur": [10.0, 11.0, 20.0, 21.0]})
    assert np.isnan(agreger_horaire(serie)["valeur"].iloc[0])


def cloche(debut="2021-01-01T00:00Z", fin="2021-12-31T22:00Z", retard=0):
    ts = pd.date_range(debut, fin, freq="h")
    valeurs = 1000 * np.clip(1 - ((ts.hour + 0.5 - 12) / 5) ** 2, 0, None)
    return pd.Series(valeurs, index=ts).shift(retard).rename_axis("ts_utc")


def test_comparer_solaire_detecte_un_retard_d_une_heure():
    resultat = comparer_solaire(cloche(retard=1), cloche()).set_index("periode")
    juin = resultat.loc[pd.Period("2021-06", "M")]
    assert juin["ecart_h"] == pytest.approx(1.0)
    assert juin["retard_h"] == 1
    assert juin["correlation"] < 1


def test_comparer_solaire_sources_identiques_et_niveau_different():
    resultat = comparer_solaire(cloche() * 0.9, cloche()).set_index("periode")
    juin = resultat.loc[pd.Period("2021-06", "M")]
    assert juin["ecart_h"] == pytest.approx(0.0)
    assert juin["retard_h"] == 0
    assert juin["rapport_energie"] == pytest.approx(0.9)


def test_comparer_solaire_utilise_les_heures_communes():
    a = cloche()
    b = cloche().copy()
    b[b.index.strftime("%Y-%m-%d") == "2021-06-15"] = np.nan
    juin = comparer_solaire(a, b).set_index("periode").loc[pd.Period("2021-06", "M")]
    assert juin["rapport_energie"] == pytest.approx(1.0)
    assert juin["heures_communes"] == 29 * 24


def mois_signales(n):
    return list(pd.period_range("2023-01", periods=n, freq="M"))


def comparaison_ecarts(ecarts):
    return pd.DataFrame({"periode": mois_signales(len(ecarts)), "ecart_h": ecarts})


def test_attribuer_origine_seuil_de_80_pourcent():
    assert attribuer_origine(comparaison_ecarts([0.05] * 16 + [0.9] * 4), mois_signales(20))["origine"] == "source"
    verdict = attribuer_origine(comparaison_ecarts([0.05] * 15 + [0.9] * 5), mois_signales(20))
    assert verdict["origine"] == "apres_entsoe"
    assert verdict["n_proches"] == 15


def test_attribuer_origine_ecart_negatif_et_valeur_limite():
    assert attribuer_origine(comparaison_ecarts([-0.1] * 5), mois_signales(5))["n_proches"] == 5
    assert attribuer_origine(comparaison_ecarts([-0.11] * 5), mois_signales(5))["n_proches"] == 0


def test_attribuer_origine_mois_absent_compte_comme_non_proche():
    verdict = attribuer_origine(comparaison_ecarts([0.0] * 15), mois_signales(20))
    assert verdict["n_proches"] == 15
    assert verdict["origine"] == "apres_entsoe"


def test_comparer_valeurs_calcul_a_la_main():
    ts = pd.date_range("2021-06-15T00:00Z", periods=3, freq="h")
    a = pd.Series([10.0, 20.0, np.nan], index=ts)
    b = pd.Series([12.0, 20.0, 99.0], index=ts)
    ligne = comparer_valeurs(a, b).iloc[0]
    assert ligne["heures_communes"] == 2
    assert ligne["ecart_moyen"] == pytest.approx(-1.0)
    assert ligne["ecart_absolu_max"] == pytest.approx(2.0)
    assert ligne["heures_differentes"] == 1


def test_horaire_variante_ne_complete_pas_avec_la_source_officielle():
    ts = pd.date_range("2021-06-15T00:00Z", periods=2, freq="h")
    horaire = pd.DataFrame({"ts_utc": ts, "solaire_mw": [1.0, 2.0], "prix_eur_mwh": [50.0, 60.0]})
    variante = horaire_variante(horaire, solaire_mw=pd.Series([9.0], index=ts[:1]))
    assert variante["solaire_mw"].iloc[0] == 9.0
    assert np.isnan(variante["solaire_mw"].iloc[1])
    assert variante["prix_eur_mwh"].iloc[1] == 60.0
    assert horaire["solaire_mw"].iloc[0] == 1.0


def quarts_d_heure():
    ts = pd.date_range("2025-06-01", periods=96, freq="15min", tz="UTC")
    return pd.Series(np.arange(96.0) * 10, index=ts)


def test_comparer_premier_quart_reconnait_un_echantillon():
    natif = quarts_d_heure()
    echantillon = natif[natif.index.minute == 0]
    r = comparer_premier_quart(echantillon, natif)
    assert r["heures"] == 24
    assert r["part_premier_quart"] == 1.0
    assert r["part_moyenne"] == 0.0
    assert r["ecart_absolu_moyenne_mw"] == pytest.approx(15.0)


def test_comparer_premier_quart_reconnait_une_vraie_moyenne():
    natif = quarts_d_heure()
    moyenne = natif.groupby(natif.index.floor("h")).mean()
    r = comparer_premier_quart(moyenne, natif)
    assert r["part_moyenne"] == 1.0
    assert r["part_premier_quart"] == 0.0
    assert r["ecart_absolu_moyenne_mw"] == pytest.approx(0.0)


def test_comparer_premier_quart_ignore_les_heures_inconnues():
    natif = quarts_d_heure()
    echantillon = natif[natif.index.minute == 0].copy()
    echantillon.iloc[3] = np.nan
    assert comparer_premier_quart(echantillon, natif)["heures"] == 23
