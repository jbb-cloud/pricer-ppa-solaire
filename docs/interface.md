# Interface : conception de l'appli de démonstration

> **Version publique.** Ce dépôt est la vitrine publique du projet : code, tests, documentation et résultats, **sans les
> données** dont la licence n'est pas confirmée (`data/appli/`, la courbe à terme, le rapport tiré des prix espagnols).
> Le développement continue dans un dépôt privé. Voir [`data/README.md`](../data/README.md) pour reconstruire les données.

Objectif : qu'un recruteur ouvre un lien et utilise le pricer sans rien installer, puis comprenne
d'où vient le prix. Conception validée le 04/11/2026 ; rien n'est encore codé.

## Choix retenus

| Sujet | Choix | Pourquoi | Écarté |
|---|---|---|---|
| Outil | Streamlit, hébergé sur Streamlit Community Cloud depuis `jbb-cloud/ppa-pricer`, **dépôt privé et appli privée** : seuls les invités par adresse e-mail l'ouvrent (décidé le 04/11/2026, voir Licences) | Python pur : l'appli appelle directement le paquet, sans API ni frontend séparés | React + API (beaucoup de travail pour une démo) |
| Périmètre | Quatre pages : pricer, cannibalisation, backtest, méthode et limites | Le recruteur voit le problème, le prix, puis la preuve que le modèle a été testé | Pricer seul |
| Calcul | En direct | Mesuré le 04/11/2026 : chargement 0,5 s, calage V2 0,8 s, prix V2 instantané, Monte-Carlo de 1 000 trajectoires en 0,7 s | Résultats précalculés |
| Partage du calcul | Une fonction du paquet, appelée par `scripts/pricer_v2.py` et par l'appli | Un seul calcul ; un test vérifie qu'elle redonne le rapport (70,6 €/MWh au centre) | Logique recopiée dans l'appli |
| Site | API PVGIS en direct (lieu, inclinaison, orientation), mise en cache ; Montpellier livré en secours | Lieu libre, API gratuite sans clé. Retenu : 2014–2023 pour un nouveau site (10 années), inclinaison optimale par défaut, orientation réglable, une liste de 16 villes ou des coordonnées. Mesuré le 04/11/2026 : 13 s pour Lyon le matin, puis 27 à 28 s pour Lille et Lyon l'après-midi (le temps dépend surtout du serveur PVGIS) ; Montpellier livré : 0,3 s. Un lieu en mer est refusé par PVGIS et l'appli retombe sur Montpellier avec un avertissement. Pour éviter cette attente, les 16 villes sont précalculées (plein sud, inclinaison optimale, toutes les années) par `scripts/precalculer_villes.py` dans `data/appli/villes/` ; seuls les réglages personnalisés appellent PVGIS | Villes précalculées |
| Données de l'appli | Dans le dépôt privé, `data/appli/` : une table horaire France compacte (prix, solaire, consommation, éolien, depuis 2015), produite par un script depuis la base | L'appli tourne sans les 185 Mo de données brutes | Agrégats seuls (plus de Monte-Carlo) ; téléchargement au démarrage (lent, fragile) |
| Backtest | Lecture des CSV de `reports/` avec graphiques interactifs | Instantané, mêmes chiffres que les rapports | Walk-forward recalculé dans l'appli (M1 et M2 trop lents) |
| Langues | Sélecteur FR/EN dans l'appli, textes dans un seul fichier ; `README.md` en anglais, `README.fr.md` en français | GitHub affiche le README anglais ; code, docs et cours restent en français | Tout traduire |

## Réglages du pricer

- **Site** : lieu, inclinaison, orientation, puissance en MWc (volumes proportionnels à la puissance).
- **Contrat** : pay-as-produced, ruban, plancher et son niveau ; côté acheteur ou vendeur.
- **Parc solaire mi-2027** : curseur en GW, par défaut 40 GW (aujourd'hui 3 scénarios fixes : 37,6 / 40 / 42).
- **Avancé** : baseload CAL 27 (par défaut la cotation du 29/10/2026, 122,61 €/MWh, trimestres mis à l'échelle comme dans la sensibilité du rapport), σ et corrélation du baseload, nombre de trajectoires.

Sorties : prix juste (€/MWh), taux de capture, revenu annuel, distribution du flux, VaR et CVaR à 95 %, parts de variance (baseload, taux de capture, volume), détail mensuel. Un bandeau rappelle que c'est une valeur de l'énergie au spot, pas un prix de contrat (pas de garanties d'origine, d'équilibrage, de crédit ni de marge).

## Gardé pour plus tard

- **Incertitude sur le parc autour du curseur** (décidé le 04/11/2026). Pour l'instant, toutes les trajectoires du Monte-Carlo de l'appli utilisent le parc du curseur. Le rapport, lui, mélange les 3 scénarios. Plus réaliste : chaque trajectoire tire un parc autour de la valeur choisie, par exemple ±5 %. C'est une hypothèse de plus, à écrire dans `docs/hypotheses.md` avec sa source (écart historique entre parc prévu et parc réalisé) avant de la coder. `simuler_risques` accepte déjà une liste de parcs, que l'appli pourra remplir par tirage.

## Licences des données (vérifiées dans les fichiers le 04/11/2026)

| Données | Licence | Publiable |
|---|---|---|
| Prix day-ahead France (Energy-Charts) | CC BY 4.0, Bundesnetzagentur \| SMARD.de (champ `license_info` des fichiers) | oui, avec attribution |
| Production et consommation France (Energy-Charts) | CC BY 4.0 selon `docs/donnees.md` ; les fichiers ne portent pas de champ de licence | **à confirmer** sur la page de licence d'Energy-Charts avant de passer le dépôt en public |
| Profils PVGIS | réutilisation libre si la source est citée : « PVGIS © European Communities, 2001–2026 » | oui, avec attribution |
| Prix Espagne (Energy-Charts) | « usage privé et interne seulement », dérivés compris | **non** : exclus de la table ; `reports/backtest/m2/chute_2024.md`, qui en dérive, est à revoir avant de passer en public |
| Prix Allemagne | CC BY 4.0, SMARD.de | non nécessaires à l'appli |

## Pourquoi un dépôt privé

La licence de la production Energy-Charts n'est pas confirmée (voir ci-dessus). Tant que le dépôt et l'appli sont privés,
les données ne sont pas republiées : c'est un usage personnel, montré à des invités. L'appli affiche des résultats calculés,
pas le jeu de données. Limites constatées le 04/11/2026 : Community Cloud gratuit n'autorise **qu'une appli privée** par
compte, partagée avec des adresses précises (pas de domaine entier), et l'invité doit se connecter pour l'ouvrir.

Pour passer un jour en public, deux voies : basculer la production sur RTE éCO2mix (Licence Ouverte, recalage complet des
modèles), ou obtenir l'accord de Fraunhofer ISE. Dans les deux cas, `data/appli/` devra être **retiré de l'historique**
avant la mise en public, puisqu'il y aura été commité.

## Étapes

1. Fonction commune de pricing, script réécrit dessus, test de non-régression sur le rapport V2.
2. Script d'export de la table horaire France et du profil de Montpellier, avec un fichier d'attributions.
3. Appel PVGIS en direct avec cache et secours.
4. Les quatre pages Streamlit et le fichier de traductions.
5. README anglais et français avec 2 ou 3 graphiques et les limites, licence du code.
6. Mise en ligne : Streamlit Community Cloud, appli privée sur dépôt privé, partagée par invitation.
