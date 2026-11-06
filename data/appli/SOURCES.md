# Sources des données de l'appli

Fichiers produits par `scripts/exporter_appli.py` à partir de la base locale, **absents de ce dépôt public**. **Usage privé** : ils ne doivent pas être
republiés tant que la licence de la production n'est pas confirmée (voir `docs/interface.md`).

| Fichier | Colonne | Source | Licence |
|---|---|---|---|
| `horaire_fr.csv.gz` | `prix_eur_mwh` | Prix day-ahead France, via Energy-Charts (Fraunhofer ISE) | CC BY 4.0, Bundesnetzagentur \| SMARD.de |
| `horaire_fr.csv.gz` | `solaire_mw`, `conso_mw`, `eolien_mw` | Production et consommation France, Energy-Charts (Fraunhofer ISE), d'après ENTSO-E et RTE | **non confirmée** |
| `profil_montpellier.csv.gz`, `villes/profil_*.csv.gz` | `solaire_mw` | Séries horaires PVGIS 5.3, 1 MWc, plein sud, inclinaison optimale (`villes/inclinaisons.csv`) | PVGIS © European Communities, 2001–2026 ; réutilisation autorisée si la source est citée |

Heures en UTC. Valeurs manquantes laissées vides (NaN à la lecture), jamais remplacées par 0.
