# Backtest du modèle M1

Généré le 30/10/2026 ; données jusqu'au 29/10/2026 13:00. 1000 trajectoires par année, graine 20261030. Protocole, définition et attentes : `docs/stochastique.md`. Erreurs en points de taux de capture (prévision − réalisé).

## Verdict (2018–2025, M1 sur 2 ans)

Critère : skill > 0 contre R1 **et** contre la V1, et couverture entre 85 et 95 %. Skill vs R1 = -0,23, skill vs V1 = -0,36, couverture = 35,4 % → **critère NON ATTEINT**.

Aucun mois publié après le 29/10/2026 n'est encore complet : le test sur données réellement inconnues reste à faire.

## Précision 2018–2025 (96 mois)

| Méthode | MAE | MAE pondérée | Biais | Skill vs R1 | Skill vs V1 |
|---|---|---|---|---|---|
| M1 | 8,1 | 11,9 | 7,0 | -0,23 | -0,36 |
| M1 sur 1 an (sensibilité) | 6,8 | 9,1 | 5,1 | -0,02 | -0,14 |
| M0 | 8,1 | 11,9 | 7,0 | -0,23 | -0,36 |
| Modèle V1, réaliste | 5,9 | 8,5 | 3,3 | +0,10 | +0,00 |
| R1 persistance | 6,6 | 8,9 | 4,8 | +0,00 | -0,11 |
| R2 climatologie | 11,2 | 17,3 | 10,4 | -0,69 | -0,87 |

## Diebold-Mariano (perte absolue, Newey-West 11 retards, Student n−1)

Statistique négative : M1 se trompe moins que l'autre méthode.

| Comparaison | Écart moyen de perte | Statistique | p-value |
|---|---|---|---|
| M1 vs R1 persistance | 1,5 | +1,69 | 0,095 |
| M1 vs Modèle V1, réaliste | 2,2 | +2,46 | 0,016 |
| M1 vs M0 | 0,0 | +0,04 | 0,967 |

## Intervalle à 90 % du taux de capture mensuel, 2018–2025

| Méthode | Couverture | Largeur moyenne | Réalisé au-dessus | Réalisé en dessous |
|---|---|---|---|---|
| M1 | 35,4 % | 8,4 | 10 | 52 |
| M1 sur 1 an (sensibilité) | 34,4 % | 7,1 | 13 | 50 |
| M0 | 41,7 % | 7,7 | 7 | 49 |

| Année | MAE M1 | MAE M1 sur 1 an | MAE M0 | MAE V1 | MAE R1 | Couverture M1 | Couverture M1 sur 1 an | Couverture M0 |
|---|---|---|---|---|---|---|---|---|
| 2018 | 3,0 | 2,5 | 3,0 | 2,8 | 2,4 | 41,7 % | 50,0 % | 75,0 % |
| 2019 | 2,6 | 3,1 | 2,5 | 2,3 | 3,1 | 50,0 % | 33,3 % | 66,7 % |
| 2020 | 5,3 | 5,0 | 5,3 | 5,8 | 4,9 | 41,7 % | 33,3 % | 41,7 % |
| 2021 | 4,2 | 4,6 | 4,2 | 2,0 | 4,6 | 33,3 % | 33,3 % | 25,0 % |
| 2022 | 2,8 | 2,9 | 3,0 | 2,9 | 2,6 | 50,0 % | 50,0 % | 58,3 % |
| 2023 | 8,5 | 9,2 | 8,5 | 3,2 | 8,2 | 33,3 % | 25,0 % | 33,3 % |
| 2024 | 18,9 | 14,6 | 18,9 | 11,5 | 14,5 | 16,7 % | 16,7 % | 16,7 % |
| 2025 | 19,5 | 12,2 | 19,5 | 17,1 | 12,5 | 16,7 % | 33,3 % | 16,7 % |

## Taux de capture annuel (baseload et volumes réalisés)

| Année | Réalisé | Erreur M1 | Erreur M0 | Erreur V1 | Erreur R1 |
|---|---|---|---|---|---|
| 2018 | 102,1 | 1,2 | 1,1 | -1,2 | 0,3 |
| 2019 | 95,7 | 2,1 | 2,0 | 0,1 | 2,0 |
| 2020 | 92,7 | 2,8 | 2,8 | -0,9 | 1,8 |
| 2021 | 86,3 | 3,4 | 3,3 | -0,4 | 1,9 |
| 2022 | 105,7 | 0,8 | 0,6 | -3,0 | -1,2 |
| 2023 | 86,3 | 8,9 | 8,8 | 2,0 | 8,1 |
| 2024 | 67,6 | 17,9 | 17,8 | 10,4 | 12,9 |
| 2025 | 58,8 | 15,9 | 15,9 | 13,3 | 9,3 |

## 2026, rapporté à part (9 mois valides)

