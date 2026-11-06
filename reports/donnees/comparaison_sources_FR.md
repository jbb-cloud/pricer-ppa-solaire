# Comparaison des sources : Energy-Charts, ENTSO-E et RTE

Généré le 30/10/2026. Règle et choix : `docs/perimetre.md` et `docs/donnees.md`. Tous les écarts sont calculés sur les heures communes à deux sources. Ce rapport ne change ni le verdict ni les données officielles de la V1.

## Origine du décalage du solaire

Règle figée avant de voir les données : écart d'heure moyenne Energy-Charts − ENTSO-E d'au plus 0,1 h sur au moins 80% des mois signalés.

Résultat : **8 mois sur 20** (40 %). **Le décalage apparaît après ENTSO-E** : les deux séries divergent sur trop de mois signalés.

| Mois signalé | Energy-Charts (h UTC) | ENTSO-E (h UTC) | Écart EC − ENTSO-E (h) | Retard EC / ENTSO-E (h) | Énergie EC / ENTSO-E | RTE (h UTC) | Écart EC − RTE (h) |
|---|---|---|---|---|---|---|---|
| 2023-07 | 12,14 | 12,14 | +0,00 | +0 | 1,00 | 12,29 | -0,15 |
| 2023-09 | 12,51 | 12,51 | +0,00 | +0 | 1,00 | 12,07 | +0,44 |
| 2023-10 | 12,66 | 12,66 | +0,00 | +0 | 1,00 | 11,95 | +0,71 |
| 2023-11 | 12,66 | 12,66 | +0,00 | +0 | 1,00 | 11,95 | +0,71 |
| 2023-12 | 12,71 | 12,71 | +0,00 | +0 | 1,00 | 12,11 | +0,59 |
| 2024-01 | 12,91 | 12,91 | +0,00 | +0 | 1,00 | 12,56 | +0,35 |
| 2024-02 | 12,86 | 12,86 | +0,00 | +0 | 1,00 | 12,56 | +0,30 |
| 2024-03 | 12,89 | 12,89 | +0,00 | +0 | 1,00 | 12,48 | +0,41 |
| 2025-01 | 12,36 | 12,01 | +0,35 | +0 | 1,00 | 12,50 | -0,14 |
| 2025-02 | 12,36 | 12,01 | +0,35 | +0 | 1,00 | 12,59 | -0,24 |
| 2025-03 | 12,26 | 11,91 | +0,36 | +0 | 1,00 | 12,43 | -0,16 |
| 2025-04 | 12,15 | 11,80 | +0,35 | +0 | 0,99 | 12,28 | -0,13 |
| 2025-05 | 12,08 | 11,72 | +0,36 | +0 | 1,00 | 12,17 | -0,09 |
| 2025-06 | 12,28 | 11,92 | +0,36 | +0 | 1,00 | 12,38 | -0,10 |
| 2025-07 | 12,26 | 11,89 | +0,36 | +0 | 1,00 | 12,42 | -0,17 |
| 2025-08 | 12,26 | 11,90 | +0,36 | +0 | 1,00 | 12,39 | -0,14 |
| 2025-09 | 12,16 | 11,80 | +0,37 | +0 | 1,00 | 12,22 | -0,06 |
| 2025-10 | 12,15 | 11,80 | +0,36 | +0 | 1,00 | 12,15 | +0,01 |
| 2025-11 | 12,17 | 11,82 | +0,35 | +0 | 1,00 | 12,12 | +0,04 |
| 2025-12 | 12,23 | 11,89 | +0,35 | +0 | 1,00 | 12,32 | -0,08 |

Ce résultat mêle deux anomalies distinctes : voir la dernière section du rapport.

## Solaire : les trois sources par année

Écart d'heure moyenne et rapport d'énergie, Energy-Charts rapporté à chaque source.

