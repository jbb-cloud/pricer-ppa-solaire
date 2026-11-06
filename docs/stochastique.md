# Modèles stochastiques horaires

Feuille de route : M0 (saisonnalité + Ornstein-Uhlenbeck gaussien), M1 (deux vitesses, queues
épaisses, régime de surplus finalement non codé), M2 (conditionnement à la charge résiduelle et croissance du parc),
puis Monte-Carlo et pricing. Chaque étape ne s'ajoute que pour corriger un défaut mesuré à la
précédente.

## Protocole, écrit avant tout résultat (30/10/2026)

**Ce qui a déjà été vu** : l'analyse descriptive, le backtest de la V1 et des mesures sur les prix
horaires de janvier 2024 à août 2026 (mémoire, queues, prix à midi). Ce protocole limite le
*data snooping* sans le supprimer : tout modèle est aussi jugé sur les mois publiés après le
29/10/2026, seul échantillon réellement inconnu.

- **Cible** : le taux de capture mensuel national de la V1 (prix et solaire Energy-Charts), pour
  rester comparable.
- **Walk-forward** : pour chaque année $T$ de 2018 à 2025, calibration sur les deux années civiles
  $T-2$ et $T-1$ (heure de Paris), puis prévision des 12 mois de $T$. 2026 est rapporté à part.
- **Point de prévision** : médiane des trajectoires simulées. **Intervalle** : quantiles 5 % et 95 %.
- **Simulation** : 1 000 trajectoires horaires, graine fixe par année.
- **Échantillon** : mois où le réalisé et toutes les méthodes sont connus.

**Critère de succès pour M1 et M2** (variante réaliste, 2018–2025) :

1. skill score > 0 contre R1 **et** contre le modèle V1 réaliste ;
2. intervalle à 90 % contenant entre 85 % et 95 % des taux de capture mensuels réalisés.

M0 est mesuré de la même façon, **sans verdict** : c'est une référence.

**Diagnostics, sans verdict** : mémoire du résidu (autocorrélations à 1, 24, 48 et 168 h), kurtosis,
part d'heures négatives, prix médian à midi d'avril à août, quantiles 5 % et 95 %, comparés entre
simulations et réalité sur 2019 et 2025. Le test de Diebold-Mariano reste celui de la V1.

## Modèle M0

Pour chaque année civile de la fenêtre, le prix est rapporté au baseload de cette année :

$$y_t = \frac{p_t}{B_{\text{année}(t)}} = s(\text{mois}, \text{heure}, \text{week-end}) + x_t,
\qquad x_{t+1} = \varphi\, x_t + \eta_t,\quad \eta_t \sim \mathcal N(0, \sigma_\eta^2)$$

$x_t$ est un processus d'Ornstein-Uhlenbeck observé au pas d'une heure, soit un AR(1) avec
$\varphi = e^{-\kappa}$. La simulation part de la loi stationnaire. La production $q$ est le profil
moyen par mois et heure de la fenêtre : il ne dépend ni de la météo ni du prix.

| Question | Décision | Raison | Alternative écartée |
|---|---|---|---|
| Échelle | prix rapporté au baseload de chaque année | le baseload annuel va de 32 à 276 €/MWh ; le taux de capture ne dépend plus du niveau ; les scénarios H5 s'y branchent | €/MWh (volatilité de 2022 mélangée aux autres années) |
| Saisonnalité | moyenne par mois × heure × week-end, 576 cases | aucune forme imposée, le creux de midi est conservé | harmoniques de Fourier (nombre à choisir, creux lissé) |
| Fenêtre | 2 ans glissants | compromis entre réactivité et bruit, choisi sans mesure sur les années de test | 1 an (bruité) ; expansive (profil dépassé, comme R2) |

## Ce que M0 ne peut pas faire, écrit avant de le lancer

Le bruit $x_t$ est indépendant de $q$. L'espérance du prix capté ne dépend donc que de $s$ et de $q$ :
la prévision revient presque à reprendre le profil des deux années passées.

- **Précision** : attendue proche de la persistance R1, sans la battre nettement.
- **Intervalles** : attendus **trop étroits**. Avec une demi-vie de l'ordre de 10 h, le bruit se moyenne
  sur un mois, alors que le niveau réel d'un mois varie beaucoup. Couverture attendue nettement sous 85 %.
- **Faits simulés** : autocorrélation à 24 h attendue trop faible, kurtosis proche de 3, pas d'amas de
  prix près de 0 à midi.

Si ces attentes se confirment, elles justifient M1. Si l'une d'elles est fausse, c'est un résultat à
comprendre avant d'aller plus loin.

## Résultats de M0 (30/10/2026)

Rapport : `reports/backtest/m0/rapport.md` ; script : `scripts/backtest_m0.py`. Ce sont des résultats
sans verdict, obtenus sur les années de test : ils orientent M1, mais ne le valident pas.

