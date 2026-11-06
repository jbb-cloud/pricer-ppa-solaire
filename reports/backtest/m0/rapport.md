# Backtest du modèle M0

Généré le 30/10/2026 ; données jusqu'au 29/10/2026 13:00. 1000 trajectoires par année, graine 20261030. Protocole et attentes : `docs/stochastique.md`. M0 est une référence, **sans verdict**. Erreurs en points de taux de capture (prévision − réalisé).

## Précision 2018–2025 (96 mois)

| Méthode | MAE | MAE pondérée | Biais | Skill vs R1 | Skill vs V1 |
|---|---|---|---|---|---|
| M0 | 8,1 | 11,9 | 7,0 | -0,23 | -0,36 |
| Modèle V1, réaliste | 5,9 | 8,5 | 3,3 | +0,10 | +0,00 |
| R1 persistance | 6,6 | 8,9 | 4,8 | +0,00 | -0,11 |
| R2 climatologie | 11,2 | 17,3 | 10,4 | -0,69 | -0,87 |

## Diebold-Mariano (perte absolue, Newey-West 11 retards, Student n−1)

Statistique négative : M0 se trompe moins que l'autre méthode.

| Comparaison | Écart moyen de perte | Statistique | p-value |
|---|---|---|---|
| M0 vs R1 persistance | 1,5 | +1,69 | 0,095 |
| M0 vs Modèle V1, réaliste | 2,2 | +2,47 | 0,015 |

## Intervalle à 90 % du taux de capture mensuel

Couverture : **41,7 %**, pour une cible de 85 à 95 %. Largeur moyenne : 7,7 points. Réalisé au-dessus de l'intervalle : 7 mois ; en dessous : 49 mois, sur 96.

| Année | MAE M0 | MAE V1 | MAE R1 | Couverture | Largeur moyenne |
|---|---|---|---|---|---|
| 2018 | 3,0 | 2,8 | 2,4 | 75,0 % | 11,2 |
| 2019 | 2,5 | 2,3 | 3,1 | 66,7 % | 5,1 |
| 2020 | 5,3 | 5,8 | 4,9 | 41,7 % | 4,4 |
| 2021 | 4,2 | 2,0 | 4,6 | 25,0 % | 5,4 |
| 2022 | 3,0 | 2,9 | 2,6 | 58,3 % | 7,7 |
| 2023 | 8,5 | 3,2 | 8,2 | 33,3 % | 8,9 |
| 2024 | 18,9 | 11,5 | 14,5 | 16,7 % | 7,7 |
| 2025 | 19,5 | 17,1 | 12,5 | 16,7 % | 11,2 |

## Taux de capture annuel (baseload et volumes réalisés)

| Année | Réalisé | Erreur M0 | Erreur V1 | Erreur R1 |
|---|---|---|---|---|
| 2018 | 102,1 | 1,1 | -1,2 | 0,3 |
| 2019 | 95,7 | 2,0 | 0,1 | 2,0 |
| 2020 | 92,7 | 2,8 | -0,9 | 1,8 |
| 2021 | 86,3 | 3,3 | -0,4 | 1,9 |
| 2022 | 105,7 | 0,6 | -3,0 | -1,2 |
| 2023 | 86,3 | 8,8 | 2,0 | 8,1 |
| 2024 | 67,6 | 17,8 | 10,4 | 12,9 |
| 2025 | 58,8 | 15,9 | 13,3 | 9,3 |

## 2026, rapporté à part (9 mois valides)

| Méthode | MAE | MAE pondérée | Biais | Skill vs R1 | Skill vs V1 |
|---|---|---|---|---|---|
| M0 | 14,1 | 13,6 | 10,9 | -0,01 | +0,10 |
| Modèle V1, réaliste | 15,7 | 17,7 | -3,6 | -0,13 | +0,00 |
| R1 persistance | 13,9 | 14,0 | 5,6 | +0,00 | +0,11 |
| R2 climatologie | 39,7 | 42,6 | 39,7 | -1,86 | -1,53 |

Couverture : **44,4 %**, pour une cible de 85 à 95 %. Largeur moyenne : 25,7 points. Réalisé au-dessus de l'intervalle : 1 mois ; en dessous : 4 mois, sur 9.

| Mois | Réalisé | M0 | Intervalle M0 | V1 | R1 |
|---|---|---|---|---|---|
| 2026-01 | 100,3 | 100,9 | 97,2 à 104,2 | 98,2 | 103,6 |
| 2026-02 | 69,5 | 93,2 | 89,3 à 96,6 | 82,3 | 90,5 |
| 2026-03 | 47,9 | 73,5 | 66,8 à 79,1 | 57,1 | 64,9 |
| 2026-04 | 10,2 | 48,5 | 22,5 à 62,0 | 41,4 | 40,5 |
| 2026-05 | 27,5 | 35,8 | -18,1 à 57,6 | 28,5 | 20,9 |
| 2026-06 | 63,4 | 51,6 | 33,7 à 62,8 | 30,6 | 49,1 |
| 2026-07 | 50,2 | 62,2 | 52,4 à 69,7 | 30,2 | 66,1 |
| 2026-08 | 58,9 | 56,4 | 45,6 à 64,6 | 31,6 | 47,9 |
| 2026-09 | 55,4 | 59,3 | 45,2 à 69,2 | 50,9 | 49,9 |

## Paramètres estimés

Écarts-types en part du baseload annuel.

| Année prévue | φ | Demi-vie (h) | σ des chocs horaires | σ de long terme |
|---|---|---|---|---|
| 2018 | 0,636 | 1,5 | 0,301 | 0,391 |
| 2019 | 0,951 | 13,8 | 0,089 | 0,286 |
| 2020 | 0,953 | 14,4 | 0,079 | 0,262 |
| 2021 | 0,950 | 13,6 | 0,093 | 0,297 |
| 2022 | 0,967 | 20,7 | 0,098 | 0,384 |
| 2023 | 0,971 | 23,4 | 0,124 | 0,518 |
| 2024 | 0,949 | 13,4 | 0,127 | 0,406 |
| 2025 | 0,954 | 14,6 | 0,135 | 0,450 |
| 2026 | 0,942 | 11,7 | 0,168 | 0,503 |

## Diagnostics : simulations et réalité

Moyenne sur 20 trajectoires, face à l'année réelle. Prix en part du baseload de l'année.

### 2019

| Propriété | Simulé | Réel |
|---|---|---|
| Autocorrélation à 1 h | 0,95 | 0,94 |
| Autocorrélation à 24 h | 0,25 | 0,47 |
| Autocorrélation à 48 h | 0,05 | 0,28 |
| Autocorrélation à 168 h | -0,07 | -0,00 |
| Kurtosis du résidu | 3,03 | 5,75 |
| Part d'heures négatives | 0,00 | 0,00 |
| Prix médian à midi, avril–août | 0,81 | 0,87 |
| Quantile 5 % | 0,35 | 0,41 |
| Quantile 95 % | 1,70 | 1,64 |

### 2025

| Propriété | Simulé | Réel |
|---|---|---|
| Autocorrélation à 1 h | 0,95 | 0,93 |
| Autocorrélation à 24 h | 0,26 | 0,55 |
| Autocorrélation à 48 h | 0,05 | 0,31 |
| Autocorrélation à 168 h | -0,10 | -0,13 |
| Kurtosis du résidu | 2,96 | 5,75 |
| Part d'heures négatives | 0,05 | 0,06 |
| Prix médian à midi, avril–août | 0,45 | 0,00 |
| Quantile 5 % | 0,02 | -0,00 |
| Quantile 95 % | 1,99 | 2,26 |