| Année | Écart EC − ENTSO-E, moyen (h) | Énergie EC / ENTSO-E | Écart EC − RTE, moyen (h) | Énergie EC / RTE |
|---|---|---|---|---|
| 2015 | +0,00 | 1,00 | -0,33 | 0,97 |
| 2016 | +0,00 | 1,00 | -0,36 | 0,97 |
| 2017 | +0,00 | 1,00 | -0,36 | 0,99 |
| 2018 | +0,00 | 1,00 | -0,34 | 0,92 |
| 2019 | +0,00 | 1,00 | -0,32 | 0,94 |
| 2020 | +0,00 | 1,00 | -0,31 | 1,00 |
| 2021 | +0,00 | 1,00 | -0,31 | 0,98 |
| 2022 | +0,00 | 1,00 | -0,31 | 0,99 |
| 2023 | +0,00 | 1,00 | +0,01 | 0,97 |
| 2024 | +0,01 | 1,00 | -0,24 | 0,95 |
| 2025 | +0,36 | 1,00 | -0,10 | 0,93 |
| 2026 | -0,00 | 1,00 | -0,38 | 0,89 |

## Contrôle de calage appliqué à chaque source

| Source | Mois contrôlés | Calage suspect | Production de nuit |
|---|---|---|---|
| Energy-Charts | 142 | 20 | 13 |
| ENTSO-E | 142 | 8 | 13 |
| RTE | 140 | 0 | 0 |

## Prix day-ahead : Energy-Charts et ENTSO-E

| Année | Heures communes | Baseload EC (€/MWh) | Baseload ENTSO-E (€/MWh) | Écart absolu moyen | Écart absolu max | Heures différentes |
|---|---|---|---|---|---|---|
| 2015 | 8664 | 38,46 | 38,46 | 0,000 | 0,000 | 0 |
| 2016 | 8784 | 36,75 | 36,75 | 0,000 | 0,000 | 0 |
| 2017 | 8760 | 44,97 | 44,97 | 0,000 | 0,000 | 0 |
| 2018 | 8760 | 50,20 | 50,20 | 0,000 | 0,000 | 0 |
| 2019 | 8760 | 39,45 | 39,45 | 0,000 | 0,000 | 0 |
| 2020 | 8784 | 32,20 | 32,20 | 0,000 | 0,000 | 0 |
| 2021 | 8760 | 109,17 | 109,17 | 0,000 | 0,000 | 0 |
| 2022 | 8760 | 275,88 | 275,88 | 0,000 | 0,000 | 0 |
| 2023 | 8760 | 96,86 | 96,86 | 0,000 | 0,000 | 0 |
| 2024 | 8784 | 58,02 | 58,02 | 0,000 | 0,000 | 0 |
| 2025 | 8760 | 61,07 | 61,07 | 0,000 | 0,000 | 0 |
| 2026 | 7272 | 89,60 | 89,60 | 0,000 | 0,000 | 0 |

Mois récents, dont les prix élevés d'août et septembre 2026 :

| Mois | Baseload EC (€/MWh) | Baseload ENTSO-E (€/MWh) | Écart absolu max |
|---|---|---|---|
| 2026-07 | 95,23 | 95,23 | 0,000 |
| 2026-08 | 122,80 | 122,80 | 0,000 |
| 2026-09 | 143,30 | 143,30 | 0,000 |
| 2026-10 | 163,43 | 163,43 | 0,000 |

## Consommation : Energy-Charts rapporté aux deux autres sources

| Année | Conso EC / ENTSO-E | Écart absolu moyen (MW) | Conso EC / RTE | Écart absolu moyen (MW) |
|---|---|---|---|---|
| 2015 | 1,000 | 0 | 0,994 | 827 |
| 2016 | 1,000 | 0 | 0,995 | 826 |
| 2017 | 1,000 | 0 | 0,996 | 810 |
| 2018 | 1,000 | 0 | 0,991 | 886 |
| 2019 | 1,000 | 0 | 0,994 | 833 |
| 2020 | 1,000 | 0 | 0,996 | 752 |
| 2021 | 1,000 | 0 | 0,995 | 776 |
| 2022 | 1,000 | 0 | 0,988 | 927 |
| 2023 | 1,000 | 0 | 0,977 | 1370 |
| 2024 | 1,000 | 0 | 0,976 | 1430 |
| 2025 | 1,002 | 690 | 0,981 | 984 |
| 2026 | 1,000 | 0 | 0,976 | 1495 |

