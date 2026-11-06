# Analyse historique

Code : `src/ppa_pricer/analyse/capture.py` (calculs), `graphiques.py` ; script
`scripts/analyser.py` ; sorties dans `reports/analyse/` (CSV mensuel et annuel, 4 graphiques).

## Décisions (29/10/2026)

| Question | Décision | Raison | Alternative écartée |
|---|---|---|---|
| Découpage des mois | mois civil de Paris (données toujours en UTC, seule l'affectation au mois se fait en heure locale) | convention des contrats et produits à terme | mois UTC (décalé d'1 à 2 h aux bords) |
| Heures utilisées | heures où prix, solaire et consommation sont tous connus | baseload et prix capté sur exactement les mêmes heures | chaque grandeur sur ses propres heures |
| Taux de capture annuel | prix capté annuel / baseload annuel | les mois très solaires pèsent plus, comme dans le revenu réel d'un parc | moyenne des 12 taux mensuels |
| Validité | au plus 5 % d'heures calendaires manquantes, sinon NaN | voir `docs/donnees.md` | — |
| Profil horaire | prix horaire / prix moyen de l'année civile | compare des périodes aux niveaux très différents (2022) ; la moyenne du jour peut être proche de 0 au printemps récent | prix / moyenne du jour ; prix bruts |
| Nuage part solaire ↔ TC | 4 panneaux (saisons), couleur = année en une seule teinte | 12 couleurs (une par mois) seraient illisibles | une couleur par mois |

Périodes invalides : janvier 2015 (prix manquants du 1er au 4) ; octobre 2026 et l'année 2026,
incomplets à la date du calcul.

## Résultats principaux

| Année | Baseload (€/MWh) | Prix capté (€/MWh) | Taux de capture | Part du solaire |
|---|---|---|---|---|
| 2015 | 38,5 | 39,3 | 102 % | 1,5 % |
| 2018 | 50,2 | 51,3 | 102 % | 2,1 % |
| 2020 | 32,2 | 29,9 | 93 % | 2,8 % |
| 2022 | 275,8 | 291,5 | 106 % | 4,0 % |
| 2023 | 96,9 | 83,6 | 86 % | 5,1 % |
| 2024 | 58,0 | 39,2 | 68 % | 5,4 % |
| 2025 | 61,1 | 35,9 | 59 % | 6,9 % |

1. **La cannibalisation est forte et récente.** Le taux de capture annuel reste proche de
   100 % jusqu'en 2022, puis chute à 59 % en 2025. Avant 2020, le solaire captait même un
   peu plus que la moyenne : en France, la demande de journée rendait les heures de midi plus
   chères que la nuit.
2. **La relation n'est pas linéaire et dépend de la saison.** Au printemps, le taux de
   capture mensuel tombe à 10–30 % pour une part du solaire de 10–13 % (avril–mai 2025–2026),
   alors qu'en été il reste autour de 50–65 % pour une part comparable. Le printemps combine
   beaucoup de soleil, une consommation modérée et souvent beaucoup d'hydraulique et de
   nucléaire disponibles.
3. **Le creux de midi est apparu après 2022.** Au printemps et en été 2023–2026, le prix vers
   14 h vaut environ 0,3 fois le prix moyen de l'année, contre 0,7 à 0,9 avant 2019.
4. **Les prix négatifs explosent** : environ 10 heures par an avant 2019, 352 en 2024, 513 en
   2025, et déjà 565 sur 2026 au 30/10.

**Conséquence pour le modèle V1** : les années de test récentes (2024–2025) ont des parts de
solaire jamais vues pendant la calibration (≤ 5 % jusqu'en 2023). Le backtest mesurera
justement la capacité du modèle à extrapoler, ce qui est la vraie difficulté d'un pricer de PPA.
