# Pricing V2 : livraison 2027

Généré le 31/10/2026. Choix, limites et attentes : `docs/pricing.md`. Site : Montpellier, 1 MWc, 1500 MWh/an.

**Ce n'est pas un prix de contrat** : valeur de l'énergie au spot, avant garanties d'origine, équilibrage, crédit et marge. Ce prix suit la cotation, qui bouge vite. La forme du taux de capture a été choisie après avoir vu les années de test. Horizon d'un an : le niveau de 2027 ne vaut pas pour la suite.

## La courbe utilisée

Clôture du 29/10/2026, relevée sur Selectra, qui cite EEX. Pas de lecture directe d'EEX.

| Échéance | Base (€/MWh) | Pointe (€/MWh) | Pointe / base |
|---|---|---|---|
| CAL 2027 | 122,6 | 129,7 | 1,06 |
| T1 2027 | 194,4 | 215,5 | 1,11 |
| T2 2027 | 80,6 | 67,3 | 0,83 |
| T3 2027 | 96,1 | 83,1 | 0,86 |
| T4 2027 | 120,5 | 154,5 | 1,28 |
| CAL 2028 | 69,9 | 81,9 | 1,17 |
| CAL 2029 | 62,5 | 76,9 | 1,23 |

## Prix du pay-as-produced

**Chiffre central : 70,6 €/MWh**, soit 57,6 % du baseload et 105 900 €/MWc par an, pour un parc de 40 GW. La V1 officielle, à 61 €/MWh, reste à 32,4 €/MWh.

| Parc à mi-2027 | GW | Part × | **V2 : part et niveau** | V1 : part seule | Persistance | Implicite de la courbe en T2 et T3 | Taux V2 T2 / T3 |
|---|---|---|---|---|---|---|---|
| Rythme de la PPE3 | 37,6 | 1,157 | **74,6** | 68,1 | 74,0 | 84,0 | 35,1 % / 36,8 % |
| Rythme récent | 40,0 | 1,231 | **70,6** | 63,6 | 74,0 | 83,0 | 29,6 % / 31,0 % |
| Accélération | 42,0 | 1,292 | **67,3** | 59,9 | 74,0 | 82,2 | 25,1 % / 26,2 % |

Taux implicite de la courbe : T2 53,9 % (R² de la droite 0,97), T3 54,4 % (R² 0,95), sur 12 années. Aucun historique de cotations ne permet de tester ce passage.

## Détail mensuel, rythme récent

| Mois | Volume (MWh) | Baseload (€/MWh) | Part du solaire | Taux V2 | Taux V1 | Persistance |
|---|---|---|---|---|---|---|
| 1 | 94 | 213,9 | 2,9 % | 100,1 % | 97,7 % | 100,3 % |
| 2 | 106 | 215,3 | 4,6 % | 87,4 % | 82,0 % | 69,5 % |
| 3 | 132 | 155,9 | 9,6 % | 63,3 % | 49,2 % | 47,9 % |
| 4 | 138 | 87,1 | 13,2 % | 32,4 % | 27,8 % | 10,2 % |
| 5 | 149 | 58,1 | 15,5 % | 25,1 % | 19,8 % | 27,5 % |
| 6 | 151 | 97,3 | 16,8 % | 31,4 % | 25,4 % | 63,4 % |
| 7 | 161 | 100,2 | 17,9 % | 28,8 % | 21,5 % | 50,2 % |
| 8 | 155 | 104,3 | 16,8 % | 32,3 % | 25,5 % | 58,9 % |
| 9 | 135 | 83,3 | 15,5 % | 32,0 % | 25,9 % | 55,4 % |
| 10 | 105 | 96,7 | 8,2 % | 70,9 % | 65,5 % | 76,5 % |
| 11 | 89 | 129,8 | 4,3 % | 87,4 % | 85,0 % | 82,3 % |
| 12 | 86 | 135,3 | 3,0 % | 98,1 % | 96,8 % | 94,7 % |

Part du revenu et du volume par trimestre : T1 50,1 % du revenu, 22,1 % du volume ; T2 10,1 % du revenu, 29,1 % du volume ; T3 12,7 % du revenu, 30,1 % du volume ; T4 27,1 % du revenu, 18,7 % du volume.

## Sensibilité au niveau

Mêmes rapports entre trimestres, parc central. Le taux de capture bouge avec le niveau : le prix n'est pas proportionnel.

| Niveau annuel | €/MWh | Prix V2 | Taux implicite |
|---|---|---|---|
| CAL 29 (long terme) | 62,5 | 29,5 | 47,2 % |
| CAL 28 | 69,9 | 34,2 | 48,9 % |
| Clôture du 2 octobre, selon un relevé de Selectra | 94,4 | 50,5 | 53,5 % |
| CAL 27, chiffre central | 122,6 | 70,6 | 57,6 % |
| +25 % | 153,3 | 93,5 | 61,0 % |

Avec CAL 27 seul et la forme 2024–2025, sans les trimestres : 73,2 €/MWh.

## Monte-Carlo : le risque