## Rejeu du backtest et du pricing, à titre de sensibilité

Une heure absente d'une source reste inconnue : on ne complète jamais avec Energy-Charts. Le prix est celui du scénario central, livraison 2027, site de Montpellier.

| Variante | Mois | MAE modèle | MAE R1 | MAE R2 | Skill R1 | Skill R2 | p DM R1 | TC 2023 | TC 2024 | TC 2025 | β | Prix modèle | Prix persistance |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Officiel (Energy-Charts) | 96 | 5,95 | 6,62 | 11,15 | +0,10 | +0,47 | 0,449 | 86,29 | 67,65 | 58,81 | -6,16 | 32,4 | 37,1 |
| Solaire ENTSO-E | 96 | 5,92 | 6,58 | 11,10 | +0,10 | +0,47 | 0,459 | 86,29 | 67,65 | 59,06 | -6,15 | 32,5 | 37,2 |
| Tout ENTSO-E | 96 | 5,92 | 6,58 | 11,10 | +0,10 | +0,47 | 0,459 | 86,29 | 67,65 | 59,06 | -6,11 | 33,1 | 37,3 |
| Solaire RTE | 96 | 5,95 | 6,79 | 11,52 | +0,12 | +0,48 | 0,284 | 84,57 | 64,84 | 56,04 | -5,87 | 29,9 | 35,6 |

## Couverture et doublons

- solaire ENTSO-E : 0 doublons retirés
- conso ENTSO-E : 0 doublons retirés
- prix ENTSO-E : 336 doublons retirés
- RTE : 24 points en double, heures concernées laissées inconnues

## Après coup : deux anomalies distinctes

La règle supposait une seule cause. Ses 20 mois en mêlent deux, ce qu'elle ne pouvait pas dire. Cette section est écrite après son résultat.

**2025 : Energy-Charts garde le premier quart d'heure.** ENTSO-E passe au quart d'heure fin 2024, mais les fichiers Energy-Charts restent horaires jusqu'à fin 2025. Une valeur horaire est alors centrée sur h + 7,5 min au lieu de h + 30 min : la courbe semble 0,375 h trop tard.

| Série, 2025 | Heures | Égale au premier quart d'heure | Égale à la moyenne de l'heure | Écart absolu moyen à la moyenne (MW) |
|---|---|---|---|---|
| solaire | 8754 | 100,00 % | 39,14 % | 356 |
| conso | 8755 | 100,00 % | 0,01 % | 690 |

**2023–2024 : l'anomalie est déjà dans ENTSO-E.** Energy-Charts égale ENTSO-E, et les deux divergent de RTE. Un retard positif signifie qu'Energy-Charts est en retard sur RTE.

| Mois | Écart EC − ENTSO-E (h) | Écart EC − RTE (h) | Meilleur retard face à RTE (h) | Corrélation à 0 h, face à RTE |
|---|---|---|---|---|
| 2023-08 | +0,00 | -0,25 | +0 | 0,991 |
| 2023-09 | +0,00 | +0,44 | +0 | 0,975 |
| 2023-10 | +0,00 | +0,71 | +1 | 0,961 |
| 2023-11 | +0,00 | +0,71 | +1 | 0,950 |
| 2023-12 | +0,00 | +0,59 | +1 | 0,957 |
| 2024-01 | +0,00 | +0,35 | +0 | 0,981 |
| 2024-02 | +0,00 | +0,30 | +0 | 0,986 |
| 2024-03 | +0,00 | +0,41 | +0 | 0,986 |
| 2024-04 | +0,00 | -0,46 | +0 | 0,983 |
