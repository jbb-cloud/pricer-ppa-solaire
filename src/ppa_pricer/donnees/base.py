"""Stockage SQLite des séries (``data/ppa.sqlite``).

On stocke les données à leur résolution d'origine (60 ou 15 minutes) : l'agrégation horaire
est un choix de modélisation, elle se fait à la lecture et pourra changer sans re-télécharger.
Les horodatages sont des chaînes ISO 8601 en UTC (``2025-10-01T22:15:00Z``), qui se trient
correctement comme du texte. Une valeur inconnue est stockée NULL et relue NaN.
"""

import sqlite3
from pathlib import Path

import pandas as pd

# Colonnes de valeurs de chaque table ; toutes les tables ont aussi zone, ts_utc, duree_min, source.
TABLES = {
    "prix_day_ahead": ["prix_eur_mwh"],
    "production_conso": ["solaire_mw", "conso_mw"],
}

FORMAT_TS = "%Y-%m-%dT%H:%M:%SZ"


def connexion(chemin: Path) -> sqlite3.Connection:
    """Ouvre (et crée si besoin) la base, avec le schéma à jour."""
    Path(chemin).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(chemin)
    for table, colonnes in TABLES.items():
        valeurs = "".join(f"{c} REAL, " for c in colonnes)
        con.execute(
            f"CREATE TABLE IF NOT EXISTS {table} (zone TEXT NOT NULL, ts_utc TEXT NOT NULL, "
            f"duree_min INTEGER NOT NULL, {valeurs}source TEXT NOT NULL, PRIMARY KEY (zone, ts_utc))"
        )
    return con


def ecrire_serie(con: sqlite3.Connection, table: str, serie: pd.DataFrame, zone: str, source: str) -> int:
    """Insère ou remplace les points : relancer le chargement ne crée pas de doublon."""
    colonnes = TABLES[table]
    valeurs = serie[colonnes].astype(object).where(serie[colonnes].notna(), None)
    lignes = [
        (zone, ts.strftime(FORMAT_TS), int(duree), *v, source)
        for ts, duree, v in zip(serie["ts_utc"], serie["duree_min"], valeurs.itertuples(index=False))
    ]
    marques = ", ".join("?" * (len(colonnes) + 4))
    with con:
        con.executemany(f"INSERT OR REPLACE INTO {table} VALUES ({marques})", lignes)
    return len(lignes)


def lire_serie(con: sqlite3.Connection, table: str, zone: str) -> pd.DataFrame:
    """Relit une série triée en DataFrame ``ts_utc``, ``duree_min`` et ses colonnes de valeurs."""
    colonnes = ", ".join(TABLES[table])
    serie = pd.read_sql_query(
        f"SELECT ts_utc, duree_min, {colonnes} FROM {table} WHERE zone = ? ORDER BY ts_utc",
        con,
        params=(zone,),
    )
    serie["ts_utc"] = pd.to_datetime(serie["ts_utc"], format=FORMAT_TS, utc=True)
    return serie.astype({c: float for c in TABLES[table]})
