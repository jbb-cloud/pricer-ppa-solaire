# Backtest du modèle V1

Généré le 29/10/2026 ; données jusqu'au 29/10/2026 13:00. Protocole : `docs/perimetre.md`. Erreurs en points de taux de capture (prévision − réalisé).

## Verdict officiel (2018–2025, variante réaliste)

Critère : skill score > 0 contre R1 **et** contre R2. Skill vs R1 = +0,10, skill vs R2 = +0,47 → **critère ATTEINT**.

## Métriques 2018–2025 (96 mois)

| Méthode | MAE | MAE pondérée | Biais | Skill vs R1 | Skill vs R2 |
|---|---|---|---|---|---|
| Modèle V1, réaliste | 5,9 | 8,5 | 3,3 | +0,10 | +0,47 |
| Modèle V1, conditionnel (part solaire réalisée) | 5,9 | 8,4 | 2,4 | +0,11 | +0,47 |
| R1 persistance | 6,6 | 8,9 | 4,8 | +0,00 | +0,41 |
| R2 climatologie | 11,2 | 17,3 | 10,4 | -0,69 | +0,00 |

## Diebold-Mariano (perte absolue, Newey-West 11 retards, Student n−1)

Statistique négative : le modèle se trompe moins que la référence.

| Comparaison | Écart moyen de perte | Statistique | p-value |
|---|---|---|---|
| Modèle V1, réaliste vs R1 persistance | -0,7 | -0,76 | 0,449 |
| Modèle V1, réaliste vs R2 climatologie | -5,2 | -2,76 | 0,007 |
| Modèle V1, conditionnel (part solaire réalisée) vs R1 persistance | -0,7 | -1,10 | 0,273 |
| Modèle V1, conditionnel (part solaire réalisée) vs R2 climatologie | -5,2 | -2,33 | 0,022 |

## Sensibilité : 2018–2025 sans 2022 (84 mois)

| Méthode | MAE | MAE pondérée | Biais | Skill vs R1 | Skill vs R2 |
|---|---|---|---|---|---|
| Modèle V1, réaliste | 6,4 | 9,3 | 4,0 | +0,11 | +0,47 |
| Modèle V1, conditionnel (part solaire réalisée) | 5,9 | 8,5 | 3,6 | +0,17 | +0,51 |
| R1 persistance | 7,2 | 9,8 | 5,5 | +0,00 | +0,41 |
| R2 climatologie | 12,1 | 19,2 | 11,3 | -0,69 | +0,00 |

## MAE par année

| Année | Modèle V1, réaliste | Modèle V1, conditionnel (part solaire réalisée) | R1 persistance | R2 climatologie |
|---|---|---|---|---|
| 2018 | 2,8 | 2,1 | 2,4 | 2,5 |
| 2019 | 2,3 | 2,0 | 3,1 | 3,3 |
| 2020 | 5,8 | 4,7 | 4,9 | 6,2 |
| 2021 | 2,0 | 3,0 | 4,6 | 5,7 |
| 2022 | 2,9 | 5,8 | 2,6 | 4,2 |
| 2023 | 3,2 | 3,8 | 8,2 | 10,7 |
| 2024 | 11,5 | 13,8 | 14,5 | 23,5 |
| 2025 | 17,1 | 12,2 | 12,5 | 33,0 |

## Taux de capture annuel (avec baseload et volumes réalisés)

Réalisé en %, puis erreur de chaque méthode en points.

| Année | Réalisé | Modèle V1, réaliste | Modèle V1, conditionnel (part solaire réalisée) | R1 persistance | R2 climatologie |
|---|---|---|---|---|---|
| 2018 | 102,1 | -1,2 | -1,8 | 0,3 | 1,6 |
| 2019 | 95,7 | 0,1 | -0,8 | 2,0 | 2,8 |
| 2020 | 92,7 | -0,9 | -0,4 | 1,8 | 3,7 |
| 2021 | 86,3 | -0,4 | -0,3 | 1,9 | 4,1 |
| 2022 | 105,7 | -3,0 | -9,2 | -1,2 | 4,7 |
| 2023 | 86,3 | 2,0 | 2,8 | 8,1 | 11,8 |
| 2024 | 67,6 | 10,4 | 12,3 | 12,9 | 21,9 |
| 2025 | 58,8 | 13,3 | 7,6 | 9,3 | 28,8 |
| **MAE** | | **3,9** | **4,4** | **4,7** | **9,9** |

## 2026, rapporté à part (9 mois valides, hors verdict)

| Méthode | MAE | MAE pondérée | Biais | Skill vs R1 | Skill vs R2 |
|---|---|---|---|---|---|
| Modèle V1, réaliste | 15,7 | 17,7 | -3,6 | -0,13 | +0,61 |
| Modèle V1, conditionnel (part solaire réalisée) | 15,3 | 16,0 | 2,3 | -0,10 | +0,61 |
| R1 persistance | 13,9 | 14,0 | 5,6 | +0,00 | +0,65 |
| R2 climatologie | 39,7 | 42,6 | 39,7 | -1,86 | +0,00 |

| Mois | Réalisé | Part solaire réalisée / prévue | Modèle V1, réaliste | Modèle V1, conditionnel (part solaire réalisée) | R1 persistance | R2 climatologie |
|---|---|---|---|---|---|---|
| 2026-01 | 100,3 | 2,3 / 2,8 % | 98,2 | 101,0 | 103,6 | 108,4 |
| 2026-02 | 69,5 | 3,8 / 4,8 % | 82,3 | 88,8 | 90,5 | 100,9 |
| 2026-03 | 47,9 | 7,8 / 8,4 % | 57,1 | 61,1 | 64,9 | 91,3 |
| 2026-04 | 10,2 | 10,7 / 11,4 % | 41,4 | 45,6 | 40,5 | 85,9 |
| 2026-05 | 27,5 | 12,6 / 14,2 % | 28,5 | 38,2 | 20,9 | 83,9 |
| 2026-06 | 63,4 | 13,6 / 15,6 % | 30,6 | 42,6 | 49,1 | 92,0 |
| 2026-07 | 50,2 | 14,6 / 16,3 % | 30,2 | 41,0 | 66,1 | 94,4 |
| 2026-08 | 58,9 | 13,6 / 15,5 % | 31,6 | 43,1 | 47,9 | 91,3 |
| 2026-09 | 55,4 | 12,6 / 11,2 % | 50,9 | 42,3 | 49,9 | 92,6 |

## Paramètres estimés à chaque calibration

| Année prévue | Mois de calibration | β |
|---|---|---|
| 2018 | 35 | -5,89 |
| 2019 | 47 | -4,50 |
| 2020 | 59 | -4,00 |
| 2021 | 71 | -4,72 |
| 2022 | 83 | -4,79 |
| 2023 | 95 | -2,86 |
| 2024 | 107 | -3,40 |
| 2025 | 119 | -5,15 |
| 2026 | 131 | -6,22 |
