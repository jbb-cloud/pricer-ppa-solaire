# Backtest du modèle M2

Généré le 30/10/2026 ; données jusqu'au 29/10/2026 13:00. 1000 trajectoires par année, graine 20261030. Protocole, définition et attentes : `docs/stochastique.md`. Erreurs en points de taux de capture (prévision − réalisé).

## Verdict (2018–2025, M2 sur 2 ans, croissance tirée)

Critère : skill > 0 contre R1 **et** contre la V1, et couverture entre 85 et 95 %. Skill vs R1 = +0,10, skill vs V1 = +0,00, couverture = 66,7 % → **critère NON ATTEINT**.

Aucun mois publié après le 29/10/2026 n'est encore complet : le test sur données réellement inconnues reste à faire.

## Précision 2018–2025 (96 mois)

| Méthode | MAE | MAE pondérée | Biais | Skill vs R1 | Skill vs V1 |
|---|---|---|---|---|---|
| M2 | 5,9 | 8,4 | 4,0 | +0,10 | +0,00 |
| M2 avec H4 (sensibilité) | 6,0 | 8,6 | 3,9 | +0,10 | -0,01 |
| M2 sur 1 an (sensibilité) | 5,7 | 7,2 | 2,8 | +0,15 | +0,05 |
| M1 | 8,1 | 11,9 | 7,0 | -0,23 | -0,36 |
| Modèle V1, réaliste | 5,9 | 8,5 | 3,3 | +0,10 | +0,00 |
| R1 persistance | 6,6 | 8,9 | 4,8 | +0,00 | -0,11 |
| R2 climatologie | 11,2 | 17,3 | 10,4 | -0,69 | -0,87 |

## Diebold-Mariano (perte absolue, Newey-West 11 retards, Student n−1)

Statistique négative : M2 se trompe moins que l'autre méthode.

| Comparaison | Écart moyen de perte | Statistique | p-value |
|---|---|---|---|
| M2 vs R1 persistance | -0,7 | -1,64 | 0,105 |
| M2 vs Modèle V1, réaliste | -0,0 | -0,02 | 0,985 |
| M2 vs M1 | -2,2 | -2,97 | 0,004 |

## Intervalle à 90 % du taux de capture mensuel, 2018–2025

| Méthode | Couverture | Largeur moyenne | Réalisé au-dessus | Réalisé en dessous | Bornes basses sous 0 |
|---|---|---|---|---|---|
| M2 | 66,7 % | 11,5 | 7 | 25 | 0 |
| M2 avec H4 (sensibilité) | 64,6 % | 11,0 | 8 | 26 | 0 |
| M2 sur 1 an (sensibilité) | 37,5 % | 7,4 | 19 | 41 | 0 |
| M1 | 35,4 % | 8,4 | 10 | 52 | 0 |

| Année | MAE M2 | Biais M2 | MAE M2 H4 | MAE M2 sur 1 an | MAE M1 | MAE V1 | MAE R1 | Couverture M2 | Largeur M2 | Couverture M1 |
|---|---|---|---|---|---|---|---|---|---|---|
| 2018 | 2,6 | -1,1 | 2,6 | 2,9 | 3,0 | 2,8 | 2,4 | 66,7 % | 6,9 | 41,7 % |
| 2019 | 2,1 | 0,7 | 2,2 | 3,0 | 2,6 | 2,3 | 3,1 | 83,3 % | 6,9 | 50,0 % |
| 2020 | 4,8 | 2,2 | 4,9 | 4,5 | 5,3 | 5,8 | 4,9 | 66,7 % | 7,2 | 41,7 % |
| 2021 | 2,9 | 1,2 | 3,0 | 5,4 | 4,2 | 2,0 | 4,6 | 66,7 % | 11,3 | 33,3 % |
| 2022 | 2,4 | -0,8 | 2,4 | 2,6 | 2,8 | 2,9 | 2,6 | 91,7 % | 12,0 | 50,0 % |
| 2023 | 4,9 | 2,8 | 3,8 | 6,5 | 8,5 | 3,2 | 8,2 | 83,3 % | 14,2 | 33,3 % |
| 2024 | 13,9 | 13,4 | 13,2 | 12,5 | 18,9 | 11,5 | 14,5 | 33,3 % | 15,2 | 16,7 % |
| 2025 | 13,9 | 13,9 | 15,9 | 7,8 | 19,5 | 17,1 | 12,5 | 41,7 % | 18,6 | 16,7 % |

