import pandas as pd
import pytest
import requests

from ppa_pricer.donnees import appli, pvgis
from ppa_pricer.donnees.appli import VILLES, ecrire_profil, profil_du_site
from ppa_pricer.donnees.pvgis import MONTPELLIER, ErreurPVGIS, Site, parametres_api, profil_en_direct


class Reponse:
    def __init__(self, statut, donnees):
        self.status_code, self._donnees, self.text = statut, donnees, str(donnees)

    def json(self):
        return self._donnees


def reponse_pvgis(pente=35.0):
    heures = [{"time": "20200621:1110", "P": 600000.0}, {"time": "20200621:1210", "P": 700000.0}]
    return Reponse(200, {"inputs": {"mounting_system": {"fixed": {"slope": {"value": pente}}}}, "outputs": {"hourly": heures}})


@pytest.fixture
def appels(monkeypatch):
    """Remplace l'API : enregistre les paramètres envoyés et renvoie la réponse choisie par le test."""
    journal = {"parametres": [], "reponse": reponse_pvgis()}

    def faux_get(url, params, timeout):
        journal["parametres"].append(params)
        if isinstance(journal["reponse"], Exception):
            raise journal["reponse"]
        return journal["reponse"]

    monkeypatch.setattr(pvgis.requests, "get", faux_get)
    return journal


@pytest.fixture
def dossier(tmp_path):
    profil = pd.DataFrame({"ts_utc": pd.date_range("2020-06-21T11:00Z", periods=2, freq="h"), "duree_min": 60, "solaire_mw": [0.5, 0.6]})
    ecrire_profil(profil, tmp_path)
    return tmp_path


def test_parametres_inchanges_pour_le_telechargement_des_rapports():
    p = parametres_api(MONTPELLIER)
    assert p["optimalinclination"] == 1 and p["aspect"] == 0 and "angle" not in p and "startyear" not in p


def test_parametres_inclinaison_orientation_annees():
    p = parametres_api(Site("x", 45.0, 5.0), inclinaison=20, orientation=-45, annees=(2014, 2023))
    assert p["angle"] == 20 and "optimalinclination" not in p
    assert p["aspect"] == -45 and (p["startyear"], p["endyear"]) == (2014, 2023)


def test_profil_en_direct_lu_en_mw_et_pente_retenue(appels):
    profil, pente = profil_en_direct(Site("x", 45.0, 5.0))
    assert pente == 35.0
    assert list(profil["solaire_mw"]) == [0.6, 0.7]
    assert profil["ts_utc"].iloc[0] == pd.Timestamp("2020-06-21T11:00Z")
    assert (appels["parametres"][0]["startyear"], appels["parametres"][0]["endyear"]) == (2014, 2023)


def test_refus_de_pvgis_remonte_son_message(appels):
    appels["reponse"] = Reponse(400, {"message": "Location over the sea. Please, select another location"})
    with pytest.raises(ErreurPVGIS, match="over the sea"):
        profil_en_direct(Site("x", 48.0, -30.0))


def test_reglages_impossibles_refuses(appels):
    with pytest.raises(ValueError):
        profil_en_direct(Site("x", 45.0, 5.0), inclinaison=120)
    assert appels["parametres"] == []


def test_montpellier_par_defaut_sans_appel_et_a_l_echelle(appels, dossier):
    r = profil_du_site(*VILLES["Montpellier"], 3.0, dossier)
    assert r.source == "cache" and r.avertissement is None and r.inclinaison == appli.INCLINAISON_MONTPELLIER
    assert list(r.profil["solaire_mw"]) == pytest.approx([1.5, 1.8])
    assert appels["parametres"] == []


def test_autre_site_demande_la_puissance_reelle(appels, dossier):
    r = profil_du_site(*VILLES["Lyon"], 2.0, dossier, inclinaison=30, orientation=10)
    assert r.source == "pvgis" and r.inclinaison == 35.0
    p = appels["parametres"][0]
    assert p["peakpower"] == 2000.0 and p["angle"] == 30 and p["aspect"] == 10


def test_montpellier_reoriente_appelle_pvgis(appels, dossier):
    assert profil_du_site(*VILLES["Montpellier"], 1.0, dossier, orientation=45).source == "pvgis"


@pytest.mark.parametrize("panne", [requests.ConnectionError("hors ligne"), Reponse(500, {"message": "erreur interne"})])
def test_secours_quand_pvgis_echoue(appels, dossier, panne):
    appels["reponse"] = panne
    r = profil_du_site(*VILLES["Lille"], 2.0, dossier)
    assert r.source == "secours" and "Montpellier" in r.avertissement
    assert list(r.profil["solaire_mw"]) == pytest.approx([1.0, 1.2])


def test_nom_de_fichier_sans_accent():
    assert appli.nom_fichier_ville("Orléans") == "profil_orleans.csv.gz"
    assert appli.nom_fichier_ville("Clermont-Ferrand") == "profil_clermont-ferrand.csv.gz"


def test_ville_precalculee_sans_appel_et_a_l_echelle(appels, dossier):
    profil = pd.DataFrame({"ts_utc": pd.date_range("2020-06-21T11:00Z", periods=2, freq="h"), "duree_min": 60, "solaire_mw": [0.2, 0.3]})
    appli.ecrire_profil_ville(profil, 41.0, "Lille", dossier)
    appli.ecrire_profil_ville(profil, 42.0, "Lille", dossier)  # remplace, sans doublon dans l'index
    r = profil_du_site(*VILLES["Lille"], 2.0, dossier)
    assert r.source == "cache" and r.inclinaison == 42.0
    assert list(r.profil["solaire_mw"]) == pytest.approx([0.4, 0.6])
    assert appels["parametres"] == []
    # Réorientée, la même ville appelle PVGIS ; une ville non précalculée aussi.
    assert profil_du_site(*VILLES["Lille"], 2.0, dossier, orientation=30).source == "pvgis"
    assert profil_du_site(*VILLES["Nice"], 2.0, dossier).source == "pvgis"
    assert len(pd.read_csv(dossier / "villes" / "inclinaisons.csv")) == 1
