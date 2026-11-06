#!/bin/zsh
# Audit A1 : reconstruit tout dans un clone neuf du dernier commit, sans toucher au dossier de travail ni au réseau.
# Usage : scripts/audit_reproduction.sh <dossier temporaire vide>
set -e
RACINE="$(cd "$(dirname "$0")/.." && pwd)"
CIBLE="$1"
PY="$RACINE/.venv/bin/python"
git clone -q "$RACINE" "$CIBLE/clone"
mkdir -p "$CIBLE/clone/data"
ln -s "$RACINE/data/raw" "$CIBLE/clone/data/raw"
cd "$CIBLE/clone"
export PYTHONPATH="$CIBLE/clone/src"
echo "Commit testé : $(git rev-parse --short HEAD)"
"$PY" -c "import ppa_pricer, sys; print('Code importé depuis le clone :', ppa_pricer.__file__.startswith(sys.argv[1]))" "$CIBLE/clone"
"$PY" -m pytest -q 2>&1 | tail -1
"$PY" -W ignore - <<'PYTHON'
from pathlib import Path
from ppa_pricer.donnees.base import connexion, ecrire_serie
from ppa_pricer.donnees.energy_charts import lire_prix_brut, lire_production_brut
con = connexion(Path("data/ppa.sqlite"))
for annee in range(2015, 2027):
    ecrire_serie(con, "prix_day_ahead", lire_prix_brut(Path(f"data/raw/energy_charts/prix_FR_{annee}.json")), zone="FR", source="energy-charts")
    ecrire_serie(con, "production_conso", lire_production_brut(Path(f"data/raw/energy_charts/production_fr_{annee}.json")), zone="FR", source="energy-charts")
con.commit()
PYTHON
for s in analyser backtest_v1 pricer_v1 backtest_m0 backtest_m1 backtest_m2 tester_chute_2024 tester_lambda_plages pricer_monte_carlo; do
  "$PY" -W ignore "scripts/$s.py" > /dev/null
  echo "ok : $s"
done
"$PY" -W ignore - "$RACINE" <<'PYTHON'
import re, sqlite3, sys
from pathlib import Path
racine = Path(sys.argv[1])
print("--- base reconstruite face à la base du projet")
for table, cles in (("prix_day_ahead", "zone, ts_utc"), ("production_conso", "zone, ts_utc")):
    a = sqlite3.connect("data/ppa.sqlite").execute(f"select * from {table} order by {cles}").fetchall()
    b = sqlite3.connect(racine / "data/ppa.sqlite").execute(f"select * from {table} order by {cles}").fetchall()
    print(table, len(a), "lignes,", "identique" if a == b else f"DIFFÉRENT ({sum(x != y for x, y in zip(a, b))} lignes)")
print("--- rapports régénérés face aux rapports versionnés")
date = re.compile(r"Généré le \d\d/\d\d/\d{4}")
total = differents = 0
for f in sorted(Path("reports").rglob("*")):
    if not f.is_file():
        continue
    g = racine / f
    total += 1
    if not g.exists():
        print("absent du projet :", f); differents += 1; continue
    if f.suffix in (".md", ".csv"):
        egal = date.sub("", f.read_text()) == date.sub("", g.read_text())
    else:
        egal = f.read_bytes() == g.read_bytes()
    if not egal:
        differents += 1
        print("DIFFÉRENT :", f)
print(f"{total} fichiers comparés, {differents} différents")
PYTHON
