# Périmètre de la V1

*Validé le 29/10/2026. Toute modification du périmètre ou du protocole de backtest est ajoutée
en bas de ce fichier (section « Journal des modifications »), avec sa date et sa raison.*

## Objectif

Prévoir le **taux de capture solaire mensuel** en France pour l'année suivante, en déduire le
**prix juste d'un PPA solaire pay-as-produced**, et mesurer objectivement la qualité de la
prévision par un **backtest walk-forward** contre des références naïves.

Pourquoi le taux de capture et pas directement le prix du PPA : le prix juste d'un PPA
pay-as-produced vaut environ *niveau baseload futur × taux de capture futur*. Le niveau
baseload est donné par le marché à terme (ou des scénarios) et nous ne prétendons pas mieux le
prévoir que lui. Le taux de capture, c'est l'effet de cannibalisation, où se trouve la valeur
ajoutée du modèle. Un PPA dure 10 à 20 ans et nous n'avons qu'environ 10 ans de données : un
backtest honnête n'est possible qu'à horizon court (un an).

## Définitions

Pour un mois $m$, avec $p_h$ le prix day-ahead de l'heure $h$ et $q_h$ la production solaire
nationale de l'heure $h$ :

- prix baseload : $B_m = \frac{1}{N_m}\sum_{h \in m} p_h$
- prix capté solaire : $C_m = \frac{\sum_{h \in m} q_h\,p_h}{\sum_{h \in m} q_h}$
- taux de capture : $TC_m = C_m / B_m$
- part du solaire : $S_m = \frac{\sum_{h \in m} q_h}{\sum_{h \in m} \text{conso}_h}$

Une heure dont le prix ou la production est manquant est exclue du mois (jamais remplacée par 0).
Le nombre d'heures exclues est suivi ; un mois trop incomplet est marqué invalide.

## Contenu de la V1

1. **Données** : prix day-ahead FR horaires (Energy-Charts, puis ENTSO-E comme référence),
   production solaire nationale et consommation (RTE éCO2mix / ODRÉ), de 2015 à aujourd'hui,
   chargés dans `data/ppa.sqlite`. Contrôles : trous, doublons, changements d'heure, passage
   des prix au quart d'heure (agrégés à l'heure par moyenne pour la V1).
2. **Analyse** : $TC_m$ et $TC$ annuel historiques, relation $S_m$ ↔ $TC_m$, graphiques dans
   `reports/`.
3. **Modèle V1** : régression linéaire du taux de capture mensuel sur la part du solaire, avec
   un effet par mois de l'année :
   $TC_m = \alpha_{\text{mois}(m)} + \beta\,S_m + \varepsilon_m$.
   Pour prévoir l'année $T$, la part du solaire $S_m$ de $T$ est estimée à partir de celle de
   $T-1$ et d'une hypothèse de croissance du parc (voir `docs/hypotheses.md`).
4. **Pricing V1** : PPA pay-as-produced d'un an pour un site de référence (profil PVGIS) :
   $\text{prix juste} = \frac{\sum_m B_m^{\text{scénario}}\;\widehat{TC}_m\;V_m}{\sum_m V_m}$,
   avec $V_m$ le volume mensuel du site et $B_m^{\text{scénario}}$ un scénario de baseload
   (bas / central / haut).

## Hors V1 (plus tard, seulement si la V1 tient son backtest)

Modèle stochastique horaire (Ornstein-Uhlenbeck, sauts, prix négatifs), Monte-Carlo, VaR, PPA
baseload, prix plancher, profil propre du site (au lieu du profil national), horizons
pluriannuels, interface Streamlit.

## Protocole de backtest

Le protocole est fixé **avant** d'écrire le modèle et de voir le moindre résultat du modèle. L'analyse descriptive, qui couvre aussi les années de test, a été vue ensuite : voir le journal.

