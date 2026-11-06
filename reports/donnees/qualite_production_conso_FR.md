# Contrôle qualité — Production solaire et consommation (FR)

Source : Energy-Charts (Fraunhofer ISE), CC BY 4.0. Généré le 30/10/2026.

- Période : 2015-01-01 01:00 CET → 2026-10-29 13:45 CET
- Passage au quart d'heure : 2026-01-01 00:00 CET
- Points : 125383
- Doublons : 0
- Points mal alignés : 0
- Trous (points absents de la grille) : 0
- Jours au nombre d'heures anormal (changements d'heure) : 0

| Colonne | Valeurs manquantes | Min | Max | Valeurs négatives |
|---|---|---|---|---|
| solaire_mw | 128 | 0.00 | 22324.80 | 0 |
| conso_mw | 92 | 28744.00 | 94492.00 | 0 |

## Par année (UTC), après agrégation horaire

Une heure est NaN si une de ses valeurs d'origine manque (règle décrite dans `docs/donnees.md`).

| Année | Heures | solaire_mw : heures NaN | solaire_mw : moyenne | conso_mw : heures NaN | conso_mw : moyenne |
|---|---|---|---|---|---|
| 2015 | 8760 | 1 | 802.92 | 1 | 53660.57 |
| 2016 | 8784 | 11 | 911.24 | 6 | 54394.40 |
| 2017 | 8760 | 0 | 1016.52 | 19 | 54448.57 |
| 2018 | 8760 | 1 | 1110.12 | 17 | 53810.35 |
| 2019 | 8760 | 2 | 1304.10 | 8 | 53382.15 |
| 2020 | 8784 | 0 | 1416.60 | 2 | 50612.78 |
| 2021 | 8760 | 0 | 1560.15 | 9 | 53222.87 |
| 2022 | 8760 | 1 | 2050.71 | 21 | 50729.32 |
| 2023 | 8760 | 4 | 2459.18 | 5 | 48594.70 |
| 2024 | 8784 | 0 | 2655.04 | 0 | 48918.20 |
| 2025 | 8760 | 5 | 3449.55 | 4 | 49724.10 |
| 2026 | 7237 | 26 | 4546.01 | 0 | 48360.49 |

## Calage physique du solaire (par mois de Paris)

Alerte si l'heure moyenne de production s'écarte de plus de 0.2 h de la médiane du même mois, ou si plus de 0.1% de l'énergie du mois est produite de 21 h à 03 h UTC. Le contrôle signale sans corriger (voir `docs/donnees.md`).

- Mois contrôlés : 142
- Mois au calage suspect : 20
- Mois avec production de nuit : 13

| Mois | Heure moyenne (UTC) | Référence (UTC) | Écart (h) | Part la nuit (%) | Alerte |
|---|---|---|---|---|---|
| 2018-07 | 11.87 | 11.92 | -0.06 | 0.72 | nuit |
| 2018-08 | 11.88 | 11.90 | -0.02 | 1.02 | nuit |
| 2019-07 | 11.92 | 11.92 | -0.00 | 0.65 | nuit |
| 2019-08 | 11.92 | 11.90 | +0.02 | 0.96 | nuit |
| 2020-07 | 11.95 | 11.92 | +0.03 | 1.39 | nuit |
| 2020-08 | 11.92 | 11.90 | +0.02 | 1.14 | nuit |
| 2020-09 | 11.82 | 11.82 | -0.00 | 0.15 | nuit |
| 2023-06 | 11.93 | 11.86 | +0.07 | 0.14 | nuit |
| 2023-07 | 12.14 | 11.92 | +0.21 | 0.32 | calage, nuit |
| 2023-09 | 12.51 | 11.82 | +0.69 | 0.00 | calage |
| 2023-10 | 12.66 | 11.74 | +0.91 | 0.00 | calage |
| 2023-11 | 12.66 | 11.77 | +0.89 | 0.00 | calage |
| 2023-12 | 12.71 | 11.82 | +0.89 | 0.00 | calage |
| 2024-01 | 12.91 | 11.97 | +0.94 | 0.02 | calage |
| 2024-02 | 12.86 | 12.03 | +0.83 | 0.00 | calage |
| 2024-03 | 12.89 | 11.94 | +0.95 | 0.00 | calage |
| 2025-01 | 12.36 | 11.97 | +0.40 | 0.00 | calage |
| 2025-02 | 12.36 | 12.03 | +0.33 | 0.00 | calage |
| 2025-03 | 12.26 | 11.94 | +0.33 | 0.00 | calage |
| 2025-04 | 12.15 | 11.83 | +0.32 | 0.00 | calage |
| 2025-05 | 12.08 | 11.83 | +0.26 | 0.00 | calage |
| 2025-06 | 12.28 | 11.86 | +0.42 | 0.20 | calage, nuit |
| 2025-07 | 12.26 | 11.92 | +0.33 | 0.19 | calage, nuit |
| 2025-08 | 12.26 | 11.90 | +0.35 | 0.00 | calage |
| 2025-09 | 12.16 | 11.82 | +0.34 | 0.00 | calage |
| 2025-10 | 12.15 | 11.74 | +0.41 | 0.00 | calage |
| 2025-11 | 12.17 | 11.77 | +0.40 | 0.00 | calage |
| 2025-12 | 12.24 | 11.82 | +0.42 | 0.00 | calage |
| 2026-06 | 11.99 | 11.86 | +0.12 | 0.14 | nuit |
| 2026-07 | 12.06 | 11.92 | +0.14 | 0.13 | nuit |
