# Audit de solidité des résultats

Lancé le 30/10/2026, sur le commit `6a5fb48`. **Le plan et les seuils ci-dessous sont écrits avant tout contrôle.** La présentation (README, notebook, interface) attend
la fin de cet audit.

## Règles

- **Une vraie erreur de calcul est corrigée** : les rapports sont régénérés, le verdict qui en découle est accepté même défavorable, et une ligne est ajoutée au journal de `docs/perimetre.md`.
- **Un choix de méthode discutable n'est pas modifié** : il est rapporté comme sensibilité. Le changer après avoir vu les résultats serait du data snooping.
- Les données officielles restent celles de H8.

## Classement de chaque résultat

| Classe | Condition |
|---|---|
| **Solide** | recalcul conforme aux tolérances, et conclusion inchangée avec toutes les graines et en retirant n'importe quelle année de test |
| **Fragile** | calcul juste, mais la conclusion change avec une graine ou une année retirée, ou repose sur une hypothèse non étayée par des données |
| **Faux** | erreur de calcul ou affirmation contredite par les rapports |

## Résultats audités

| Code | Résultat |
|---|---|
| R1 | Taux de capture historiques (102,1 % en 2018, 58,81 % en 2025) et baseloads |
| R2 | La V1 atteint son critère : skill de +0,10 contre R1 et de +0,47 contre R2 |
| R3 | Le gain de la V1 sur R1 n'est pas significatif (p = 0,449) |
| R4 | M1 et M2 n'atteignent pas leur critère ; M2 égale la V1 et bat nettement M1 |
| R5 | Aucune variante n'explique la chute de 2024 |
| R6 | Prix 2027 à 61 €/MWh : 31,4 (Monte-Carlo), 32,4 (V1), 37,1 (persistance) |
| R7 | Répartition du risque par contrat : le ruban surcouvre, le plancher horaire transfère peu de risque |
| R8 | VaR à 95 % du spot : 23 300 € fixés d'avance, plutôt 26 000 € |
| R9 | Deux causes aux décalages du solaire : ENTSO-E ou en amont en 2023–2024, Energy-Charts en 2025 |
| R10 | Prix identiques entre Energy-Charts et ENTSO-E |

## Bloc A : les calculs sont-ils justes ?

| Contrôle | Méthode | Seuil |
|---|---|---|
| A1, reproduction | reconstruire la base depuis les fichiers bruts dans un dossier temporaire et la comparer ; relancer les scripts de résultats ; tester un clone neuf du commit | base identique ; rapports identiques hors date de génération ; tests réussis |
| A2, recalcul indépendant | un agent séparé recalcule les chiffres clés depuis les fichiers bruts, sans le code, les docs ni les rapports du projet | déterministe : 0,05 point, 0,1 €/MWh, 0,01 de p-value, 0,002 de λ. Simulé : 0,3 point d'erreur moyenne, 5 points de couverture, 1 €/MWh, 2 000 € de VaR |
| A3, fuites de données | sur les vraies données, remplacer tout ce qui suit la date de coupure par des valeurs absurdes | prévisions strictement identiques |
| A4, cohérence des docs | un second agent confronte docs et cours aux rapports : chiffres, comparaisons entre définitions différentes, affirmations trop fortes | chaque écart est listé et traité |

## Bloc B : les conclusions tiennent-elles ?

| Contrôle | Méthode | Seuil |
|---|---|---|
| B1, graines | M1, M2 et Monte-Carlo sur 10 graines | verdict et classement inchangés ; étendue rapportée |
| B2, année retirée | skills de la V1 et de M2 en retirant chaque année de 2018 à 2025 | critère de la V1 maintenu pour les 8 retraits |
| B3, intervalle de confiance | skill de la V1 contre R1 et R2 : bootstrap par années entières, 10 000 tirages, intervalle à 90 % | l'intervalle contre R1 exclut-il 0 ? Lecture sans seuil pour R2 |
| B4, test de Diebold-Mariano | p-value avec 5, 11 et 17 retards | conclusion à 5 % inchangée |

Huit années forment un petit échantillon : un bootstrap par années reste approximatif, et il est lu comme un ordre de grandeur.

## Bloc C : les hypothèses de prix sont-elles défendables ?

| Contrôle | Méthode | Seuil |
|---|---|---|
| C1, baseload | situer 61 €/MWh face aux 12 derniers mois, à 2026 et aux références publiques accessibles | aucune décision automatique : le scénario n'est pas modifié, l'écart est mesuré |
| C2, classement des hypothèses | faire varier une à une le baseload, le modèle, la croissance, la source du solaire, la fenêtre et le profil du site | classement par effet sur le prix 2027 |

## Bloc D : l'erreur sur le prix et la VaR