- **Walk-forward, fenêtre expansive** : pour chaque année de test $T$ de 2018 à la dernière
  année complète (2025), le modèle est calibré uniquement sur les données strictement
  antérieures au 1er janvier $T$, puis prévoit les 12 valeurs $TC_m$ de $T$. Soit environ
  96 prévisions mensuelles. Les années 2015 à 2017 ne servent qu'à la première calibration.
- **Deux variantes**, pour séparer les sources d'erreur :
  - *conditionnelle* : la part du solaire réalisée de $T$ est donnée au modèle. On teste la
    relation $S \to TC$ seule (variante « oracle » sur cette entrée, signalée comme telle) ;
  - *réaliste* : la part du solaire de $T$ est elle-même prévue. C'est la performance réelle
    de l'outil.
- **Références naïves** à battre :
  - R1, persistance : $\widehat{TC}_m(T) = TC_m(T-1)$, le même mois de l'année précédente ;
  - R2, moyenne climatologique : la moyenne de $TC$ pour ce mois de l'année sur toutes les
    années antérieures à $T$.
- **Métriques**, en points de taux de capture :
  - MAE (erreur absolue moyenne) ;
  - biais (erreur moyenne signée, prévision − réalisé) ;
  - *skill score* $= 1 - \text{MAE}_{\text{modèle}} / \text{MAE}_{\text{référence}}$, contre R1
    et contre R2 ;
  - test de Diebold-Mariano (variance HAC) sur les écarts d'erreur, pour savoir si la
    différence avec chaque référence est significative.
- **Présentation** : un tableau global et un tableau par année. La période complète est le
  résultat principal ; le même calcul sans 2022 (crise des prix) est donné à côté, à titre de
  sensibilité. Aucune année n'est retirée a posteriori.
- **Critère de succès de la V1** : skill score > 0 contre R1 **et** contre R2 dans la variante
  réaliste, sur 2018–2025.
- **Garde-fous** : un test pytest vérifie que la fonction de calibration ne reçoit jamais de
  donnée postérieure à la date de coupure. Chaque version du modèle produit son rapport de
  backtest dans `reports/backtest/`, et les rapports précédents sont conservés pour comparer
  les versions.

## Journal des modifications

- 29/10/2026 : version initiale.
- 29/10/2026, **avant tout résultat du modèle** (après l'analyse descriptive, qui couvre aussi les
  années de test) :
  - forme du modèle : on garde uniquement le modèle prévu ($TC_m = \alpha_{\text{mois}} + \beta S_m$).
    L'analyse montre une relation coudée et saisonnière, mais choisir une autre forme d'après ces
    graphiques serait du *data snooping*. D'éventuelles variantes seront figées puis évaluées sur
    les mois publiés après le 29/10/2026, et signalées comme conçues après avoir vu les données ;
  - prévision de la part du solaire (variante réaliste) : hypothèse H4, confirmée ;
  - années de test : verdict officiel sur 2018–2025 ; les mois valides de 2026 (janvier–septembre)
    sont rapportés à part ;
  - métriques complémentaires, qui ne changent pas le critère de succès : MAE pondérée par
    l'énergie solaire réalisée du mois, et erreur sur le taux de capture annuel. Le taux annuel
    prévu combine les 12 prévisions mensuelles avec le baseload et les volumes réalisés,
    $\widehat{TC}_T = \sum_m \widehat{TC}_m B_m Q_m \,/\, (B_T \sum_m Q_m)$, pour mesurer seulement la
    prévision du taux de capture ; avec des prévisions mensuelles parfaites, on retrouve
    exactement le taux annuel réalisé ;
  - Diebold-Mariano : perte absolue, variance de long terme de Newey-West (noyau de Bartlett,
    11 retards), p-value bilatérale d'une loi de Student à $n-1$ degrés de liberté ;
  - toutes les méthodes sont comparées sur le même échantillon de mois.
