# Données : sources et choix de traitement

## Prix day-ahead France

- **Source** : API Energy-Charts (Fraunhofer ISE), `https://api.energy-charts.info/price?bzn=FR`.
  Les données viennent de SMARD (Bundesnetzagentur), sous licence CC BY 4.0 : à citer dans le
  README et les graphiques. Pas de jeton nécessaire. ENTSO-E servira de source de contrôle.
- **Format brut** : JSON, horodatages en secondes Unix (UTC) = début de la période de
  livraison ; un prix absent vaut `null`.
- **Code** : `src/ppa_pricer/donnees/energy_charts.py`, `base.py`, `controles.py` ; script
  `scripts/telecharger_donnees.py` ; rapport `reports/donnees/qualite_prix_day_ahead_FR.md`.
- **Constat** : 95 heures sans prix, toutes du 1er au 4 janvier 2015 (heure de Paris) ; aucun
  trou, doublon ni anomalie de changement d'heure ensuite.

### Décisions (29/10/2026)

| Question | Décision | Raison | Alternative écartée |
|---|---|---|---|
| Découpage du téléchargement | un fichier JSON brut par année civile UTC dans `data/raw/energy_charts/` | une année passée ne se re-télécharge jamais ; le brut est conservé pour relire sans re-télécharger | une seule requête (tout re-télécharger, risque d'expiration) |
| Durée d'un point (60 ou 15 min) | déduite de la date : 15 min à partir du 30/09/2025 22:00 UTC | un trou dans la source ne fausse pas la durée | écart au point suivant (une heure manquante ferait un point de 2 h) |
| Agrégation à l'heure (V1) | moyenne simple des 4 quarts d'heure | prix d'un produit à puissance constante sur l'heure | — |
| Heure dont un quart d'heure manque | NaN | ne pas fabriquer de prix sur une heure incomplète | moyenne des quarts présents (biais si le manquant est un pic) |
| Stockage | résolution d'origine en SQLite, agrégation à la lecture | l'agrégation est un choix de modèle, modifiable sans re-télécharger | stocker directement l'horaire |
| Prix absent | NaN (NULL en base), jamais 0 | règle du projet | — |

## Production solaire et consommation France

- **Source** : API Energy-Charts, `https://api.energy-charts.info/public_power?country=fr`
  (données ENTSO-E, fournies par RTE), CC BY 4.0. On garde « Solar » et « Load » ; les autres
  filières restent dans le JSON brut. RTE éCO2mix pourra servir de contrôle.
- **Format brut** : puissances moyennes en MW par période ; pas horaire jusqu'au 31/12/2025,
  15 minutes à partir du 1er janvier 2026 00:00 heure de Paris (31/12/2025 23:00 UTC, constaté
  dans les données).
- **Code** : `lire_production_brut` dans `energy_charts.py` ; table `production_conso` ;
  rapport `reports/donnees/qualite_production_conso_FR.md`.
- **Constat** : 0 à 26 heures manquantes par an et par colonne, éparpillées ; aucun trou dans
  la grille. Ordres de grandeur cohérents : solaire moyen ≈ 0,8 GW en 2015 (≈ 7 TWh/an) et
  ≈ 3,4 GW en 2025 (≈ 30 TWh/an). Ce constat ne porte que sur la grille temporelle ; le calage
  physique des valeurs a des anomalies, voir « Contrôle de calage du solaire ».

### Décisions (29/10/2026)

| Question | Décision | Raison | Alternative écartée |
|---|---|---|---|
| Source | Energy-Charts | même chaîne que les prix, données depuis 2015 | RTE éCO2mix (deuxième chaîne à écrire) |
| Agrégation à l'heure | même règle que les prix : moyenne des 4 quarts d'heure, NaN si un manque | une puissance moyenne en MW sur l'heure = énergie en MWh ; cohérence avec les prix | moyenne des quarts présents |
| Solaire à 0 la nuit | vrai zéro, conservé | production réellement nulle ; seuls les `null` sont des manquants | — |
| Part du solaire | production solaire / consommation | mesure standard de pénétration, liée à la formation du prix | production solaire / production totale |
| Mois valide pour le taux de capture | au plus 5 % d'heures manquantes | tolère des trous isolés ; janvier 2015 (13 % sans prix) est exclu | aucun trou toléré ; tout garder |

## Profil de production d'un site

- **Source** : API PVGIS 5.3 de la Commission européenne, `https://re.jrc.ec.europa.eu/api/v5_3/seriescalc`,
  base d'ensoleillement SARAH3, 2005–2023. Pas de jeton nécessaire.
- **Format brut** : JSON horaire, puissance `P` en W, horodatage UTC à la minute 10 de chaque heure.
  Conservé dans `data/raw/pvgis/` (15,8 Mo pour un site).
- **Code** : `src/ppa_pricer/donnees/pvgis.py`. La série n'est pas chargée en base : elle sert aux
  volumes du pricing (`docs/pricing.md`).
- **Constat** : 166 536 heures, sans doublon ni valeur manquante ; 1 409 à 1 554 MWh/MWc selon
  l'année pour Montpellier.

## Contrôle de calage du solaire

- **Pourquoi** : les contrôles de grille vérifient que chaque heure existe une seule fois, pas
  que la valeur de cette heure est plausible. Une série décalée d'une heure y passe sans
  anomalie, alors qu'elle change les prix associés à la production. Or le midi solaire ne bouge
  pas d'une année à l'autre : en UTC, l'heure moyenne de production d'un mois doit rester proche
  de celle du même mois des autres années.
- **Code** : `controler_calage_solaire` dans `controles.py` ; section du rapport
  `reports/donnees/qualite_production_conso_FR.md`, régénérable sans téléchargement ni écriture
  en base avec `scripts/telecharger_donnees.py --sans-telechargement`.
- **Constat (30/10/2026)** : sur 142 mois, 20 ont un calage suspect et 13 une production de nuit.

| Période | Écart à la médiane du même mois | Lecture |
|---|---|---|
| 2015–2022 | au plus 0,12 h | stable, sert à situer le seuil |
| juillet 2023 | +0,21 h | décalage visible surtout sur une semaine |
| sept. 2023 – mars 2024 | +0,69 à +0,95 h | environ une heure trop tard, retour net en avril 2024 ; **déjà dans ENTSO-E** |
| janv. – déc. 2025 | +0,26 à +0,42 h | **Energy-Charts garde le premier quart d'heure** de chaque heure |
| Nuit (21 h – 03 h UTC) | 0,13 à 1,39 % de l'énergie du mois | juil.–août 2018 et 2019, juil.–sept. 2020, juin–juil. 2023, 2025 et 2026 |

- **Comparaison à ENTSO-E et RTE** : voir la section suivante, qui remplace le test ponctuel du 30/10/2026 (solaire RTE sur 2022–2026 seulement).

### Décisions (30/10/2026)

| Question | Décision | Raison | Alternative écartée |
|---|---|---|---|
| Référence de l'heure moyenne | médiane du même mois sur toute la série | aucune période choisie à la main, résiste tant que les années décalées sont minoritaires | midi solaire théorique (plus de code, hypothèse sur la longitude du parc) ; années 2015–2022 (choisies après avoir vu l'anomalie) |
| Seuil de calage | écart de plus de 0,2 h | marge au-dessus du maximum de 0,12 h de 2015–2022, signale juillet 2023 | 0,25 h (manque juillet 2023) ; 0,15 h (proche du bruit normal) |
| Seuil de nuit | plus de 0,1 % de l'énergie du mois, de 21 h à 03 h UTC | ignore les traces sans effet sur le taux de capture | toute valeur non nulle |
| Traitement | signaler sans corriger ; verdict V1 calculé sur les données telles que publiées | même principe que les autres contrôles ; changer les données après avoir vu les résultats fausserait le protocole | recaler la série ; passer à RTE dès la V1 |

