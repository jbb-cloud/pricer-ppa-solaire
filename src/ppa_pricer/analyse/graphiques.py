"""Graphiques de l'analyse historique (PNG dans ``reports/analyse/``).

Conventions : un seul axe des ordonnées par graphique ; couleurs catégorielles dans un ordre
fixe (bleu, orange, vert d'eau) ; une progression dans le temps est codée par une seule teinte
du clair au foncé ; heures affichées en heure de Paris ; source citée sous chaque graphique.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.ticker import PercentFormatter  # noqa: E402

from ppa_pricer.analyse.capture import periodes_paris  # noqa: E402
from ppa_pricer.donnees.controles import FUSEAU_AFFICHAGE  # noqa: E402

FOND = "#fcfcfb"
TEXTE = "#0b0b0b"
TEXTE_SECONDAIRE = "#52514e"
GRILLE = "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
RAMPE_BLEUE = LinearSegmentedColormap.from_list("bleu", ["#b7d3f6", "#5598e7", "#1c5cab", "#0d366b"])
SOURCE = "Source : Energy-Charts (Fraunhofer ISE) / SMARD, ENTSO-E — CC BY 4.0. Calculs : ppa-pricer."
SAISONS = {
    "Hiver (déc.–fév.)": [12, 1, 2],
    "Printemps (mars–mai)": [3, 4, 5],
    "Été (juin–août)": [6, 7, 8],
    "Automne (sept.–nov.)": [9, 10, 11],
}

plt.rcParams.update(
    {
        "figure.facecolor": FOND,
        "axes.facecolor": FOND,
        "savefig.facecolor": FOND,
        "font.size": 10,
        "text.color": TEXTE,
        "axes.labelcolor": TEXTE_SECONDAIRE,
        "axes.edgecolor": GRILLE,
        "axes.grid": True,
        "grid.color": GRILLE,
        "grid.linewidth": 0.8,
        "xtick.color": TEXTE_SECONDAIRE,
        "ytick.color": TEXTE_SECONDAIRE,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
    }
)


def _entete(fig, titre: str, sous_titre: str) -> float:
    """Titre, sous-titre et source ; renvoie la hauteur (fraction) libre sous l'en-tête."""
    hauteur = fig.get_figheight()
    fig.text(0.01, 1 - 0.2 / hauteur, titre, ha="left", va="top", fontsize=13, fontweight="bold")
    fig.text(0.01, 1 - 0.5 / hauteur, sous_titre, ha="left", va="top", color=TEXTE_SECONDAIRE)
    fig.text(0.01, 0.08 / hauteur, SOURCE, ha="left", va="bottom", fontsize=8, color=TEXTE_SECONDAIRE)
    return 1 - 0.85 / hauteur


def _enregistrer(fig, chemin: Path) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(chemin, dpi=150)
    plt.close(fig)


def _finir(fig, chemin: Path, titre: str, sous_titre: str) -> None:
    haut = _entete(fig, titre, sous_titre)
    fig.tight_layout(rect=(0, 0.3 / fig.get_figheight(), 1, haut))
    _enregistrer(fig, chemin)


def taux_capture_dans_le_temps(mensuel: pd.DataFrame, annuel: pd.DataFrame, chemin: Path) -> None:
    """Taux de capture mensuel (ligne fine) et annuel (points reliés, placés en milieu d'année)."""
    fig, ax = plt.subplots(figsize=(10, 5))
    x_mois = mensuel["periode"].dt.to_timestamp() + pd.Timedelta("14D")
    ax.plot(x_mois, mensuel["taux_capture"], color=SERIES[0], linewidth=1.2, label="Mensuel")
    an = annuel.dropna(subset=["taux_capture"])
    x_an = an["periode"].dt.to_timestamp() + pd.Timedelta("182D")
    ax.plot(x_an, an["taux_capture"], color=SERIES[1], linewidth=2, marker="o", markersize=7,
            markeredgecolor=FOND, markeredgewidth=1.5, label="Annuel", zorder=3)
    dernier = an.iloc[-1]
    ax.annotate(f"{dernier['periode']} : {dernier['taux_capture']:.0%}", (x_an.iloc[-1], dernier["taux_capture"]),
                xytext=(0, -22), textcoords="offset points", ha="center", color=TEXTE, fontweight="bold",
                bbox={"facecolor": FOND, "edgecolor": "none", "pad": 1.5})
    ax.axhline(1, color=TEXTE_SECONDAIRE, linewidth=1, linestyle="--")
    ax.text(x_mois.iloc[-1], 1.16, "100 % = le solaire capte le prix moyen", color=TEXTE_SECONDAIRE,
            fontsize=8, ha="right", va="bottom")
    ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.set_ylim(0, 1.2)
    ax.set_ylabel("Taux de capture (prix capté / baseload)")
    ax.legend(loc="lower left")
    _finir(fig, chemin, "Taux de capture solaire en France",
           "Prix moyen touché par le solaire rapporté au prix moyen de toutes les heures, 2015–2026")