- 30/10/2026, **après les résultats du backtest** : un test physique a révélé des décalages
  horaires et des valeurs de nuit dans le solaire Energy-Charts, invisibles pour les contrôles de
  grille (détail dans `docs/donnees.md`, hypothèses H7 et H8). Le protocole, le modèle, les
  données et le verdict officiel ne changent pas : les corriger maintenant serait une décision
  prise après avoir vu les résultats. Avec le solaire RTE, à titre de sensibilité, le verdict
  reste le même (skill +0,14 vs R1 et +0,50 vs R2, Diebold-Mariano vs R1 toujours non
  significatif), mais le taux de capture 2025 passe de 58,81 % à 56,05 %. Le choix de la source
  du solaire est reporté à la V2.
- 30/10/2026, **pricing V1** (détail dans `docs/pricing.md`), après les résultats du backtest. Le
  protocole, le modèle et le verdict ne changent pas. Précisions apportées au périmètre :
  - livraison 2027 ; la part du solaire utilise H4 glissante (H9), car H4 demande une année 2026
    complète. Sur une année civile, les deux donnent le même résultat ;
  - scénarios de baseload fixés (H5) et site de référence choisi (H10) ;
  - la persistance est affichée à côté du modèle, parce que le backtest ne permet pas d'affirmer
    que le modèle fait mieux ; ajout d'une mesure de l'erreur de H2 sur 2016–2023.
- 30/10/2026, **contrôle multi-sources, règle fixée avant de voir les données ENTSO-E** : solaire,
  consommation et prix ENTSO-E, solaire et consommation RTE, de 2015 à aujourd'hui. Le décalage du
  solaire est attribué à la source (ENTSO-E ou en amont) si l'heure moyenne de production
  d'Energy-Charts et celle d'ENTSO-E, sur leurs heures communes, diffèrent d'au plus 0,1 h sur au
  moins 80 % des 20 mois signalés par le contrôle de calage (soit au moins 16 mois) ; sinon, il
  apparaît après ENTSO-E. Le résultat et le rejeu du backtest et du pricing sont des sensibilités :
  ils ne changent ni le verdict ni les données officielles de la V1.
- 30/10/2026, **modèles stochastiques, protocole écrit avant le premier résultat de M0** : voir
  `docs/stochastique.md`. Le verdict de la V1 ne change pas. M1 et M2 devront avoir un skill > 0 contre
  R1 et contre la V1, et un intervalle à 90 % couvrant 85 à 95 % des réalisés ; M0 est mesuré sans
  verdict. Tous sont aussi jugés sur les mois publiés après le 29/10/2026.
- 30/10/2026, **M1 défini avant son premier lancement** : loi empirique par case et deux
  Ornstein-Uhlenbeck latents (`docs/stochastique.md`), avec attentes écrites. La fenêtre et le critère du
  protocole ne changent pas ; la fenêtre de 1 an est une sensibilité sans verdict.
- 30/10/2026, **M2 défini avant son premier lancement** : rang conditionné à la charge résiduelle française, tirage de
  la météo par semaines sur la fenêtre et de la croissance du parc parmi les croissances passées
  (`docs/stochastique.md`, H11 à H13). Le protocole et le critère ne changent pas ; H4 et la fenêtre de 1 an sont des
  sensibilités sans verdict. L'éolien est lu dans les fichiers bruts, sans modifier la base.
- 30/10/2026, **test de la chute de 2024, règle fixée avant de le lancer et avant de voir les données voisines** : variantes
  et seuil dans `docs/stochastique.md` (biais de 2024 sous 5 points, sans dégrader 2018–2023 de plus de 0,5 point). Le test
  n'a pas de verdict sur M2 et ne change pas le protocole. Téléchargement approuvé : production et prix de l'Allemagne et de
  l'Espagne, 2015–2026, Energy-Charts.
