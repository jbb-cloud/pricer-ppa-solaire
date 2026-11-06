# Pricing V1

Code : `src/ppa_pricer/pricing/v1.py`, `src/ppa_pricer/donnees/pvgis.py` ; script
`scripts/pricer_v1.py` ; sorties dans `reports/pricing/v1/` (`rapport.md`, `prix.csv`,
`detail_mensuel.csv`).

Le résultat est une **valeur de l'énergie au spot**, pas un prix de contrat : il ne tient compte ni
des garanties d'origine, ni des coûts d'équilibrage, ni du risque de crédit, ni de la marge.

## La formule

Pour un PPA pay-as-produced d'un an, avec $B_m$ le baseload du mois, $\widehat{TC}_m$ le taux de
capture national prévu et $V_m$ le volume mensuel du site :

$$\text{prix juste} = \frac{\sum_m B_m\,\widehat{TC}_m\,V_m}{\sum_m V_m}$$

## Décisions (30/10/2026)

| Question | Décision | Raison | Alternative écartée |
|---|---|---|---|
| Année de livraison | 2027 | première année complète après les données, horizon d'un an comme le backtest | 2026, déjà presque écoulée |
| Part du solaire | H4 glissante : part de chaque mois sur les 12 derniers mois valides × leur croissance sur 12 mois | H4 demande une année 2026 complète et renvoie NaN ; la version glissante donne exactement H4 sur une année civile | saisir des scénarios de croissance (valeurs arbitraires) ; attendre janvier 2027 (aucun prix d'ici là) |
| Niveaux de baseload | 50 / 61 / 77 €/MWh : baseloads observés en 2018, en 2025 et sur oct. 2025 – sept. 2026 | trois états réels du marché, sans source payante | 12 derniers mois ± 25 % (marge arbitraire, centre tiré par août–septembre 2026) ; cotation publique (source partielle ou datée) |
| Forme mensuelle du baseload | moyenne 2024–2025 du rapport baseload du mois / baseload de l'année, renormalisée sur les heures de 2027 | années récentes complètes, hors crise ; le niveau annuel du scénario reste exact | forme plate ; forme des 12 derniers mois (août–septembre 2026 inhabituels) |
| Site de référence | Montpellier, 1 MWc, plein sud, inclinaison optimale (39°), pertes de 14 % | zone très ensoleillée, configuration courante d'un parc au sol fixe | Bordeaux ; Bourges |
| Volumes | moyenne de chaque mois sur toutes les années PVGIS (2005–2023), mois complets seulement | volume d'une année météo typique, sans parier sur une année | une seule année |
| Taux de capture affiché | modèle V1 et persistance côte à côte, avec les erreurs passées | le backtest ne permet pas d'affirmer que le modèle fait mieux que la persistance | modèle seul |
| Plancher sur le taux prévu | aucun : le taux reste celui de la formule | le taux mensuel le plus bas reste positif, y compris à +40 % de croissance (6,3 %) ; tout plancher serait un nouveau choix de modèle | plancher à 0 |

## Résultats (livraison 2027)

Données jusqu'au 29/10/2026, calibration sur 140 mois valides, $\hat\beta = -6{,}16$, croissance
appliquée de 20,8 %. Volume du site : 1 500 MWh/MWc par an.

| Scénario | Baseload (€/MWh) | Modèle V1 (€/MWh) | Taux implicite | Persistance (€/MWh) | Taux implicite |
|---|---|---|---|---|---|
| Bas | 50 | 26,5 | 53,1 % | 30,4 | 60,8 % |
| Central | 61 | 32,4 | 53,1 % | 37,1 | 60,8 % |
| Haut | 77 | 40,9 | 53,1 % | 46,8 | 60,8 % |

1. **L'écart entre méthodes est du même ordre que les erreurs passées.** Au scénario central, modèle
   et persistance diffèrent de 4,7 €/MWh. Sur 2024–2025, les erreurs annuelles valent 6,3 et
   8,1 €/MWh pour le modèle, 7,9 et 5,7 €/MWh pour la persistance, à ce même baseload.
2. **La croissance du solaire pèse lourd.** À baseload central, le prix du modèle passe de 38,4 €/MWh
   sans croissance à 26,7 €/MWh à +40 %, soit environ 3 €/MWh par tranche de 10 %. Sur la même fenêtre
   d'octobre à août, la croissance vaut 18 % avec Energy-Charts et 24 % avec RTE.
3. **Le profil du site compte.** Avec les volumes nationaux des 12 derniers mois, le prix central
   tomberait à 24,8 €/MWh pour le modèle et 31,2 €/MWh pour la persistance. Le site produit plus en
   hiver (janvier : 6,3 % de son volume contre 3,1 % au national), quand le baseload et le taux de
   capture sont élevés.

## Mesure de l'hypothèse H2

Le rapport compare, pour chaque année complète, le taux réel du site (prix réels, série PVGIS de
l'année) à la formule du pricing (taux national de chaque mois, volumes moyens du site).

- **Résultat** : 0,6 point d'écart absolu moyen sur 2016–2023, 1,7 point au plus. Appliquée mois par
  mois, H2 tient bien sur cette période.
- **Limite principale** : PVGIS s'arrête en 2023. Le contrôle ne couvre pas le régime récent, où les
  prix varient davantage au sein d'une journée : il ne valide pas H2 pour 2027.
- **Horodatage** : les valeurs PVGIS sont à la minute 10 de chaque heure. En les interpolant vers le
  milieu de l'heure (test ponctuel du 30/10/2026, sans script dans le dépôt), le taux du site gagne
  environ 0,5 point : l'effet est faible devant les autres incertitudes.

## Limites

- **Fiabilité de la prévision** : voir le backtest. L'avantage sur la persistance n'est pas
  significatif, et le modèle s'est trompé de 10 à 13 points sur 2024–2025.
- **Horizon de H4 glissante** : les 12 mois de base sont centrés sur début avril 2026, soit environ
  15 mois avant le milieu de 2027, mais on n'applique qu'un an de croissance. La part prévue est
  donc probablement sous-estimée.
- **Baseload** : les scénarios sont des états observés, pas des prévisions ni une courbe à terme.
  Les prix élevés d'août–septembre 2026 (123 et 143 €/MWh), qui pèsent sur le scénario haut, sont identiques à ENTSO-E
  (`docs/donnees.md`), sans que ce soit une preuve indépendante.
- **Données solaires** : les anomalies de calage et de niveau (`docs/donnees.md`) touchent le taux
  de capture, la part du solaire et sa croissance.
- **Hors périmètre** : production payée même à prix négatif (H3), pas d'actualisation sur un an, pas
  de contrat pluriannuel.

## Monte-Carlo de pricing, défini avant son lancement (30/10/2026)

**Question** : pour une livraison en 2027, quelle est la distribution du revenu d'un MWc à Montpellier, et qui porte quel risque
selon le contrat ? Ce n'est toujours pas un prix de contrat : garanties d'origine, équilibrage, crédit et marge restent exclus.

**Horizon** : un an, le seul que le backtest valide. Un PPA dure 10 à 20 ans : ce résultat ne s'y étend pas.

### Simulation, par trajectoire

1. **Prix et solaire national** : M2 tel quel, fenêtre 2024–2025, niveaux des 12 derniers mois valides, croissances passées tirées
   et portées sur l'horizon entre le milieu de ces 12 mois et le milieu de 2027. Le prix normalisé est ramené à une moyenne annuelle de 1.
2. **Volume du site** : une année PVGIS entière tirée parmi 2005–2023, soit 12 volumes mensuels. Dans le mois, la forme est celle du
   solaire national de la trajectoire (H2). Le volume est indépendant de la météo de M2 : corrélation mesurée de 0,04 avec le taux de capture national (H18).
3. **Baseload** : loi lognormale de **moyenne** 61 €/MWh, notre scénario central, qui n'est **pas** une cotation (la cotation 2027 vaut le double, voir la V2), avec $\sigma = 0{,}25$. Il est lié au taux de capture
   annuel de la trajectoire par une copule gaussienne de corrélation 0,65 (H15, H16). Le prix horaire vaut $p_t = B\,y_t$.
4. **Erreur de modèle** : une erreur tirée parmi les 8 erreurs annuelles de M2 en backtest, centrées, retirée du taux de capture (H17).

### Contrats

Chaque flux se calcule par trajectoire. $Q = \sum_t q_t$ est le volume, $R = \sum_t q_t p_t$ le revenu au spot, $H$ le nombre d'heures. Dans tous les cas,
vendeur + acheteur = $R$. Chaque prix est fixé pour que l'espérance du flux de l'acheteur soit nulle, avant erreur de modèle. Cette espérance est prise sous la loi simulée, pas sous une mesure de marché.

| Contrat | Prix juste | Vendeur | Acheteur |
|---|---|---|---|
| Spot, sans contrat | — | $R$ | — |
| Pay-as-produced | $K = E[R]/E[Q]$ | $KQ$ | $R - KQ$ |
| Plancher $K_f$ à 0, 10 et 20 €/MWh | prime $\pi = E[\sum_t q_t (K_f - p_t)^+]/E[Q]$ | $R + \sum_t q_t (K_f - p_t)^+ - \pi Q$ | $\pi Q - \sum_t q_t (K_f - p_t)^+$ |
| Ruban, puissance $V = E[Q]/H$ | $K = E[B]$ | $R - V\sum_t (p_t - K)$ | $V\sum_t (p_t - K)$ |

### Risque

Avec la perte $L = E[X] - X$ : $\text{VaR}_{95} = q_{95}(L)$ et $\text{CVaR}_{95} = E[L \mid L \geq \text{VaR}_{95}]$. **Le chiffre principal inclut l'erreur de modèle**, et la VaR
sans erreur est donnée à côté. Le risque est séparé de deux façons : parts de la variance de $\ln R = \ln Q + \ln B + \ln TC$, et VaR en figeant tour à tour le
volume, le baseload et le taux de capture.

| Question | Décision | Raison | Alternative écartée |
|---|---|---|---|
| Niveau | M2 tel quel, V1 à côté | jeu égal en backtest et écart d'environ 8 % sur le prix, sans mécanisme de plus | recalage sur la V1 (12 paramètres pour un faible écart) |
| Baseload | $\sigma = 0{,}25$, corrélation 0,65 | historique hors crise et lien mesuré, plus prudent que $\sigma = 0{,}17$, mais 4 années sur 10 sortent de l'intervalle (`docs/audit.md`) ; le cas indépendant est rapporté | $\sigma = 0{,}17$ (lecture de nos scénarios, sans donnée de marché) ; trois scénarios (pas de VaR globale, mais rapportés à côté) |
| Erreur de modèle | deux VaR, chiffre principal avec erreur | le backtest couvre 66,7 % au lieu de 90 % | sans erreur (VaR trop faible) |
| Contrats | spot, pay-as-produced, plancher, ruban ; deux côtés | même simulation, et montre qui porte quel risque | un seul contrat |

**Limites** :

- $\sigma$ et la corrélation sont des hypothèses : la corrélation repose sur 10 points et une crise comme 2022 sort de cette loi ;
- la corrélation mesure des variations annuelles, elle est appliquée à des écarts simulés, et elle va de 0,26 à 0,70 selon les années retirées (H16) ;
- l'erreur de modèle ne compte que 8 valeurs ; sur le plancher, elle ne modifie pas la valeur du put (approximation) ;
- la production n'est pas réduite aux heures à prix négatif (H3), ce qui surestime la valeur du plancher pour un parc qui s'arrêterait ;
- mêmes limites que M2 : pas de réaction du marché, voisins et nucléaire non modélisés, décalages du solaire Energy-Charts (H8).

### Contrôle en walk-forward

Pour 2018–2025, on regarde si le taux de capture annuel national réalisé tombe dans l'intervalle à 90 % de M2, sans erreur de modèle puis avec les seules
erreurs connues avant l'année. Huit années ne permettent pas de valider une VaR : c'est un contrôle de bon sens, sans verdict.

### Attentes écrites avant le lancement

Le prototype a déjà donné des ordres de grandeur sur 2027, sans réalisé à comparer. Hors baseload à moyenne 61 et contrôle, les chiffres viennent de lui. L'attente du contrôle porte, elle, sur du réalisé.

- **Prix juste** du pay-as-produced de 30 à 33 €/MWh (V1 : 32,4 ; persistance : 37,1).
- **Spot** : VaR à 95 % d'environ 19 000 €/MWc sans erreur de modèle, et de 1 000 à 3 000 € de plus avec.
- **Pay-as-produced** : le vendeur ne garde que le volume, VaR d'environ 2 000 à 2 500 €/MWc ; l'acheteur porte presque tout le reste.
- **Plancher** : prime de l'ordre de 4 à 6 €/MWh à 0 €/MWh, 8 à 11 à 10 €/MWh, et 13 à 16 à 20 €/MWh.
- **Ruban** : l'acheteur porte le baseload sur tout le volume, avec une VaR environ double de celle de l'acheteur en pay-as-produced. **Le vendeur perd quand le
  baseload monte**, car il vend le prix baseload sur tout son volume alors que sa production ne capte qu'environ la moitié de ce prix.
- **Décomposition** : baseload au-dessus de 70 % de la variance, volume sous 5 %.
- **Contrôle** : 5 à 6 années sur 8 dans l'intervalle sans erreur de modèle, avec 2024 et 2025 sous la borne basse. Avec les erreurs connues avant l'année, 2024 reste
  sous la borne, car aucune grosse erreur n'avait encore été observée.

## Résultats du Monte-Carlo (30/10/2026)

Rapport : `reports/pricing/monte_carlo/rapport.md` ; script : `scripts/pricer_monte_carlo.py`. Livraison 2027, 1 MWc à Montpellier, 1 500 MWh/an.

**Prix juste du pay-as-produced : 31,4 €/MWh** (erreur d'échantillonnage à 90 % : 30,9 à 32,0). À baseload égal, fixé à 61 €/MWh, il vaut **31,0 €/MWh**, contre 32,4 pour la V1 et 37,1 pour la persistance. La V1 n'applique en outre qu'un an de croissance, contre 1,25 an ici : à horizon égal, elle donne 30,7 €/MWh.
**VaR à 95 % du spot : 23 300 €/MWc** pour un revenu moyen de 47 400 €, erreur d'échantillonnage à 90 % de 22 200 à 24 300 €. Ce chiffre est trop faible : voir plus bas.

**Ces chiffres supposent un baseload de 61 €/MWh, soit la moitié de la cotation 2027 : ils ne sont pas un prix pour 2027. Voir le pricing V2 plus bas.**

| Contrat | Côté | Prix juste (€/MWh) | Écart-type (€) | VaR 95 % (€) | CVaR 95 % (€) | Corrélation avec le baseload |
|---|---|---|---|---|---|---|
| Spot, sans contrat | vendeur | — | 16 700 | 23 300 | 26 800 | +0,94 |
| Pay-as-produced | vendeur | 31,4 | 1 300 | 2 900 | 2 900 | +0,17 |
| Pay-as-produced | acheteur | 31,4 | 16 400 | 23 000 | 26 400 | +0,94 |
| Plancher à 0 €/MWh | vendeur | prime de 4,3 | 17 200 | 23 900 | 27 500 | +0,95 |
| Plancher à 10 €/MWh | vendeur | prime de 8,6 | 16 700 | 22 900 | 26 300 | +0,95 |
| Plancher à 20 €/MWh | vendeur | prime de 13,7 | 16 000 | 21 600 | 24 800 | +0,95 |
| Plancher à 0, 10, 20 €/MWh | acheteur | | 1 600 à 2 300 | 3 100 à 4 200 | 3 900 à 4 900 | −0,44 à +0,21 |
| Ruban | vendeur | 60,9 | 9 800 | 17 200 | 24 300 | **−0,81** |
| Ruban | acheteur | 60,9 | 23 600 | 33 800 | 39 000 | +1,00 |

| Attente écrite avant | Résultat | Attente |
|---|---|---|
| Prix juste de 30 à 33 €/MWh | 31,4 | confirmée |
| VaR du spot d'environ 19 000 € sans erreur de modèle | 22 600 € (20 700 € depuis la médiane, 19 300 € dans le prototype) | **fausse** : le prototype mesurait la perte depuis la médiane, et j'ai retenu la moyenne, plus élevée, ce qui explique 1 900 € sur 3 300 €. Le reste vient des tirages et de la loi de baseload à moyenne 61 |
| Erreur de modèle : 1 000 à 3 000 € de plus | +700 € sur ce tirage, +300 € en moyenne sur 30 tirages ; +2 900 € à baseload fixé | **fausse** quand le baseload varie |
| Vendeur en pay-as-produced : 2 000 à 2 500 € | 2 900 € | **manquée de peu** : 19 années PVGIS, la VaR tombe sur la pire année |
| Acheteur en pay-as-produced : presque tout le reste | 23 000 € | confirmée |
| Primes de plancher | 4,3 ; 8,6 ; 13,7 €/MWh | confirmée |
| Acheteur du ruban environ au double du pay-as-produced | 33 800 € contre 23 000 €, soit ×1,5 | **partielle** |
| Le vendeur du ruban perd quand le baseload monte | corrélation de −0,81 | confirmée |
| Baseload au-dessus de 70 % de la variance, volume sous 5 % | baseload 57,3 %, covariances 33,0 %, taux de capture 9,0 %, volume 0,7 % | **partielle** : la corrélation de 0,65 passe dans les covariances |
| Contrôle : 5 à 6 années sur 8 dans l'intervalle ; 2024 et 2025 sous la borne | **2 sur 8** ; 2024 et 2025 sous la borne | **fausse** sur le compte |

### Qui porte quel risque

- **Pay-as-produced** : le revenu du vendeur ne dépend plus que de sa production (2 900 €, chiffre instable : 1 800 à 2 900 € selon la graine et les années PVGIS). L'acheteur prend le prix et le profil, et doit couvrir un volume variable (23 000 €). Son risque suit surtout une baisse du baseload.
- **Ruban** : l'acheteur porte le baseload sur tout le volume (33 800 €). Le vendeur garde un risque du même ordre que le spot, **mais de sens opposé** : il perd quand les prix montent, car il a vendu
  1 500 MWh au baseload alors que sa production n'en capte qu'environ la moitié. Un ruban ne couvre donc pas un producteur solaire : il le surcouvre sur le niveau et lui laisse le profil.
- **Plancher horaire** : il transfère peu de risque annuel. Le plancher à 20 €/MWh a une prime de 13,7 €/MWh, soit environ 20 500 €/an, rendue en espérance : son coût net attendu est nul. Il réduit la VaR sans erreur de modèle de 9 % en moyenne sur 10 graines (de 21 900 à 19 900 €). Le put paie surtout à midi, sur 97 % des jours d'avril à août :
  c'est plus un échange de flux prévisibles qu'une assurance. Le plancher à 0 €/MWh **augmente** même la VaR (23 900 €) : il paie davantage quand le baseload est haut, car les prix négatifs sont multipliés par $B$ dans $p_t = B\,y_t$. Cet effet
  vient au moins en partie de cette forme ; je ne l'ai pas séparé. Une protection du risque annuel passerait plutôt par un plancher sur le prix moyen, non testé.

### La VaR est trop faible : ce que montre le contrôle (analyse après coup)

Le taux de capture annuel national réalisé ne tombe dans l'intervalle à 90 % que **2 années sur 8** (2019 et 2023), et 1 sur 6 avec les erreurs connues avant l'année. La largeur moyenne de l'intervalle est de 9,1 points, pour une erreur moyenne de 9,4 points.

**Une cause établie, une autre non** : H17 mesure l'erreur annuelle avec le baseload et les volumes mensuels réalisés, alors que le Monte-Carlo simule aussi quels mois sont chers. En gardant les vrais taux mensuels mais en prenant la forme du baseload simulée, le taux annuel de 2022 tombe de
105,7 à 89,9 %, et celui de 2018 de 102,1 à 92,8 %. Cette erreur n'était pas dans H17. En revanche, les erreurs de 2024 et 2025 existent déjà à mois réalisés (12,4 et 10,9 points), et leur cause reste non établie. Le backtest du prix à forme connue existe désormais (D1 de `docs/audit.md`) : 5,9 points d'erreur moyenne pour la V1, 13,8 au pire.

| Erreur annuelle (points) | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Écart-type |
|---|---|---|---|---|---|---|---|---|---|
| H17, mois réalisés | 0,0 | 0,9 | 1,2 | 1,4 | −1,1 | 3,3 | 12,4 | 10,9 | 5,1 |
| Sur les trajectoires | −10,0 | −0,4 | 4,4 | 5,9 | −17,5 | 3,1 | 21,8 | 11,9 | 12,2 |

| Erreur de modèle, moyenne sur 30 tirages | VaR 95 % du spot | VaR 95 % à baseload fixé | Taux de capture du site, 5 % à 95 % |
|---|---|---|---|
| Aucune | 22 600 € | 9 000 € | 41,5 à 57,6 % |
| H17 (chiffre fixé d'avance : 23 300 € sur un seul tirage) | 22 900 € | 11 900 € | 38,0 à 60,1 % |
| Mesurée sur les trajectoires | **26 100 €** | **18 700 €** | 30,6 à 72,8 % |

**À retenir, corrigé le 31/10/2026** : le chiffre fixé d'avance reste 23 300 €. La ligne ci-dessus, 26 100 €, applique une erreur du taux **national** à un revenu de **site** : au niveau du site, c'est **24 000 €** (51 % du revenu moyen). Avec les variations historiques du baseload, crise comprise, c'est **33 800 €** (72 %). Ces chiffres viennent après le résultat, et 8 valeurs ne font pas une loi. Tirer l'erreur puis l'ajouter à des trajectoires déjà dispersées compte probablement une partie du bruit deux fois.

## Pricing V2, défini avant son lancement (31/10/2026)

**Pourquoi** : l'audit montre que le baseload de 61 €/MWh vaut la moitié de la cotation 2027, et que la part du solaire seule n'explique pas la chute de 2024. La V2 ancre le niveau sur la courbe à terme, et relie le taux de capture à la part du solaire et au niveau de prix.
Les rapports V1, M0, M1 et M2 ne changent pas. **Le verdict de la V1 reste celui de la V1.**

### Le niveau : la courbe à terme

Fichier versionné `data/marche/courbe_fr_2026-10-29.csv` : clôture du 29/10/2026, relevée sur [Selectra, qui cite EEX](https://entreprises.selectra.info/energie/electricite/cal). Ce n'est pas une lecture directe d'EEX. Le niveau de chaque trimestre vient de la courbe ; dans un trimestre, la forme par mois reste la moyenne 2024–2025 (H19).

### Le taux de capture : le modèle V2

$$TC_m = \alpha_{\text{mois}} + \beta\, S_m + \gamma \ln B_{q(m)} + \delta\, S_m \ln B_{q(m)}$$

$S_m$ est la part du solaire dans la consommation, $B_q$ le baseload du trimestre du mois. Les paramètres sont estimés par moindres carrés sur tous les mois valides antérieurs à la coupure.

| Question | Décision | Raison | Alternative écartée |
|---|---|---|---|
| Courbe | CAL 27 et trimestres | le site produit surtout en T2 et T3, cotés bien sous T1 | CAL seul avec la forme historique |
| Taux central | V1 + niveau × part | meilleure erreur mesurée, 5,2 contre 5,9 | part seule, implicite de la courbe et persistance : affichés comme fourchette |
| Part du solaire | dans la consommation | la part dans la production est pire : 6,9 d'erreur, car le retour du nucléaire la maintient à 4,5 % en 2023 comme en 2024 | part dans la production |
| Parc | 38, 40 et 42 GW à mi-2027 | relie la cannibalisation à une grandeur publique (H20) | croissance H4 |
| Monte-Carlo | refait sur la courbe | le chiffre officiel de VaR ne doit pas reposer sur un niveau connu pour être faux | laissé à 61 €/MWh |

**Parc solaire (H20)** : 34,0 GW au 30/06/2026, dont 3,0 GW raccordés au premier semestre, soit 31,0 GW fin 2025 ([SDES](https://www.statistiques.developpement-durable.gouv.fr/tableau-de-bord-solaire-photovoltaique-deuxieme-trimestre-2026)). Les 12 mois de base, d'octobre 2025 à septembre 2026, sont centrés sur le 01/04/2026, soit 32,5 GW par interpolation. À mi-2027 : **37,6 GW** au rythme de la PPE3, qui vise [48 GW en 2030](https://questions.assemblee-nationale.fr/dyn/17/questions/QANR5L17QE12722) (3,6 GW/an), **40 GW** au rythme récent (6 GW/an), **42 GW** si le rythme accélère (8 GW/an). La part de chaque mois est celle de la base × (parc de mi-2027 / 32,5). Le facteur de charge est supposé constant.

### Le backtest de la V2

Mêmes années (2018–2025), même walk-forward et mêmes mois que la V1, avec la part prévue par H4, car les scénarios de parc n'existent pas dans le passé.

Comme aucun historique de cotations n'est disponible, deux variantes encadrent la réalité :

- **Niveau réalisé** : le niveau du trimestre testé est donné, comme une cotation parfaite. C'est le résultat principal, mais il est **favorable** par construction.
- **Niveau persistant** : le niveau du même trimestre de l'année précédente, sans information sur l'année testée.

**Critère** : skill > 0 contre R1 et contre la V1, avec le niveau réalisé. **Cette forme a été choisie après avoir vu les années de test** : ce critère ne la valide pas. Seuls les mois publiés après le 29/10/2026 forment un test propre. Les paramètres sont donc gelés dans `reports/backtest/v2/parametres_geles.csv`.

### Le Monte-Carlo sur la courbe

Même moteur et mêmes contrats que le Monte-Carlo à 61 €/MWh, avec ces changements :

1. **Baseload** : lognormal de moyenne CAL 27, soit 122,61 €/MWh, $\sigma = 0{,}25$, corrélation de 0,65 avec le taux de capture.
2. **Forme** : le prix normalisé de chaque trimestre est multiplié par une constante, pour que sa moyenne sur les trajectoires égale T/CAL. La dispersion entre trajectoires reste celle de M2.
3. **Parc** : chaque trajectoire tire l'un des trois scénarios, avec la même probabilité.
4. **Erreur de modèle** : celle du contrôle D1 de l'audit, mesurée au niveau du site et à forme connue (écart-type de 7,9 points), et non plus H17. Ce choix est fait après avoir vu que H17 était trop faible.

Le **prix central vient du modèle V2**. Le Monte-Carlo sert à mesurer le **risque** : son prix juste, issu de M2, est affiché à côté.

**Limites** :

- le niveau réalisé du backtest est plus favorable qu'une vraie cotation, qui peut se tromper ;
- une cotation bouge vite : CAL 27 est passé d'environ 94 à 123 €/MWh en octobre 2026, selon les relevés de Selectra, et le prix V2 la suit ;
- la cotation d'un prix à terme n'est pas une espérance physique : elle peut contenir une prime de risque ;
- $p_t = B\,y_t$ multiplie les prix négatifs par $B$, et le problème s'aggrave à 122,61 €/MWh : la prime du plancher à 0 €/MWh est donc surestimée. Une sensibilité garde les prix négatifs à l'échelle de 61 €/MWh ;
- l'erreur de modèle s'ajoute à des trajectoires déjà dispersées, ce qui compte probablement une partie du bruit deux fois ;
- le lien entre niveau et taux de capture n'est pas causal : le baseload contient lui-même le prix de midi ;
- l'horizon reste d'un an, et le niveau de 2027 ne vaut pas pour la suite : CAL 28 et CAL 29 cotent 69,89 et 62,48 €/MWh.

### Attentes écrites avant le lancement

Les prototypes ont déjà donné des ordres de grandeur, sans réalisé pour 2027. Les chiffres de backtest ont été vus sur un prototype.

- **Backtest, niveau réalisé** : erreur moyenne de 5,0 à 5,4 points, skill > 0 contre R1 et contre la V1, biais de 2024 d'environ +6 points, et de 2025 d'environ +12 points.
- **Backtest, niveau persistant** : l'essentiel du gain disparaît, avec une erreur moyenne de 5,6 à 6,2 points.
- **Significativité** : le gain sur la V1 n'est pas significatif (p > 0,05) ; il reste positif dans au moins 6 retraits d'année sur 8.
- **Prix 2027** : environ 74, 70 et 67 €/MWh pour 38, 40 et 42 GW. Fourchette à 40 GW : part seule 63, persistance 74, implicite de la courbe 82.
- **Monte-Carlo** : prix juste de 58 à 72 €/MWh ; VaR du spot de 40 000 à 55 000 €/MWc, soit de 45 à 60 % du revenu moyen ; baseload toujours premier risque.
- **Plancher** : prime à 0 €/MWh bien plus élevée qu'à 61 €/MWh, puis nettement plus basse avec les prix négatifs à l'échelle de 61 €/MWh.

## Résultats du pricing V2 (31/10/2026)

Rapports : `reports/pricing/v2/rapport.md` et `reports/backtest/v2/rapport.md` ; scripts : `scripts/pricer_v2.py` et `scripts/backtest_v2.py`.

**Prix central du pay-as-produced pour 2027 : 70,6 €/MWh**, soit 57,6 % de CAL 27 et environ 105 900 €/MWc par an, pour un parc de 40 GW. **Fourchette de 60 à 84 €/MWh** selon le parc et la méthode. Ce n'est toujours pas un prix de contrat : garanties d'origine, équilibrage, crédit et marge restent exclus.

| Parc à mi-2027 | **V2 : part et niveau** | V1 : part seule | Persistance | Implicite de la courbe en T2 et T3 |
|---|---|---|---|---|
| 37,6 GW, rythme de la PPE3 | **74,6** | 68,1 | 74,0 | 84,0 |
| 40 GW, rythme récent | **70,6** | 63,6 | 74,0 | 83,0 |
| 42 GW, accélération | **67,3** | 59,9 | 74,0 | 82,2 |

| Backtest 2018–2025 | MAE | Biais | Skill vs R1 | Skill vs V1 | 2024 | 2025 | 2026 (à part) |
|---|---|---|---|---|---|---|---|
| V2, niveau réalisé | 5,2 | +2,4 | +0,22 | +0,13 | 7,1 | 13,1 | 12,5 |
| V2, niveau persistant | 5,3 | +2,7 | +0,19 | +0,10 | 10,0 | 12,9 | 20,1 |
| V1 | 5,9 | +3,3 | +0,10 | — | 11,5 | 17,1 | 15,7 |
| R1 | 6,6 | +4,8 | — | −0,11 | 14,5 | 12,5 | 13,9 |

| Attente écrite avant | Résultat | Attente |
|---|---|---|
| Niveau réalisé : erreur de 5,0 à 5,4, biais de 2024 vers +6, de 2025 vers +12 | 5,2 ; +6,3 ; +12,4 (déjà vu sur le prototype) | confirmée |
| Niveau persistant : l'essentiel du gain disparaît, de 5,6 à 6,2 | **5,3** ; skill de +0,10 contre la V1 | **fausse** sur 2018–2025. Le gain ne vient donc pas surtout de la connaissance du niveau. En 2026, en revanche, connaître le niveau compte : 12,5 contre 20,1 |
| Gain sur la V1 non significatif, positif dans au moins 6 retraits sur 8 | p = 0,314 ; 8 retraits sur 8 ; intervalle à 90 % de −0,14 à +0,26 | confirmée |
| Prix de 74 / 70 / 67 ; 63, 74 et 82 à 40 GW | 74,6 / 70,6 / 67,3 ; 63,6, 74,0 et 83,0 | confirmée |
| Monte-Carlo : prix juste de 58 à 72 ; VaR de 40 000 à 55 000 € et de 45 à 60 % du revenu ; baseload premier risque | 59,4 ; 44 500 € ; 50 % ; 77 % de la variance | confirmée |
| Prime du plancher à 0 €/MWh bien plus élevée, puis plus basse à l'échelle de 61 €/MWh | 11,3, puis 5,8 €/MWh (4,3 à 61 €/MWh) | confirmée |

**Risque** (Monte-Carlo sur la courbe, avec l'erreur de modèle du site) :

| Contrat | Côté | VaR 95 % (€/MWc) | Corrélation avec le baseload |
|---|---|---|---|
| Spot, sans contrat | vendeur | 44 500 (41 400 à 44 800 selon la graine) | +0,98 |
| Pay-as-produced | vendeur | 5 400 (3 400 à 5 500) | +0,22 |
| Pay-as-produced | acheteur | 43 600 | +0,98 |
| Ruban | vendeur | 45 100 | −0,95 |
| Ruban | acheteur | 68 600 | +1,00, mécanique |

Le revenu moyen du Monte-Carlo est de 89 100 €/MWc. La VaR va de 37 900 à 64 000 € selon les hypothèses de baseload, soit de 43 à 72 % du revenu moyen. **Elle reste un ordre de grandeur.**

**Ce qu'il faut retenir** :

- **Le niveau est passé devant tout** : le prix double avec la cotation. CAL 27 est passé d'environ 94 à 123 €/MWh en octobre, soit de 50,5 à 70,6 €/MWh sur le prix V2.
- **La moitié du revenu vient de T1** : 50 % du revenu pour 22 % du volume, car T1 est coté 194 €/MWh. Le prix dépend donc fortement d'une seule cotation d'hiver.
- **Le niveau de 2027 ne vaut pas pour un PPA long** : à CAL 28 et CAL 29, le prix V2 tombe à 34,2 et 29,5 €/MWh. Pour un contrat de 10 ans, cette différence compte plus que tout le reste.
- **Le désaccord sur le taux d'été reste large** : 30 % pour V2, 54 % implicites de la courbe, et de 34 à 55 % réalisés sur les 12 derniers mois. C'est ce qui sépare 70 de 83 €/MWh.
- **Le Monte-Carlo est plus bas que V2** : 59,4 contre 70,6 €/MWh, car M2 hérite de la loi de prix de 2024–2025, un régime de baseload bien plus bas. Il sert à mesurer le risque, pas le niveau.
- **Le plancher n'est pas crédible à ce niveau** : 896 heures négatives simulées contre 583 sur les 12 derniers mois, à −35,8 €/MWh contre −11,5 €/MWh. Toutes les VaR avec plancher dépassent celle du spot, ce qui vient de cet artefact. Ne pas utiliser ces primes.
- **Les paramètres de V2 sont instables** : β va de −25,2 à −6,6, puis −13,9 selon la calibration, et δ de +5,33 à +0,45, puis +1,79. Ce modèle reste une piste.
- **La chute de 2024 reste mal prévue** : +6,3 points de biais, même avec le vrai niveau.
