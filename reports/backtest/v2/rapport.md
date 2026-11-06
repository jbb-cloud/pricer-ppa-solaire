# Backtest du modèle V2

Généré le 31/10/2026. Définition, limites et attentes : `docs/pricing.md`. Erreurs en points de taux de capture (prévision − réalisé). Part du solaire prévue par H4.

**La forme de V2 a été choisie après avoir vu ces années** : ce backtest ne la valide pas. Le niveau réalisé équivaut à une cotation parfaite et lui est donc favorable. Le niveau persistant est celui du même trimestre de l'année précédente. Seuls les mois publiés après le 29/10/2026 forment un test propre.

## Critère (2018–2025, 96 mois, niveau réalisé)

Skill > 0 contre R1 et contre la V1. Skill vs R1 = +0,22, skill vs V1 = +0,13 → **critère ATTEINT, sans valeur de preuve**.

## Précision

| Méthode | MAE | Biais | Skill vs R1 | Skill vs V1 | Skill vs R2 |
|---|---|---|---|---|---|
| V2, niveau réalisé | 5,2 | 2,4 | +0,22 | +0,13 | +0,53 |
| V2, niveau persistant | 5,3 | 2,7 | +0,19 | +0,10 | +0,52 |
| V1 | 5,9 | 3,3 | +0,10 | +0,00 | +0,47 |
| M2 | 5,9 | 4,0 | +0,10 | +0,00 | +0,47 |
| R1 | 6,6 | 4,8 | +0,00 | −0,11 | +0,41 |
| R2 | 11,2 | 10,4 | −0,69 | −0,87 | +0,00 |

## Par année

| Année | V2, niveau réalisé | V2, niveau persistant | V1 | M2 | R1 | R2 | Biais V2, niveau réalisé |
|---|---|---|---|---|---|---|---|
| 2018 | 3,5 | 2,8 | 2,8 | 2,6 | 2,4 | 2,5 | −0,8 |
| 2019 | 2,6 | 2,1 | 2,3 | 2,1 | 3,1 | 3,3 | −0,8 |
| 2020 | 5,7 | 5,6 | 5,8 | 4,8 | 4,9 | 6,2 | 0,4 |
| 2021 | 4,8 | 2,2 | 2,0 | 2,9 | 4,6 | 5,7 | 2,7 |
| 2022 | 1,6 | 2,3 | 2,9 | 2,4 | 2,6 | 4,2 | 0,5 |
| 2023 | 3,2 | 4,8 | 3,2 | 4,9 | 8,2 | 10,7 | −1,6 |
| 2024 | 7,1 | 10,0 | 11,5 | 13,9 | 14,5 | 23,5 | 6,3 |
| 2025 | 13,1 | 12,9 | 17,1 | 13,9 | 12,5 | 33,0 | 12,4 |
| 2026 (9 mois, à part) | 12,5 | 20,1 | 15,7 | 15,8 | 13,9 | 39,7 | 0,7 |

## Diebold-Mariano (perte absolue, Newey-West 11 retards, Student n−1)

| Comparaison | Statistique | p-value |
|---|---|---|
| V2, niveau réalisé contre V1 | −1,01 | 0,314 |
| V2, niveau réalisé contre R1 | −1,45 | 0,151 |
| V2, niveau réalisé contre M2 | −0,87 | 0,389 |
| V2, niveau persistant contre V1 | −1,15 | 0,254 |
| V2, niveau persistant contre R1 | −2,22 | 0,029 |

## Robustesse

Skill en retirant chaque année, puis bootstrap par années entières (10000 tirages, à lire comme un ordre de grandeur).

| Comparaison | Tout | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Retraits > 0 | IC à 90 % | Tirages > 0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V2, niveau réalisé contre V1 | +0,13 | +0,15 | +0,14 | +0,14 | +0,19 | +0,11 | +0,14 | +0,04 | +0,07 | 8 sur 8 | −0,14 à +0,26 | 83 % |
| V2, niveau réalisé contre R1 | +0,22 | +0,25 | +0,22 | +0,25 | +0,24 | +0,21 | +0,14 | +0,10 | +0,30 | 8 sur 8 | −0,04 à +0,41 | 92 % |
| V2, niveau réalisé contre M2 | +0,13 | +0,15 | +0,14 | +0,16 | +0,18 | +0,12 | +0,10 | −0,03 | +0,15 | 7 sur 8 | −0,14 à +0,31 | 78 % |
| V2, niveau persistant contre V1 | +0,10 | +0,11 | +0,10 | +0,11 | +0,11 | +0,10 | +0,15 | +0,09 | +0,02 | 8 sur 8 | −0,07 à +0,18 | 86 % |
| V2, niveau persistant contre R1 | +0,19 | +0,21 | +0,18 | +0,23 | +0,16 | +0,20 | +0,15 | +0,15 | +0,26 | 8 sur 8 | +0,04 à +0,33 | 98 % |

## Paramètres

`parametres_geles.csv` fige les paramètres estimés sur tous les mois valides, pour le test sur les mois nouveaux.

| Calibration pour | β | γ | δ | Mois |
|---|---|---|---|---|
| 2018 | −25,16 | −0,081 | +5,33 | 35 |
| 2019 | −13,71 | −0,033 | +2,21 | 47 |
| 2020 | −9,32 | −0,046 | +1,49 | 59 |
| 2021 | −12,65 | −0,049 | +2,35 | 71 |
| 2022 | −6,63 | −0,006 | +0,45 | 83 |
| 2023 | −8,31 | −0,020 | +0,99 | 95 |
| 2024 | −8,19 | −0,016 | +0,94 | 107 |
| 2025 | −12,70 | −0,024 | +1,66 | 119 |
| 2026 | −13,68 | −0,025 | +1,80 | 131 |
| 2027 | −13,87 | −0,022 | +1,79 | 140 |