def part_solaire_vs_taux_capture(mensuel: pd.DataFrame, chemin: Path) -> None:
    """Nuage mensuel part du solaire ↔ taux de capture, un panneau par saison, couleur = année."""
    m = mensuel.dropna(subset=["taux_capture", "part_solaire"])
    mois = m["periode"].dt.month
    annees = m["periode"].dt.year
    fig, axes = plt.subplots(1, 4, figsize=(13, 4.6), sharex=True, sharey=True)
    for ax, (saison, liste) in zip(axes, SAISONS.items()):
        s = mois.isin(liste)
        points = ax.scatter(m.loc[s, "part_solaire"], m.loc[s, "taux_capture"], c=annees[s], cmap=RAMPE_BLEUE,
                            vmin=annees.min(), vmax=annees.max(), s=40, edgecolors=FOND, linewidths=0.8)
        ax.set_title(saison, fontsize=10, loc="left", color=TEXTE)
        ax.axhline(1, color=TEXTE_SECONDAIRE, linewidth=1, linestyle="--")
        ax.set_xlim(0, 0.155)
        ax.set_xticks([0, 0.05, 0.10])
        ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.set_xlabel("Part du solaire (prod. / conso.)")
    axes[0].set_ylabel("Taux de capture mensuel")
    barre = fig.colorbar(points, ax=axes, fraction=0.015, pad=0.01)
    barre.set_label("Année")
    barre.outline.set_visible(False)
    haut = _entete(fig, "Plus il y a de solaire, moins il capte",
                   "Un point par mois, 2015–2026 ; couleur de plus en plus foncée avec les années")
    fig.subplots_adjust(left=0.06, right=0.9, top=haut - 0.06, bottom=0.17, wspace=0.08)
    _enregistrer(fig, chemin)


PERIODES_PROFIL = {"2015–2018": (2015, 2018), "2019–2022": (2019, 2022), "2023–2026": (2023, 2026)}


def profil_horaire_prix(horaire: pd.DataFrame, chemin: Path) -> None:
    """Profil journalier moyen du prix, par saison et par période, en indice.

    Chaque prix horaire est divisé par le prix moyen de son année civile, pour comparer des
    périodes aux niveaux très différents (2022). On ne divise pas par la moyenne du jour :
    elle peut être proche de 0 au printemps récent et rendrait le ratio instable.
    """
    h = horaire.dropna(subset=["prix_eur_mwh"])
    local = h["ts_utc"].dt.tz_convert(FUSEAU_AFFICHAGE)
    annee = local.dt.year
    indice = h["prix_eur_mwh"] / h.groupby(annee)["prix_eur_mwh"].transform("mean")
    d = pd.DataFrame({"indice": indice, "heure": local.dt.hour, "mois": local.dt.month, "annee": annee})

    fig, axes = plt.subplots(1, 4, figsize=(13, 4.6), sharex=True, sharey=True)
    for ax, (saison, liste) in zip(axes, SAISONS.items()):
        for couleur, (nom, (debut, fin)) in zip(SERIES, PERIODES_PROFIL.items()):
            s = d["mois"].isin(liste) & d["annee"].between(debut, fin)
            profil = d[s].groupby("heure")["indice"].mean()
            ax.plot(profil.index, profil.to_numpy(), color=couleur, linewidth=2, label=nom)
        ax.set_title(saison, fontsize=10, loc="left", color=TEXTE)
        ax.axhline(1, color=TEXTE_SECONDAIRE, linewidth=1, linestyle="--")
        ax.set_xticks([0, 6, 12, 18, 23])
        ax.set_xlabel("Heure de Paris")
    axes[0].set_ylabel("Prix / prix moyen de l'année")
    axes[0].legend(loc="lower left")
    _finir(fig, chemin, "Le creux de midi se creuse",
           "Profil journalier moyen du prix day-ahead, en indice (1 = prix moyen de l'année)")