| Méthode | MAE | MAE pondérée | Biais | Skill vs R1 | Skill vs V1 |
|---|---|---|---|---|---|
| M1 | 13,9 | 13,4 | 10,5 | -0,00 | +0,11 |
| M1 sur 1 an (sensibilité) | 15,1 | 15,5 | 4,4 | -0,09 | +0,04 |
| M0 | 14,1 | 13,6 | 10,9 | -0,01 | +0,10 |
| Modèle V1, réaliste | 15,7 | 17,7 | -3,6 | -0,13 | +0,00 |
| R1 persistance | 13,9 | 14,0 | 5,6 | +0,00 | +0,11 |
| R2 climatologie | 39,7 | 42,6 | 39,7 | -1,86 | -1,53 |

| Méthode | Couverture | Largeur moyenne | Réalisé au-dessus | Réalisé en dessous |
|---|---|---|---|---|
| M1 | 44,4 % | 23,9 | 1 | 4 |
| M1 sur 1 an (sensibilité) | 33,3 % | 19,6 | 2 | 4 |
| M0 | 44,4 % | 25,7 | 1 | 4 |

| Mois | Réalisé | M1 | Intervalle M1 | M0 | V1 | R1 |
|---|---|---|---|---|---|---|
| 2026-01 | 100,3 | 100,8 | 97,0 à 105,0 | 100,9 | 98,2 | 103,6 |
| 2026-02 | 69,5 | 93,2 | 89,1 à 97,3 | 93,2 | 82,3 | 90,5 |
| 2026-03 | 47,9 | 73,8 | 65,7 à 79,4 | 73,5 | 57,1 | 64,9 |
| 2026-04 | 10,2 | 47,9 | 26,6 à 60,2 | 48,5 | 41,4 | 40,5 |
| 2026-05 | 27,5 | 34,5 | -3,6 à 53,5 | 35,8 | 28,5 | 20,9 |
| 2026-06 | 63,4 | 51,0 | 33,7 à 61,5 | 51,6 | 30,6 | 49,1 |
| 2026-07 | 50,2 | 62,0 | 50,7 à 69,1 | 62,2 | 30,2 | 66,1 |
| 2026-08 | 58,9 | 55,8 | 41,1 à 66,4 | 56,4 | 31,6 | 47,9 |
| 2026-09 | 55,4 | 58,5 | 45,7 à 68,5 | 59,3 | 50,9 | 49,9 |

## Paramètres estimés

Fenêtre de 2 ans. La dernière colonne rappelle la demi-vie unique de M0.

| Année prévue | Poids rapide | Demi-vie rapide (h) | Demi-vie lente (h) | Erreur d'ajustement | Demi-vie M0 (h) |
|---|---|---|---|---|---|
| 2018 | 0,38 | 4,1 | 69,5 | 0,015 | 1,5 |
| 2019 | 0,32 | 3,9 | 89,2 | 0,015 | 13,8 |
| 2020 | 0,35 | 4,8 | 116,5 | 0,013 | 14,4 |
| 2021 | 0,32 | 4,9 | 110,4 | 0,012 | 13,6 |
| 2022 | 0,25 | 4,1 | 82,0 | 0,011 | 20,7 |
| 2023 | 0,18 | 4,0 | 156,8 | 0,008 | 23,4 |
| 2024 | 0,28 | 4,7 | 124,5 | 0,022 | 13,4 |
| 2025 | 0,40 | 5,4 | 87,3 | 0,024 | 14,6 |
| 2026 | 0,29 | 2,5 | 45,4 | 0,021 | 11,7 |

## Diagnostics : simulations et réalité

Moyenne sur 20 trajectoires, face à l'année réelle. Prix en part du baseload de l'année.

### 2019

| Propriété | M1 | M0 | Réel |
|---|---|---|---|
| Autocorrélation à 1 h | 0,89 | 0,95 | 0,94 |
| Autocorrélation à 24 h | 0,40 | 0,25 | 0,47 |
| Autocorrélation à 48 h | 0,30 | 0,05 | 0,28 |
| Autocorrélation à 168 h | -0,04 | -0,07 | -0,00 |
| Kurtosis du résidu | 10,78 | 3,03 | 5,75 |
| Part d'heures négatives | 0,00 | 0,00 | 0,00 |
| Prix médian à midi, avril–août | 0,81 | 0,81 | 0,87 |
| Quantile 5 % | 0,42 | 0,35 | 0,41 |
| Quantile 95 % | 1,71 | 1,70 | 1,64 |

### 2025

| Propriété | M1 | M0 | Réel |
|---|---|---|---|
| Autocorrélation à 1 h | 0,91 | 0,95 | 0,93 |
| Autocorrélation à 24 h | 0,36 | 0,26 | 0,55 |
| Autocorrélation à 48 h | 0,25 | 0,05 | 0,31 |
| Autocorrélation à 168 h | -0,06 | -0,10 | -0,13 |
| Kurtosis du résidu | 4,36 | 2,96 | 5,75 |
| Part d'heures négatives | 0,03 | 0,05 | 0,06 |
| Prix médian à midi, avril–août | 0,50 | 0,45 | 0,00 |
| Quantile 5 % | 0,02 | 0,02 | -0,00 |
| Quantile 95 % | 1,97 | 1,99 | 2,26 |