## Comparaison à ENTSO-E et RTE (30/10/2026)

Rapport : `reports/donnees/comparaison_sources_FR.md` ; script : `scripts/comparer_sources.py`. Fichiers ENTSO-E dans `data/raw/entsoe/` (36 fichiers, 50 Mo, non versionnés, hors de la base).

**Résultat de la règle fixée avant de voir les données** : 8 mois signalés sur 20 sont à moins de 0,1 h d'ENTSO-E, sous le seuil de 16 : « le décalage apparaît après ENTSO-E ».
**Cette conclusion est trop courte** : la règle supposait une seule cause, et ces 20 mois en mêlent deux. Ce qui suit est écrit après son résultat.

| Anomalie | Mois | Ce qui est établi | Origine |
|---|---|---|---|
| Premier quart d'heure | 2025, et dès fin 2024 pour le solaire | ENTSO-E passe au quart d'heure le 19/12/2024 pour le solaire et le 31/12/2024 pour la consommation, mais les fichiers Energy-Charts restent horaires jusqu'à fin 2025. Sur 2025, **100,00 % de ses valeurs horaires égalent le premier quart d'heure d'ENTSO-E**, contre 39,14 % pour la moyenne de l'heure pour le solaire et 0,01 % pour la consommation | **Energy-Charts** |
| Décalage de 2023–2024 | juil. 2023, sept. 2023 – mars 2024 | Energy-Charts et ENTSO-E sont identiques (écart de 0,00 h), RTE s'en écarte. D'octobre à décembre 2023, la corrélation avec RTE passe de 0,95–0,96 à 0,99 avec 1 h de retard | **ENTSO-E ou en amont** |