## Taux de capture annuel (baseload et volumes réalisés)

| Année | Réalisé | Erreur M2 | Erreur M1 | Erreur V1 | Erreur R1 |
|---|---|---|---|---|---|
| 2018 | 102,1 | 0,0 | 1,2 | -1,2 | 0,3 |
| 2019 | 95,7 | 0,9 | 2,1 | 0,1 | 2,0 |
| 2020 | 92,7 | 1,2 | 2,8 | -0,9 | 1,8 |
| 2021 | 86,3 | 1,4 | 3,4 | -0,4 | 1,9 |
| 2022 | 105,7 | -1,1 | 0,8 | -3,0 | -1,2 |
| 2023 | 86,3 | 3,3 | 8,9 | 2,0 | 8,1 |
| 2024 | 67,6 | 12,4 | 17,9 | 10,4 | 12,9 |
| 2025 | 58,8 | 10,9 | 15,9 | 13,3 | 9,3 |

## 2026, rapporté à part (9 mois valides)

| Méthode | MAE | MAE pondérée | Biais | Skill vs R1 | Skill vs V1 |
|---|---|---|---|---|---|
| M2 | 15,7 | 16,6 | -3,8 | -0,13 | -0,00 |
| M2 avec H4 (sensibilité) | 20,5 | 23,0 | -12,1 | -0,48 | -0,31 |
| M2 sur 1 an (sensibilité) | 17,6 | 18,9 | -3,7 | -0,26 | -0,12 |
| M1 | 13,9 | 13,4 | 10,5 | -0,00 | +0,11 |
| Modèle V1, réaliste | 15,7 | 17,7 | -3,6 | -0,13 | +0,00 |
| R1 persistance | 13,9 | 14,0 | 5,6 | +0,00 | +0,11 |
| R2 climatologie | 39,7 | 42,6 | 39,7 | -1,86 | -1,53 |

| Méthode | Couverture | Largeur moyenne | Réalisé au-dessus | Réalisé en dessous | Bornes basses sous 0 |
|---|---|---|---|---|---|
| M2 | 44,4 % | 32,0 | 3 | 2 | 1 |
| M2 avec H4 (sensibilité) | 33,3 % | 32,8 | 4 | 2 | 2 |
| M2 sur 1 an (sensibilité) | 22,2 % | 22,1 | 4 | 3 | 1 |
| M1 | 44,4 % | 23,9 | 1 | 4 | 1 |

| Mois | Réalisé | M2 | Intervalle M2 | M1 | V1 | R1 |
|---|---|---|---|---|---|---|
| 2026-01 | 100,3 | 98,5 | 91,5 à 105,1 | 100,8 | 98,2 | 103,6 |
| 2026-02 | 69,5 | 87,9 | 82,9 à 93,2 | 93,2 | 82,3 | 90,5 |
| 2026-03 | 47,9 | 62,3 | 53,2 à 70,2 | 73,8 | 57,1 | 64,9 |
| 2026-04 | 10,2 | 31,0 | 7,7 à 48,5 | 47,9 | 41,4 | 40,5 |
| 2026-05 | 27,5 | 6,5 | -57,8 à 34,4 | 34,5 | 28,5 | 20,9 |
| 2026-06 | 63,4 | 33,6 | 14,6 à 46,3 | 51,0 | 30,6 | 49,1 |
| 2026-07 | 50,2 | 49,9 | 32,9 à 60,2 | 62,0 | 30,2 | 66,1 |
| 2026-08 | 58,9 | 36,3 | 18,9 à 48,5 | 55,8 | 31,6 | 47,9 |
| 2026-09 | 55,4 | 42,9 | 29,1 à 54,7 | 58,5 | 50,9 | 49,9 |

