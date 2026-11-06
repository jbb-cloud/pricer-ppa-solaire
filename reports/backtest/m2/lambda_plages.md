# Test d'un λ par heure et par saison

Généré le 30/10/2026. Valeurs réelles de l'année données au modèle : ce n'est pas une prévision. 1000 trajectoires par année, graine 20261030. Définition, attentes et règle écrites avant le lancement : `docs/stochastique.md`.

## Résultat de la règle

Biais de 2024 sous 5 points en valeur absolue, sans dégrader l'erreur de 2018–2023 de plus de 0,5 point par rapport à A.

| Méthode | Biais 2024 | Erreur 2024 | Erreur 2018–2023 | Règle | Biais 2025 | Erreur 2025 | Biais 2026 (à part) | Erreur 2026 (à part) |
|---|---|---|---|---|---|---|---|---|
| A, référence | +15,5 | 15,5 | 2,8 | non | +10,5 | 13,0 | −2,3 | 14,3 |
| D, λ unique | +15,0 | 15,0 | 3,2 | non | +10,5 | 14,0 | −2,2 | 9,9 |
| D, λ par heure × saison | +12,0 | 12,0 | 3,0 | non | +8,4 | 13,1 | +2,9 | 9,9 |

## Avril–août 2024, en part du baseload annuel

| Cas | Midi (11–16 h) | Autres heures | Ratio | Biais du taux de capture, avril–août | Biais, autres mois |
|---|---|---|---|---|---|
| Réel | 0,23 | 0,82 | 0,29 | — | — |
| A, référence | 0,76 | 1,04 | 0,74 | +27,1 | +7,2 |
| D, λ unique | 0,54 | 0,81 | 0,67 | +25,1 | +7,8 |
| D, λ par heure × saison | 0,48 | 0,87 | 0,54 | +17,5 | +8,1 |

## Biais par année

| Année | A, référence | D, λ unique | D, λ par heure × saison |
|---|---|---|---|
| 2018 | −0,2 | −0,1 | −0,3 |
| 2019 | +0,6 | +0,6 | +0,3 |
| 2020 | +1,8 | +2,6 | +2,6 |
| 2021 | +1,5 | +2,3 | +2,3 |
| 2022 | −1,6 | +0,8 | +0,9 |
| 2023 | +2,3 | +3,0 | +3,1 |
| 2024 | +15,5 | +15,0 | +12,0 |
| 2025 | +10,5 | +10,5 | +8,4 |
| 2026 | −2,3 | −2,2 | +2,9 |

## λ estimés

Moyenne par plage, avril–août, sur la fenêtre de calibration de chaque année testée.

| Année testée | Nuit 0–6 h | Matin 7–10 h | Midi 11–16 h | Soir 17–23 h | Autres mois, tout | Plus petit | Plus grand |
|---|---|---|---|---|---|---|---|
| 2018 | 0,55 | 0,59 | 0,63 | 0,54 | 0,73 | 0,48 | 0,76 |
| 2019 | 0,34 | 0,40 | 0,45 | 0,28 | 0,51 | 0,17 | 0,55 |
| 2020 | 0,62 | 0,66 | 0,64 | 0,58 | 0,50 | 0,40 | 0,68 |
| 2021 | 0,57 | 0,65 | 0,60 | 0,58 | 0,70 | 0,50 | 0,75 |
| 2022 | 0,69 | 0,75 | 0,71 | 0,69 | 0,43 | 0,37 | 0,76 |
| 2023 | 0,76 | 0,76 | 0,79 | 0,76 | 0,52 | 0,47 | 0,81 |
| 2024 | 0,36 | 0,44 | 0,57 | 0,32 | 0,52 | 0,25 | 0,62 |
| 2025 | 0,51 | 0,55 | 0,60 | 0,45 | 0,62 | 0,23 | 0,71 |
| 2026 | 0,57 | 0,58 | 0,26 | 0,61 | 0,73 | 0,19 | 0,78 |