- **Pourquoi 0,36 h en 2025** : une valeur du premier quart d'heure est centrée sur h + 7,5 min au lieu de h + 30 min, soit 0,375 h d'écart apparent. L'effet réel est faible : énergie à 0,998 de la moyenne, et écart absolu moyen de 356 MW sur le solaire et de 690 MW sur la consommation.
- **Production de nuit** : 13 mois chez Energy-Charts comme chez ENTSO-E, aucun chez RTE. Elle vient donc aussi d'ENTSO-E ou d'en amont.
- **Prix** : Energy-Charts et ENTSO-E sont identiques à 0,000 €/MWh sur toutes les heures communes, y compris août, septembre et octobre 2026 (122,80 ; 143,30 ; 163,43 €/MWh, octobre incomplet). Ces niveaux sont donc bien ceux publiés. Ce n'est pas une preuve indépendante, car les deux sources remontent aux mêmes publications.
- **Consommation** : identique à ENTSO-E sauf en 2025 (premier quart d'heure), et de 0,976 à 0,996 fois celle de RTE selon les années.
- **Niveau du solaire** : Energy-Charts égale ENTSO-E, mais il vaut de 0,89 à 1,00 fois RTE selon les années. La cause de cet écart n'est pas établie.

| Rejeu, sensibilité | MAE modèle | Skill vs R1 / vs R2 | p vs R1 | Taux 2023 / 2024 / 2025 | Prix 2027 (€/MWh) |
|---|---|---|---|---|---|
| Officiel (Energy-Charts) | 5,95 | +0,10 / +0,47 | 0,449 | 86,29 / 67,65 / 58,81 | 32,4 |
| Solaire ENTSO-E | 5,92 | +0,10 / +0,47 | 0,459 | 86,29 / 67,65 / 59,06 | 32,5 |
| Tout ENTSO-E | 5,92 | +0,10 / +0,47 | 0,459 | 86,29 / 67,65 / 59,06 | 33,1 |
| Solaire RTE | 5,95 | +0,12 / +0,48 | 0,284 | 84,57 / 64,84 / 56,04 | 29,9 |

**Conclusions** :

- le verdict de la V1 tient dans les quatre variantes ;
- corriger le premier quart d'heure de 2025 sur le solaire ne pèse presque rien (+0,25 point sur 2025, +0,1 €/MWh). Passer aussi la consommation et les prix à ENTSO-E ajoute 0,7 €/MWh au total, surtout par la consommation ;
- le choix de RTE pèse davantage (2,8 points sur 2025, 2,5 €/MWh sur le prix). Sur 2025, caler Energy-Charts sur les niveaux mensuels de RTE fait passer de 58,80 à 57,73 % : 1,1 point vient des niveaux entre les mois, et 1,7 point de la forme dans le mois. La cause reste inexpliquée ;
- **RTE n'est pas une vérité absolue** : ses valeurs de :00 et :30 forment une moyenne centrée sur h + 15 min, ce qui expliquerait environ 0,25 h de son écart habituel de 0,33 h avec Energy-Charts (explication probable, non vérifiée).

Rien ne change dans les données officielles (H8). Le choix de la source reste reporté à la V2.

## Allemagne et Espagne

Production et prix day-ahead, 2015–2026, Energy-Charts, téléchargés le 30/10/2026 par `scripts/telecharger_voisins.py` (49 fichiers
dans `data/raw/energy_charts/`, non versionnés, hors de la base). Usage limité au test de la chute de 2024.

- **Marché allemand** : DE-AT-LU jusqu'au 30/09/2018, puis DE-LU. Les deux zones sont réunies pour la lecture des prix.
- **Pas de temps** : Allemagne au quart d'heure dès 2015 ; Espagne au quart d'heure à partir de la toute fin de 2022. Le pas
  est donc constaté dans les fichiers (`charger_filiere`), et non déduit d'une date comme pour la France.
- **Charge résiduelle** : la série publiée égale exactement conso − solaire − éolien sur les deux pays (écart nul).
- **Trous** : Allemagne, 1 heure en 2026 ; Espagne, 27 heures en 2015, 36 en 2025 et au plus 3 les autres années. Ils restent NaN.
- **Non contrôlé** : le calage horaire du solaire de ces deux pays n'a pas été testé comme celui de la France.