1000 trajectoires, graine 20261030. Baseload de moyenne 122,6 €/MWh, σ = 0,25, corrélation de 0,65 avec le taux de capture. Chaque trajectoire tire l'un des 3 scénarios de parc. Prix de M2, calés en espérance sur les trimestres de la courbe. L'erreur de modèle combine chaque trajectoire à chacune des 8 erreurs de site du backtest, sans tirage.

**Revenu moyen au spot : 89 100 €/MWc. VaR à 95 % avec erreur de modèle : 44 500 €, soit 50 % du revenu moyen.** Prix juste du Monte-Carlo : 59,4 €/MWh, à comparer au prix central de 70,6 €/MWh, qui vient du modèle V2. Taux de capture annuel : médiane 47,7 %, intervalle à 90 % de 41,7 à 54,1 %.

| Contrat | Côté | Prix (€/MWh) | Flux moyen | Écart-type | VaR 95 % | CVaR 95 % | VaR sans erreur | Corrélation avec le baseload |
|---|---|---|---|---|---|---|---|---|
| Spot, sans contrat | vendeur | — | 89 100 | 32 300 | **44 500** | 51 200 | 40 700 | +0,98 |
| Pay-as-produced | vendeur | 59,4 | 89 100 | 2 500 | **5 400** | 5 400 | 5 400 | +0,22 |
| Plancher à 0 €/MWh | vendeur | 11,3 | 89 100 | 34 700 | **48 100** | 55 500 | 44 200 | +0,98 |
| Plancher à 10 €/MWh | vendeur | 15,4 | 89 100 | 34 400 | **47 600** | 54 800 | 43 500 | +0,98 |
| Plancher à 20 €/MWh | vendeur | 20,0 | 89 100 | 34 000 | **46 800** | 53 800 | 42 800 | +0,99 |
| Ruban | vendeur | 122,5 | 89 100 | 24 600 | **45 100** | 61 200 | 36 100 | −0,95 |
| Pay-as-produced | acheteur | 59,4 | −0 | 31 700 | **43 600** | 50 100 | 39 100 | +0,98 |
| Plancher à 0 €/MWh | acheteur | 11,3 | −0 | 4 000 | **7 200** | 10 100 | 7 200 | −0,71 |
| Plancher à 10 €/MWh | acheteur | 15,4 | −0 | 4 000 | **7 200** | 9 900 | 7 200 | −0,64 |
| Plancher à 20 €/MWh | acheteur | 20,0 | −0 | 3 900 | **7 000** | 9 600 | 7 000 | −0,54 |
| Ruban | acheteur | 122,5 | −0 | 47 600 | **68 600** | 80 400 | 68 600 | +1,00 |

### D'où vient le risque du spot

Parts de la variance de ln R attribuées par covariance : leur somme vaut 100 %.

Baseload 77,0 %, taux de capture 20,1 %, volume 2,9 %.

### Sensibilités de la VaR du spot

| Hypothèse | VaR sans erreur | VaR avec erreur | VaR avec erreur / revenu moyen |
|---|---|---|---|
| σ = 0,25, corrélation 0,65 (chiffre principal) | 40 700 | 44 500 | 50 % |
| σ = 0,25, corrélation 0,26 | 36 700 | 41 400 | 47 % |
| σ = 0,25, indépendant | 33 800 | 39 000 | 45 % |
| σ = 0,17, corrélation 0,65 | 32 500 | 37 900 | 43 % |
| Variations historiques du baseload, crise comprise | 64 100 | 64 000 | 72 % |
| Baseload fixé à la cotation | 13 200 | 28 000 | 32 % |

### Plancher : prix négatifs multipliés par le baseload, ou non

Dans $p_t = B\,y_t$, un prix négatif grossit avec $B$. La seconde colonne garde les prix négatifs à l'échelle de 61 €/MWh.

| Plancher (€/MWh) | Prime, formule du modèle | Prime, prix négatifs à l'échelle de 61 €/MWh |
|---|---|---|
| 0 | 11,3 | 5,8 |
| 10 | 15,4 | 9,8 |
| 20 | 20,0 | 14,5 |

Heures à prix négatif simulées : 896 par an, contre 583 d'octobre 2025 à septembre 2026. Prix moyen quand il est négatif : −35,8 €/MWh simulés, contre −11,5 €/MWh sur ces 12 mois.

### Stabilité sur 10 graines

| Grandeur | Minimum | Moyenne | Maximum |
|---|---|---|---|
| Prix juste du Monte-Carlo (€/MWh) | 59,0 | 59,6 | 60,3 |
| VaR du spot (€) | 41 400 | 43 200 | 44 800 |
| VaR de l'acheteur en pay-as-produced (€) | 40 500 | 42 400 | 43 600 |
| VaR du vendeur en pay-as-produced (€) | 3 400 | 4 600 | 5 500 |
| VaR de l'acheteur du ruban (€) | 60 200 | 65 400 | 69 000 |
| VaR du vendeur du ruban (€) | 43 600 | 44 900 | 46 400 |
