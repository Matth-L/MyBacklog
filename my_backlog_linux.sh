#!/usr/bin/env bash
# Lance MyBacklog sous Linux / macOS : crée un environnement virtuel si besoin,
# installe les dépendances, puis démarre l'application (ouverture auto du navigateur).
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Création de l'environnement virtuel..."
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install --quiet -r requirements.txt
python3 app.py