- 30/10/2026, **résultat du test de la chute de 2024** : aucune variante ne passe la règle (biais de +14,5 à +15,5 points). Le
  protocole, le verdict et les données officielles ne changent pas. Analyse après coup dans `docs/stochastique.md`.
- 30/10/2026, **test d'un λ par heure et par saison, défini avant de le lancer** (`docs/stochastique.md`) : même règle que le test
  précédent. Quel que soit le résultat, M2 ne change pas et le projet passe au pricing.
- 30/10/2026, **résultat du test d'un λ par heure et par saison** : règle non atteinte (biais de +12,0 points). M2, le protocole et le
  verdict ne changent pas ; le projet passe au pricing, comme décidé avant le test.
- 30/10/2026, **Monte-Carlo de pricing défini avant son lancement** (`docs/pricing.md`, H15 à H18) : livraison 2027, M2 tel quel, spot, pay-as-produced, plancher et
  ruban, des deux côtés. Corrigé le même jour : la comparaison entre M2 et la V1 pour 2027 opposait deux définitions différentes (`docs/stochastique.md`).
- 30/10/2026, **résultat du Monte-Carlo** (`docs/pricing.md`) : prix juste de 31,4 €/MWh, VaR à 95 % du spot de 23 300 €/MWc. Le contrôle ne place que 2 années sur 8 dans l'intervalle : l'erreur de modèle retenue était
  sous-estimée, et l'ordre de grandeur honnête de la VaR est plutôt 26 000 €. Le chiffre fixé d'avance n'est pas modifié ; la correction est écrite à côté, comme résultat après coup.
- 30/10/2026, **résultat du contrôle multi-sources** (`docs/donnees.md`) : selon la règle, 8 mois signalés sur 20 sont proches d'ENTSO-E, donc le décalage « apparaît après ENTSO-E ». La règle supposait une seule cause, mais il y en a deux : 2023–2024 vient
  d'ENTSO-E ou d'en amont, 2025 d'Energy-Charts, qui garde le premier quart d'heure (constaté après le résultat). Le verdict de la V1 tient dans toutes les variantes, et les données officielles ne changent pas. Le rejeu complet remplace les chiffres du test ponctuel ci-dessus (+0,12 et +0,48 ; p = 0,284 ; taux 2025 de 56,04 %).
- 31/10/2026, **pricing V2 défini avant son lancement** (`docs/pricing.md`, H19 à H22), à la demande de priorité sur le niveau de prix et la cannibalisation : baseload ancré sur la courbe à terme, taux de capture relié à la part du solaire et au niveau, scénarios de parc en GW, Monte-Carlo refait. Les rapports V1, M0, M1 et M2 et leurs verdicts ne changent pas. La forme du modèle V2 a été choisie après avoir vu les années de test : seuls les mois publiés après le 29/10/2026 la jugeront. C'est une décision explicite qui dépasse la règle de l'audit, selon laquelle un choix de méthode n'est pas modifié.
- 31/10/2026, **correction de la VaR du Monte-Carlo à 61 €/MWh** : « plutôt 26 000 € » appliquait une erreur du taux national à un revenu de site. Au niveau du site, c'est 24 000 €, et 33 800 € avec les variations historiques du baseload (`docs/audit.md`).
- 31/10/2026, **résultat de l'audit et du pricing V2** : `docs/audit.md` et `docs/pricing.md`. Les calculs sont reproduits ; plusieurs conclusions sont requalifiées ; les documents et le cours sont corrigés. La V1 reste officielle pour son backtest ; pour une livraison en 2027, le prix de référence devient celui de la V2.
- 31/10/2026, **précision sur les sources** : le périmètre annonçait la production et la consommation RTE ; les données officielles viennent d'Energy-Charts (`docs/donnees.md`, H8). Le taux de capture exclut aussi les 84 heures sans consommation de 2015–2025, pour garder les mêmes heures que la part du solaire : la définition ci-dessus était incomplète. Effet négligeable (skill de 0,101 contre 0,099).
