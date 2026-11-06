# Audit, blocs C et D : prix et risque

Plan et seuils : `docs/audit.md`. Les scénarios officiels ne changent pas : tout ici est une sensibilité.

## C1. Le baseload de 61 €/MWh

| Période | Baseload (€/MWh) |
|---|---|
| 2025-10 | 57,5 |
| 2025-11 | 59,1 |
| 2025-12 | 68,6 |
| 2026-01 | 102,7 |
| 2026-02 | 46,0 |
| 2026-03 | 63,9 |
| 2026-04 | 39,8 |
| 2026-05 | 52,2 |
| 2026-06 | 66,1 |
| 2026-07 | 95,2 |
| 2026-08 | 122,8 |
| 2026-09 | 143,3 |

12 derniers mois valides : **76,6 €/MWh**. Année 2026 jusqu'au 29/10 : **89,6 €/MWh**. Octobre 2026, incomplet : 163,4 €/MWh. 2025 : 61,1 €/MWh.

| Cotation publique, base, clôture du 27/10/2026 (Selectra, qui cite EEX) | €/MWh |
|---|---|
| CAL 2027 | 120,3 |
| CAL 2028 | 70,8 |
| CAL 2029 | 62,5 |
| T1 | 189,8 |
| T2 | 78,0 |
| T3 | 95,1 |
| T4, déduit de CAL et de T1 à T3 | 119,6 |

Le scénario central de 61 €/MWh vaut **51 %** de cette cotation, et le scénario haut de 77 €/MWh en vaut 64 %. Il reste proche de CAL 2029 (62,5 €/MWh) : plausible à long terme, pas pour une livraison en 2027.

## C2. Quelle hypothèse déplace le plus le prix 2027 ?

Référence : V1, baseload de 61 €/MWh, soit **32,4 €/MWh**. Une seule hypothèse change à la fois.

| Hypothèse | Variation | Prix bas | Prix haut | Étendue (€/MWh) |
|---|---|---|---|---|
| Baseload | 2026 jusqu'au 29/10, puis cotation CAL 2027 avec la forme 2024–2025 | 47,5 | 63,9 | 16,3 |
| Baseload | scénarios bas et haut (50 et 77 €/MWh) | 26,5 | 40,9 | 14,3 |
| Croissance du solaire, V1 | +40 % puis aucune | 26,7 | 38,4 | 11,7 |
| Croissance du solaire, M2 | aucune, puis la dernière croissance seule (H4) | 26,8 | 36,1 | 9,3 |
| Baseload | cotation CAL 2027 et trimestres publics, taux V1 puis persistance | 63,7 | 72,5 | 8,8 |
| Profil du site | volumes nationaux au lieu du site | 24,8 | 32,4 | 7,6 |
| Modèle | M2 au Monte-Carlo, puis persistance | 31,0 | 37,1 | 6,1 |
| Source du solaire (rapport des sources) | RTE, puis tout ENTSO-E | 29,9 | 33,1 | 3,2 |
| Forme du baseload | 2025 seule, puis 2023–2025 | 31,6 | 32,8 | 1,2 |
| Fenêtre de M2 | 1 an | 31,0 | 31,7 | 0,8 |

## D1. Backtest du prix annuel, 2018–2025

Prix prévu pour un baseload annuel de 1, avec la forme connue à l'avance (les deux années précédentes), face au prix réalisé selon la formule du pricing. Le niveau annuel n'est pas prévu : il relève du marché à terme. Erreur en points de baseload ; à 61 €/MWh, 1 point vaut 0,61 €/MWh.

| Méthode | Erreur moyenne (points) | Biais (points) | Erreur la plus forte (points) | Erreur moyenne à 61 €/MWh | Solide (sous 5 points) |
|---|---|---|---|---|---|
| Taux annuel de l'année précédente | 7,6 | 3,9 | 15,8 | 4,6 €/MWh | **non** |
| R1 mensuel, forme connue | 6,6 | 3,4 | 17,0 | 4,0 €/MWh | **non** |
| V1, forme connue | 5,9 | 1,7 | 13,8 | 3,6 €/MWh | **non** |
| V1, forme réalisée (irréaliste) | 3,7 | 2,3 | 12,9 | 2,3 €/MWh | oui |
| M1, forme connue | 8,5 | 5,7 | 22,5 | 5,2 €/MWh | **non** |
| M2 médian, forme connue | 6,1 | 2,7 | 16,5 | 3,7 €/MWh | **non** |
| M2, trajectoires (comme le Monte-Carlo) | 6,1 | 2,6 | 16,4 | 3,7 €/MWh | **non** |

| Année | Baseload | Réalisé | Année précédente | V1 | M2 trajectoires | Intervalle à 90 % de M2 | Dans l'intervalle |
|---|---|---|---|---|---|---|---|
| 2018 | 50,2 | 102,2 | 97,9 | 96,3 | 97,3 | 94,9 à 99,8 | **non** |
| 2019 | 39,4 | 99,4 | 102,2 | 98,4 | 99,2 | 96,7 à 101,4 | oui |
| 2020 | 32,2 | 97,7 | 99,4 | 97,5 | 99,6 | 97,4 à 101,4 | oui |
| 2021 | 109,2 | 91,1 | 97,7 | 95,2 | 96,7 | 93,8 à 99,2 | **non** |
| 2022 | 275,8 | 101,8 | 91,1 | 91,7 | 93,1 | 89,4 à 97,0 | **non** |
| 2023 | 96,9 | 90,0 | 101,8 | 90,2 | 91,6 | 86,5 à 96,8 | oui |
| 2024 | 58,0 | 74,2 | 90,0 | 88,0 | 90,6 | 86,0 à 94,8 | **non** |
| 2025 | 61,1 | 67,0 | 74,2 | 79,3 | 76,2 | 70,2 à 80,4 | **non** |

Le taux annuel du site réalisé tombe dans l'intervalle de M2 **3 années sur 8**, pour 7,2 attendues.

## D2. Calibrage de la VaR

### Le baseload sort-il de l'intervalle à 90 %, centré sur l'année précédente ?

| σ | Années hors de l'intervalle, sur 10 | Attendu | Années concernées |
|---|---|---|---|
| 0,25 | 4 | 1 | 2021, 2022, 2023, 2024 |
| 0,17 | 4 | 1 | 2021, 2022, 2023, 2024 |

### VaR à 95 % du spot, baseload de moyenne 61 €/MWh

Moyenne sur 30 tirages de l'erreur. Le rapport au revenu moyen ne dépend pas du niveau du baseload : à 120 €/MWh, les montants sont environ 2 fois plus élevés.

| Cas | VaR 95 % | Revenu moyen | VaR / revenu moyen |
|---|---|---|---|
| σ = 0,25, corrélation 0,65, sans erreur de modèle | 22 600 € | 47 200 € | 48 % |
| Idem, erreur du taux national sur les trajectoires | 26 000 € | 47 300 € | 55 % |
| Idem, erreur du prix du site (D1) | 24 000 € | 47 200 € | 51 % |
| Variations historiques du baseload, crise comprise, sans erreur | 33 800 € | 46 800 € | 72 % |
| Variations historiques, erreur du prix du site (D1) | 33 900 € | 46 900 € | 72 % |