| Contrôle | Méthode | Seuil |
|---|---|---|
| D1, backtest du prix annuel | pour 2018–2025, prix prévu avec la forme de baseload connue à l'avance et le niveau annuel réalisé, face au prix réalisé, pour V1, M1, M2 et la persistance | erreur moyenne rapportée en points et en €/MWh ; solide sous 5 points |
| D2, calibrage de la VaR | fréquence à laquelle le baseload réalisé sort de σ = 0,25 centré sur l'année précédente ; VaR avec les variations historiques crise comprise | sorties attendues : 10 % ; écart rapporté |

## Résultats (31/10/2026)

Rapports : `reports/audit/conclusions.md`, `reports/audit/fuites.md`, `reports/audit/prix.md`. Scripts : `scripts/audit_reproduction.sh`, `scripts/audit_fuites.py`, `scripts/audit_conclusions.py`, `scripts/audit_prix.py`.

**En bref : les calculs sont justes, mais plusieurs conclusions étaient trop fortes, et le prix 2027 à 61 €/MWh reposait sur le mauvais niveau.**

| Code | Résultat | Classe | Preuve |
|---|---|---|---|
| R1 | Taux de capture et baseloads | **Solide** comme calcul sur Energy-Charts | recalcul à 0,02 point près. Le niveau de 2025 dépend de la source : de 56,0 à 59,1 % |
| R2 | La V1 atteint son critère | **Solide** contre R2, **fragile** contre R1 | critère maintenu sur 8 retraits sur 8, mais skill contre R1 de −0,14 à +0,35 (76 % des tirages > 0), et de −0,13 sur 2026 |
| R3 | Gain de la V1 sur R1 non significatif | **Solide** | p de 0,41 à 0,45 selon les retards, 0,46 au recalcul |
| R4 | M1 et M2 sans critère ; M2 égale la V1 et bat M1 | **Solide**, sauf M2 contre M1 sur 2026 | critère atteint sur 0 graine sur 10 ; M2 contre V1 de −0,003 à +0,006 ; M2 contre M1 significatif sur 2018–2025 (p de 0,001 à 0,012), mais −0,13 sur 2026 |
| R5 | Aucune variante n'explique 2024 | **Solide**, avec une portée limitée | règle non atteinte sur 7 essais ; la marge du test est étroite (+4,5 au mieux) et le résultat passe par la forme de M2 |
| R6 | Prix 2027 à 61 €/MWh | **Faux comme prix 2027**, calcul juste | 32,34 à 32,37 et 37,07 à 37,10 €/MWh au recalcul, mais 61 €/MWh vaut 50 % de la cotation. La V1 n'applique qu'un an de croissance sur 1,25 : 30,7 €/MWh à horizon égal. Remplacé par la V2 |
| R7 | Répartition du risque | Ruban et pay-as-produced : **solide**. Plancher : **fragile** | ruban sur 10 graines sur 10 et corrélation de −0,81 à −0,95. Plancher : 873 heures négatives contre 583, trop profondes, et l'effet sur la VaR change de signe avec le niveau |
| R8 | VaR de 23 300 € puis « plutôt 26 000 € » | **Fragile** ; le 26 000 € est **faux** | il mêlait une erreur nationale à un revenu de site : 24 000 € au site. Baseload hors de son intervalle 4 années sur 10, corrélation de 0,26 à 0,70. Ordre de grandeur : 50 à 72 % du revenu moyen |
| R9 | Deux causes aux décalages | **Solide** pour 2025 et pour l'identité d'ENTSO-E en 2023–2024 | 100,00 % des heures égalent le premier quart d'heure ; le décalage d'1 h face à RTE ne vaut que d'octobre à décembre 2023 ; l'étape en amont reste inconnue |
| R10 | Prix identiques entre Energy-Charts et ENTSO-E | **Solide**, sans être une preuve indépendante | écart de 0,000 ; les deux sources remontent aux mêmes publications |

### Bloc A

- **A1, reproduction : réussie.** Clone neuf du commit `6a5fb48` : base reconstruite identique (132 146 et 125 383 lignes), 31 rapports identiques hors date, 190 tests réussis.
- **A2, recalcul indépendant : conforme**, après réconciliation.

| Grandeur | Projet | Recalcul | Commentaire |
|---|---|---|---|
| β | −6,16 | −6,1608 | |
| MAE R1, V1 | 6,618 ; 5,949 | 6,607 ; 5,955 | mon code exclut aussi 84 heures sans consommation : en alignant, 6,607 et 5,953 |
| p de la V1 contre R1 | 0,449 | 0,462 | idem : 0,462 en alignant. Seul écart au-delà de la tolérance de 0,01, expliqué |
| Prix V1 et persistance | 32,37 ; 37,10 | 32,34 ; 37,07 | janvier 2005 exclu au recalcul : 32,37 et 37,10 en l'incluant |
| λ de M2 | 0,48 à 0,63 | 0,48 à 0,63 | tous à 0,002 près |
| MAE et couverture de M2 | 5,94 ; 66,7 % | 5,95 ; 67,7 % | dans le bruit de simulation |
| Prix juste et VaR du Monte-Carlo | 31,4 ; 22 600 € | 31,3 ; 21 100 € (21 000 à 22 700) | dans la tolérance ; 22 600 € est le haut de l'étendue des graines |
| VaR du ruban, acheteur et vendeur | 33 800 ; 15 800 € | 32 200 ; 17 200 € | dans la tolérance |

  Le document disait « prix ou production manquants » alors que le code exclut aussi une consommation manquante : c'est une définition à préciser, sans effet sur le verdict (skill de 0,101 contre 0,099). Le code reste inchangé. **L'agent signale aussi trois faiblesses de conception** : M2 mélange deux régimes dans sa loi de prix ; la V1 n'applique qu'un an de croissance sur 1,25 an ; le Monte-Carlo mêle des niveaux de 2026 et une loi arrêtée à 2025.
