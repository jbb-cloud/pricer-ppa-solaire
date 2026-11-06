# Pricing V1 : PPA pay-as-produced, livraison 2027

Généré le 30/10/2026 ; données jusqu'au 29/10/2026 13:00. Choix : `docs/pricing.md`.

Site : Montpellier (43,61 N, 3,88 E), 1 MWc, plein sud, inclinaison 39°, pertes 14 %. Volume : moyenne PVGIS 2005–2023, soit 1 500 MWh/MWc par an.

**Ce n'est pas un prix de contrat** : c'est la valeur de l'énergie au spot, avant garanties d'origine, coûts d'équilibrage, risque de crédit et marge, avec le taux de capture national (H2) et une production payée même à prix négatif (H3).

## Prix juste par scénario de baseload

| Scénario | Baseload (€/MWh) | Modèle V1 (€/MWh) | Taux implicite | Persistance (€/MWh) | Taux implicite | Revenu modèle (€/MWc) | Revenu persistance (€/MWc) |
|---|---|---|---|---|---|---|---|
| bas | 50 | **26,5** | 53,1 % | **30,4** | 60,8 % | 39 789 | 45 604 |
| central | 61 | **32,4** | 53,1 % | **37,1** | 60,8 % | 48 543 | 55 636 |
| haut | 77 | **40,9** | 53,1 % | **46,8** | 60,8 % | 61 276 | 70 230 |

Effet du profil du site : avec les volumes nationaux des 12 derniers mois, le prix central serait de 24,8 €/MWh pour le modèle et 31,2 €/MWh pour la persistance. Le site produit plus en hiver (janvier : 6,3 % de son volume, contre 3,1 % au national), quand le baseload et le taux de capture sont élevés.

## Détail mensuel, scénario central

Part du solaire prévue = part des 12 derniers mois valides (2025-10 à 2026-09) × 1,208. Forme du baseload : moyenne 2024–2025.

| Mois | Volume (MWh) | Baseload (€/MWh) | Part de base | Part prévue | Taux modèle | Taux persistance |
|---|---|---|---|---|---|---|
| janv. | 94 | 91,3 | 2,3 % | 2,8 % | 98,0 % | 100,3 % |
| févr. | 106 | 91,9 | 3,8 % | 4,5 % | 82,5 % | 69,5 % |
| mars | 132 | 66,6 | 7,8 % | 9,4 % | 50,3 % | 47,9 % |
| avr. | 138 | 35,9 | 10,7 % | 12,9 % | 29,4 % | 10,2 % |
| mai | 149 | 24,0 | 12,6 % | 15,2 % | 21,6 % | 27,5 % |
| juin | 151 | 40,1 | 13,6 % | 16,5 % | 27,4 % | 63,4 % |
| juil. | 161 | 53,7 | 14,6 % | 17,6 % | 23,6 % | 50,2 % |
| août | 155 | 55,9 | 13,6 % | 16,5 % | 27,4 % | 58,9 % |
| sept. | 135 | 44,6 | 12,6 % | 15,2 % | 27,8 % | 55,4 % |
| oct. | 105 | 61,4 | 6,7 % | 8,1 % | 66,4 % | 76,5 % |
| nov. | 89 | 82,4 | 3,5 % | 4,2 % | 85,5 % | 82,3 % |
| déc. | 86 | 85,9 | 2,5 % | 3,0 % | 97,1 % | 94,7 % |

## Sensibilité à la croissance du solaire, modèle V1, scénario central

| Croissance appliquée | Prix (€/MWh) | Taux implicite | Taux mensuel le plus bas |
|---|---|---|---|
| +0 % | 38,4 | 63,0 % | 37,7 % (mai) |
| +10 % | 35,5 | 58,2 % | 29,9 % (mai) |
| +20 % | 32,6 | 53,4 % | 22,1 % (mai) |
| +30 % | 29,7 | 48,6 % | 14,4 % (mai) |
| +40 % | 26,7 | 43,8 % | 6,3 % (juil.) |

## Erreurs passées sur le taux de capture annuel

Prévision − réalisé, en points (backtest V1), et leur équivalent à un baseload de 61 €/MWh. Un point positif signifie un prix trop élevé.

| Année | Modèle (points) | Modèle (€/MWh) | Persistance (points) | Persistance (€/MWh) |
|---|---|---|---|---|
| 2023 | +2,0 | +1,2 | +8,1 | +5,0 |
| 2024 | +10,4 | +6,3 | +12,9 | +7,9 |
| 2025 | +13,3 | +8,1 | +9,3 | +5,7 |

Sur les 9 mois valides de 2026, l'erreur mensuelle moyenne vaut 15,7 points pour le modèle et 13,9 pour la persistance.

## Erreur de l'hypothèse H2 : formule du pricing et taux réel du site

*Site réel* : prix réels et série PVGIS de l'année. *Formule V1* : taux national de chaque mois et volumes moyens du site, comme dans le pricing. Écart absolu moyen : 0,6 point. Les données PVGIS s'arrêtent avant le régime récent, le plus cannibalisé : ce contrôle ne valide pas H2 pour 2027.

| Année | National | Site réel | Formule V1 | Écart formule − site (points) |
|---|---|---|---|---|
| 2016 | 94,6 % | 98,4 % | 97,9 % | -0,6 |
| 2017 | 92,1 % | 98,4 % | 97,9 % | -0,6 |
| 2018 | 102,1 % | 102,2 % | 102,2 % | -0,0 |
| 2019 | 95,7 % | 99,6 % | 99,4 % | -0,2 |
| 2020 | 92,7 % | 96,0 % | 97,7 % | +1,7 |
| 2021 | 86,3 % | 91,6 % | 91,1 % | -0,4 |
| 2022 | 105,7 % | 101,5 % | 101,8 % | +0,3 |
| 2023 | 86,3 % | 88,9 % | 90,0 % | +1,1 |

## Paramètres du modèle

Calibration sur 140 mois valides, β = -6,16.
