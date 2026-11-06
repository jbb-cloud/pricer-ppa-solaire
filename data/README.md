# Données

Ce dépôt public **ne contient pas de données brutes**. Elles se retéléchargent depuis leurs sources publiques :

```bash
.venv/bin/python scripts/telecharger_donnees.py   # prix day-ahead, production et consommation France → data/raw/ et data/ppa.sqlite
.venv/bin/python scripts/exporter_appli.py        # table horaire compacte et profils de l'appli → data/appli/
.venv/bin/python scripts/precalculer_villes.py    # profils PVGIS des 16 villes → data/appli/villes/
```

`comparer_sources.py` demande un jeton ENTSO-E gratuit dans `.env` (`ENTSOE_API_KEY=...`, jamais commité).

## Ce qui a été retiré, et pourquoi

| Fichier du projet | Raison |
|---|---|
| `data/appli/*.csv.gz`, `data/appli/villes/` | La production et la consommation viennent d'Energy-Charts, dont la licence n'est pas confirmée pour ces séries. Les sources et licences sont détaillées dans [`appli/SOURCES.md`](appli/SOURCES.md). |
| `data/marche/courbe_fr_AAAA-MM-JJ.csv` | Cotations à terme EEX relevées sur un site tiers : les données EEX ne sont pas librement redistribuables. |
| `reports/backtest/m2/chute_2024.md` et `.csv` | Ils utilisent les prix espagnols d'Energy-Charts, sous licence « usage privé et interne seulement ». |

## Format de la courbe à terme

`scripts/pricer_v2.py` et `scripts/exporter_appli.py` lisent un fichier `data/marche/courbe_fr_2026-10-29.csv` :

```csv
echeance,base_eur_mwh,pointe_eur_mwh
CAL_2027,...,...
T1_2027,...,...
T2_2027,...,...
T3_2027,...,...
T4_2027,...,...
```

La moyenne des trimestres, pondérée par les heures, doit être à moins de 1 % du contrat calendaire
(voir `src/ppa_pricer/pricing/courbe.py`).