- **A3, fuites : aucune**, sur les vraies données, pour V1, M0, M1, M2 et la livraison 2027.
- **A4, cohérence des documents : 23 écarts notables, tous traités.** Les tableaux recopiés étaient presque tous exacts ; les vrais problèmes étaient des explications et des comparaisons. Les plus importants :
  - le cours se contredisait sur qui porte le volume en pay-as-produced ;
  - il présentait la cause de la baisse du taux de capture comme établie, tout en la disant non établie ailleurs ;
  - il expliquait mal le taux au-dessus de 100 % : celui de 2022 vient d'un été cher, pas de midi contre la nuit ;
  - il comparait 31,4 €/MWh, à baseload aléatoire, à 32,4 €/MWh à baseload fixé ;
  - il comparait une prime brute de plancher à une baisse de VaR, alors que cette prime est rendue en espérance.

  Trois chiffres restent sans rapport source : ceux de prototypes et de tests ponctuels signalés comme tels dans `docs/stochastique.md`, 89,9 et 92,8 % dans `docs/pricing.md`, et 0,04 pour H18, dont la définition est désormais écrite.

### Bloc B

- **B1, graines** : M2, MAE de 5,91 à 5,97 et couverture de 65,6 à 66,7 %, critère atteint sur 0 graine sur 10. M2 contre V1 : positif sur 6 graines sur 10, soit une égalité. Monte-Carlo à 61 €/MWh : prix de 31,2 à 31,8 €/MWh, VaR de 21 000 à 22 600 €.
- **B2, année retirée** : le critère de la V1 tient sur 8 retraits sur 8, mais le skill contre R1 tombe à +0,01 sans 2023.
- **B3, intervalles à 90 %** : V1 contre R1, −0,14 à +0,35 ; V1 contre R2, +0,35 à +0,54 ; M2 contre V1, −0,19 à +0,13 ; M2 contre M1, +0,21 à +0,31.
- **B4, retards** : conclusion à 5 % inchangée pour toutes les comparaisons.

### Bloc C

- **C1, baseload** : le scénario central vaut 50 % de la cotation CAL 27 de 122,61 €/MWh. Il est proche de CAL 29 (62,48 €/MWh), donc plausible à long terme, pas pour 2027. La cotation vient de Selectra, qui cite EEX : pas de lecture directe, mais la moyenne des trimestres redonne CAL 27, et les prix spot du même site correspondent à ENTSO-E à l'arrondi près.
- **Date de la cotation** : `reports/audit/prix.md` utilise la clôture du 27/10 (120,34 €/MWh), relevée en premier ; le pricing V2 utilise celle du 29/10 (122,61 €/MWh).
- **C2, classement** : le niveau de baseload déplace le plus le prix, puis la croissance du solaire, le profil du site, le modèle et la source du solaire. La forme du baseload à l'intérieur de l'historique et la fenêtre de M2 pèsent peu.

### Bloc D

- **D1, prix annuel à forme connue** : erreur moyenne de 5,9 points pour la V1, 6,1 pour M2, 6,6 pour R1 et 7,6 avec le taux de l'année précédente. **Aucune méthode réaliste ne passe le seuil de 5 points.** La V1 à forme réalisée fait 3,7 : la forme du baseload coûte donc environ 2 points. À 61 €/MWh, l'erreur moyenne vaut 3,6 €/MWh ; à 122,61 €/MWh, environ 7 €/MWh. Pire erreur de la V1 : 13,8 points.
- **D2, VaR** : le baseload sort de l'intervalle à 90 % centré sur l'année précédente 4 années sur 10 (2021 à 2024), pour 1 attendue. Le taux du site tombe dans l'intervalle de M2 3 années sur 8.

### Ce que l'audit ne couvre pas

Quelques affirmations générales de marché dans le cours restent sans source et à vérifier, par exemple le rôle du couplage dans la formation du prix. L'espérance d'un prix juste est prise sous la loi simulée, pas sous une mesure de marché. Les données brutes ne sont pas comparées à d'autres sources que RTE et ENTSO-E, et le calage du solaire allemand et espagnol n'est pas contrôlé. **Aucun modèle n'a encore été jugé sur des mois vraiment nouveaux** : c'est le contrôle le plus important qui reste à faire, dès que novembre 2026 sera complet.
