# Monte-Carlo de pricing : livraison 2027

Généré le 30/10/2026. 1000 trajectoires, graine 20261030. Choix et attentes : `docs/pricing.md`.

Site : Montpellier, 1 MWc, 1500 MWh/an en moyenne. Baseload de moyenne 61 €/MWh, σ = 0,25, corrélation de 0,65 avec le taux de capture. Solaire national de départ : 4,0 GW en moyenne. Fenêtre M2 : 2024–2025.

**Ce n'est pas un prix de contrat** : valeur de l'énergie au spot, avant garanties d'origine, équilibrage, crédit et marge. Montants arrondis à la centaine d'euros. Horizon d'un an : ce résultat ne s'étend pas à un PPA de 10 à 20 ans.

## Prix justes

| Contrat | Prix juste (€/MWh) |
|---|---|
| **Pay-as-produced, Monte-Carlo** | **31,4** (erreur d'échantillonnage à 90 % : 30,9 à 32,0) |
| Pay-as-produced, baseload fixé à 61 | 31,0 |
| Pay-as-produced, V1 | 32,4 |
| Pay-as-produced, persistance | 37,1 |
| Prime du plancher à 0 €/MWh | 4,3 |
| Prime du plancher à 10 €/MWh | 8,6 |
| Prime du plancher à 20 €/MWh | 13,7 |
| Ruban | 60,9 |

Taux de capture annuel du site : médiane de 51,7 %, intervalle à 90 % de 41,5 à 57,6 %, avant erreur de modèle.

## Risque par contrat (€/MWc sur l'année)

VaR et CVaR à 95 %, pertes mesurées par rapport au flux moyen. Le chiffre principal inclut l'erreur de modèle. Pour le plancher, cette erreur ne modifie pas la valeur du put.

VaR du spot avec erreur de modèle, erreur d'échantillonnage à 90 % : 22 200 à 24 300 €.

| Contrat | Côté | Flux moyen | Écart-type | VaR 95 % | CVaR 95 % | VaR sans erreur de modèle | Corrélation avec le baseload |
|---|---|---|---|---|---|---|---|
| Spot, sans contrat | vendeur | 47 400 | 16 700 | **23 300** | 26 800 | 22 600 | +0,94 |
| Pay-as-produced | vendeur | 47 200 | 1 300 | **2 900** | 2 900 | 2 900 | +0,17 |
| Plancher à 0 €/MWh | vendeur | 47 400 | 17 200 | **23 900** | 27 500 | 23 900 | +0,95 |
| Plancher à 10 €/MWh | vendeur | 47 400 | 16 700 | **22 900** | 26 300 | 22 400 | +0,95 |
| Plancher à 20 €/MWh | vendeur | 47 400 | 16 000 | **21 600** | 24 800 | 21 100 | +0,95 |
| Ruban | vendeur | 47 400 | 9 800 | **17 200** | 24 300 | 15 800 | −0,81 |
| Pay-as-produced | acheteur | 300 | 16 400 | **23 000** | 26 400 | 22 000 | +0,94 |
| Plancher à 0 €/MWh | acheteur | −0 | 1 600 | **3 100** | 3 900 | 3 100 | −0,44 |
| Plancher à 10 €/MWh | acheteur | −0 | 1 900 | **3 500** | 4 300 | 3 500 | −0,10 |
| Plancher à 20 €/MWh | acheteur | −0 | 2 300 | **4 200** | 4 900 | 4 200 | +0,21 |
| Ruban | acheteur | −0 | 23 600 | **33 800** | 39 000 | 33 800 | +1,00 |

## D'où vient le risque du spot

Sans erreur de modèle. Chaque source figée laisse la VaR des deux autres.

| Source | Part de la variance de ln R | VaR en figeant cette source |
|---|---|---|
| Baseload | 57,3 % | 9 000 |
| Taux de capture | 9,0 % | 17 900 |
| Volume | 0,7 % | 22 400 |
| Covariances | 33,0 % | — |
| Tout | 100 % | 22 600 |

## Sensibilités du spot

| σ du baseload | Corrélation | Prix juste (€/MWh) | VaR 95 %, sans erreur | VaR 95 %, avec erreur |
|---|---|---|---|---|
| 0,25 | 0,65 | 31,4 | 22 600 | 23 300 |
| 0,25 | 0,00 | 30,9 | 18 600 | 19 600 |
| 0,17 | 0,65 | 31,3 | 18 100 | 19 300 |
| 0,17 | 0,00 | 30,9 | 14 700 | 16 100 |
| 0,00 | 0,00 | 31,0 | 9 000 | 12 200 |

### Baseload fixé par scénario

| Scénario | Baseload | Prix juste (€/MWh) | VaR 95 %, sans erreur | VaR 95 %, avec erreur |
|---|---|---|---|---|
| bas | 50 | 25,4 | 7 400 | 10 000 |
| central | 61 | 31,0 | 9 000 | 12 200 |
| haut | 77 | 39,1 | 11 300 | 15 300 |

## Contrôle en walk-forward : taux de capture annuel national

Dans l'intervalle à 90 % de M2 : **2 années sur 8**, sans erreur de modèle. Avec les seules erreurs connues avant l'année : 1 sur 6. Huit années ne valident pas une VaR : c'est un contrôle de bon sens, sans verdict.

| Année | Réalisé | Médiane M2 | Intervalle sans erreur | Intervalle avec les erreurs connues |
|---|---|---|---|---|
| 2018 | 102,1 | 92,1 | 89,6 à 94,5 | — |
| 2019 | 95,7 | 95,3 | 92,1 à 98,5 | — |
| 2020 | 92,7 | 97,1 | 94,3 à 100,0 | 94,1 à 100,1 |
| 2021 | 86,3 | 92,3 | 88,4 à 95,8 | 88,3 à 96,0 |
| 2022 | 105,7 | 88,2 | 83,8 à 92,7 | 83,8 à 93,0 |
| 2023 | 86,3 | 89,4 | 81,8 à 97,8 | 81,3 à 97,9 |
| 2024 | 67,6 | 89,4 | 83,2 à 95,7 | 82,8 à 95,9 |
| 2025 | 58,8 | 70,7 | 63,6 à 74,9 | 59,8 à 76,8 |

## Après coup : l'erreur de modèle retenue était sous-estimée

H17 mesure l'erreur annuelle avec le baseload et les volumes mensuels réalisés. Or le Monte-Carlo simule aussi quels mois sont chers : l'erreur à comparer se lit sur les trajectoires. Ce résultat vient après le lancement : il ne remplace pas le chiffre principal fixé d'avance, mais il dit que ce chiffre est trop faible.

| Erreur annuelle (points) | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Écart-type |
|---|---|---|---|---|---|---|---|---|---|
| H17, mois réalisés | 0,0 | 0,9 | 1,2 | 1,4 | −1,1 | 3,3 | 12,4 | 10,9 | 5,1 |
| Sur les trajectoires | −10,0 | −0,4 | 4,4 | 5,9 | −17,5 | 3,1 | 21,8 | 11,9 | 12,2 |

Moyenne sur 30 tirages de l'erreur, sur le même jeu de trajectoires :

| Erreur de modèle | VaR 95 % du spot | VaR 95 % à baseload fixé | Taux de capture du site, 5 % à 95 % |
|---|---|---|---|
| Aucune | 22 600 | 9 000 | 41,5 à 57,6 % |
| H17, chiffre principal | 22 900 | 11 900 | 38,0 à 60,1 % |
| Mesurée sur les trajectoires | 26 100 | 18 700 | 30,6 à 72,8 % |