def heures_prix_negatifs(horaire: pd.DataFrame, chemin: Path) -> None:
    """Nombre d'heures à prix négatif : total par année, puis détail année × mois."""
    h = horaire.dropna(subset=["prix_eur_mwh"])
    local = h["ts_utc"].dt.tz_convert(FUSEAU_AFFICHAGE)
    negatif = h["prix_eur_mwh"] < 0
    table = negatif.groupby([local.dt.year, local.dt.month]).sum().unstack(fill_value=0)
    table = table.reindex(columns=range(1, 13), fill_value=0)
    derniere = h["ts_utc"].max().tz_convert(FUSEAU_AFFICHAGE)

    fig, (haut, bas) = plt.subplots(2, 1, figsize=(10, 8), gridspec_kw={"height_ratios": [1, 1.3]})
    totaux = table.sum(axis=1)
    barres = haut.bar(totaux.index, totaux.to_numpy(), color=SERIES[0], width=0.7)
    barres[-1].set_hatch("////")
    barres[-1].set_facecolor("#86b6ef")
    barres[-1].set_edgecolor(FOND)
    for annee, valeur in totaux.tail(3).items():
        haut.text(annee, valeur, f"{valeur}", ha="center", va="bottom", color=TEXTE, fontweight="bold")
    haut.text(totaux.index[-1], totaux.iloc[-1] * 0.5, f"jusqu'au\n{derniere:%d/%m}", ha="center",
              color=TEXTE, fontsize=8, bbox={"facecolor": FOND, "edgecolor": "none", "pad": 1.5})
    haut.set_xticks(totaux.index)
    haut.grid(axis="x", visible=False)
    haut.set_ylabel("Heures par an")

    image = bas.imshow(table.to_numpy(), cmap=RAMPE_BLEUE, aspect="auto")
    image.cmap.set_under(FOND)
    image.set_clim(0.5, table.to_numpy().max())
    for i, annee in enumerate(table.index):
        for j in range(12):
            v = table.iloc[i, j]
            if v > 0:
                fonce = v > table.to_numpy().max() * 0.45
                bas.text(j, i, v, ha="center", va="center", fontsize=7, color=FOND if fonce else TEXTE)
    bas.set_xticks(range(12), ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août",
                               "sept.", "oct.", "nov.", "déc."])
    bas.set_yticks(range(len(table.index)), table.index)
    bas.grid(False)
    for cote in bas.spines.values():
        cote.set_visible(False)
    _finir(fig, chemin, "Heures à prix négatif en France",
           "Heures dont le prix day-ahead horaire est négatif (moyenne des quarts d'heure depuis oct. 2025)")


def produire_tous(horaire: pd.DataFrame, mensuel: pd.DataFrame, annuel: pd.DataFrame, dossier: Path) -> list[Path]:
    """Produit les quatre graphiques de l'analyse et renvoie leurs chemins."""
    chemins = {
        "taux_capture_temps.png": lambda c: taux_capture_dans_le_temps(mensuel, annuel, c),
        "part_solaire_vs_taux_capture.png": lambda c: part_solaire_vs_taux_capture(mensuel, c),
        "profil_horaire_prix.png": lambda c: profil_horaire_prix(horaire, c),
        "heures_prix_negatifs.png": lambda c: heures_prix_negatifs(horaire, c),
    }
    for nom, tracer in chemins.items():
        tracer(dossier / nom)
    return [dossier / nom for nom in chemins]
