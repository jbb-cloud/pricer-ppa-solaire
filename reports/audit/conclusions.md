# Audit, bloc B : robustesse des conclusions

96 mois, 2018–2025. Plan et seuils : `docs/audit.md`.

## B1. Graines

10 graines, 1000 trajectoires. Seuil : verdict et classement inchangés.

| Modèle | Graine | MAE | Biais | Skill vs R1 | Skill vs V1 | Couverture |
|---|---|---|---|---|---|---|
| M2 | 20261030 | 5,94 | 4,04 | +0,103 | +0,002 | 66,7 % |
| M2 | 1 | 5,92 | 4,03 | +0,106 | +0,006 | 66,7 % |
| M2 | 2 | 5,97 | 4,04 | +0,099 | −0,003 | 66,7 % |
| M2 | 3 | 5,97 | 4,05 | +0,098 | −0,003 | 66,7 % |
| M2 | 4 | 5,95 | 4,05 | +0,101 | −0,000 | 66,7 % |
| M2 | 5 | 5,91 | 4,03 | +0,107 | +0,006 | 66,7 % |
| M2 | 6 | 5,94 | 4,03 | +0,103 | +0,002 | 65,6 % |
| M2 | 7 | 5,96 | 4,03 | +0,099 | −0,002 | 66,7 % |
| M2 | 8 | 5,94 | 4,05 | +0,102 | +0,001 | 66,7 % |
| M2 | 9 | 5,92 | 4,03 | +0,105 | +0,005 | 66,7 % |
| M1 | 20261030 | 8,12 | 7,02 | −0,227 | −0,365 | 35,4 % |
| M1 | 1 | 8,11 | 7,01 | −0,225 | −0,363 | 37,5 % |
| M1 | 2 | 8,09 | 7,01 | −0,222 | −0,360 | 37,5 % |
| M1 | 3 | 8,10 | 7,02 | −0,224 | −0,362 | 37,5 % |
| M1 | 4 | 8,11 | 7,02 | −0,226 | −0,364 | 37,5 % |
| M1 | 5 | 8,09 | 7,00 | −0,222 | −0,360 | 36,5 % |
| M1 | 6 | 8,09 | 7,01 | −0,223 | −0,361 | 38,5 % |
| M1 | 7 | 8,11 | 7,02 | −0,226 | −0,364 | 37,5 % |
| M1 | 8 | 8,11 | 7,02 | −0,226 | −0,364 | 35,4 % |
| M1 | 9 | 8,10 | 7,02 | −0,224 | −0,362 | 35,4 % |

| Modèle | MAE, étendue | Skill vs R1, étendue | Skill vs V1, étendue | Graines avec skill vs V1 > 0 | Couverture, étendue | Critère atteint |
|---|---|---|---|---|---|---|
| M2 | 5,91 à 5,97 | +0,098 à +0,107 | −0,003 à +0,006 | 6 sur 10 | 65,6 à 66,7 % | 0 sur 10 |
| M1 | 8,09 à 8,12 | −0,227 à −0,222 | −0,365 à −0,360 | 0 sur 10 | 35,4 à 38,5 % | 0 sur 10 |

### Monte-Carlo 2027, sans erreur de modèle

| Grandeur | Minimum | Moyenne | Maximum |
|---|---|---|---|
| Prix juste du pay-as-produced (€/MWh) | 31,2 | 31,5 | 31,8 |
| Prime du plancher à 20 €/MWh (€/MWh) | 13,6 | 13,7 | 13,8 |
| VaR du spot (€) | 21 000 | 21 900 | 22 600 |
| VaR du vendeur du ruban (€) | 15 300 | 16 000 | 16 900 |
| VaR de l'acheteur du ruban (€) | 31 800 | 32 800 | 34 100 |
| VaR du vendeur, plancher à 0 €/MWh (€) | 21 500 | 22 300 | 23 900 |
| VaR du vendeur, plancher à 20 €/MWh (€) | 19 300 | 19 900 | 21 100 |

Plancher à 0 €/MWh au-dessus du spot : 9 graines sur 10. Plancher à 20 €/MWh sous le spot : 10 sur 10. Ruban : VaR acheteur au-dessus du vendeur sur 10 graines sur 10.

## B2. Année retirée

Skill en retirant l'année de la colonne. Critère de la V1 : skill > 0 contre R1 et contre R2.

| Comparaison | Tout | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Retraits où le skill reste > 0 |
|---|---|---|---|---|---|---|---|---|---|---|
| V1 contre R1 | +0,10 | +0,11 | +0,09 | +0,13 | +0,06 | +0,11 | +0,01 | +0,06 | +0,25 | 8 sur 8 |
| V1 contre R2 | +0,47 | +0,48 | +0,47 | +0,50 | +0,45 | +0,47 | +0,43 | +0,45 | +0,46 | 8 sur 8 |
| M2 contre R1 | +0,10 | +0,11 | +0,09 | +0,11 | +0,08 | +0,10 | +0,05 | +0,13 | +0,17 | 8 sur 8 |
| M2 contre V1 | +0,00 | −0,00 | −0,00 | −0,02 | +0,02 | −0,01 | +0,04 | +0,07 | −0,10 | 3 sur 8 |
| M2 contre M1 | +0,27 | +0,27 | +0,27 | +0,28 | +0,26 | +0,27 | +0,24 | +0,27 | +0,26 | 8 sur 8 |

Critère de la V1 maintenu pour 8 retraits sur 8.

## B3. Intervalle de confiance du skill

Bootstrap par années entières, 10000 tirages. Avec 8 blocs, c'est un ordre de grandeur.

| Comparaison | Skill | 5 % | 95 % | Part des tirages avec skill > 0 |
|---|---|---|---|---|
| V1 contre R1 | +0,10 | −0,14 | +0,35 | 76 % |
| V1 contre R2 | +0,47 | +0,35 | +0,54 | 100 % |
| M2 contre R1 | +0,10 | −0,01 | +0,26 | 93 % |
| M2 contre V1 | +0,00 | −0,19 | +0,13 | 50 % |
| M2 contre M1 | +0,27 | +0,21 | +0,31 | 100 % |

### En ajoutant les mois valides de 2026 (hors protocole)

105 mois.

| Comparaison | 2018–2025 | Avec 2026 | 2026 seul |
|---|---|---|---|
| V1 contre R1 | +0,10 | +0,06 | −0,13 |
| V1 contre R2 | +0,47 | +0,50 | +0,61 |
| M2 contre R1 | +0,10 | +0,06 | −0,13 |
| M2 contre V1 | +0,00 | +0,00 | −0,00 |
| M2 contre M1 | +0,27 | +0,21 | −0,13 |

## B4. Diebold-Mariano selon le nombre de retards

| Comparaison | p, 5 retards | p, 11 retards | p, 17 retards | Conclusion à 5 % |
|---|---|---|---|---|
| V1 contre R1 | 0,406 | 0,450 | 0,446 | stable (non significatif à 11 retards) |
| V1 contre R2 | 0,001 | 0,007 | 0,020 | stable (significatif à 11 retards) |
| M2 contre R1 | 0,115 | 0,105 | 0,095 | stable (non significatif à 11 retards) |
| M2 contre V1 | 0,983 | 0,985 | 0,985 | stable (non significatif à 11 retards) |
| M2 contre M1 | 0,001 | 0,004 | 0,012 | stable (significatif à 11 retards) |