## Paramètres estimés

Fenêtre de 2 ans. Croissance réalisée : donnée pour comparer, jamais utilisée par le modèle.

| Année prévue | λ | Poids rapide | Demi-vie rapide (h) | Demi-vie lente (h) | Croissances connues | Médiane | H4 | Réalisée | λ sur 1 an |
|---|---|---|---|---|---|---|---|---|---|
| 2018 | 0,61 | 0,43 | 2,4 | 85,3 | 2 | 12,5 % | 11,6 % | 9,2 % | 0,69 |
| 2019 | 0,54 | 0,33 | 2,2 | 115,6 | 3 | 11,6 % | 9,2 % | 17,5 % | 0,61 |
| 2020 | 0,60 | 0,34 | 2,3 | 117,2 | 4 | 12,5 % | 17,5 % | 8,6 % | 0,67 |
| 2021 | 0,63 | 0,33 | 2,4 | 131,0 | 5 | 11,6 % | 8,6 % | 10,1 % | 0,69 |
| 2022 | 0,48 | 0,27 | 2,5 | 163,3 | 6 | 10,8 % | 10,1 % | 31,4 % | 0,64 |
| 2023 | 0,49 | 0,19 | 2,3 | 246,5 | 7 | 11,6 % | 31,4 % | 19,9 % | 0,69 |
| 2024 | 0,55 | 0,32 | 2,7 | 147,1 | 8 | 12,5 % | 19,9 % | 8,0 % | 0,72 |
| 2025 | 0,63 | 0,47 | 2,3 | 66,1 | 9 | 11,6 % | 8,0 % | 29,9 % | 0,63 |
| 2026 | 0,63 | 0,49 | 1,9 | 58,9 | 10 | 12,5 % | 29,9 % | 19,1 % | 0,66 |

## Diagnostics : simulations et réalité

Moyenne sur 20 trajectoires, face à l'année réelle. Prix en part du baseload de l'année.

### 2019

| Propriété | M2 | M1 | Réel |
|---|---|---|---|
| Autocorrélation à 1 h | 0,87 | 0,89 | 0,94 |
| Autocorrélation à 24 h | 0,42 | 0,40 | 0,47 |
| Autocorrélation à 48 h | 0,30 | 0,30 | 0,28 |
| Autocorrélation à 168 h | -0,01 | -0,04 | -0,00 |
| Kurtosis du résidu | 9,81 | 10,78 | 5,75 |
| Part d'heures négatives | 0,00 | 0,00 | 0,00 |
| Prix médian à midi, avril–août | 0,79 | 0,81 | 0,87 |
| Quantile 5 % | 0,40 | 0,42 | 0,41 |
| Quantile 95 % | 1,72 | 1,71 | 1,64 |

### 2025

| Propriété | M2 | M1 | Réel |
|---|---|---|---|
| Autocorrélation à 1 h | 0,87 | 0,91 | 0,93 |
| Autocorrélation à 24 h | 0,36 | 0,36 | 0,55 |
| Autocorrélation à 48 h | 0,21 | 0,25 | 0,31 |
| Autocorrélation à 168 h | -0,03 | -0,06 | -0,13 |
| Kurtosis du résidu | 4,29 | 4,36 | 5,75 |
| Part d'heures négatives | 0,04 | 0,03 | 0,06 |
| Prix médian à midi, avril–août | 0,35 | 0,50 | 0,00 |
| Quantile 5 % | 0,00 | 0,02 | -0,00 |
| Quantile 95 % | 1,98 | 1,97 | 2,26 |