| Attente écrite avant | Résultat | Attente |
|---|---|---|
| Précision proche de R1 | MAE de 8,1 contre 6,6 pour R1 et 5,9 pour la V1 ; skill de −0,23 contre R1 (p = 0,095) | **fausse** : M0 fait moins bien que R1 |
| Couverture nettement sous 85 % | **41,7 %**, et 16,7 % en 2024 comme en 2025 | confirmée |
| Autocorrélation à 24 h trop faible | simulé 0,25–0,26, réel 0,47–0,55 ; à 48 h : 0,05 contre 0,28–0,31 | confirmée |
| Kurtosis proche de 3 | simulé environ 3, réel 5,75 | confirmée |
| Pas d'amas de prix près de 0 à midi | prix médian d'avril à août 2025 : 0,45 fois le baseload simulé, 0,00 en réalité | confirmée |

**Pourquoi l'attente sur la précision était fausse** : la fenêtre de 2 ans regarde plus loin en arrière que
R1 alors que le taux de capture baisse. Le biais atteint +7,0 points, et 49 des 56 mois hors de l'intervalle
sont sous sa borne basse. Sur les 9 mois valides de 2026, M0 revient au niveau de R1 (14,1 contre 13,9).

**Une part correcte pour une mauvaise raison** : en 2025, la part d'heures négatives simulée (5 %) est proche
du réel (6 %). Le prix médian à midi montre pourtant que la forme de la distribution n'est pas la bonne.

### Ce que M1 doit corriger

1. **Deux vitesses** : une seule demi-vie (12 à 23 h selon la fenêtre) ne reproduit pas la mémoire sur 24 et
   48 h.
2. **Pics** : pour 2018, $\varphi$ tombe à 0,636 contre environ 0,95 ailleurs. Ce n'est pas une erreur de
   calcul : trois heures de novembre 2016 à 874, 850 et 830 €/MWh, avec trois autres, font 46 % de la somme des
   résidus au carré. En tronquant les résidus à 0,1 % et 99,9 %, $\varphi$ vaut 0,906 (test ponctuel). Il faut
   des queues épaisses, et une estimation qui ne dépende pas de quelques heures.
3. **Prix bloqués près de 0** : c'est l'argument pour un régime de surplus.
4. **Incertitude de niveau** : à centre inchangé, il faudrait des intervalles environ 5,5 fois plus larges pour
   couvrir 90 % des mois. Retirer le biais moyen ne suffit pas : la couverture tombe même à 26 %, car l'erreur
   n'est pas un décalage constant et suit le changement de régime (test ponctuel, a posteriori). C'est aussi ce
   que doit traiter M2.

## Modèle M1, défini avant son premier lancement (30/10/2026)

M1 garde la distribution réelle des prix de chaque case et ne modélise que leur dynamique :

1. dans chaque case (mois × heure × week-end, comme M0), le prix normalisé $y_t$ est remplacé par son
   score normal $z_t = \Phi^{-1}\big((r_t - 0{,}5)/n\big)$, avec $r_t$ son rang dans la case et $n$ la taille de
   la case ; les ex æquo reçoivent le même rang moyen ;
2. $z_t$ suit deux Ornstein-Uhlenbeck indépendants :
   $z_t = \sqrt{w}\,a_t + \sqrt{1-w}\,b_t$, où $a$ et $b$ sont des AR(1) de variance 1, de coefficients
   $\varphi_r$ (rapide) et $\varphi_l$ (lent) ;
3. pour simuler, on revient aux prix par la loi empirique de la case : $y_t = F^{-1}_{\text{case}}(\Phi(z_t))$.

On parle de copule gaussienne : la dépendance dans le temps est gaussienne, mais pas la loi des prix.

| Question | Décision | Raison | Alternative écartée |
|---|---|---|---|
| Architecture | loi par case et deux vitesses | dans le prototype en échantillon, reproduit la mémoire, les queues et les prix près de 0 avec 3 paramètres de dynamique ; les rangs ne dépendent pas des pics. Hors échantillon, voir les résultats plus bas | deux OU + Student (pas d'amas près de 0) ; avec un état de Markov (mémoire dégradée dans le prototype, bien plus de paramètres) |
| Estimation | $w$, $\varphi_r$, $\varphi_l$ ajustés aux moindres carrés sur l'autocorrélation de $z$ de 1 à 72 h | simple et testable | maximum de vraisemblance par filtre de Kalman (plus de code pour 3 paramètres) |
| Fenêtre | 2 ans et mêmes cases que M0 ; 1 an rapporté à part, sans verdict | ne change qu'une chose à la fois par rapport à M0 | 1 an ou années récentes pondérées en résultat principal (choisi après avoir vu M0) |
| Extrêmes | aucun prix au-delà de ceux observés dans la case | simple, peu d'effet sur le taux de capture ; à revoir si la VaR le demande | queue de Pareto (trop de paramètres pour 16 à 30 observations par case) |

Prototype en échantillon, calibration 2023–2024, sans comparer de prévision au réalisé (réel entre
parenthèses) : mémoire à 24 h de 0,36 (0,53), à 48 h de 0,27 (0,33), kurtosis de 4,5 (3,95), 3 % d'heures
négatives (3 %), prix médian à midi de 0,44 (0,44). Largeur moyenne de l'intervalle : 15,6 points, contre
11,1 pour M0.

### Attentes écrites avant le premier lancement

- **Critère du protocole : attendu non atteint.** La prévision centrale reste liée au profil passé : skill
  attendu négatif contre R1 et contre la V1. Couverture attendue meilleure que M0 (41,7 %), mais encore
  nettement sous 85 %.
- **Diagnostics** : mémoire et queues nettement meilleures que M0. Sur 2025, prix médian à midi encore trop
  élevé, car le changement de régime n'est pas modélisé.
- **Estimation** : plus de valeur aberrante pour 2018 comme le φ de M0, puisque les rangs ignorent la taille
  des pics.
- **Fenêtre de 1 an** : erreur plus proche de R1, couverture à mesurer.

## Résultats de M1 (30/10/2026)

Rapport : `reports/backtest/m1/rapport.md` ; script : `scripts/backtest_m1.py`.

**Verdict du protocole : critère NON ATTEINT.** Skill de −0,23 contre R1 et de −0,36 contre la V1, couverture
de 35,4 %. Aucun mois publié après le 29/10/2026 n'est encore complet : le test sur données inconnues reste à
faire.

| Attente écrite avant | Résultat | Attente |
|---|---|---|
| Critère non atteint | MAE de 8,1, identique à M0 (Diebold-Mariano contre M0 : p = 0,967) | confirmée |
| Couverture meilleure que M0 | **35,4 % contre 41,7 %** | **fausse** |
| Mémoire nettement meilleure | 2025, à 24 h : 0,36 contre 0,26 (réel 0,55) ; à 48 h : 0,25 contre 0,05 (réel 0,31) ; à 1 h : 0,91 contre 0,95 (réel 0,93) | confirmée à 24 et 48 h |
| Queues nettement meilleures | 2025 : 4,36 contre 2,96 (réel 5,75) ; mais 2019 : 10,78 contre 3,03 (réel 5,75) | **partielle** : dépassement en 2019 |
| Prix à midi encore trop élevé en 2025 | 0,50, réel 0,00 | confirmée |
| Plus de valeur aberrante pour 2018 | demi-vies stables : 2,5 à 5,4 h et 45 à 157 h | confirmée |
| Fenêtre de 1 an plus proche de R1 | MAE de 6,8 contre 6,6 ; couverture de 34,4 % | confirmée |

### Pourquoi la couverture n'augmente pas (tests ponctuels, a posteriori)

- **L'écart avec M0 vient de 2018–2019** : 70,8 % contre 45,8 %. Depuis 2020, les deux couvrent exactement
  31,9 % des mois. Pour 2018, l'intervalle de M0 était élargi (11,2 points contre 5,4) par le pic de novembre
  2016 : sa meilleure couverture cette année-là tient à ce défaut d'estimation.
- **La bonne incertitude n'est pas simulée** : le taux de capture d'un même mois varie en moyenne absolue de 6,6 points
  d'une année à l'autre sur 2018–2025, et de 13,5 points sur 2024–2025. La demi-largeur moyenne de
  l'intervalle à 90 % de M1 n'est que de 4,2 points : ce ne sont pas les mêmes mesures, mais l'écart est clair. M0 et M1 simulent le bruit à l'intérieur d'une année, pas le
  changement de profil d'une année à l'autre.
- **Hypothèse testée et rejetée** : je pensais que le facteur lent, commun à toutes les heures, s'annulait dans
  le ratio. Cela vaut pour 2019 (largeur de 3,9 points avec le lent seul, 6,4 avec le rapide seul), pas pour 2025
  (18,7 contre 11,5).

### Ce que M1 apporte

Sur le baseload du mois rapporté à celui de l'année, l'intervalle à 90 % couvre 45,8 % des réalisés contre
29,2 % pour M0, avec une largeur de 48,8 points contre 28,1 (mesure descriptive, hors protocole). C'est utile
pour le risque de revenu, mais encore loin de 90 %.

M1 sert donc de base dynamique pour la suite, **pas de modèle de prévision du taux de capture**. La prochaine
étape doit modéliser le changement de profil d'une année à l'autre : c'est le rôle de M2.

## Modèle M2, défini avant son premier lancement (30/10/2026)

M2 ajoute à M1 le lien entre le prix et le parc solaire. La charge résiduelle agit sur le **rang** du prix dans
sa case :

$$R_t = \text{conso}_t - \text{solaire}_t - \text{éolien}_t, \qquad x_t = \frac{R_t - \mu_{\text{case}}}{\sigma_{\text{case}}}$$

$$z_t = \lambda\, x_t + \sqrt{1-\lambda^2}\;\varepsilon_t, \qquad y_t = F^{-1}_{\text{case}}\big(\Phi(z_t)\big)$$

$\varepsilon_t$ suit les deux Ornstein-Uhlenbeck de M1. Avec $\lambda = 0$, on retrouve exactement M1. Plus de
solaire fait baisser $R_t$, donc $x_t$, donc le rang : le prix reste dans les valeurs observées de la case.

**Calibration** sur la fenêtre $T-2$, $T-1$ : lois $F_{\text{case}}$, $\mu_{\text{case}}$ et $\sigma_{\text{case}}$ ; $\lambda$ est la
corrélation entre $x_t$ et le score normal $z_t$ ; $w$, $\varphi_r$, $\varphi_l$ sont ajustés sur l'autocorrélation de
$\varepsilon_t = (z_t - \lambda x_t)/\sqrt{1-\lambda^2}$, de 1 à 72 h.

**Simulation** de l'année $T$, pour chaque trajectoire :

1. **Météo** : pour chaque semaine, une année de la fenêtre est tirée. Solaire, éolien et consommation viennent
   ensemble de la même semaine, décalée d'un multiple de 7 jours pour garder les jours de la semaine. Chaque série
   est d'abord divisée par sa moyenne annuelle. Une semaine incomplète est remplacée par la semaine complète la plus
   proche de la même année : aucune valeur n'est inventée, et aucun trou ne devient 0.
2. **Parc** : le solaire est ramené au niveau moyen de $T-1$, multiplié par $(1+g)$. La croissance $g$ est tirée une
   fois par trajectoire parmi les croissances annuelles connues avant $T$.
3. **Éolien et consommation** : niveau moyen de $T-1$, sans croissance.
4. **Prix** : $x'_t$ utilise les $\mu_{\text{case}}$ et $\sigma_{\text{case}}$ de la fenêtre, puis la formule ci-dessus.
5. **Taux de capture** : calculé avec le solaire simulé de la trajectoire, et non plus un profil moyen.

| Question | Décision | Raison | Alternative écartée |
|---|---|---|---|
| Forme | rang conditionné | un seul paramètre de plus que M1 ; reproduit le taux de capture de la fenêtre à 2,3 points près ; la sensibilité au solaire croît seule de −0,8 à −5,4 points pour +10 % | courbe additive (taux de capture de 2,7 % et borne de −132 % en 2027 : aucun plancher) ; M1 + choc annuel (n'explique rien, non prototypé) |
| Variable | charge résiduelle France | déjà disponible, une seule nouveauté à la fois | avec nucléaire disponible (pas de gain net, −68 % à un test de +4 GW, car le nucléaire varie peu dans une case) ; voisins (téléchargement et second changement, à faire plus tard si besoin) |
| Parc | tirage parmi les croissances passées | représente l'incertitude, dépend moins d'une seule année | H4 (taux unique très bruité, rapporté à part, sans verdict) ; aucune croissance (ignore une hausse certaine) |
| Météo | semaines des 2 années de la fenêtre | passe le contrôle : 61,3 contre 64,3 réel | 2015 à $T-1$ (plus de diversité, mais 5 points perdus, sans explication à ce stade) |
| Fenêtre | 2 ans ; 1 an rapporté à part, sans verdict | comme M0 et M1 | — |

**Ce qui a déjà été vu** : les contrôles et prototypes n'ont comparé aucune prévision à un réalisé. Le prototype de
prévision porte sur 2027, qui n'a pas de réalisé. En revanche, les prix à midi et les courbes prix-charge résiduelle par
année couvrent des années de test : M2 est donc conçu après les avoir vues, et seuls les mois publiés après le
29/10/2026 forment un test propre.

**Limites connues** :

- aucune réaction du marché à la hausse du parc (batteries, modulation du nucléaire, écrêtement, déplacement de la
  demande) ;
- la production n'est pas réduite aux heures à prix négatif (H3) ;
- le parc et le prix des pays voisins ne sont pas modélisés ;
- $F_{\text{case}}$ reste celle de la fenêtre : aucun prix hors des valeurs observées ;
- le ratio devient instable quand le prix moyen d'un mois approche 0, et une borne peut alors passer sous 0 ;
- les décalages du solaire Energy-Charts (H8) touchent aussi la charge résiduelle ;
- la disponibilité du nucléaire n'est pas modélisée.

### Attentes écrites avant le premier lancement

- **Critère du protocole : attendu non atteint.** Le skill contre la V1 reste attendu négatif ; contre R1, je n'ai pas
  d'attente ferme, car corriger le biais de M1 aide mais la chute de 2024 reste inexpliquée.
- **Couverture** : attendue nettement au-dessus de M1 (35,4 %), de l'ordre de 60 à 85 %. Rien n'assure qu'elle atteigne
  85 %, car l'intervalle s'élargit surtout dans le régime récent.
- **Biais** : réduit par rapport à M1 (+7,0 points), à moins de 4 points en valeur absolue.
- **2018–2021** : proche de M1, à 2 points d'erreur moyenne près, car la sensibilité au parc y est faible.
- **2024** : erreur encore élevée, car la charge résiduelle de midi n'explique pas la chute du prix.
- **Diagnostics 2025** : prix médian à midi sous celui de M1 (0,50) mais encore au-dessus du réel (0,00) ; mémoire à
  24 h meilleure que M1 (0,36), car la météo apporte sa propre mémoire.
- **Estimation** : $\lambda$ stable, entre 0,45 et 0,65.
- **Sensibilités** : fenêtre de 1 an plus précise que 2 ans, comme pour M1 ; H4 pas plus précise que le tirage.

## Résultats de M2 (30/10/2026)

Rapport : `reports/backtest/m2/rapport.md` ; script : `scripts/backtest_m2.py`.

**Verdict du protocole : critère NON ATTEINT**, à cause de la couverture : 66,7 % au lieu de 85 à 95 %. Le skill est de
+0,10 contre R1 (Diebold-Mariano : p = 0,105, non significatif) et de +0,002 contre la V1 (5,94 contre 5,95 points,
p = 0,985) : c'est une égalité, pas une victoire. M2 bat nettement M1 (8,1 points, p = 0,004). Aucun mois publié après le
29/10/2026 n'est encore complet : le test sur données inconnues reste à faire.

| Attente écrite avant | Résultat | Attente |
|---|---|---|
| Critère non atteint | couverture de 66,7 % | confirmée |
| Skill négatif contre la V1 | +0,002, égalité | **fausse** |
| Couverture de 60 à 85 % | 66,7 % | confirmée |
| Biais sous 4 points | +4,04 points (M1 : +7,0) | **manquée de peu** |
| 2018–2021 proche de M1, à 2 points près | écarts de 0,4 à 1,3 point | confirmée |
| 2024 encore mal prévue | MAE de 13,9 points, couverture de 33,3 % | confirmée |
| Prix médian à midi en 2025 entre M1 et le réel | 0,35 (M1 0,50, réel 0,00) | confirmée |
| Mémoire à 24 h meilleure que M1 en 2025 | 0,36 contre 0,36 (réel 0,55) | **fausse** |
| λ entre 0,45 et 0,65 | 0,48 à 0,63 | confirmée |
| Fenêtre de 1 an plus précise | MAE de 5,7 contre 5,9, mais couverture de 37,5 % | confirmée pour la précision |
| H4 pas plus précise | MAE de 6,0 contre 5,9 | confirmée |

### Où M2 réussit et où il échoue

| Période | MAE M2 | MAE V1 | MAE R1 | Couverture M2 | Largeur M2 |
|---|---|---|---|---|---|
| 2018–2023 | 3,3 | 3,2 | 4,3 | 76,4 % | 9,8 |
| 2024–2025 | 13,9 | 14,3 | 13,5 | 37,5 % | 16,9 |
| 2026 (9 mois, à part) | 15,7 | 15,7 | 13,9 | 44,4 % | 32,0 |

Le gain sur M1 est réel, mais le changement de régime de 2024–2025 reste manqué. Sur 2026, M2 fait moins bien que la
persistance, et la borne basse de mai 2026 descend à −57,8 % : c'est l'instabilité du ratio annoncée dans les limites.

### D'où vient l'erreur (tests ponctuels, a posteriori, sans verdict)

On redonne au modèle ce qu'il ne pouvait pas connaître : la croissance réalisée du parc, ou toute la charge résiduelle
réelle de l'année, heure par heure. Si l'erreur reste, elle ne vient pas de la prévision du solaire français.

| Année | M2 | Parc réalisé | Charge réelle | Biais avec la charge réelle |
|---|---|---|---|---|
| 2018 | 2,6 | 2,6 | 1,5 | −0,3 |
| 2019 | 2,1 | 2,1 | 1,7 | +0,6 |
| 2020 | 4,8 | 4,9 | 3,3 | +1,8 |
| 2021 | 2,9 | 2,9 | 2,4 | +1,4 |
| 2022 | 2,4 | 3,4 | 3,9 | −1,7 |
| 2023 | 4,9 | 4,4 | 4,1 | +2,3 |
| **2024** | **13,9** | **14,8** | **15,5** | **+15,5** |
| 2025 | 13,9 | 9,8 | 13,2 | +10,5 |
| 2026 (9 mois) | 15,7 | 17,3 | 14,1 | −2,3 |

- **2024 ne vient pas de la prévision du solaire français** : même avec la vraie charge résiduelle, M2 reste 15,5 points trop haut. Ce test vaut à travers la forme de M2, elle-même en cause plus bas.
  Candidats à ce stade : le retour du nucléaire (+4 GW à midi), le solaire des voisins, la baisse du baseload (les deux
  premiers sont testés plus bas, sans réussir la règle).
- **2025 vient en partie du parc** : la croissance réalisée (29,9 %) dépasse nettement la médiane tirée (11,6 %). La
  connaître ramène l'erreur de 13,9 à 9,8 points.
- **2026 : en partie juste pour une mauvaise raison.** La médiane tirée (12,5 %) sous-estime la croissance à période
  égale (+19,1 %), ce qui compense un modèle trop sensible : avec la bonne croissance, l'erreur monte à 17,3 points et le
  biais à −6,3 points. Cela va dans le sens de l'absence de réaction du marché, sans le démontrer.

### Prévision 2027, comparaison corrigée le 30/10/2026

Une première version de cette section opposait 34,2 % pour M2 à 53,1 % pour la V1, et concluait que M2 n'était pas utilisable.
**Cette comparaison était fausse** : 34,2 % est une moyenne de taux mensuels pondérée par le solaire national, alors que 53,1 % est
une valeur du pricing, avec les volumes du site et la forme du baseload. À définition égale :

| Définition | M2 | V1 | Persistance |
|---|---|---|---|
| Moyenne des taux mensuels, pondérée par le solaire national | 33,7 % | 41,9 % | 54,8 % |
| Formule du pricing, volumes du site, baseload de 61 €/MWh | 30,0 €/MWh (49,2 %) | 32,4 €/MWh (53,1 %) | 37,1 €/MWh (60,8 %) |

L'écart entre M2 et la V1 est donc d'environ 8 % sur le prix, pas de 19 points. Calculé directement sur les prix horaires simulés à baseload fixé, M2
donne 31,0 €/MWh (31,4 €/MWh avec le baseload aléatoire du Monte-Carlo). Son taux médian de mai vaut −28 % : le prix moyen du mois approche 0 et le ratio n'a plus de sens, ce qui plaide
pour raisonner sur le revenu plutôt que sur le taux mensuel. Le niveau de M2 reste à prendre avec prudence, à cause du test de 2026.

M2 reste un meilleur simulateur que M1, et fait jeu égal avec la V1 tout en donnant des trajectoires horaires. La suite
est de tester ce qui manque à 2024 : le nucléaire et les voisins.

## Test de la chute de 2024, règle écrite avant de le lancer (30/10/2026)

**Question** : quelle variable explique que M2 reste 15,5 points trop haut en 2024, même avec la vraie charge résiduelle
française ? Ce test est lancé après le backtest : il n'a pas de verdict sur M2 et ne change pas le protocole.

**Ce qui a déjà été vu** : les médianes de midi par année (prix, solaire, nucléaire disponible, hydraulique, échanges),
pas les données voisines ni aucun résultat de ce test.

**Méthode** : on garde M2, sa fenêtre $T-2$, $T-1$ et ses lois par case. Pour l'année $T$, on donne les valeurs réelles
heure par heure, sans tirage de météo ni de croissance, et le solaire réel sert au taux de capture. Les trajectoires ne
tirent que $\varepsilon_t$. Toutes les variantes sont réestimées sur la fenêtre :

$$z_t = \sum_i \lambda_i\, x_{i,t} + \sqrt{1-V}\;\varepsilon_t, \qquad V = \text{Var}\Big(\sum_i \lambda_i\, x_{i,t}\Big)$$

Chaque $x_i$ est réduite dans sa case, les $\lambda_i$ viennent d'une régression de $z$ sur les $x_i$.

| Variante | Charge française $R$ | Voisins |
|---|---|---|
| A, référence | conso − solaire − éolien | non |
| B, nucléaire | $R_A$ − nucléaire disponible | non |
| C, hydraulique | $R_A$ − hydraulique au fil de l'eau | non |
| D, France complète | $R_A$ − nucléaire disponible − hydraulique au fil de l'eau | non |
| E, voisins | $R_A$ | un coefficient pour l'Allemagne, un pour l'Espagne |
| F, tout | comme D | comme E |

- **Nucléaire disponible** : maximum de la production sur 7 jours glissants, centré (H14). La fenêtre et l'année $T$ sont
  calculées séparément, pour que la calibration ne voie aucune heure de $T$.
- **Voisins** : charge résiduelle du pays (conso − solaire − éolien), sur les mêmes heures. Les prix voisins ne servent
  qu'à une lecture descriptive de la convergence à midi.
- **Échantillon** : 2018 à 2025, et 2026 à part. Mêmes mois valides que le backtest de M2.

**Règle** : une variante explique 2024 si, sur les mois de 2024, $|\text{biais}| < 5$ points, **et** si son erreur moyenne sur
2018–2023 ne dépasse pas celle de la variante A de plus de 0,5 point. Le résultat de 2025 est rapporté sans condition.

**Ce que le test ne dit pas** : ces valeurs ne sont pas connues à l'avance. Une variante qui réussit explique la chute,
elle n'améliore pas la prévision. Le test ne sépare pas non plus la cause et l'effet entre pays couplés.

## Résultat du test de la chute de 2024 (30/10/2026)

Script : `scripts/tester_chute_2024.py`. Le rapport détaillé n'est pas publié dans cette version : il contient des prix espagnols, dont la licence n'autorise qu'un usage privé.

**Résultat de la règle : aucune variante n'explique 2024.** Le biais reste entre +14,5 et +15,5 points, loin du seuil de
5 points. Les variantes ne dégradent pas 2018–2023, mais ne corrigent pas non plus 2024.

| Variante | Biais 2024 | Erreur 2018–2023 | Règle | Biais 2025 | Erreur 2025 | Biais 2026 (à part) | Erreur 2026 (à part) |
|---|---|---|---|---|---|---|---|
| A, référence | +15,5 | 2,8 | non | +10,5 | 13,0 | −2,3 | 14,3 |
| B, nucléaire | +15,2 | 2,9 | non | +6,9 | 12,8 | −5,4 | 13,0 |
| C, hydraulique | +15,3 | 2,8 | non | +12,7 | 14,5 | +0,8 | 12,5 |
| D, France complète | +15,0 | 3,2 | non | +10,5 | 14,0 | −2,2 | 9,9 |
| E, voisins | +15,3 | 2,7 | non | +7,1 | 8,3 | −12,6 | 20,1 |
| F, tout | +14,5 | 2,7 | non | +5,7 | 7,9 | −12,8 | 18,5 |

### Ce résultat ne prouve pas que ces variables sont hors de cause (analyse après coup)

**Le test pouvait réussir, de justesse.** Je soupçonnais les lois de 2022–2023 de bloquer le modèle, car il ne peut pas
descendre sous leurs valeurs. Cette hypothèse est rejetée comme cause principale : en ramenant les vrais prix de 2024 dans
les bornes de leur case, le biais tombe à +4,5 points, sous le seuil. La marge reste étroite.

**La forme du modèle est probablement en cause.** Sur avril–août 2024, en part du baseload annuel (500 trajectoires ; le rapport `lambda_plages.md` en utilise 1 000, d'où de faibles écarts) :

| Cas | Midi (11–16 h) | Autres heures | Ratio | Biais du taux de capture, avril–août |
|---|---|---|---|---|
| Réel | 0,23 | 0,82 | 0,29 | — |
| A, référence | 0,75 | 1,03 | 0,73 | +26,8 |
| B, nucléaire | 0,56 | 0,82 | 0,68 | +25,7 |
| D, France complète | 0,53 | 0,81 | 0,66 | +25,0 |
| F, tout | 0,57 | 0,88 | 0,65 | +24,2 |

Le nucléaire amène les autres heures au bon niveau (0,82), mais il baisse toutes les heures presque autant, alors qu'en
2024 c'est surtout midi qui s'effondre. Or le taux de capture est un ratio : baisser tout le monde le change à peine. Le
même $\lambda$ s'applique à toutes les heures. C'est mon explication la plus probable à ce stade, testée à la section suivante.

### Ce qu'on peut dire, et ce qu'on ne peut pas dire

- **Voisins : pas de gain stable.** Ils réduisent l'erreur de 2025 (de 13,0 à 8,3 points) mais la dégradent en 2026 (de 14,3
  à 20,1 points).
- **2024 ne ressemble pas à un prix importé d'Allemagne**, lecture descriptive : à midi, d'avril à août, le prix médian français
  tombe à 5,38 €/MWh quand l'allemand reste à 29,00 €/MWh, et l'écart de moins de 1 € passe de 43,7 % à 29,8 % des heures. Cela ne prouve aucune
  cause.
- **La cause de la chute de 2024 reste donc non établie.** Le test ne dit pas que le nucléaire ne joue aucun rôle.
- **Limite de cette section** : ces explications sont trouvées après le résultat, sur l'année qu'elles expliquent.

## Test d'un λ par heure et par saison, défini avant de le lancer (30/10/2026)

**Hypothèse** : le biais de 2024 vient en partie du $\lambda$ unique, qui baisse toutes les heures presque autant. Elle a été
formulée après avoir vu le résultat précédent. Ce test reste donc une explication a posteriori, sans verdict sur M2.

**Définition** : variante D (conso − solaire − éolien − nucléaire disponible − hydraulique au fil de l'eau), mêmes lois,
même fenêtre, mêmes valeurs réelles de l'année, mais un $\lambda$ par couple heure de Paris × saison :

$$z_t = \lambda_{h,s}\, x_t + \sqrt{1-\lambda_{h,s}^2}\;\varepsilon_t, \qquad s \in \{\text{avril–août},\ \text{autres mois}\}$$

Soit 48 coefficients, chacun estimé sur la fenêtre par la corrélation entre $x_t$ et $z_t$, sur au moins 300 heures. La variance de
$z_t$ reste 1 dans chaque plage. La dynamique de $\varepsilon_t$ est réestimée comme dans les variantes précédentes.

| Question | Décision | Raison | Alternative écartée |
|---|---|---|---|
| Découpage | heure × saison | le plus souple : un échec écarte vraiment l'hypothèse, et le test explique sans prévoir | 4 plages × 2 saisons (un échec resterait discutable) ; midi d'été et le reste (test peu puissant) |
| Saison | avril–août | définition des diagnostics du protocole, écrite avant le premier résultat de M0 | autre découpage (choisi après avoir vu 2024) |
| Variables | variante D | seule base française au décalage assez grand à midi ; A demanderait $\lambda = 2{,}78$ | D et F (aucun gain stable des voisins, un essai de plus sur 2024) |

**Règle, inchangée** : biais de 2024 sous 5 points en valeur absolue, et erreur de 2018–2023 sans dégradation de plus de
0,5 point par rapport à la variante A.

**Ce qui a déjà été vu** : les $\lambda$ par plage sur les fenêtres de calibration, sans 2024, et le décalage de midi de la variante D
en 2024, issu du test précédent.

**Attentes écrites avant le lancement** : prix moyen à midi d'avril à août vers 0,37 (D : 0,53 ; réel : 0,23) ; ratio entre midi et
les autres heures d'environ 0,45 (D : 0,66 ; réel : 0,29) ; biais de 2024 en baisse, entre +7 et +13 points, donc **règle
probablement non atteinte** ; 2018–2023 sans dégradation.

**La suite est décidée avant le résultat** : dans tous les cas, M2 ne change pas et on passe au pricing. Une réussite est
notée comme une piste à juger plus tard sur des mois nouveaux, car elle utilise le nucléaire réel, inconnu à l'avance.

## Résultat du test d'un λ par heure et par saison (30/10/2026)

Rapport : `reports/backtest/m2/lambda_plages.md` ; script : `scripts/tester_lambda_plages.py`.

**Résultat de la règle : non atteinte.** Le biais de 2024 passe de +15,0 à +12,0 points, loin du seuil de 5 points. Le $\lambda$ unique
n'est donc pas la seule cause de la chute, et ce test ne la rend pas expliquée.

| Méthode | Biais 2024 | Erreur 2018–2023 | Règle | Biais 2025 | Erreur 2025 | Erreur 2026 (à part) |
|---|---|---|---|---|---|---|
| A, référence | +15,5 | 2,8 | non | +10,5 | 13,0 | 14,3 |
| D, $\lambda$ unique | +15,0 | 3,2 | non | +10,5 | 14,0 | 9,9 |
| D, $\lambda$ par heure × saison | +12,0 | 3,0 | non | +8,4 | 13,1 | 9,9 |

Sur avril–août 2024, en part du baseload annuel :

| Cas | Midi | Autres heures | Ratio | Biais du taux de capture, avril–août | Biais, autres mois |
|---|---|---|---|---|---|
| Réel | 0,23 | 0,82 | 0,29 | — | — |
| D, $\lambda$ unique | 0,54 | 0,81 | 0,67 | +25,1 | +7,8 |
| D, $\lambda$ par heure × saison | 0,48 | 0,87 | 0,54 | +17,5 | +8,1 |

| Attente écrite avant | Résultat | Attente |
|---|---|---|
| Règle non atteinte | biais de +12,0 points | confirmée |
| Biais de 2024 entre +7 et +13 points | +12,0 | confirmée |
| 2018–2023 sans dégradation | 3,0 points (A : 2,8), dans la marge | confirmée |
| Prix à midi vers 0,37 | 0,48 | **fausse** |
| Ratio vers 0,45 | 0,54 | **fausse** |

**Ce qu'on en retient** :

- Le $\lambda$ variable va dans le bon sens : le ratio baisse de 0,67 à 0,54. Le prix de midi reste pourtant le double du réel.
- Mon calcul de faisabilité était trop optimiste : il supposait le même décalage à toutes les heures de midi.
- Les autres mois gardent un biais d'environ +8 points, que ce découpage ne touche pas.
- **La cause de la chute de 2024 reste non établie.** Sept essais ont maintenant visé cette même année : toute nouvelle variante
  conçue à partir d'elle prouverait de moins en moins. Seuls les mois publiés après le 29/10/2026 pourront trancher.

Comme décidé avant le test, M2 ne change pas et le projet passe au pricing, avec ces limites écrites.
